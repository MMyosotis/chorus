#!/usr/bin/env python3
"""Little Kitty 后端测试 CLI — 直接调用 chat_stream，不走 HTTP。"""

import sys

try:
    import readline  # noqa: F401
except ImportError:
    pass

from backend.app import create_app  # 触发初始化
from backend.chat import chat_stream, reset_history

_ = create_app  # 只需触发 side effect

COLORS = {
    "token": "\033[0m",       # 默认
    "tool_call": "\033[33m",  # 黄
    "tool_result": "\033[36m", # 青
    "done": "\033[32m",       # 绿
    "error": "\033[31m",      # 红
}
RESET = "\033[0m"


def main():
    print("Little Kitty 测试 CLI（输入 q 退出，输入 /reset 重置）\n")

    while True:
        try:
            query = input("\033[1;34m>>> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break

        if query.strip().lower() in ("q", "exit"):
            break
        if query.strip() == "/reset":
            reset_history()
            print("\033[32m已重置对话\033[0m\n")
            continue
        if not query.strip():
            continue

        for event in chat_stream(query):
            etype = event["type"]
            color = COLORS.get(etype, "")

            if etype == "token":
                print(event["content"], end="", flush=True)
            elif etype == "tool_call":
                print(f"\n{color}[tool_call] {event['name']}({event['arguments']}){RESET}")
            elif etype == "tool_result":
                content = event["content"]
                if len(content) > 500:
                    content = content[:500] + f"... ({len(event['content'])} chars total)"
                print(f"{color}[tool_result] {event['name']}: {content}{RESET}")
            elif etype == "done":
                reason = event.get("reason")
                if reason:
                    print(f"\n{color}[done] {reason}{RESET}")
                else:
                    print()  # 最终回复换行
            elif etype == "error":
                print(f"\n{color}[error] {event['content']}{RESET}")

    print("\n再见！")


if __name__ == "__main__":
    main()
