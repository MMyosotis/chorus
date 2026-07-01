# kitty/agents/subagent.py
"""SubAgentService：子 Agent 后台线程 ReAct loop，写库不连 SSE。

与 supervisor 共享纯件（drain_stream / ToolDispatch.dispatch / render_invoke_message /
parse_output / 状态机），不抽共用 ReAct 基类（决策模式不同）。主流程单文件可读全：
load task → render invoke → 循环 ReAct（heartbeat→drain→exec tools→无 tool_call 则
parse+persist+return）→ 异常 CAS running→failed。
横切（trace）经扁平 hook 注册表，ctx 带 source=subagent + task_id；hook 事件用 list()
消费丢弃（subagent 不连 SSE，trace 已在 hook 内写库）。
"""
from __future__ import annotations

import dataclasses
import json
import logging
import time
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
        """后台线程入口：跑子 Agent ReAct，写库不连 SSE。异常 CAS running→failed。

        run_started_at 在 try 外捕获并与 _run_loop 共用同一份租约令牌；except 路径据此
        校验租约——闭 takeover 竞态：旧 worker 的 _call_model 抛异常时若任务已被新 worker
        抢占（started_at 漂移），不 CAS failed、不写 failed activity，让新 worker 继续。
        """
        task = self._task_repo.get(task_id)
        if task is None:
            logger.warning("subagent: task %s not found", task_id)
            return
        run_started_at = task.started_at
        try:
            self._run_loop(task, run_started_at)
        except Exception as e:
            logger.exception("subagent task %s failed", task_id)
            # 租约校验：漂移（被 zombie reclaim + 新 worker 重抢）则不动新 worker 的 task
            if not self._lease_valid(task_id, run_started_at):
                logger.info("subagent task %s lease expired on failure, skip failed CAS", task_id)
                return
            self._task_repo.cas_update(
                task_id, TaskStatus.RUNNING.value, TaskStatus.FAILED.value,
                error=str(e), finished_at=time.time(),
            )
            self._write_activity(task, failed_activity(task.agent_type, str(e)))

    def _run_loop(self, task, run_started_at: Optional[float]) -> None:
        task_id = task.id
        # 运行租约：run 已在 try 外捕获 started_at（与 except 共用同一份令牌）；entry 校验是
        # 多线程竞态护栏（被 zombie reclaim + 新 worker 重 CAS 即 started_at 变）。
        if not self._lease_valid(task_id, run_started_at):
            logger.info("subagent task %s lease expired on enter, abort", task_id)
            return
        # started activity（subagent 必写，scheduler 不写；首次进入写）
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
        done_images: list[str] = []  # image 专用：累计已生成 URL，task 重跑随重置

        iteration = 1  # 内存计数器，仅用于撞 _MAX_STEPS 上限判断（不落库、不喂 trace）
        while iteration <= _MAX_STEPS:
            self._task_repo.touch_updated_at(task_id)  # 心跳防 zombie
            # 协作式取消：每轮复查任务态。被 cancel_pipeline/zombie 回收即退出本 worker，
            # 不 append done 气泡、不 finalize（闭 I-1 double-execute / I-2 孤儿气泡）。
            latest = self._task_repo.get(task_id)
            if latest is None or latest.status != TaskStatus.RUNNING.value:
                logger.info("subagent task %s no longer running (status=%s), abort loop",
                            task_id, latest.status if latest else "gone")
                return
            result = self._call_model(entry, system_prompt, history, tools, ctx)
            tool_results = self._exec_tools(result, task, ctx, done_images) if result.tool_calls else []
            if not result.tool_calls:
                try:
                    self._finalize(task, result, profile, run_started_at)
                    return
                except ValidationError as e:
                    # 把纠错提示喂回模型，继续 ReAct 自纠；撞 _MAX_STEPS 才 FAILED
                    self._write_activity(task, retrying_activity(task.agent_type))
                    history.append({"role": "assistant",
                                    "content": "".join(result.text_parts) or None})
                    history.append({"role": "user", "content": e.correction})
                    iteration += 1
                    continue
            history.append(_assistant_view(result))
            history.extend(_tool_msg_views(tool_results))
            iteration += 1
        # 超过最大步数仍未结束 → failed（租约内才 CAS + 写 activity，漂移则不动新 worker 的 task）
        if self._lease_valid(task_id, run_started_at):
            self._task_repo.cas_update(
                task_id, TaskStatus.RUNNING.value, TaskStatus.FAILED.value,
                error=f"超过最大 ReAct 步数 {_MAX_STEPS}", finished_at=time.time(),
            )
            self._write_activity(task, failed_activity(task.agent_type, "超过最大步数"))

    def _lease_valid(self, task_id: str, run_started_at: Optional[float]) -> bool:
        """运行租约校验：当前 task 仍 running 且 started_at 未变（未被 zombie reclaim+重抢）。"""
        latest = self._task_repo.get(task_id)
        if latest is None or latest.status != TaskStatus.RUNNING.value:
            return False
        return latest.started_at == run_started_at

    def _write_activity(self, task, draft: ActivityDraft, *,
                        tool_call_id: Optional[str] = None, tool_name: Optional[str] = None) -> None:
        """写用户态活动，fail-open（失败只记日志，不影响主流程）。"""
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
        list(self._hooks.trigger("BeforeModelRequest", ctx))  # 消费丢弃事件(trace 已写库)
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
            call_view = {"id": call.id, "name": call.name, "arguments": call.arguments, "seq": tc.seq}
            list(self._hooks.trigger(
                "PreToolUse", ctx, call_view,
                self._tools.format_display(call.name, call.arguments),
                self._tools.running_label(call.name),
            ))
            # tool_started activity（仅 visible 工具）
            if is_user_visible_tool(call.name):
                draft = tool_started_activity(task.agent_type, call.name, call.arguments)
                if draft is not None:
                    self._write_activity(task, draft, tool_call_id=call.id, tool_name=call.name)
            d = self._tools.dispatch(call, tool_ctx)
            # tool_done activity + done_images 累计（image）
            if is_user_visible_tool(call.name):
                meta = getattr(d, "activity_meta", None)
                td = tool_done_activity(
                    task.agent_type, call.name, meta, task.progress_total, done_images,
                )
                # 先用 done_images（不含当前 url）算进度，再 append 供下一轮累计——
                # 对齐 _image_done 的 all_images = done_images + [url] 契约，避免双计。
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

    def _finalize(self, task, result, profile, run_started_at: Optional[float]) -> None:
        """解析产物 → CAS running→终态 → upsert artifacts/narrative → write activity。

        CAS 先于产物落库（闭 I-2）：事务内先 CAS，持有（status 未漂移）才 upsert 产物；
        漂移（被 cancel_pipeline/zombie 回收/新 worker 抢占）则不 upsert，避免孤儿产物。
        parse_output 抛 ValidationError 不在此处理——上抛到 _run_loop 喂回 correction 自纠。
        done 台词随 narrative 落 task_artifacts，由前端流水线查 graph 渲染，不进 messages。

        finished_at 口径：仅 running→finished（finalize 角色）写真终态写 finished_at；
        running→awaiting_confirm（HIL 阻塞态）不写。租约校验在 parse_output 之后、CAS 之前——
        parse_output 仍能抛 ValidationError 触发自纠，CAS + 产物 + activity 仅租约内才落。
        """
        content = "".join(result.text_parts)
        artifacts, narrative = parse_output(content, task.agent_type)
        if not self._lease_valid(task.id, run_started_at):
            logger.info("subagent finalize lease expired for task %s, abort", task.id)
            return
        to_status = (
            TaskStatus.FINISHED.value if task.agent_type == "finalize"
            else TaskStatus.AWAITING_CONFIRM.value
        )
        is_terminal = to_status == TaskStatus.FINISHED.value
        cas_fields = {"finished_at": time.time()} if is_terminal else {}
        # 事务内 CAS 先行 + 持有才 upsert：status 翻转与产物原子可见，漂移则两者皆不落
        with self._conn.transaction():
            ok = self._task_repo.cas_update(task.id, TaskStatus.RUNNING.value, to_status, **cas_fields)
            if ok:
                artifacts_dict = dataclasses.asdict(artifacts)
                self._artifacts_repo.upsert(
                    task.id, artifacts=artifacts_dict,
                    narrative=dataclasses.asdict(narrative),
                )
        if not ok:
            logger.warning("subagent finalize CAS failed (status drifted) for task %s", task.id)
            return
        # 写 activity（CAS 成功后，事务外）
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
