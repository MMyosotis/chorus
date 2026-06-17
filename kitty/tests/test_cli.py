#!/usr/bin/env python3
"""Little Kitty 后端测试 CLI — 直接调用 ChatService.stream，不走 HTTP。"""

try:
    import readline  # noqa: F401
except ImportError:
    pass

import kitty.app as _app  # 触发 AppContainer 装配

_container = _app.app.state.container


COLORS = {
    "token": "\033[0m",         # 默认
    "tool_call": "\033[33m",    # 黄
    "tool_result": "\033[36m",  # 青
    "done": "\033[32m",         # 绿
    "error": "\033[31m",        # 红
}
RESET = "\033[0m"


def main():
    svc = _container.session_service
    chat = _container.chat_service
    session = svc.create("CLI 调试")
    session_id = session.id
    print(f"Little Kitty 测试 CLI（输入 q 退出，输入 /new 新建会话）")
    print(f"当前会话: {session_id}\n")

    while True:
        try:
            query = input("\033[1;34m>>> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break

        if query.strip().lower() in ("q", "exit"):
            break
        if query.strip() == "/new":
            session = svc.create("CLI 调试")
            session_id = session.id
            print(f"\033[32m已新建会话 {session_id}\033[0m\n")
            continue
        if not query.strip():
            continue

        for ev in chat.stream(session_id, query):
            etype = ev.type
            color = COLORS.get(etype, "")

            if etype == "token":
                print(ev.content, end="", flush=True)
            elif etype == "tool_call":
                print(f"\n{color}[tool_call] {ev.name}({ev.arguments}){RESET}")
            elif etype == "tool_result":
                content = ev.content
                if len(content) > 500:
                    content = content[:500] + f"... ({len(ev.content)} chars total)"
                print(f"{color}[tool_result] {ev.name}: {content}{RESET}")
            elif etype == "title_update":
                print(f"\n\033[35m[title_update] {ev.title}{RESET}")
            elif etype == "done":
                if ev.reason:
                    print(f"\n{color}[done] {ev.reason}{RESET}")
                else:
                    print()  # 最终回复换行
            elif etype == "error":
                print(f"\n{color}[error] {ev.content}{RESET}")

    print("\n再见！")


if __name__ == "__main__":
    main()
