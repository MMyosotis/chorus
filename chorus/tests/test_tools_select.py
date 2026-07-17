"""ToolDispatch.select_schemas smoke test：名字白名单筛选 + web_search 开关。"""
from __future__ import annotations

from chorus.tools import Tool, ToolContext, ToolDispatch, ToolOutcome


class _FakeTool(Tool):
    """最小工具：只暴露名字，run 不可达。"""

    def __init__(self, name):
        self.name = name
        self.description = name
        self.parameters = {}

    def run(self, arguments, ctx: ToolContext) -> ToolOutcome:
        raise AssertionError("select_schemas 不应触发 run")


def _registry(*names: str, web_search: bool = True):
    class _S:
        def get_web_search(self):
            return web_search
    return ToolDispatch([_FakeTool(n) for n in names], _S())


def _stub_settings():
    class _S:
        def get_web_search(self):
            return True
    return _S()


def test_select_by_names():
    reg = _registry("baidu_search", "generate_image", "load_skill")
    # image 角色白名单（全集顺序保留）
    got = [s["function"]["name"] for s in reg.select_schemas(["baidu_search", "generate_image", "load_skill"])]
    assert got == ["baidu_search", "generate_image", "load_skill"]
    # idea 角色白名单（不含生图）
    got = [s["function"]["name"] for s in reg.select_schemas(["baidu_search", "load_skill"])]
    assert got == ["baidu_search", "load_skill"]
    # 不存在的名字静默跳过
    got = [s["function"]["name"] for s in reg.select_schemas(["baidu_search", "nope"])]
    assert got == ["baidu_search"]
    # 空白名单
    assert reg.select_schemas([]) == []


def test_web_search_disabled_drops_baidu_search():
    reg = _registry("baidu_search", "load_skill", web_search=False)
    # 关闭联网搜索：搜索工具被剔除，保留其余
    got = [s["function"]["name"] for s in reg.select_schemas(["baidu_search", "load_skill"])]
    assert got == ["load_skill"]
    # 白名单本就不含搜索工具时无副作用
    got = [s["function"]["name"] for s in reg.select_schemas(["load_skill"])]
    assert got == ["load_skill"]


def test_dispatch_normalizes_tool_run_result():
    """工具返回 ToolRunResult → DispatchResult 透传 activity_meta。"""
    from chorus.tools.framework import DispatchResult, Reply, Tool, ToolContext, ToolRunResult

    class _MetaTool(Tool):
        name = "baidu_search"
        description = "x"
        parameters = {"type": "object", "properties": {}}
        def run(self, arguments, ctx):
            return ToolRunResult(Reply("可见文本"), activity_meta={"refs": [{"title": "t"}]})

    class _BareTool(Tool):
        name = "load_skill"
        description = "x"
        parameters = {"type": "object", "properties": {}}
        def run(self, arguments, ctx):
            return ToolRunResult(Reply("裸 outcome"))

    from chorus.tools.framework import ToolDispatch
    disp = ToolDispatch([_MetaTool(), _BareTool()], _stub_settings())
    from chorus.tools.models import ToolCall
    d1 = disp.dispatch(ToolCall(id="c1", name="baidu_search", arguments={}), ToolContext())
    assert isinstance(d1, DispatchResult)
    assert d1.activity_meta == {"refs": [{"title": "t"}]}
    assert d1.outcome.content == "可见文本"
    d2 = disp.dispatch(ToolCall(id="c2", name="load_skill", arguments={}), ToolContext())
    assert d2.activity_meta is None  # 未带活动元数据，透传为空


def main():
    test_select_by_names()
    test_web_search_disabled_drops_baidu_search()
    test_dispatch_normalizes_tool_run_result()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
