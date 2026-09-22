"""轨迹视图服务：取会话轨迹与任务图，喂领域装配出成品视图。"""
from typing import Optional

from chorus.domain.trace import build_trace_view
from chorus.services.task import TaskService
from chorus.services.trace import TraceService


class TraceViewService:
    def __init__(self, trace: TraceService, task: TaskService):
        self._trace = trace
        self._task = task

    def collect(self, session_id: str, agent_key: Optional[str] = None) -> dict:
        """收集轨迹与任务角色映射，装配控制台成品视图。"""
        agent_type_by_task = {node.id: node.agent_type for node in self._task.get_graph(session_id).nodes}
        return build_trace_view(self._trace.list_traces(session_id), agent_type_by_task, agent_key)
