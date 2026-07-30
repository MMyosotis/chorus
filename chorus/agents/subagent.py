"""子 agent 服务：后台线程跑 ReAct，写库不连事件流。

业务差异进策略，与主调度共享内核、工具派发与状态机纯件，横切经扁平钩子。
"""
from __future__ import annotations

import dataclasses
from time import perf_counter
from typing import Optional

from chorus.agents.loop import AgentLoop, LoopAction, LoopSignal
from chorus.agents.runtime import AgentContext
from chorus.domain.prompt import PromptContext, build_system_prompt, subagent_base
from chorus.domain.skill import SkillLoader
from chorus.domain.log import get_logger
from chorus.domain.stream import StreamResult, silent_consume
from chorus.config import TOOL_WHITELISTS
from chorus.domain.task import (
    AGENT_PROFILES,
    AbandonError,
    TaskStatus,
    ValidationError,
    downstream_view,
)
from chorus.domain.task.aside import AsideGenerator
from chorus.domain.task.progress import UnitCounter
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.agents.chat_model import ChatModelProvider
from chorus.services.message import MessageService
from chorus.tools import ToolDispatch

_MAX_STEPS = 8
_UNIT_MARKER = {"idea": "### ", "script": "## ", "finalize": "## "}

_logger = get_logger("subagent")


class _MarkdownUnits:
    """正文角色的结构单元计数:数标题标记。"""

    def __init__(self, marker: str):
        self._counter = UnitCounter(marker)

    def feed(self, text: str) -> None:
        self._counter.feed(text)

    def flush(self, repo: TaskProgressRepository, task_id: str, chars: int) -> None:
        repo.set_composing(task_id, chars, self._counter.count)


class _CharsOnlyUnits:
    """不数结构单元的角色计数:仅写字数。"""

    def feed(self, text: str) -> None:
        pass

    def flush(self, repo: TaskProgressRepository, task_id: str, chars: int) -> None:
        repo.set_composing_chars(task_id, chars)


class ProgressSink:
    """逐字累计正文量与结构单元,节流覆盖写进度快照。"""

    def __init__(self, task_id: str, repo: TaskProgressRepository, units):
        self._task_id = task_id
        self._repo = repo
        self._units = units
        self._chars = 0
        self._last_flush_at = perf_counter()
        self._last_flush_chars = 0

    def feed(self, content: str) -> None:
        was_empty = self._chars == 0
        self._chars += len(content)
        self._units.feed(content)
        if was_empty:
            self._repo.set_activity(self._task_id, "composing")
        now = perf_counter()
        if self._chars - self._last_flush_chars < 16 and now - self._last_flush_at < 0.5:
            return
        self._units.flush(self._repo, self._task_id, self._chars)
        self._last_flush_chars = self._chars
        self._last_flush_at = now


class SubagentLoopStrategy:
    """subagent 的回合自动机差异面：内存历史、静默消费、进度写入与租约终态校验。

    每轮顶部做僵死回收早退（状态复查与心跳），四个终态写入点拦截陈旧工作线程。
    """

    max_steps = _MAX_STEPS

    def __init__(self, *, task, owner_id, profile, invoke,
                 task_repo, progress_repo, finalize, guarded_fail, skill_loader, tool_names, tool_dispatch):
        self.task = task
        self.owner_id = owner_id
        self.profile = profile
        self.history = [{"role": "user", "content": invoke}]
        self._task_repo = task_repo
        self._progress_repo = progress_repo
        self._finalize = finalize
        self._guarded_fail = guarded_fail
        self._skill_loader = skill_loader
        self._tool_names = tool_names
        self._tool_dispatch = tool_dispatch
        self._produced_units = 0

    def before_turn(self):
        self._task_repo.touch_updated_at(self.task.id)  # 心跳防僵死
        latest = self._task_repo.get(self.task.id)
        if latest is None or latest.status != TaskStatus.RUNNING:
            _logger.info("cooperative cancel, early exit", extra={"task_id": self.task.id})
            return False
        self._progress_repo.set_activity(self.task.id, "thinking")
        return True

    def message_start(self, ctx):
        return []

    def provider_messages(self):
        ctx = PromptContext(
            base=subagent_base(self.task.agent_type),
            tool_names=self._tool_names,
            skill_loader=self._skill_loader,
        )
        return [{"role": "system", "content": build_system_prompt(ctx)}] + self.history

    def consume(self, stream):
        marker = _UNIT_MARKER.get(self.task.agent_type)
        units = _MarkdownUnits(marker) if marker else _CharsOnlyUnits()
        sink = ProgressSink(self.task.id, self._progress_repo, units)
        return silent_consume(stream, on_token=sink.feed)

    def before_dispatch(self, call):
        kind, detail = self._tool_dispatch.activity(call.name, call.arguments)
        if kind:
            self._progress_repo.set_activity(self.task.id, kind, detail)

    def after_dispatch(self, call, dispatch):
        self._produced_units += dispatch.units_produced
        self._progress_repo.set_composing_units(self.task.id, self._produced_units)

    def after_tools(self, ctx, result, pairs):
        self.history.append(_assistant_view(result))
        self.history.extend(
            {"role": "tool", "tool_call_id": call.id, "content": dispatch.outcome.content}
            for call, dispatch in pairs
        )
        return LoopAction(LoopSignal.CONTINUE, [])

    def after_text(self, ctx, result):
        content = "".join(result.text_parts)
        try:
            artifacts = self.profile.parse_output(content)
        except AbandonError as e:
            # 模型主动声明放弃：翻失败并写说明，不落降级产物
            self._guarded_fail(self.task, e.reason, self.owner_id)
            return LoopAction(LoopSignal.FINISH, [])
        except ValidationError as e:
            # 纠错提示喂回模型继续自纠，撞上限才判失败
            _logger.debug("format self-correction", extra={"task_id": self.task.id})
            self._progress_repo.set_signal(self.task.id, "刚才格式没对齐，重新理一理")
            self.history.append({"role": "assistant", "content": content or None})
            self.history.append({"role": "user", "content": e.correction})
            return LoopAction(LoopSignal.CONTINUE, [])

        self._finalize(self.task, artifacts, self.owner_id)
        return LoopAction(LoopSignal.FINISH, [])

    def on_exhausted(self):
        self._guarded_fail(self.task, f"超过最大 ReAct 步数 {_MAX_STEPS}", self.owner_id)
        return LoopAction(LoopSignal.FINISH, [])

    def on_error(self, ctx, error):
        self._guarded_fail(self.task, str(error), self.owner_id)
        return LoopAction(LoopSignal.FINISH, [])


class SubAgentService:
    def __init__(
        self,
        message_service: MessageService,
        task_repo: TaskRepository,
        task_artifacts_repo: TaskArtifactsRepository,
        task_progress_repo: TaskProgressRepository,
        content_repo: TaskContentRepository,
        tool_dispatcher: ToolDispatch,
        chat_model_provider: ChatModelProvider,
        loop: AgentLoop,
        aside_generator: AsideGenerator,
        skill_loader: SkillLoader,
    ):
        self._message = message_service
        self._task_repo = task_repo
        self._artifacts_repo = task_artifacts_repo
        self._progress = task_progress_repo
        self._content_repo = content_repo
        self._tools = tool_dispatcher
        self._models = chat_model_provider
        self._loop = loop
        self._aside = aside_generator
        self._skill = skill_loader

    def run(self, task_id: str) -> None:
        """后台线程入口，跑 ReAct 写库，异常转失败。"""
        task = self._task_repo.get(task_id)
        content = self._content_repo.load(task_id)
        try:
            self._run_loop(task, content, task.owner_id)
        except Exception as e:
            _logger.exception("subagent failed", extra={"task_id": task_id})
            self._guarded_fail(task, str(e), task.owner_id)

    def _run_loop(self, task, content, owner_id: Optional[float]) -> None:
        # 入口租约校验，被回收重抢则放弃
        if not self._lease_valid(task.id, owner_id):
            _logger.info("entry lease invalid, abort", extra={"task_id": task.id})
            return

        invoke = self._build_invoke(task, content)
        self._progress.set_aside(task.id, self._aside.generate(task.agent_type, invoke))
        self._progress.set_composing_label(task.id, AGENT_PROFILES[task.agent_type].composing_label)
        entry = self._models.get_entry()
        schemas = self._tools.select_schemas(TOOL_WHITELISTS[task.agent_type])
        ctx = AgentContext(
            session_id=task.session_id,
            source="subagent",
            task_id=task.id,
            chat_model=entry.model_id,
            tool_schemas=schemas,
        )
        strategy = SubagentLoopStrategy(
            task=task,
            owner_id=owner_id,
            profile=AGENT_PROFILES[task.agent_type],
            invoke=invoke,
            task_repo=self._task_repo,
            progress_repo=self._progress,
            finalize=self._finalize,
            guarded_fail=self._guarded_fail,
            skill_loader=self._skill,
            tool_names=TOOL_WHITELISTS[task.agent_type],
            tool_dispatch=self._tools,
        )

        list(self._loop.run(ctx, entry=entry, strategy=strategy))

    def _guarded_fail(self, task, error: str, owner_id: Optional[float]) -> None:
        """租约校验后再失败，供入口外层与策略错误回调共享。"""
        if self._lease_valid(task.id, owner_id):
            self._fail(task, error)
        else:
            _logger.warning("lease invalid, drop fail write", extra={"task_id": task.id, "error": error})

    def _fail(self, task, error: str) -> None:
        """翻转为失败并写错误信息。"""
        self._task_repo.transition(task.id, TaskStatus.FAILED)
        self._content_repo.set_error(task.id, error)
        self._progress.set_signal(task.id, "这步失败了")
        _logger.info("task failed", extra={"task_id": task.id, "error": error})

    def _lease_valid(self, task_id: str, owner_id: Optional[float]) -> bool:
        """租约校验：任务仍运行且归属标识未变（未被回收重抢）。"""
        latest = self._task_repo.get(task_id)
        return latest is not None and latest.status == TaskStatus.RUNNING and latest.owner_id == owner_id

    def _build_invoke(self, task, content) -> str:
        prior = self._artifacts_repo.load(task.id)
        deps_outputs: dict = {}
        for dep_id in task.dependencies:
            dep_art = self._artifacts_repo.load(dep_id)
            deps_outputs[dep_id] = downstream_view(dep_art.artifacts)

        return content.render_invoke(
            deps_outputs,
            dataclasses.asdict(prior.artifacts) if prior else None,
        )

    def _finalize(self, task, artifacts, owner_id: Optional[float]) -> None:
        """先翻转状态再落产物。"""
        if not self._lease_valid(task.id, owner_id):
            _logger.warning("lease invalid, drop finalize", extra={"task_id": task.id})
            return

        # 一律转待复核（成品亦然）：先翻状态再落产物，避免孤儿产物
        self._task_repo.transition(task.id, TaskStatus.AWAITING_CONFIRM)
        self._artifacts_repo.upsert(task.id, task.agent_type, artifacts=artifacts)
        _logger.info("task awaiting confirm", extra={"task_id": task.id})


def _assistant_view(result: StreamResult) -> dict:
    return {
        "role": "assistant",
        "content": "".join(result.text_parts) or None,
        "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.name, "arguments": tc.arguments}}
            for _, tc in sorted(result.tool_calls.items())
        ],
    }
