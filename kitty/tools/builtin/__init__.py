"""内置工具（类化版本，由 create_app() 装配进 ToolRegistry）。

旧的函数式工具文件（bash.py / read_file.py / ...）已废弃，阶段 5 删除。
"""

from kitty.tools.builtin.baidu_search import BaiduSearchTool
from kitty.tools.builtin.bash import BashTool
from kitty.tools.builtin.edit_file import EditFileTool
from kitty.tools.builtin.generate_image import GenerateImageTool
from kitty.tools.builtin.glob_search import GlobSearchTool
from kitty.tools.builtin.load_skill import LoadSkillTool
from kitty.tools.builtin.read_file import ReadFileTool
from kitty.tools.builtin.write_file import WriteFileTool

__all__ = [
    "BashTool",
    "ReadFileTool",
    "WriteFileTool",
    "EditFileTool",
    "GlobSearchTool",
    "LoadSkillTool",
    "GenerateImageTool",
    "BaiduSearchTool",
]
