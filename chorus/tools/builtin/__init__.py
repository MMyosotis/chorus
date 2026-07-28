"""内置工具集，由装配函数登记进调度器。"""

from chorus.tools.builtin.baidu_search import BaiduSearchTool
from chorus.tools.builtin.create_plan import CreatePlanTool
from chorus.tools.builtin.generate_image import GenerateImageTool
from chorus.tools.builtin.list_skill import ListSkillTool
from chorus.tools.builtin.load_skill import LoadSkillTool
from chorus.tools.builtin.present_options import PresentOptionsTool
from chorus.tools.builtin.update_intent_state import UpdateIntentStateTool

__all__ = [
    "LoadSkillTool",
    "ListSkillTool",
    "GenerateImageTool",
    "BaiduSearchTool",
    "CreatePlanTool",
    "UpdateIntentStateTool",
    "PresentOptionsTool",
]
