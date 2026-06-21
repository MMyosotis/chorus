"""内置工具（类化版本，由 create_app() 装配进 ToolRegistry）。"""

from kitty.tools.builtin.baidu_search import BaiduSearchTool
from kitty.tools.builtin.generate_image import GenerateImageTool
from kitty.tools.builtin.load_skill import LoadSkillTool
from kitty.tools.builtin.output_plan import OutputPlanTool

__all__ = [
    "LoadSkillTool",
    "OutputPlanTool",
    "GenerateImageTool",
    "BaiduSearchTool",
]
