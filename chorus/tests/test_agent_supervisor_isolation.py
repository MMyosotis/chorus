# chorus/tests/test_agent_supervisor_isolation.py
"""supervisor 白名单隔离 + loop 工具名无关契约。

运行：.venv/bin/python -m chorus.tests.test_agent_supervisor_isolation
"""
from __future__ import annotations

from chorus.agents.supervisor import SupervisorService
from chorus.config import TOOL_WHITELISTS
from chorus.tools import ToolDispatch
from chorus.tools.builtin import BaiduSearchTool, CreatePlanTool, LoadSkillTool, OutputPlanTool
from chorus.tools.builtin.generate_image import GenerateImageTool


def _stub_settings():
    class _S:
        def get_image_test_mode(self):
            return False

        def get_web_search(self):
            return True
    return _S()


def _stub_provider():
    class _P:
        def get_entry(self):
            raise AssertionError("schema 筛选测试不应触发 run")
    return _P()


def _registry() -> ToolDispatch:
    # 不需真实 client/repo，只为 schema 筛选
    return ToolDispatch([
        LoadSkillTool(None),
        OutputPlanTool(),
        CreatePlanTool(None, None),
        BaiduSearchTool(None),
        GenerateImageTool(_stub_settings(), _stub_provider()),
    ], _stub_settings())


def test_supervisor_whitelist_excludes_generate_image():
    """supervisor 白名单不含 generate_image——它是传话筒/管人的领导，不碰产物。"""
    tools = TOOL_WHITELISTS["supervisor"]
    assert "generate_image" not in tools
    assert "create_plan" in tools


def test_supervisor_schemas_filtered_by_whitelist():
    """registry.select_schemas 按 supervisor 白名单筛后，喂 LLM 的 schemas 不含
    generate_image（领导不碰产物），output_plan 是独立展示计划工具故暴露；web_search
    关闭时再剔除 baidu_search。"""
    reg = _registry()
    sup_names = {s["function"]["name"] for s in reg.select_schemas(TOOL_WHITELISTS["supervisor"])}
    assert sup_names == set(TOOL_WHITELISTS["supervisor"])  # web_search 开 → 全白名单命中
    assert "generate_image" not in sup_names
    assert "output_plan" in sup_names


def test_web_search_disabled_drops_baidu_search():
    """web_search 关闭时 select_schemas 从结果里剔除 baidu_search。"""
    class _OffSettings:
        def get_web_search(self):
            return False
    reg = ToolDispatch([BaiduSearchTool(None), LoadSkillTool(None)], _OffSettings())
    got = {s["function"]["name"] for s in reg.select_schemas(TOOL_WHITELISTS["supervisor"])}
    assert "baidu_search" not in got
    assert "load_skill" in got


def test_loop_does_not_reference_tool_name_literals():
    """loop 分流只依赖 isinstance(outcome)，源码不出现 'create_plan' 字面量做路由判断。"""
    import inspect
    # TOOL_WHITELISTS 里有 'create_plan'，但 _dispatch_tools/_handle_terminal 分流段不应硬判名
    dispatch_src = inspect.getsource(SupervisorService._dispatch_tools)
    handle_src = inspect.getsource(SupervisorService._handle_terminal)
    assert "create_plan" not in dispatch_src  # 无硬编码名
    # 禁按工具名做相等路由（tc.get("name") 后比名）；tc.get("seq") 取时序字段不属此列
    assert 'tc.get("name")' not in dispatch_src and 'name == "create_plan"' not in dispatch_src
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
