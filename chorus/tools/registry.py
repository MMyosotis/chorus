"""工具登记装配：把工具子系统装配成调度器实例。

组合根，位于框架与内置工具之上，往下单向依赖不被反依赖。工具内部胶水内化于此。
"""

from __future__ import annotations

from chorus.config import BAIDU_SEARCH_API_KEY, BAIDU_SEARCH_BASE_URL
from chorus.domain.skill import SkillLoader
from chorus.repo.connection import ConnectionFactory
from chorus.repo.task import TaskRepository
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
    """装配默认工具调度器。工具内部胶水内化于此，外界只暴露跨层依赖。"""
    image_models = ImageModelProvider(settings_service)
    baidu_client = BaiduSearchClient(BAIDU_SEARCH_API_KEY, BAIDU_SEARCH_BASE_URL)
    return ToolDispatch([
        LoadSkillTool(skill_loader),
        OutputPlanTool(),
        GenerateImageTool(settings_service, image_models),
        BaiduSearchTool(baidu_client),
        CreatePlanTool(task_repo, conn),
    ], settings_service)
