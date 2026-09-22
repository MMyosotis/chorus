"""执行聚合：轨迹条目聚合成模型调用与统一工具执行记录。

响应摘要打底、工具调用事件覆盖、工具结果补全，仅结果的保留占位；
供控制台视图投影与消息轨迹摘要共用同一套合并规则。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from chorus.domain.task.models import AgentType
from chorus.domain.trace.models import (
    MessageTrace,
    ModelRequest,
    ModelResponse,
    ToolCallSummary,
    ToolInvocation,
    TraceEntry,
    TraceToolCall,
    TraceToolResult,
)
from chorus.domain.trace.items import AgentRole, role_for


@dataclass
class ToolExecution:
    """一次工具执行的统一记录：调用事件定字段，结果对象原样保留。"""

    tool_call_id: str
    name: str
    arguments: dict
    display: str
    result: Optional[TraceToolResult] = None


def merge_tools(
    summaries: Iterable[ToolCallSummary],
    calls: Iterable[TraceToolCall],
    results: Iterable[TraceToolResult],
) -> list[ToolExecution]:
    """按调用 id 合并三类来源成统一工具执行记录。"""
    executions: dict[str, ToolExecution] = {}
    for summary in summaries:
        executions[summary.tool_call_id] = ToolExecution(
            tool_call_id=summary.tool_call_id, name=summary.name,
            arguments=summary.arguments, display=summary.name,
        )
    for call in calls:
        executions[call.tool_call_id] = ToolExecution(
            tool_call_id=call.tool_call_id, name=call.name,
            arguments=call.arguments, display=call.display,
        )
    for result in results:
        execution = executions.setdefault(
            result.tool_call_id,
            ToolExecution(tool_call_id=result.tool_call_id, name=result.name, arguments={}, display=""),
        )
        execution.result = result
    return list(executions.values())


@dataclass
class Call:
    """同一条模型消息的请求、响应与工具轨迹聚合。"""

    key: str
    created_at: float
    role: AgentRole
    request: ModelRequest
    response: Optional[ModelResponse] = None
    response_at: Optional[float] = None
    tools: list[ToolExecution] = field(default_factory=list)
    tools_last_at: float = 0.0

    @property
    def start_at(self) -> float:
        return self.created_at

    @property
    def end_at(self) -> float:
        return max(self.created_at, self.response_at or 0.0, self.tools_last_at)

    @property
    def returned_tool_ids(self) -> list[str]:
        """请求末尾连续工具消息的调用标识，保留现场顺序。"""
        ids = []
        for message in reversed(self.request.messages):
            if message.get("role") != "tool":
                break
            ids.append(message["tool_call_id"])
        return ids[::-1]


@dataclass
class _ExecutionEvents:
    """执行事件累积器：模型响应与工具轨迹统一收集，类型判断只此一处。"""

    responses: list[tuple[float, ModelResponse]] = field(default_factory=list)
    tool_calls: list[TraceToolCall] = field(default_factory=list)
    tool_results: list[TraceToolResult] = field(default_factory=list)
    tools_last_at: float = 0.0

    def absorb(self, entry: TraceEntry) -> None:
        """按载荷类型吸收条目，非执行事件不产生变化。"""
        payload = entry.payload
        if isinstance(payload, ModelResponse):
            self.responses.append((entry.created_at, payload))
        elif isinstance(payload, TraceToolCall):
            self.tool_calls.append(payload)
        elif isinstance(payload, TraceToolResult):
            self.tool_results.append(payload)
            self.tools_last_at = max(self.tools_last_at, entry.created_at)

    def merge_tools(self) -> list[ToolExecution]:
        summaries = [summary for _, response in self.responses for summary in response.tool_calls]
        return merge_tools(summaries, self.tool_calls, self.tool_results)


@dataclass
class _CallDraft:
    """调用聚合的累积状态：先收齐原始事件，收尾统一合并。"""

    key: str
    created_at: float
    role: AgentRole
    request: ModelRequest
    events: _ExecutionEvents = field(default_factory=_ExecutionEvents)

    @classmethod
    def from_request(cls, entry: TraceEntry, agent_type_by_task: dict[str, AgentType]) -> "_CallDraft":
        """从请求条目开出调用聚合草稿。"""
        return cls(
            key=_entry_key(entry), created_at=entry.created_at,
            role=role_for(entry.task_id, agent_type_by_task), request=entry.payload,
        )

    def finish(self) -> Call:
        """把收集结果转换成调用记录。"""
        response_at, response = self.events.responses[-1] if self.events.responses else (None, None)
        return Call(
            key=self.key, created_at=self.created_at,
            role=self.role,
            request=self.request, response=response, response_at=response_at,
            tools=self.events.merge_tools(),
            tools_last_at=self.events.tools_last_at,
        )


def _entry_key(entry: TraceEntry) -> str:
    return entry.message_id or f"{entry.source}:{entry.task_id or ''}:{entry.created_at}"


def build_calls(entries: Iterable[TraceEntry], agent_type_by_task: dict[str, AgentType]) -> list[Call]:
    """先按请求开聚合，关联条目统一交聚合状态吸收，收尾转成调用记录。"""
    ordered = sorted(entries, key=lambda item: item.created_at)
    drafts: dict[str, _CallDraft] = {}
    for entry in ordered:
        if isinstance(entry.payload, ModelRequest):
            draft = _CallDraft.from_request(entry, agent_type_by_task)
            drafts[draft.key] = draft
            continue
        draft = drafts.get(_entry_key(entry))
        if draft is not None:
            draft.events.absorb(entry)
    return sorted((draft.finish() for draft in drafts.values()), key=lambda call: call.created_at)


def tool_names_by_id(calls: list[Call]) -> dict[str, str]:
    """会话级工具名映射：工具结果轨迹是名称的权威来源。"""
    return {
        tool_id: execution.result.name
        for tool_id, execution in tool_executions_by_id(calls).items()
    }


def tool_executions_by_id(calls: list[Call]) -> dict[str, ToolExecution]:
    """会话级工具执行索引：回填归属按结果标识跨调用连接。"""
    return {
        execution.result.tool_call_id: execution
        for call in calls for execution in call.tools if execution.result is not None
    }


def _tool_invocation(execution: ToolExecution) -> ToolInvocation:
    """把统一工具执行投影成消息摘要工具行，尚无结果用占位值。"""
    result = execution.result
    return ToolInvocation(
        tool_call_id=execution.tool_call_id, name=execution.name,
        arguments=execution.arguments, display=execution.display,
        duration_ms=result.duration_ms if result else 0,
        content=result.content if result else "",
    )


def aggregate_trace(message_id: str, entries: Iterable[TraceEntry]) -> MessageTrace:
    """从执行事件生成消息轨迹摘要，思考段累计全部响应。"""
    events = _ExecutionEvents()
    for entry in entries:
        events.absorb(entry)
    return MessageTrace(
        message_id=message_id,
        thinking=[segment for _, response in events.responses for segment in response.thinking_segments],
        tools=[_tool_invocation(execution) for execution in events.merge_tools()],
    )
