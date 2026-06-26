# kitty/tests/test_agent_supervisor_isolation.py
"""supervisor 白名单隔离 + loop 工具名无关契约。

运行：.venv/bin/python -m kitty.tests.test_agent_supervisor_isolation
"""
from __future__ import annotations

from chorus.agents.supervisor import SUPERVISOR_TOOLS, SupervisorService
from chorus.tools import ToolRegistry
from chorus.tools.builtin import BaiduSearchTool, CreatePlanTool, LoadSkillTool, OutputPlanTool
from chorus.tools.builtin.generate_image import GenerateImageTool


def _registry() -> ToolRegistry:
    # 不需真实 client/repo，只为 schema 全集
    return ToolRegistry([
        LoadSkillTool(),
        OutputPlanTool(),
        CreatePlanTool(None, None),
        BaiduSearchTool(None),
        GenerateImageTool(lambda: False, "", {}, "x"),
    ])


def test_supervisor_tools_excludes_generate_image():
    """白名单不含 generate_image——supervisor 不碰产物。"""
    assert "generate_image" not in SUPERVISOR_TOOLS
    assert "create_plan" in SUPERVISOR_TOOLS


def test_supervisor_schemas_filtered_by_whitelist():
    """从 registry 全集筛后，supervisor 喂 LLM 的 schemas 不含 generate_image/output_plan。"""
    from chorus.tools import select_schemas_by_names
    all_names = {s["function"]["name"] for s in _registry().schemas_openai()}
    assert "generate_image" in all_names  # registry 全集有
    sup_schemas = select_schemas_by_names(_registry().schemas_openai(), SUPERVISOR_TOOLS)
    sup_names = {s["function"]["name"] for s in sup_schemas}
    assert sup_names == set(SUPERVISOR_TOOLS)
    assert "generate_image" not in sup_names
    assert "output_plan" not in sup_names


def test_loop_does_not_reference_tool_name_literals():
    """loop 分流只依赖 isinstance(outcome)，源码不出现 'create_plan' 字面量做路由判断。"""
    import inspect
    # SUPERVISOR_TOOLS 常量声明里有 'create_plan'，但 _dispatch_tools/_handle_terminal 分流段不应硬判名
    dispatch_src = inspect.getsource(SupervisorService._dispatch_tools)
    handle_src = inspect.getsource(SupervisorService._handle_terminal)
    assert "create_plan" not in dispatch_src  # 无硬编码名
    assert "tc.get" not in dispatch_src and 'name == "create_plan"' not in dispatch_src
    # handle_terminal 不认 Terminal 载荷类型——工具副作用自洽，主流程只管终止
    assert "isinstance" not in handle_src
    assert "payload" not in handle_src


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
