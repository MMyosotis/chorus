#!/usr/bin/env python3
"""Chorus 后端调试 CLI：直接调 supervisor 的 SSE 流，不走 HTTP。

subagent/scheduler 不连 SSE，其流水线进展此处观察不到。
"""

try:
    import readline  # noqa: F401
except ImportError:
    pass

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chorus.app as _app
from chorus.startup import run_startup

_supervisor = _app.app.state.supervisor_service
_session = _app.app.state.session_service
run_startup(_app.app.state.scheduler)


COLORS = {
    "reasoning": "\033[90m",
    "token": "\033[0m",
    "tool_call": "\033[33m",
    "tool_result": "\033[36m",
    "task_plan_created": "\033[35m",
    "done": "\033[32m",
    "error": "\033[31m",
}
RESET = "\033[0m"


def _truncate(text: str, limit: int = 500) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"... ({len(text)} chars total)"


def _handle_event(ev) -> None:
    etype = ev.type
    color = COLORS.get(etype, "")

    if etype == "reasoning":
        print(f"{color}{ev.content}{RESET}", end="", flush=True)
    elif etype == "reasoning_done":
        print()  # 思考段结束换行，与正文分隔
    elif etype == "token":
        print(ev.content, end="", flush=True)
    elif etype == "tool_call":
        print(f"\n{color}[tool_call] {ev.name}({ev.arguments}){RESET}")
    elif etype == "tool_result":
        print(f"{color}[tool_result] {ev.name}: {_truncate(ev.content)}{RESET}")
    elif etype == "task_plan_created":
        tasks = ", ".join(f"{t['agent_type']}#{t['seq']}={t['status']}" for t in ev.tasks)
        print(f"\n{color}[task_plan_created] pipeline={ev.pipeline_id} tasks=[{tasks}]{RESET}")
    elif etype == "title_update":
        print(f"\n\033[35m[title_update] {ev.title}{RESET}")
    elif etype == "done":
        print()  # 最终回复换行
    elif etype == "error":
        print(f"\n{color}[error] {ev.content}{RESET}")


def main() -> None:
    session = _session.create("CLI 调试")
    session_id = session.id
    print("Chorus 调试 CLI（输入 q 退出，/new 新建会话）")
    print(f"当前会话: {session_id}\n")

    while True:
        try:
            query = input("\033[1;34m>>> \033[0m")
        except (EOFError, KeyboardInterrupt):
            break

        stripped = query.strip()
        if stripped.lower() in ("q", "exit"):
            break
        if stripped == "/new":
            session = _session.create("CLI 调试")
            session_id = session.id
            print(f"\033[32m已新建会话 {session_id}\033[0m\n")
            continue
        if not stripped:
            continue

        for ev in _supervisor.stream(session_id, query):
            _handle_event(ev)

    print("\n再见！")


if __name__ == "__main__":
    main()
