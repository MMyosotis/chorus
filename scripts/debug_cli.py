#!/usr/bin/env python3
"""Chorus 后端调试 CLI — 直接调 SupervisorService.stream，不走 HTTP。

贴近 HTTP 路由行为：从 SettingsService 读生图模型与联网搜索开关传入 stream（对话模型
由 ChatModelProvider 内部按 settings 自取，supervisor.stream 不再接收 model 参数），
使 CLI 与浏览器表现一致。只消费 supervisor 的 SSE 流；subagent/scheduler 在后台
线程写库不连 SSE，其流水线进展 CLI 观察不到（前端靠轮询 get_graph，此处不模拟）。
"""

try:
    import readline  # noqa: F401
except ImportError:
    pass

# 自举项目根入 sys.path：脚本运行时 sys.path[0] 是 scripts/，非项目根；
# chorus 未装成 editable 包，故显式加入项目根使 import chorus.* 可用。
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chorus.app as _app  # 触发 create_app 装配（lifespan 不在 import 阶段跑）
from chorus.startup import run_startup

# CLI 不经 server，lifespan 不会触发，显式跑一次启动副作用。
# skill_loader 是 create_app 的装配局部变量、未挂 app.state，此处经 supervisor 私有
# 属性取用（务实取法；改架构应把 skill_loader 也挂 app.state，暂不为此动 app.py）。
_supervisor = _app.app.state.supervisor_service
_settings = _app.app.state.settings_service
_session = _app.app.state.session_service
run_startup(_supervisor._skill, _session, _app.app.state.scheduler)


COLORS = {
    "reasoning": "\033[90m",        # 灰（思考流）
    "token": "\033[0m",             # 默认
    "tool_call": "\033[33m",        # 黄
    "tool_result": "\033[36m",      # 青
    "task_plan_created": "\033[35m",  # 紫（建图）
    "done": "\033[32m",             # 绿
    "error": "\033[31m",            # 红
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

        for ev in _supervisor.stream(
            session_id, query,
            web_search=_settings.get_web_search(),
        ):
            _handle_event(ev)

    print("\n再见！")


if __name__ == "__main__":
    main()
