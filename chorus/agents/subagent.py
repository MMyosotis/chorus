"""子 agent 服务：后台线程跑 ReAct，写库不连事件流。

与主调度共享流消费、工具派发、产物解析与状态机等纯件。主流程：装载任务 → 渲染调用
→ 循环思考执行工具，无工具调用则解析产物落库 → 异常转失败。横切经扁平钩子，事件
消费丢弃，轨迹由钩子写库。
"""
from __future__ import annotations

import dataclasses
import json
import logging
from typing import Optional

from chorus.agents.runtime import AgentContext
from chorus.domain.prompt import build_subagent_system_prompt
from chorus.domain.stream import StreamResult, drain_stream
from chorus.config import TOOL_WHITELISTS
from chorus.domain.task import (
    AGENT_PROFILES,
    TaskStatus,
    ValidationError,
    parse_output,
    render_invoke_message,
)
from chorus.domain.task.activity import (
    ActivityDraft,
    awaiting_activity,
    done_activity,
    failed_activity,
    is_user_visible_tool,
    retrying_activity,
    started_activity,
    tool_done_activity,
    tool_started_activity,
)
from chorus.hooks import HookRegistry
from chorus.repo.connection import ConnectionFactory
from chorus.repo.task import TaskRepository
from chorus.repo.task_activities import TaskActivitiesRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.agents.chat_model import ChatModelProvider
from chorus.services.message import MessageService
from chorus.tools import ToolCall, ToolContext, ToolDispatch

logger = logging.getLogger(__name__)
_MAX_STEPS = 8


class SubAgentService:
    def __init__(
        self,
        conn: ConnectionFactory,
        message_service: MessageService,
        task_repo: TaskRepository,
        task_artifacts_repo: TaskArtifactsRepository,
        task_activities_repo: TaskActivitiesRepository,
        tool_dispatcher: ToolDispatch,
        hooks: HookRegistry,
        chat_model_provider: ChatModelProvider,
        max_tokens: int,
    ):
        self._conn = conn
        self._message = message_service
        self._task_repo = task_repo
        self._artifacts_repo = task_artifacts_repo
        self._activities = task_activities_repo
        self._tools = tool_dispatcher
        self._hooks = hooks
        self._models = chat_model_provider
        self._max_tokens = max_tokens

    def run(self, task_id: str) -> None:
        """后台线程入口，跑 ReAct 写库，异常转失败。

        失败路径先校验运行租约：若任务已被回收并重抢，则不写失败，让新 worker 继续。
        """
        task = self._task_repo.get(task_id)
        if task is None:
            logger.warning("subagent: task %s not found", task_id)
            return
        my_owner_id = task.owner_id
        try:
            self._run_loop(task, my_owner_id)
        except Exception as e:
            logger.exception("subagent task %s failed", task_id)
            # 租约校验：被回收重抢则不动新 worker 的任务
            if not self._lease_valid(task_id, my_owner_id):
                logger.info("subagent task %s lease expired on failure, skip failed CAS", task_id)
                return
            self._task_repo.cas_update(
                task_id, TaskStatus.RUNNING.value, TaskStatus.FAILED.value,
                error=str(e),
            )
            self._write_activity(task, failed_activity(task.agent_type, str(e)))

    def _run_loop(self, task, my_owner_id: Optional[float]) -> None:
        task_id = task.id
        # 入口租约校验，被回收重抢则放弃
        if not self._lease_valid(task_id, my_owner_id):
            logger.info("subagent task %s lease expired on enter, abort", task_id)
            return
        # 写开始活动
        self._write_activity(task, started_activity(task.agent_type))
        profile = AGENT_PROFILES[task.agent_type]
        entry = self._models.get_entry()
        ctx = AgentContext(
            session_id=task.session_id, source="subagent", task_id=task_id,
            chat_model=entry.model_id,
        )
        invoke = self._build_invoke(task)
        system_prompt = build_subagent_system_prompt(task.agent_type)
        history: list[dict] = [{"role": "user", "content": invoke}]
        tools = self._tools.select_schemas(TOOL_WHITELISTS[task.agent_type])
        done_images: list[str] = []  # 配图角色累计已生成图，重跑随重置

        iteration = 1  # 内存计数器，仅用于撞上限判断
        while iteration <= _MAX_STEPS:
            self._task_repo.touch_updated_at(task_id)  # 心跳防僵死
            # 协作式取消：每轮复查任务态，被取消或回收即退出
            latest = self._task_repo.get(task_id)
            if latest is None or latest.status != TaskStatus.RUNNING.value:
                logger.info("subagent task %s no longer running (status=%s), abort loop",
                            task_id, latest.status if latest else "gone")
                return
            result = self._call_model(entry, system_prompt, history, tools, ctx)
            tool_results = self._exec_tools(result, task, ctx, done_images) if result.tool_calls else []
            if not result.tool_calls:
                try:
                    self._finalize(task, result, profile, my_owner_id)
                    return
                except ValidationError as e:
                    # 纠错提示喂回模型继续自纠，撞上限才判失败
                    self._write_activity(task, retrying_activity(task.agent_type))
                    history.append({"role": "assistant",
                                    "content": "".join(result.text_parts) or None})
                    history.append({"role": "user", "content": e.correction})
                    iteration += 1
                    continue
            history.append(_assistant_view(result))
            history.extend(_tool_msg_views(tool_results))
            iteration += 1
        # 超过最大步数仍未结束则判失败，租约内才落库
        if self._lease_valid(task_id, my_owner_id):
            self._task_repo.cas_update(
                task_id, TaskStatus.RUNNING.value, TaskStatus.FAILED.value,
                error=f"超过最大 ReAct 步数 {_MAX_STEPS}",
            )
            self._write_activity(task, failed_activity(task.agent_type, "超过最大步数"))

    def _lease_valid(self, task_id: str, my_owner_id: Optional[float]) -> bool:
        """租约校验：任务仍运行且 owner_id 未变（未被回收重抢）。"""
        latest = self._task_repo.get(task_id)
        if latest is None or latest.status != TaskStatus.RUNNING.value:
            return False
        return latest.owner_id == my_owner_id

    def _write_activity(self, task, draft: ActivityDraft, *,
                        tool_call_id: Optional[str] = None, tool_name: Optional[str] = None) -> None:
        """写用户态活动，失败只记日志不影响主流程。"""
        try:
            self._activities.append(
                task.id,
                event_type=draft.event_type,
                role_line=draft.role_line, status=draft.status,
                tool_name=tool_name, tool_call_id=tool_call_id,
                detail_md=draft.detail_md,
                summary_json=draft.summary_json, progress_json=draft.progress_json,
                artifact_preview_json=draft.artifact_preview_json,
            )
        except Exception:  # noqa: BLE001 — activity fail-open
            logger.warning("activity write failed task=%s", task.id, exc_info=True)

    def _build_invoke(self, task) -> str:
        prior = self._artifacts_repo.load(task.id)
        deps_outputs: dict = {}
        for dep_id in task.dependencies:
            dep_art = self._artifacts_repo.load(dep_id)
            if dep_art is not None:
                deps_outputs[dep_id] = dep_art.artifacts
        return render_invoke_message(
            task, deps_outputs,
            prior.artifacts if prior else None, task.feedback,
        )

    def _call_model(self, entry, system_prompt, history, tools, ctx) -> StreamResult:
        messages = [{"role": "system", "content": system_prompt}] + history
        ctx.turn.reset()
        ctx.turn.provider_messages = messages
        ctx.tool_schemas = tools
        list(self._hooks.trigger("BeforeModelRequest", ctx))  # 消费丢弃事件
        stream = entry.client.chat.completions.create(
            model=entry.model_id, messages=messages, tools=tools or None,
            max_tokens=self._max_tokens, stream=True,
        )
        result = drain_stream(stream)
        ctx.turn.apply_stream(result)
        list(self._hooks.trigger("AfterModelResponse", ctx))
        return result

    def _exec_tools(self, result, task, ctx, done_images: list[str]) -> list[dict]:
        tool_ctx = ToolContext(session_id=task.session_id)
        views: list[dict] = []
        for _, tc in sorted(result.tool_calls.items()):
            call = ToolCall(id=tc.id, name=tc.name, arguments=_parse_args(tc.arguments))
            call_view = {"id": call.id, "name": call.name, "arguments": call.arguments}
            list(self._hooks.trigger(
                "PreToolUse", ctx, call_view,
                self._tools.format_display(call.name, call.arguments),
                self._tools.running_label(call.name),
            ))
            # 仅可见工具写开始活动
            if is_user_visible_tool(call.name):
                draft = tool_started_activity(task.agent_type, call.name, call.arguments)
                if draft is not None:
                    self._write_activity(task, draft, tool_call_id=call.id, tool_name=call.name)
            d = self._tools.dispatch(call, tool_ctx)
            # 工具完成活动 + 配图累计
            if is_user_visible_tool(call.name):
                meta = getattr(d, "activity_meta", None)
                td = tool_done_activity(
                    task.agent_type, call.name, meta, task.progress_total, done_images,
                )
                # 先按已累计算进度，再追加当前图供下一轮，避免双计
                if call.name == "generate_image" and meta and meta.get("url"):
                    done_images.append(meta["url"])
                if td is not None:
                    self._write_activity(task, td, tool_call_id=call.id, tool_name=call.name)
            list(self._hooks.trigger("PostToolUse", ctx, call_view, d))
            views.append({
                "tool_call_id": call.id, "name": call.name,
                "content": d.outcome.content, "duration_ms": d.duration_ms,
            })
        return views

    def _finalize(self, task, result, profile, my_owner_id: Optional[float]) -> None:
        """解析产物，先翻转状态再落产物，最后写活动。

        事务内先 CAS 翻转状态，持有才落产物，避免漂移产生孤儿产物。解析失败上抛由
        调用方喂回模型自纠。完成台词随产物落库，由前端查图渲染，不进消息表。
        """
        content = "".join(result.text_parts)
        artifacts, narrative = parse_output(content, task.agent_type)
        if not self._lease_valid(task.id, my_owner_id):
            logger.info("subagent finalize lease expired for task %s, abort", task.id)
            return
        to_status = (
            TaskStatus.FINISHED.value if task.agent_type == "finalize"
            else TaskStatus.AWAITING_CONFIRM.value
        )
        is_terminal = to_status == TaskStatus.FINISHED.value
        # 事务内先 CAS 再落产物，状态与产物原子可见，漂移则两者皆不落
        with self._conn.transaction():
            ok = self._task_repo.cas_update(task.id, TaskStatus.RUNNING.value, to_status)
            if ok:
                artifacts_dict = dataclasses.asdict(artifacts)
                self._artifacts_repo.upsert(
                    task.id, artifacts=artifacts_dict,
                    narrative=dataclasses.asdict(narrative),
                )
        if not ok:
            logger.warning("subagent finalize CAS failed (status drifted) for task %s", task.id)
            return
        # 写活动（事务外）
        if is_terminal:
            self._write_activity(task, done_activity(task.agent_type, narrative))
        else:
            self._write_activity(task, awaiting_activity(task.agent_type, narrative))


def _parse_args(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


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


def _tool_msg_views(tool_results: list[dict]) -> list[dict]:
    return [{"role": "tool", "tool_call_id": r["tool_call_id"], "content": r["content"]}
            for r in tool_results]
