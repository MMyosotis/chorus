"""会话标题领域规则纯函数断言：clean_generated_title / normalize_title。

LLM 原始标题剥引号/书名号 + 截 30 字；入库标题去空白 + 截 60 字（均硬截断无省略号）。
依赖真实 OpenAI 的服务非纯函数，此处不测。
"""
from __future__ import annotations

from chorus.domain.title import (
    STORED_TITLE_MAX_LEN,
    _GENERATED_MAX_LEN,
    clean_generated_title,
    normalize_title,
)


def test_stored_title_max_len_is_60():
    assert STORED_TITLE_MAX_LEN == 60
    assert _GENERATED_MAX_LEN == 30


def test_clean_strips_quotes_and_brackets():
    # 引号 / 书名号 / 角括号 / 反引号 / 空白均在剥离集合内
    assert clean_generated_title('"夏日晚风"') == "夏日晚风"
    assert clean_generated_title("「夏日晚风」") == "夏日晚风"
    assert clean_generated_title("《夏日晚风》") == "夏日晚风"
    assert clean_generated_title("  `夏日晚风`  ") == "夏日晚风"
    assert clean_generated_title("'夏日晚风'") == "夏日晚风"


def test_clean_truncates_to_30_no_ellipsis():
    raw = "啊" * 40
    out = clean_generated_title(raw)
    assert len(out) == 30
    assert out == raw[:30]
    assert "…" not in out and "..." not in out


def test_clean_returns_none_for_empty_or_pure_marks():
    assert clean_generated_title("") is None
    assert clean_generated_title("   ") is None
    assert clean_generated_title('"""') is None  # 全是剥离字符 -> 空
    assert clean_generated_title("「」") is None


def test_clean_preserves_inner_punctuation():
    # 仅剥首尾, 内部标点保留
    assert clean_generated_title('"夏日晚风：一篇随笔"') == "夏日晚风：一篇随笔"


def test_normalize_truncates_to_60_no_ellipsis():
    title = "字" * 70
    out = normalize_title(title)
    assert len(out) == 60
    assert out == title[:60]
    assert "…" not in out and "..." not in out


def test_normalize_strips_whitespace():
    assert normalize_title("  hello  ") == "hello"


def test_normalize_empty_and_none_become_empty_string():
    assert normalize_title("") == ""
    assert normalize_title(None) == ""  # 空值兜底为空串
    assert normalize_title("   ") == ""  # 去空白后为空


def test_normalize_custom_max_len():
    assert normalize_title("abcdef", max_len=3) == "abc"
    assert normalize_title("ab", max_len=3) == "ab"  # 不足不补


def test_clean_then_normalize_pipeline():
    # 模拟真实链路：先清洗再归一
    raw = '  "夏日晚风"  '
    assert normalize_title(clean_generated_title(raw)) == "夏日晚风"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
