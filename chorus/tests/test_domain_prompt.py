# kitty/tests/test_domain_prompt.py
"""系统提示词纯函数断言：supervisor / subagent prompt 拼装规则。

覆盖 ``kitty/domain/prompt`` 的 ``build_system_prompt``（supervisor）与
``build_subagent_system_prompt``（各角色），锚定 prompt 含关键锚点（create_plan
工具、profiles 注入、ARTIFACTS/NARRATIVE 段标记、禁 emoji 约束）。

运行：``.venv/bin/python -m kitty.tests.test_domain_prompt``
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
        assert "<<<ARTIFACTS:json>>>" in p
        assert "<<<NARRATIVE:json>>>" in p
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
