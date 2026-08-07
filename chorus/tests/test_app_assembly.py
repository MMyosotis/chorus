"""create_app 装配冒烟：临时库上完成全链路装配，锚定 service/repo/tool 签名一致。

单测各自直接构造 service 不经 create_app，装配错（如参数多塞）会漏网；本用例补这条安全网。
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import chorus.app as app_module


def test_create_app_assembles_all_services():
    """create_app 在临时库上装配成功，关键 service 挂到 app.state。"""
    tmp = Path(tempfile.mkdtemp())
    with patch.object(app_module, "DATA_DIR", tmp):
        app = app_module.create_app()
    for attr in ("session_service", "message_service", "task_service",
                 "supervisor_service", "intent_state_service", "scheduler",
                 "memory_service"):
        assert getattr(app.state, attr) is not None, f"app.state.{attr} 未装配"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
