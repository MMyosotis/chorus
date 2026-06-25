# kitty/agents/subagent.py
"""SubAgentService：子 Agent 后台线程 ReAct loop，写库不连 SSE。

与 supervisor 共享纯件（drain_stream / ToolRegistry.dispatch / render_invoke_message /
parse_output / 状态机），不抽共用 ReAct 基类（决策模式不同）。主流程单文件可读全：
load task → render invoke → 循环 ReAct（heartbeat→drain→exec tools→task_steps.append
→无 tool_call 则 parse+persist+return）→ 异常 CAS running→failed。
横切（trace）经扁平 hook 注册表，ctx 带 source=subagent + task_id；hook 事件用 list()
消费丢弃（subagent 不连 SSE，trace 已在 hook 内写库）。
"""
from __future__ import annotations

import json
import logging
import time
import uuid
from typing import Optional

from kitty.agents.runtime import AgentContext
from kitty.domain.prompt import build_subagent_system_prompt
from kitty.domain.stream import StreamResult, drain_stream
from kitty.domain.task import (
    AGENT_PROFILES,
    TaskStatus,
    ValidationError,
    parse_output,
    render_invoke_message,
)
from kitty.hooks import HookRegistry
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.task import TaskRepository
from kitty.repositories.task_artifacts import TaskArtifactsRepository
from kitty.repositories.task_steps import TaskStepsRepository
from kitty.services.message import MessageService
from kitty.tools import ToolCall, ToolCtxFactory, ToolRegistry, select_schemas_by_names

logger = logging.getLogger(__name__)
_MAX_STEPS = 8


class SubAgentService:
    def __init__(
        self,
        conn: ConnectionFactory,
        message_service: MessageService,
        task_repo: TaskRepository,
        task_artifacts_repo: TaskArtifactsRepository,
        task_steps_repo: TaskStepsRepository,
        tool_registry: ToolRegistry,
        tool_ctx_factory: ToolCtxFactory,
        hooks: HookRegistry,
        chat_models: dict,
        subagent_models: dict,
        max_tokens: int,
        all_tool_schemas: list[dict],
        clock=time.time,
    ):
        self._conn = conn
        self._message = message_service
        self._task_repo = task_repo
        self._artifacts_repo = task_artifacts_repo
        self._steps_repo = task_steps_repo
        self._tools = tool_registry
        self._tool_ctx_factory = tool_ctx_factory
        self._hooks = hooks
        self._models = chat_models
        self._subagent_models = subagent_models
        self._max_tokens = max_tokens
        self._all_schemas = all_tool_schemas
        self._clock = clock

    def run(self, task_id: str) -> None:
        """后台线程入口：跑子 Agent ReAct，写库不连 SSE。异常 CAS running→failed。"""
        try:
            self._run_loop(task_id)
        except Exception as e:
            logger.exception("subagent task %s failed", task_id)
            self._task_repo.cas_update(
                task_id, TaskStatus.RUNNING.value, TaskStatus.FAILED.value, error=str(e)
            )

    def _run_loop(self, task_id: str) -> None:
        task = self._task_repo.get(task_id)
        if task is None:
            logger.warning("subagent: task %s not found", task_id)
            return
        profile = AGENT_PROFILES[task.agent_type]
        ctx = AgentContext(
            session_id=task.session_id, source="subagent", task_id=task_id,
            chat_model=self._subagent_models.get(task.agent_type, ""),
        )
        # enter 进度气泡（静态出场语，narrative 尚未产出）
        self._message.append_progress_message(
            task.session_id, message_id=uuid.uuid4().hex, content=profile.enter_line,
        )
        invoke = self._build_invoke(task)
        system_prompt = build_subagent_system_prompt(task.agent_type)
        history: list[dict] = [{"role": "user", "content": invoke}]
        tools = select_schemas_by_names(self._all_schemas, profile.tools)
        entry = self._models[self._subagent_models[task.agent_type]]

        iteration = self._steps_repo.next_iteration(task_id)
        while iteration <= _MAX_STEPS:
            self._task_repo.touch_updated_at(task_id)  # 心跳防 zombie
            # 协作式取消：每轮复查任务态。被 cancel_pipeline/zombie 回收即退出本 worker，
            # 不 append done 气泡、不 finalize（闭 I-1 double-execute / I-2 孤儿气泡）。
            latest = self._task_repo.get(task_id)
            if latest is None or latest.status != TaskStatus.RUNNING.value:
                logger.info("subagent task %s no longer running (status=%s), abort loop",
                            task_id, latest.status if latest else "gone")
                return
            result = self._call_model(entry, system_prompt, history, tools, ctx, iteration)
            tool_results = self._exec_tools(result, task, ctx) if result.tool_calls else []
            self._steps_repo.append(
                task_id, iteration, _join_thinking(result),
                "".join(result.text_parts) or None,
                _tool_calls_view(result) or None,
                tool_results or None, result.finish_reason,
            )
            if not result.tool_calls:
                try:
                    self._finalize(task, result, profile)
                    return
                except ValidationError as e:
                    # 把纠错提示喂回模型，继续 ReAct 自纠；撞 _MAX_STEPS 才 FAILED
                    history.append({"role": "assistant",
                                    "content": "".join(result.text_parts) or None})
                    history.append({"role": "user", "content": e.correction})
                    iteration += 1
                    continue
            history.append(_assistant_view(result))
            history.extend(_tool_msg_views(tool_results))
            iteration += 1
        # 超过最大步数仍未结束 → failed
        self._task_repo.cas_update(
            task_id, TaskStatus.RUNNING.value, TaskStatus.FAILED.value,
            error=f"超过最大 ReAct 步数 {_MAX_STEPS}",
        )

    def _build_invoke(self, task) -> str:
        prior = self._artifacts_repo.load(task.id)
        deps_outputs: dict = {}
        for dep_id in task.dependencies:
            dep_art = self._artifacts_repo.load(dep_id)
            if dep_art is not None:
                deps_outputs[dep_id] = dep_art.step_output
        return render_invoke_message(
            task, deps_outputs,
            prior.step_output if prior else None, task.feedback,
        )

    def _call_model(self, entry, system_prompt, history, tools, ctx, iteration: int) -> StreamResult:
        messages = [{"role": "system", "content": system_prompt}] + history
        ctx.turn.reset(iteration)  # 带 iteration，trace 行记正确轮次（修 M-1 恒为 0）
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

    def _exec_tools(self, result, task, ctx) -> list[dict]:
        tool_ctx = self._tool_ctx_factory(task.session_id, None)
        views: list[dict] = []
        for _, tc in sorted(result.tool_calls.items()):
            call = ToolCall(id=tc["id"], name=tc["name"], arguments=_parse_args(tc["arguments"]))
            call_view = {"id": call.id, "name": call.name, "arguments": call.arguments}
            list(self._hooks.trigger(
                "PreToolUse", ctx, call_view,
                self._tools.format_display(call.name, call.arguments),
                self._tools.running_label(call.name),
            ))
            d = self._tools.dispatch(call, tool_ctx)
            list(self._hooks.trigger("PostToolUse", ctx, call_view, d.tool_result))
            views.append({
                "tool_call_id": call.id, "name": call.name,
                "content": d.tool_result.content, "duration_ms": d.tool_result.duration_ms,
            })
        return views

    def _finalize(self, task, result, profile) -> None:
        """解析产物 → CAS running→awaiting_confirm|finished → 持有时落 artifacts + done 气泡。

        CAS 先于产物落库（闭 I-2）：事务内先 CAS，持有（status 未漂移）才 upsert 产物；
        漂移（被 cancel_pipeline/zombie 回收）则不 upsert、不 append done 气泡，避免孤儿
        产物/气泡。parse_output 抛 ValidationError 不在此处理——上抛到 _run_loop 由其喂回
        correction 供模型自纠。done 气泡事务外尽力写（失败不回滚已落 task/产物）。
        """
        content = "".join(result.text_parts)
        artifacts, narrative = parse_output(content, task.agent_type)
        done_text = (narrative.get("done_line") or "") if narrative else ""
        to_status = (
            TaskStatus.FINISHED.value if task.agent_type == "finalize"
            else TaskStatus.AWAITING_CONFIRM.value
        )
        # 事务内 CAS 先行 + 持有才 upsert：status 翻转与产物原子可见，漂移则两者皆不落
        with self._conn.transaction():
            ok = self._task_repo.cas_update(task.id, TaskStatus.RUNNING.value, to_status)
            if ok:
                self._artifacts_repo.upsert(
                    task.id, step_output=artifacts, artifacts=artifacts, narrative=narrative,
                )
        if not ok:
            logger.warning("subagent finalize CAS failed (status drifted) for task %s", task.id)
            return
        self._message.append_progress_message(
            task.session_id, message_id=uuid.uuid4().hex, content=done_text or "完成",
        )


def _parse_args(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}


def _join_thinking(result: StreamResult) -> Optional[str]:
    return "\n".join(s.text for s in result.thinking_segments) or None


def _tool_calls_view(result: StreamResult) -> list[dict]:
    return [
        {"id": tc["id"], "name": tc["name"], "arguments": _parse_args(tc["arguments"])}
        for _, tc in sorted(result.tool_calls.items())
    ]


def _assistant_view(result: StreamResult) -> dict:
    return {
        "role": "assistant",
        "content": "".join(result.text_parts) or None,
        "tool_calls": [
            {"id": tc["id"], "type": "function",
             "function": {"name": tc["name"], "arguments": tc["arguments"]}}
            for _, tc in sorted(result.tool_calls.items())
        ],
    }


def _tool_msg_views(tool_results: list[dict]) -> list[dict]:
    return [{"role": "tool", "tool_call_id": r["tool_call_id"], "content": r["content"]}
            for r in tool_results]
