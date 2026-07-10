"""意图旁白生成:读 invoke 调小模型,失败兜默认文案。"""
from unittest.mock import MagicMock
from chorus.domain.task.aside import AsideGenerator


def test_generate_returns_cleaned_aside():
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content="打算用光线挪动串起一杯咖啡的时间"))]
    )
    gen = AsideGenerator(client, "deepseek-flash")
    out = gen.generate("script", "写一篇秋日阳台咖啡...")
    assert out == "打算用光线挪动串起一杯咖啡的时间"


def test_generate_returns_default_on_exception():
    client = MagicMock()
    client.chat.completions.create.side_effect = RuntimeError("network")
    gen = AsideGenerator(client, "deepseek-flash")
    assert gen.generate("script", "invoke") == "我在打磨这段文案"


def test_generate_returns_default_on_empty():
    client = MagicMock()
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=""))]
    )
    gen = AsideGenerator(client, "deepseek-flash")
    assert gen.generate("idea", "invoke") == "我在琢磨一个好选题"


def test_generate_truncates_long_aside():
    client = MagicMock()
    long = "a" * 50
    client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=long))]
    )
    gen = AsideGenerator(client, "m")
    assert len(gen.generate("script", "i")) <= 30


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
