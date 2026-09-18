"""子 agent 服务：后台线程跑 ReAct，写库不连事件流。

业务差异进策略，与主调度共享内核、工具派发与状态机纯件，横切经扁平钩子。
"""
from __future__ import annotations

from typing import Optional, cast

from chorus.agents.loop import AgentLoop, LoopStrategy
from chorus.agents.progress_sink import ProgressSink
from chorus.agents.runtime import AgentContext, LoopAction, LoopSignal
from chorus.domain.bypass import BypassScope
from chorus.domain.compact import apply_micro
from chorus.domain.message import (
    AssistantMessage,
    Message,
    ToolMessage,
    UserMessage,
    build_provider_messages,
)
from chorus.domain.prompt.subagent import (
    InvokeInputs,
    SubagentSystemInputs,
    SubagentUserInputs,
)
from chorus.domain.skill import SkillLoader
from chorus.domain.log import get_logger
from chorus.domain.memory import MemoryRecall
from chorus.domain.stream import silent_consume
from chorus.config import TOOL_WHITELISTS
from chorus.domain.task import (
    AGENT_PROFILES,
    AbandonError,
    Task,
    TaskContent,
    TaskStatus,
    ValidationError,
    invoke_text,
)
from chorus.domain.task.aside import AsideGenerator
from chorus.repo.task import TaskRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.services.memory import MemoryService
from chorus.services.task_lease import LeaseGuard
from chorus.repo.task_content import TaskContentRepository
from chorus.agents.chat_model import ChatModelProvider
from chorus.services.message import MessageService
from chorus.tools import ToolDispatch

_MAX_STEPS = 20
_UNIT_MARKER = {"idea": "### ", "script": "## ", "finalize": "## "}

_logger = get_logger("subagent")


class SubagentLoopStrategy(LoopStrategy):
    """subagent 的回合自动机差异面：内存历史、静默消费、进度写入与租约终态校验。

    每轮顶部做僵死回收早退（状态复查与心跳），四个终态写入点拦截陈旧工作线程。
    """

    max_steps = _MAX_STEPS

    def __init__(self, *, task, owner_id, profile, invoke,
                 task_repo, progress_repo, lease, skill_loader, tool_dispatch,
                 memory: MemoryRecall):
        self.task = task
        self.owner_id = owner_id
        self.profile = profile
        self.history: list[Message] = [UserMessage.transient(task.session_id, content=invoke)]
        self._task_repo = task_repo
        self._progress_repo = progress_repo
        self._lease = lease
        self._skill_loader = skill_loader
        self._tool_dispatch = tool_dispatch
        self._produced_units = 0
        self._recall = memory

    def before_turn(self):
        self._task_repo.touch_updated_at(self.task.id)  # 心跳防僵死
        latest = self._task_repo.get(self.task.id)
        if latest is None or latest.status != TaskStatus.RUNNING:
            _logger.info("cooperative cancel, early exit", extra={"task_id": self.task.id})
            return False
        self._progress_repo.set_activity(self.task.id, "thinking")
        return True

    def provider_messages(self):
        system_inputs = SubagentSystemInputs(
            agent_type=self.task.agent_type,
            skill_loader=self._skill_loader,
            digest=self._recall.digest,
        )
        user_inputs = SubagentUserInputs(memories=self._recall.items)
        msgs = build_provider_messages(system_inputs.render_system_prompt(), self.history)
        user_inputs.inject_user_context(msgs)
        return msgs

    def consume(self, stream):
        marker = _UNIT_MARKER.get(self.task.agent_type)
        sink = ProgressSink(self.task.id, self._progress_repo, marker)
        return silent_consume(stream, on_token=sink.feed)

    def before_dispatch(self, call):
        kind, detail = self._tool_dispatch.activity(call.name, call.arguments)
        if kind:
            self._progress_repo.set_activity(self.task.id, kind, detail)

    def after_dispatch(self, call, dispatch):
        self._produced_units += dispatch.units_produced
        self._progress_repo.set_composing_units(self.task.id, self._produced_units)

    def after_tools(self, ctx, result, pairs):
        session_id = self.task.session_id
        self.history.append(AssistantMessage.transient_from_stream(session_id, result))
        self.history.extend(
            ToolMessage.transient(session_id, tool_call_id=call.id, name=call.name, content=dispatch.outcome.content)
            for call, dispatch in pairs
        )
        # 内存历史不进库，微压缩自己走一遍，不经压缩编排服务
        self.history, _ = apply_micro(self.history)
        return LoopAction(LoopSignal.CONTINUE, [])

    def after_text(self, ctx, result):
        content = "".join(result.text_parts)
        try:
            artifacts = self.profile.parse_output(content)
        except AbandonError as e:
            return self._abandon(e)
        except ValidationError as e:
            return self._format_correction(content, e)

        self._lease.finalize(self.task, artifacts, self.owner_id)
        return LoopAction(LoopSignal.FINISH, [])

    def _abandon(self, error: AbandonError) -> LoopAction:
        """模型主动声明放弃：翻失败并写说明，不落降级产物。"""
        self._lease.fail(self.task, error.reason, self.owner_id)
        return LoopAction(LoopSignal.FINISH, [])

    def _format_correction(self, content: str, error: ValidationError) -> LoopAction:
        """纠错提示喂回模型继续自纠；空正文不进历史（接口拒收空发言）。"""
        _logger.debug("format self-correction", extra={"task_id": self.task.id})
        self._progress_repo.set_signal(self.task.id, "刚才格式没对齐，重新理一理")
        if content:
            self.history.append(AssistantMessage.transient(self.task.session_id, content=content))
        self.history.append(UserMessage.transient(self.task.session_id, content=f"{error.correction}\n若确无法完成，按失败块格式输出：# 失败\\n失败说明。"))
        return LoopAction(LoopSignal.CONTINUE, [])

    def on_truncation_exhausted(self, ctx):
        self._lease.fail(self.task, "输出超长被截断，无法成稿", self.owner_id)
        return LoopAction(LoopSignal.FINISH, [])

    def on_exhausted(self):
        self._lease.fail(self.task, f"超过最大 ReAct 步数 {_MAX_STEPS}", self.owner_id)
        return LoopAction(LoopSignal.FINISH, [])

    def on_error(self, ctx, error):
        self._lease.fail(self.task, str(error), self.owner_id)
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
        memory_service: MemoryService,
        lease: LeaseGuard,
    ):
        self._message = message_service
        self._task_repo = task_repo
        self._artifacts_repo = task_artifacts_repo
        self._progress = task_progress_repo
        self._content_repo = content_repo
        self._tools = tool_dispatcher
        self._models = chat_model_provider
        self._loop = loop
        self._aside_gen = aside_generator
        self._skill = skill_loader
        self._memory = memory_service
        self._lease = lease

    def run(self, task_id: str) -> None:
        """后台线程入口，跑 ReAct 写库，异常转失败。"""
        task = cast(Task, self._task_repo.get(task_id))
        content = cast(TaskContent, self._content_repo.load(task_id))
        try:
            self._run_loop(task, content, task.owner_id)
        except Exception as e:
            _logger.exception("subagent failed", extra={"task_id": task_id})
            self._lease.fail(task, str(e), task.owner_id)

    def _run_loop(self, task: Task, content: TaskContent, owner_id: Optional[float]) -> None:
        # 入口租约校验，被回收重抢则放弃
        if not self._lease.valid(task.id, owner_id):
            _logger.info("entry lease invalid, abort", extra={"task_id": task.id})
            return

        invoke = self._build_invoke(task, content)
        scope = BypassScope(task.session_id, task_id=task.id, source="subagent")
        self._progress.set_aside(task.id, self._aside_gen.generate(task.agent_type, invoke, scope))
        self._progress.set_composing_label(task.id, AGENT_PROFILES[task.agent_type].composing_label)
        entry = self._models.get_entry()
        schemas = self._tools.select_schemas(TOOL_WHITELISTS[task.agent_type])
        memory = self._prepare_memory(task, invoke, scope)
        ctx = AgentContext(
            session_id=task.session_id,
            source="subagent",
            task_id=task.id,
            chat_model=entry.model_id,
            tool_schemas=schemas,
            pricing=entry.pricing,
        )
        strategy = SubagentLoopStrategy(
            task=task,
            owner_id=owner_id,
            profile=AGENT_PROFILES[task.agent_type],
            invoke=invoke,
            task_repo=self._task_repo,
            progress_repo=self._progress,
            lease=self._lease,
            skill_loader=self._skill,
            tool_dispatch=self._tools,
            memory=memory,
        )

        list(self._loop.run(ctx, entry=entry, strategy=strategy))

    def _prepare_memory(self, task, invoke, scope: BypassScope) -> MemoryRecall:
        """入口同步召回一次，缓存进策略供每轮注入，工具循环内不重召。"""
        return self._memory.recall_for(task.agent_type, invoke, scope)

    def _build_invoke(self, task: Task, content: TaskContent) -> str:
        dependencies: list[tuple[str, str]] = []
        for dep_id in task.dependencies:
            dep_task = cast(Task, self._task_repo.get(dep_id))
            dep_art = self._artifacts_repo.load(dep_id)
            dependencies.append((AGENT_PROFILES[dep_task.agent_type].display_name, invoke_text(dep_art.artifacts)))

        prior = self._artifacts_repo.load(task.id)
        return InvokeInputs(
            skeleton=content.invoke_message,
            dependencies=dependencies,
            prior=invoke_text(prior.artifacts) if prior else None,
            feedback=content.feedback,
        ).assemble_invoke()
