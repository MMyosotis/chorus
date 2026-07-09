"""系统提示词纯函数断言：supervisor / subagent prompt 拼装规则。

锚定 prompt 含关键锚点（create_plan 工具、profiles 注入、Markdown 产出协议与 chorus 注释话术、禁 emoji）。
"""
from __future__ import annotations

from chorus.domain.prompt import (
    PromptContext,
    build_subagent_system_prompt,
    build_system_prompt,
)


def test_subagent_prompts():
    for at in ("idea", "script", "image", "finalize"):
        p = build_subagent_system_prompt(at)
        assert "<!-- chorus:awaiting=" in p
        assert "<!-- chorus:done=" in p
        assert "<<<ARTIFACTS" not in p
        assert "禁用任何 emoji" in p


def test_supervisor_prompt_has_profiles():
    p = build_system_prompt(PromptContext())
    assert "create_plan" in p
    assert "finalize" in p
    assert "选题官" in p  # profiles 注入


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
