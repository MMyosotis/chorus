"""内置工具（类化版本，由 build_tool_dispatch 装配进 ToolDispatch）。"""

from chorus.tools.builtin.baidu_search import BaiduSearchTool
from chorus.tools.builtin.create_plan import CreatePlanTool
from chorus.tools.builtin.generate_image import GenerateImageTool
from chorus.tools.builtin.load_skill import LoadSkillTool
from chorus.tools.builtin.output_plan import OutputPlanTool

__all__ = [
    "LoadSkillTool",
    "OutputPlanTool",
    "GenerateImageTool",
    "BaiduSearchTool",
    "CreatePlanTool",
]
