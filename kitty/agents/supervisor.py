# kitty/agents/supervisor.py
"""SupervisorService：supervisor SSE 流式 loop（原 ChatService 迁入+改造）。

主流程单文件可读全（spec 5.1）：only_reply 走原生 content 流式；new_plan 解析
create_plan 工具参数 → validate_steps → expand_pipeline → 事务批量落库 →
yield TaskPlanCreatedEvent。create_plan tool_call 不落库（瞬时路由信号），
friendly_reply 作为普通 assistant 气泡 append。横切（trace/title/异常收尾）挂扁平
hook 注册表，ctx 带 source=supervisor。
"""
from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Iterator, Optional

from openai import OpenAI

from kitty.agents.runtime import AgentContext
from kitty.domain.events import (
    DoneEvent,
    ErrorEvent,
    MessageStartEvent,
    SseEvent,
    TaskPlanCreatedEvent,
)
from kitty.domain.prompt import PromptContext, build_system_prompt
from kitty.domain.skill import SkillLoader, format_skill_hints
from kitty.domain.stream import consume_stream
from kitty.domain.task import (
    ACTIVE_STATUSES,
    CreationIntent,
    StepSpec,
    ValidationError,
    expand_pipeline,
    validate_steps,
)
from kitty.hooks import HookRegistry
from kitty.repositories.connection import ConnectionFactory
from kitty.repositories.task import TaskRepository
from kitty.services.message import MessageService
from kitty.services.session import SessionService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatModelEntry:
    client: OpenAI
    model_id: str


CREATE_PLAN_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "create_plan",
        "description": (
            "当用户要创作图文博文时调用，按用户实际自主编排创作步骤；"
            "普通对话直接文本回复不调用本工具。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "thought": {"type": "string", "description": "内部思考，不展示给用户"},
                "friendly_reply": {"type": "string", "description": "建任务前对用户的友好回复，会作为流程节拍气泡展示"},
                "intent": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string", "description": "创作主题/方向"},
                        "style": {"type": "string", "description": "风格倾向，如轻松/专业/种草"},
                        "image_count": {"type": "integer", "description": "配图数量，默认 3"},
                        "extra": {"type": "object", "description": "其它要求"},
                    },
                    "required": ["topic"],
                },
                "steps": {
                    "type": "array",
                    "description": "创作步骤序列；末步须为 finalize；deps 引用 steps 内前置索引",
                    "items": {
                        "type": "object",
                        "properties": {
                            "agent_type": {"type": "string", "enum": ["idea", "script", "image", "finalize"]},
                            "deps": {"type": "array", "items": {"type": "integer"}, "description": "前置步骤索引(0-based)"},
                            "focus": {"type": "string", "description": "本步针对本次任务的具体指令"},
                        },
                        "required": ["agent_type", "deps", "focus"],
                    },
                },
            },
            "required": ["thought", "friendly_reply", "intent", "steps"],
        },
    },
}


class SupervisorService:
    def __init__(
        self,
        session_service: SessionService,
        message_service: MessageService,
        skill_loader: SkillLoader,
        hooks: HookRegistry,
        models: dict,
        default_model_id: str,
        max_tokens: int,
        task_repo: TaskRepository,
        conn: ConnectionFactory,
        clock=time.time,
    ):
        self._session = session_service
        self._message = message_service
        self._skill = skill_loader
        self._hooks = hooks
        self._models = models
        self._default_model_id = default_model_id
        self._max_tokens = max_tokens
        self._task_repo = task_repo
        self._conn = conn
        self._clock = clock

    def stream(
        self, session_id: str, user_message: str, *,
        model: Optional[str] = None, image_model: Optional[str] = None,
        web_search: Optional[bool] = None,
    ) -> Iterator[SseEvent]:
        if not self._session.exists(session_id):
            yield ErrorEvent(content="session not found")
            return
        entry = self._models[model or self._default_model_id]
        ctx = AgentContext(
            session_id=session_id, user_message=user_message,
            tool_schemas=[CREATE_PLAN_TOOL_SCHEMA],
            image_model=image_model, chat_model=entry.model_id,
        )
        try:
            self._message.append_user_message(session_id, user_message)
            self._session.touch(session_id)
            i = 0
            correction: Optional[str] = None
            while True:
                ctx.turn.reset(i)
                ctx.turn.message_id = uuid.uuid4().hex
                yield MessageStartEvent(id=ctx.turn.message_id)
                prompt = build_system_prompt(PromptContext(
                    skill_hints=format_skill_hints(self._skill.list_summaries()),
                ))
                ctx.turn.provider_messages = self._message.build_provider_messages(session_id, prompt)
                if correction:
                    ctx.turn.provider_messages.append({"role": "user", "content": correction})
                yield from self._hooks.trigger("BeforeModelRequest", ctx)
                stream = entry.client.chat.completions.create(
                    model=entry.model_id, messages=ctx.turn.provider_messages,
                    tools=[CREATE_PLAN_TOOL_SCHEMA], max_tokens=self._max_tokens, stream=True,
                )
                result = yield from consume_stream(stream)
                ctx.turn.apply_stream(result)
                yield from self._hooks.trigger("AfterModelResponse", ctx)

                args = self._route(ctx)
                if args is None:  # only_reply
                    content = "".join(ctx.turn.text_parts) if ctx.turn.text_parts else None
                    self._message.append_assistant_message(
                        session_id, message_id=ctx.turn.message_id, content=content, tool_calls=[],
                    )
                    self._session.touch(session_id)
                    yield DoneEvent()
                    yield from self._hooks.trigger("Stop", ctx)
                    return
                # new_plan：尝试建图
                ok, correction_or_none, tasks = self._build_and_persist_plan(session_id, args)
                if ok:
                    self._message.append_assistant_message(
                        session_id, message_id=ctx.turn.message_id,
                        content=args.get("friendly_reply") or "好的，开始为你创作", tool_calls=[],
                    )
                    self._session.touch(session_id)
                    yield TaskPlanCreatedEvent(
                        pipeline_id=tasks[0].pipeline_id,
                        tasks=[{"id": t.id, "agent_type": t.agent_type, "seq": t.seq, "status": t.status}
                               for t in tasks],
                    )
                    yield DoneEvent()
                    return
                if correction is not None:  # 已重试过仍失败 → 降级
                    yield from self._fallback_only_reply(session_id, ctx, entry)
                    return
                correction = correction_or_none
                i += 1
        except Exception as e:
            ctx.outcome.exception = e
            yield from self._hooks.trigger("Error", ctx)
            yield ErrorEvent(content=str(e))

    def _route(self, ctx: AgentContext) -> Optional[dict]:
        if ctx.turn.finish_reason != "tool_calls" or not ctx.turn.accumulated_tool_calls:
            return None
        tc = next(iter(ctx.turn.accumulated_tool_calls.values()))
        if tc.get("name") != "create_plan":
            return None
        return _parse_args(tc.get("arguments", ""))

    def _build_and_persist_plan(self, session_id: str, args: dict) -> tuple[bool, Optional[str], Optional[list]]:
        try:
            intent = CreationIntent(
                topic=args["intent"]["topic"],
                style=args["intent"].get("style", ""),
                image_count=args["intent"].get("image_count", 3),
                extra=args["intent"].get("extra", {}),
            )
            steps = [
                StepSpec(agent_type=s["agent_type"], deps=s.get("deps", []), focus=s["focus"])
                for s in args["steps"]
            ]
            validate_steps(steps)
        except (KeyError, TypeError) as e:
            return False, f"create_plan 参数缺失或格式错: {e}", None
        except ValidationError as e:
            return False, e.correction, None
        if self._task_repo.count_by_session_statuses(session_id, ACTIVE_STATUSES) > 0:
            return False, "该会话已有进行中的创作任务，请先完成或放弃当前任务再新建", None
        tasks = expand_pipeline(intent, steps)
        now = self._clock()
        with self._conn.transaction():
            for t in tasks:
                self._task_repo.insert(t.model_copy(update={
                    "session_id": session_id, "created_at": now, "updated_at": now,
                }))
        return True, None, tasks

    def _fallback_only_reply(self, session_id: str, ctx: AgentContext, entry) -> Iterator[SseEvent]:
        ctx.turn.reset(99)
        ctx.turn.message_id = uuid.uuid4().hex
        yield MessageStartEvent(id=ctx.turn.message_id)
        prompt = build_system_prompt(PromptContext())
        messages = self._message.build_provider_messages(session_id, prompt)
        messages.append({"role": "user", "content": "我没完全理解你的创作需求，能否补充说明主题和想要的内容？"})
        yield from self._hooks.trigger("BeforeModelRequest", ctx)
        stream = entry.client.chat.completions.create(
            model=entry.model_id, messages=messages, tools=None,
            max_tokens=self._max_tokens, stream=True,
        )
        result = yield from consume_stream(stream)
        ctx.turn.apply_stream(result)
        yield from self._hooks.trigger("AfterModelResponse", ctx)
        content = "".join(result.text_parts) if result.text_parts else None
        self._message.append_assistant_message(
            session_id, message_id=ctx.turn.message_id, content=content, tool_calls=[],
        )
        self._session.touch(session_id)
        yield DoneEvent()
        yield from self._hooks.trigger("Stop", ctx)


def _parse_args(raw: str) -> dict:
    try:
        import json
        return json.loads(raw) if raw else {}
    except json.JSONDecodeError:
        return {}
