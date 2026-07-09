"""子 agent 服务：后台线程跑 ReAct，写库不连事件流。

业务差异进策略，与主调度共享内核、工具派发与状态机纯件，横切经扁平钩子。
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from chorus.agents.loop import AgentLoop, LoopAction, LoopSignal
from chorus.agents.runtime import AgentContext
from chorus.domain.prompt import build_subagent_system_prompt
from chorus.domain.stream import StreamResult, silent_consume
from chorus.config import TOOL_WHITELISTS
from chorus.domain.task import (
    AGENT_PROFILES,
    TaskStatus,
    ValidationError,
)
from chorus.domain.task.activity import (
    ActivityDraft,
    awaiting_activity,
    done_activity,
    failed_activity,
    retrying_activity,
    started_activity,
    tool_done_activity,
    tool_started_activity,
)
from chorus.repo.task import TaskRepository
from chorus.repo.task_activities import TaskActivitiesRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.agents.chat_model import ChatModelProvider
from chorus.services.message import MessageService
from chorus.tools import ToolDispatch

_MAX_STEPS = 8


class SubagentLoopStrategy:
    """subagent 的回合自动机差异面：内存历史、静默消费、活动写入与租约终态校验。

    每轮顶部做协作式取消（状态复查与心跳），四个终态写入点拦截陈旧工作线程。
    """

    max_steps = _MAX_STEPS

    def __init__(self, *, task, progress_total, owner_id, profile, invoke,
                 task_repo,
                 write_activity, finalize, guarded_fail):
        self.task = task
        self.progress_total = progress_total
        self.owner_id = owner_id
        self.profile = profile
        self.history = [{"role": "user", "content": invoke}]
        self.done_images = []
        self._task_repo = task_repo
        self._write_activity = write_activity
        self._finalize = finalize
        self._guarded_fail = guarded_fail

    def before_turn(self):
        self._task_repo.touch_updated_at(self.task.id)  # 心跳防僵死
        latest = self._task_repo.get(self.task.id)
        if latest is None or latest.status != TaskStatus.RUNNING:
            return False
        return True

    def provider_messages(self):
        prompt = build_subagent_system_prompt(self.task.agent_type)
        return [{"role": "system", "content": prompt}] + self.history

    def consume(self, stream):
        return silent_consume(stream)

    def before_dispatch(self, call):
        self._write_activity(self.task, tool_started_activity(call.name, call.arguments))

    def after_dispatch(self, call, dispatch):
        tool_done = tool_done_activity(
            call.name, dispatch.activity_meta,
            self.progress_total,
            self.done_images,
        )
        # 先按已累计算进度，再追加当前图供下一轮，避免双计
        if call.name == "generate_image" and dispatch.activity_meta and dispatch.activity_meta.get("url"):
            self.done_images.append(dispatch.activity_meta["url"])
        if tool_done is not None:
            self._write_activity(self.task, tool_done)

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
            artifacts, narrative = self.profile.parse_output(content)
        except ValidationError as e:
            # 纠错提示喂回模型继续自纠，撞上限才判失败
            self._write_activity(self.task, retrying_activity())
            self.history.append({"role": "assistant", "content": content or None})
            self.history.append({"role": "user", "content": e.correction})
            return LoopAction(LoopSignal.CONTINUE, [])

        self._finalize(self.task, artifacts, narrative, self.owner_id)
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
        task_activities_repo: TaskActivitiesRepository,
        content_repo: TaskContentRepository,
        tool_dispatcher: ToolDispatch,
        chat_model_provider: ChatModelProvider,
        loop: AgentLoop,
    ):
        self._message = message_service
        self._task_repo = task_repo
        self._artifacts_repo = task_artifacts_repo
        self._activities = task_activities_repo
        self._content_repo = content_repo
        self._tools = tool_dispatcher
        self._models = chat_model_provider
        self._loop = loop

    def run(self, task_id: str) -> None:
        """后台线程入口，跑 ReAct 写库，异常转失败。"""
        task = self._task_repo.get(task_id)
        content = self._content_repo.load(task_id)
        try:
            self._run_loop(task, content, task.owner_id)
        except Exception as e:
            self._guarded_fail(task, str(e), task.owner_id)

    def _run_loop(self, task, content, owner_id: Optional[float]) -> None:
        # 入口租约校验，被回收重抢则放弃
        if not self._lease_valid(task.id, owner_id):
            return

        self._write_activity(task, started_activity(task.agent_type))
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
            progress_total=content.progress_total if content else None,
            owner_id=owner_id,
            profile=AGENT_PROFILES[task.agent_type],
            invoke=self._build_invoke(task, content),
            task_repo=self._task_repo,
            write_activity=self._write_activity,
            finalize=self._finalize,
            guarded_fail=self._guarded_fail,
        )

        list(self._loop.run(ctx, entry=entry, strategy=strategy))

    def _guarded_fail(self, task, error: str, owner_id: Optional[float]) -> None:
        """租约校验后再失败，供入口外层与策略错误回调共享。"""
        if self._lease_valid(task.id, owner_id):
            self._fail(task, error)

    def _fail(self, task, error: str) -> None:
        """翻转为失败并写错误信息。"""
        self._task_repo.transition(task.id, TaskStatus.RUNNING, TaskStatus.FAILED)
        self._content_repo.set_error(task.id, error)

        self._write_activity(task, failed_activity(error))

    def _lease_valid(self, task_id: str, owner_id: Optional[float]) -> bool:
        """租约校验：任务仍运行且归属标识未变（未被回收重抢）。"""
        latest = self._task_repo.get(task_id)
        return latest is not None and latest.status == TaskStatus.RUNNING and latest.owner_id == owner_id

    def _write_activity(self, task, draft: ActivityDraft) -> None:
        """写活动，失败不阻断主流程。"""
        try:
            self._activities.append(task.id, draft)
        except Exception:
            pass

    def _build_invoke(self, task, content) -> str:
        prior = self._artifacts_repo.load(task.id)
        deps_outputs: dict = {}
        for dep_id in task.dependencies:
            dep_art = self._artifacts_repo.load(dep_id)
            deps_outputs[dep_id] = dataclasses.asdict(dep_art.artifacts)

        return content.render_invoke(
            deps_outputs,
            dataclasses.asdict(prior.artifacts) if prior else None,
        )

    def _finalize(self, task, artifacts, narrative, owner_id: Optional[float]) -> None:
        """先翻转状态再落产物，最后写活动。"""
        if not self._lease_valid(task.id, owner_id):
            return

        to_status = (
            TaskStatus.FINISHED if task.agent_type == "finalize"
            else TaskStatus.AWAITING_CONFIRM
        )
        is_terminal = to_status == TaskStatus.FINISHED

        # 先翻状态再落产物，最后写活动
        self._task_repo.transition(task.id, TaskStatus.RUNNING, to_status)
        self._artifacts_repo.upsert(task.id, task.agent_type, artifacts=artifacts, narrative=narrative)

        if is_terminal:
            self._write_activity(task, done_activity(narrative))
        else:
            self._write_activity(task, awaiting_activity(narrative))


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
