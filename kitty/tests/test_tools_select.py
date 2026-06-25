"""select_schemas_by_names smoke test。运行：.venv/bin/python -m kitty.tests.test_tools_select"""
from __future__ import annotations

from kitty.tools import select_schemas_by_names


def test_select_by_names():
    all_schemas = [
        {"type": "function", "function": {"name": "baidu_search", "description": "x"}},
        {"type": "function", "function": {"name": "generate_image", "description": "y"}},
        {"type": "function", "function": {"name": "load_skill", "description": "z"}},
    ]
    # image 角色白名单
    got = select_schemas_by_names(all_schemas, ["baidu_search", "generate_image", "load_skill"])
    assert [s["function"]["name"] for s in got] == ["baidu_search", "generate_image", "load_skill"]
    # idea 角色白名单（不含 generate_image）
    got = select_schemas_by_names(all_schemas, ["baidu_search", "load_skill"])
    assert [s["function"]["name"] for s in got] == ["baidu_search", "load_skill"]
    # 不存在的名字静默跳过
    got = select_schemas_by_names(all_schemas, ["baidu_search", "nope"])
    assert [s["function"]["name"] for s in got] == ["baidu_search"]
    # 空白名单
    assert select_schemas_by_names(all_schemas, []) == []


def main():
    test_select_by_names()
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
