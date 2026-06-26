"""ToolDispatch.select_schemas smoke test：名字白名单筛选 + web_search 开关。

运行：.venv/bin/python -m chorus.tests.test_tools_select"""
from __future__ import annotations

from chorus.tools import Tool, ToolContext, ToolDispatch, ToolOutcome


class _FakeTool(Tool):
    """最小 Tool：只暴露 name，run 不可达（select_schemas 不触发 run）。"""

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


def test_select_by_names():
    reg = _registry("baidu_search", "generate_image", "load_skill")
    # image 角色白名单（全集顺序保留）
    got = [s["function"]["name"] for s in reg.select_schemas(["baidu_search", "generate_image", "load_skill"])]
    assert got == ["baidu_search", "generate_image", "load_skill"]
    # idea 角色白名单（不含 generate_image）
    got = [s["function"]["name"] for s in reg.select_schemas(["baidu_search", "load_skill"])]
    assert got == ["baidu_search", "load_skill"]
    # 不存在的名字静默跳过
    got = [s["function"]["name"] for s in reg.select_schemas(["baidu_search", "nope"])]
    assert got == ["baidu_search"]
    # 空白名单
    assert reg.select_schemas([]) == []


def test_web_search_disabled_drops_baidu_search():
    reg = _registry("baidu_search", "load_skill", web_search=False)
    # web_search 关闭：baidu_search 被剔除，保留其余
    got = [s["function"]["name"] for s in reg.select_schemas(["baidu_search", "load_skill"])]
    assert got == ["load_skill"]
    # 白名单本就不含 baidu_search 时无副作用
    got = [s["function"]["name"] for s in reg.select_schemas(["load_skill"])]
    assert got == ["load_skill"]


def main():
    test_select_by_names()
    test_web_search_disabled_drops_baidu_search()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
