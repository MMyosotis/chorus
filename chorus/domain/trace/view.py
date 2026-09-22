"""轨迹视图装配：先构建完整轮组，再投影展示行与会话统计。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional, Union

from chorus.domain.task.models import AgentType
from chorus.domain.trace.aggregation import Call, ToolExecution, build_calls, tool_executions_by_id, tool_names_by_id
from chorus.domain.trace.models import ModelUsage, TraceEntry
from chorus.domain.trace.items import (
    AgentRole,
    Bypass,
    UserInputItem,
    build_bypasses,
    build_user_inputs,
    user_input_for,
    SUPERVISOR_ROLE,
)
from chorus.domain.trace.rows import (
    BypassRow,
    LoopRow,
    TimelineRow,
    ToolbackRow,
    UserRow,
    toolback_tools,
)


_TimelineItem = Union[Call, Bypass, UserInputItem]

_EVENT_ORDER: dict[type, int] = {Call: 0, Bypass: 1, UserInputItem: 1}
_FIRST_TURN_NUMBER = 1
_BYPASS_ONLY_TURN_NUMBER = 0


def _event_sort_key(item: _TimelineItem) -> tuple[float, int]:
    return item.created_at, _EVENT_ORDER[type(item)]


@dataclass
class _Turn:
    """完整轮组：用户输入置于轮首，调用与旁路按事件顺序保存。"""

    number: int
    user: Optional[UserInputItem] = None
    items: list[Call | Bypass] = field(default_factory=list)

    @property
    def first_call(self) -> Optional[Call]:
        return next((item for item in self.items if isinstance(item, Call)), None)

    def accepts_call(self, call: Call) -> bool:
        if self.first_call is None:
            return self.user is not None
        return bool(call.returned_tool_ids)


@dataclass
class _TurnBuilder:
    """收集完整轮组，首轮建立时接纳此前的旁路。"""

    _turns: list[_Turn] = field(default_factory=list)
    _current: Optional[_Turn] = None
    _leading_bypasses: list[Bypass] = field(default_factory=list)

    def add(self, item: _TimelineItem) -> None:
        if isinstance(item, UserInputItem):
            self._open_turn(item)
            return
        if isinstance(item, Bypass):
            items = self._current.items if self._current is not None else self._leading_bypasses
            items.append(item)
            return
        current = self._current
        if current is None or not current.accepts_call(item):
            current = self._open_turn(user_input_for(item.request, item.created_at))
        current.items.append(item)

    def _open_turn(self, user: Optional[UserInputItem]) -> _Turn:
        turn: _Turn = _Turn(
            number=len(self._turns) + _FIRST_TURN_NUMBER,
            user=user, items=list(self._leading_bypasses),
        )
        self._current = turn
        self._leading_bypasses = []
        self._turns.append(turn)
        return turn

    def finish(self) -> list[_Turn]:
        if self._turns:
            return self._turns
        if self._leading_bypasses:
            return [_Turn(number=_BYPASS_ONLY_TURN_NUMBER, items=list(self._leading_bypasses))]
        return []


def _split_turns(calls: list[Call], bypasses: list[Bypass], users: list[UserInputItem],) -> list[_Turn]:
    """按输入与调用边界构建轮组，首轮前的旁路并入首轮。"""
    builder = _TurnBuilder()
    for item in sorted([*calls, *bypasses, *users], key=_event_sort_key):
        builder.add(item)
    return builder.finish()


def _project_item_rows(
    item: Call | Bypass,
    turn_number: int,
    executions_by_id: dict[str, ToolExecution],
    tool_name_by_id: dict[str, str],
) -> list[TimelineRow]:
    """投影单个执行条目，关联工具结果紧邻回传调用。"""
    if isinstance(item, Bypass):
        bypass_row = BypassRow(turn=turn_number,created_at=item.created_at,item=item)
        return [bypass_row]

    call = item
    returned_executions = [
        executions_by_id[tool_id]
        for tool_id in call.returned_tool_ids
        if tool_id in executions_by_id
    ]

    rows: list[TimelineRow] = []
    if returned_executions:
        toolback = ToolbackRow(turn=turn_number, created_at=call.created_at, tools=toolback_tools(returned_executions))
        rows.append(toolback)

    call_row = LoopRow(turn=turn_number, created_at=call.created_at, call=call, tool_name_by_id=tool_name_by_id)
    rows.append(call_row)
    return rows


def _project_rows(
    turn: _Turn,
    executions_by_id: dict[str, ToolExecution],
    tool_name_by_id: dict[str, str],
) -> list[TimelineRow]:
    """用户行固定在轮首，其余条目保持轮内顺序。"""
    rows: list[TimelineRow] = []
    if turn.user is not None:
        user_row = UserRow(turn=turn.number, created_at=turn.user.created_at, item=turn.user)
        rows.append(user_row)

    for item in turn.items:
        item_rows = _project_item_rows(
            item=item,
            turn_number=turn.number,
            executions_by_id=executions_by_id,
            tool_name_by_id=tool_name_by_id,
        )
        rows.extend(item_rows)
    return rows


def _turn_row(
    turn: _Turn,
    executions_by_id: dict[str, ToolExecution],
    tool_name_by_id: dict[str, str],
) -> dict:
    """单轮组成品行：轮头取首个模型调用的角色名，缺则退旁路。"""
    rows = _project_rows(turn, executions_by_id, tool_name_by_id)
    role_item = turn.first_call or next(iter(turn.items), None)
    start_at = min(row.start_at for row in rows)
    end_at = max(row.end_at for row in rows)
    return {
        "turn": turn.number,
        "items": [row.dump() for row in rows],
        "agent_name": role_item.role.name if role_item else "—",
        "duration_ms": round((end_at - start_at) * 1000),
    }


@dataclass
class _UsageTotals:
    """用量与费用累积器。"""

    cost_cny: Optional[float] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def add(self, cost_cny: Optional[float], usage: Optional[ModelUsage]) -> None:
        if cost_cny is not None:
            self.cost_cny = (self.cost_cny or 0) + cost_cny
        if usage is not None:
            self.input_tokens += usage.input_tokens
            self.output_tokens += usage.output_tokens
            self.total_tokens += usage.total_tokens


def _time_span(calls: list[Call], bypasses: list[Bypass]) -> tuple[float, float]:
    """最早开始时间与最晚结束时间（响应或工具结果收尾）。"""
    first = min([call.start_at for call in calls] + [row.start_at for row in bypasses])
    last = max([call.end_at for call in calls] + [row.end_at for row in bypasses])
    return first, last


def _build_stats(calls: list[Call], bypasses: list[Bypass], turns: list[_Turn]) -> Optional[dict]:
    """全会话统计：折算旁路用量与费用，双空返 None。"""
    if not calls and not bypasses:
        return None
    first, last = _time_span(calls, bypasses)
    totals = _UsageTotals()
    tool_count = 0
    for call in calls:
        tool_count += sum(execution.result is not None for execution in call.tools)
        if call.response is not None:
            totals.add(call.response.cost_cny, call.response.usage)
    for row in bypasses:
        totals.add(row.payload.cost_cny, row.payload.usage)
    return {
        "duration_ms": round((last - first) * 1000),
        "turn_count": max((turn.number for turn in turns if turn.first_call is not None), default=0),
        "call_count": len(calls),
        "bypass_count": len(bypasses),
        "tool_count": tool_count,
        "cost_cny": totals.cost_cny,
        "input_tokens": totals.input_tokens,
        "output_tokens": totals.output_tokens,
        "total_tokens": totals.total_tokens,
    }


def _collect_agents(calls: list[Call], bypasses: list[Bypass]) -> list[dict]:
    """按首次出现顺序收集来源角色页签清单。"""
    seen: dict[str, AgentRole] = {}
    for record in [*calls, *bypasses]:
        seen.setdefault(record.role.key, record.role)
    return [{"key": role.key, "label": role.label} for role in seen.values()]


def build_trace_view(
    entries: Iterable[TraceEntry],
    agent_type_by_task: dict[str, AgentType],
    agent_key: Optional[str] = None,
) -> dict:
    """装配控制台成品视图；agent_key 过滤时间线并重算轮次，角色清单与统计始终全量。"""
    entries = list(entries)
    all_calls = build_calls(entries, agent_type_by_task)
    all_bypasses = build_bypasses(entries, agent_type_by_task)
    all_users = build_user_inputs(entries)
    names_by_id = tool_names_by_id(all_calls)
    all_turns = _split_turns(all_calls, all_bypasses, all_users)
    calls = all_calls
    turns = all_turns

    if agent_key:
        calls = [call for call in all_calls if call.role.key == agent_key]
        bypasses = [row for row in all_bypasses if row.role.key == agent_key]
        users = list(all_users) if agent_key == SUPERVISOR_ROLE.key else []
        turns = _split_turns(calls, bypasses, users)

    executions_by_id = tool_executions_by_id(calls)
    return {
        "agents": _collect_agents(all_calls, all_bypasses),
        "stats": _build_stats(all_calls, all_bypasses, all_turns),
        "turns": [_turn_row(turn, executions_by_id, names_by_id) for turn in turns],
    }
