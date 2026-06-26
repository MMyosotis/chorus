"""工具登记装配：build_tool_dispatch 把工具子系统装配成 ToolDispatch 实例。

registry 是组合根——位于 framework / builtin / clients 之上，往下单向 import，
不被任何一方反向依赖。image_models / baidu_client 等中间件内化于此，不泄露到
app 作用域。ToolDispatch 类本身（登记+查 schema+派发）在 tools/framework.py。
"""

from __future__ import annotations

from chorus.config import BAIDU_SEARCH_API_KEY, BAIDU_SEARCH_BASE_URL
from chorus.domain.skill import SkillLoader
from chorus.repositories.connection import ConnectionFactory
from chorus.repositories.task import TaskRepository
from chorus.services.settings import SettingsService
from chorus.tools.builtin import (
    BaiduSearchTool,
    CreatePlanTool,
    LoadSkillTool,
    OutputPlanTool,
)
from chorus.tools.builtin.generate_image import GenerateImageTool, ImageModelProvider
from chorus.tools.clients.baidu_search import BaiduSearchClient
from chorus.tools.framework import ToolDispatch


def build_tool_dispatch(
    settings_service: SettingsService,
    task_repo: TaskRepository,
    conn: ConnectionFactory,
    skill_loader: SkillLoader,
) -> ToolDispatch:
    """装配默认工具调度器。

    image_models / baidu_client 等工具内部胶水内化于此，外界只暴露跨层依赖
    （settings / task_repo / conn / skill_loader）。新增工具或改某工具依赖只改本函数。
    """
    image_models = ImageModelProvider(settings_service)
    baidu_client = BaiduSearchClient(BAIDU_SEARCH_API_KEY, BAIDU_SEARCH_BASE_URL)
    return ToolDispatch([
        LoadSkillTool(skill_loader),
        OutputPlanTool(),
        GenerateImageTool(settings_service, image_models),
        BaiduSearchTool(baidu_client),
        CreatePlanTool(task_repo, conn),
    ], settings_service)
