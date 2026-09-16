"""agent 旁白生成:读 invoke 调小模型,失败兜默认文案。"""
from unittest.mock import MagicMock

from chorus.domain.bypass import BypassScope
from chorus.domain.task.aside import AsideGenerator
from chorus.tests._helpers import build_bypass_caller

_SCOPE = BypassScope("s1")


def test_generate_returns_cleaned_aside():
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        usage=None,
        choices=[MagicMock(message=MagicMock(content="打算用光线挪动串起一杯咖啡的时间"))],
    )
    gen = AsideGenerator(build_bypass_caller(client)[0])
    out = gen.generate("script", "写一篇秋日阳台咖啡...", _SCOPE)
    assert out == "打算用光线挪动串起一杯咖啡的时间"


def test_generate_records_bypass_trace():
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        usage=None,
        choices=[MagicMock(message=MagicMock(content="我正在撰写正文"))],
    )
    caller, entries = build_bypass_caller(client)
    AsideGenerator(caller).generate("script", "invoke", _SCOPE)
    assert len(entries) == 1
    payload = entries[0].payload
    assert payload.purpose == "aside"
    assert payload.status == "success"
    assert payload.content == "我正在撰写正文"


def test_generate_returns_default_on_exception():
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("network")
    gen = AsideGenerator(build_bypass_caller(client)[0])
    assert gen.generate("script", "invoke", _SCOPE) == "我正在撰写正文"


def test_generate_returns_default_on_empty():
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        usage=None,
        choices=[MagicMock(message=MagicMock(content=""))],
    )
    gen = AsideGenerator(build_bypass_caller(client)[0])
    assert gen.generate("idea", "invoke", _SCOPE) == "我正在调研候选选题"


def test_generate_truncates_long_aside():
    client = MagicMock()
    long = "a" * 50
    client.chat.completions.create.return_value = MagicMock(
        usage=None,
        choices=[MagicMock(message=MagicMock(content=long))],
    )
    gen = AsideGenerator(build_bypass_caller(client)[0])
    assert len(gen.generate("script", "i", _SCOPE)) <= 30


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
