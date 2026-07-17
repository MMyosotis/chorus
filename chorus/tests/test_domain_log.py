"""日志体系 smoke：配置/格式化/上下文字段/过期清理，吞异常处留栈契约。

不追求全埋点覆盖，只锚定 setup_logging 落盘格式与吞异常处改 logger.exception 后栈不丢。
"""

from __future__ import annotations

import io
import logging
import tempfile
import types
from pathlib import Path

from chorus.domain.log import (
    ContextFormatter,
    cleanup_old_logs,
    ctx_fields,
    get_logger,
    setup_logging,
)


def _ctx(session="s1", task="t1", source="supervisor", step=3):
    return types.SimpleNamespace(
        session_id=session, task_id=task, source=source, step=step,
    )


def test_ctx_fields_extracts_context():
    fields = ctx_fields(_ctx())
    assert fields == {"session_id": "s1", "task_id": "t1", "source": "supervisor", "step": 3}


def test_ctx_fields_none_returns_empty():
    assert ctx_fields(None) == {}


def test_ctx_fields_missing_task_id_fills_dash():
    fields = ctx_fields(types.SimpleNamespace(session_id="s1", task_id=None, source="supervisor", step=0))
    assert fields["task_id"] == "-"


def test_get_logger_prepends_chorus():
    assert get_logger("loop").name == "chorus.loop"
    assert get_logger("chorus.hook").name == "chorus.hook"


def test_setup_logging_writes_file_with_context_fields():
    log_dir = Path(tempfile.mkdtemp())
    try:
        setup_logging(level="INFO", log_dir=log_dir, max_bytes=100000, backup_count=1)
        logger = get_logger("loop")
        logger.info("dispatch task", extra=ctx_fields(_ctx()))
        for handler in logging.getLogger().handlers:
            handler.flush()
        content = (log_dir / "chorus.log").read_text(encoding="utf-8")
        assert "dispatch task" in content
        assert "session=s1" in content
        assert "task=t1" in content
        assert "src=supervisor" in content
        assert "step=3" in content
        assert "chorus.loop" in content
    finally:
        for handler in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(handler)
            handler.close()


def test_setup_logging_is_idempotent_no_duplicate_handlers():
    log_dir = Path(tempfile.mkdtemp())
    try:
        setup_logging(level="INFO", log_dir=log_dir)
        setup_logging(level="INFO", log_dir=log_dir)
        assert len(logging.getLogger().handlers) == 2  # 文件 + stderr 各一，不重复
    finally:
        for handler in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(handler)
            handler.close()


def test_formatter_fills_dash_for_missing_fields():
    fmt = ContextFormatter()
    record = logging.LogRecord(
        name="chorus.x", level=logging.INFO, pathname=__file__, lineno=1,
        msg="bare log", args=None, exc_info=None,
    )
    out = fmt.format(record)
    assert "session=-" in out
    assert "task=-" in out
    assert "bare log" in out


def test_logger_exception_captures_traceback():
    """吞异常处改 logger.exception 后，traceback 必须落盘。"""
    log_dir = Path(tempfile.mkdtemp())
    try:
        setup_logging(level="ERROR", log_dir=log_dir, max_bytes=100000, backup_count=1)
        logger = get_logger("loop")
        try:
            raise ValueError("模拟崩溃")
        except ValueError:
            logger.exception("agent loop failed", extra=ctx_fields(_ctx()))
        for handler in logging.getLogger().handlers:
            handler.flush()
        content = (log_dir / "chorus.log").read_text(encoding="utf-8")
        assert "ValueError" in content
        assert "模拟崩溃" in content
        assert "Traceback" in content
    finally:
        for handler in logging.getLogger().handlers[:]:
            logging.getLogger().removeHandler(handler)
            handler.close()


def test_cleanup_old_logs_removes_expired_keeps_active():
    import os
    import time as _time
    log_dir = Path(tempfile.mkdtemp())
    old = log_dir / "chorus.log.1"
    old.write_text("旧", encoding="utf-8")
    active = log_dir / "chorus.log"
    active.write_text("活跃", encoding="utf-8")
    # 把旧文件 mtime 改到 10 天前
    old_ts = _time.time() - 10 * 86400
    os.utime(old, (old_ts, old_ts))
    removed = cleanup_old_logs(log_dir, retention_days=7)
    assert removed == 1
    assert not old.exists()
    assert active.exists()


def test_cleanup_zero_retention_does_nothing():
    log_dir = Path(tempfile.mkdtemp())
    (log_dir / "chorus.log.1").write_text("x", encoding="utf-8")
    assert cleanup_old_logs(log_dir, retention_days=0) == 0


def main():
    test_ctx_fields_extracts_context()
    test_ctx_fields_none_returns_empty()
    test_ctx_fields_missing_task_id_fills_dash()
    test_get_logger_prepends_chorus()
    test_setup_logging_writes_file_with_context_fields()
    test_setup_logging_is_idempotent_no_duplicate_handlers()
    test_formatter_fills_dash_for_missing_fields()
    test_logger_exception_captures_traceback()
    test_cleanup_old_logs_removes_expired_keeps_active()
    test_cleanup_zero_retention_does_nothing()
    print("test_domain_log 全部通过")


if __name__ == "__main__":
    main()
