"""日志：分级日志的薄封装与上下文格式化。

围绕「日志」单一概念的基础设施：配置 root logger、提供按层命名的取 logger 入口、
把 agent 上下文映射成日志字段、清理过期日志文件。标准库实现，不引第三方。
"""

from __future__ import annotations

import logging
import os
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

_DEFAULT_FORMAT = (
    "%(asctime)s %(levelname)-5s %(name)s "
    "session=%(session_id)s task=%(task_id)s src=%(source)s step=%(step)s | %(message)s"
)

_UNSET = object()


class ContextFormatter(logging.Formatter):
    """带 agent 上下文字段的格式化器，缺失字段填 -。"""

    def __init__(self, fmt: str = _DEFAULT_FORMAT, datefmt: str = "%Y-%m-%d %H:%M:%S") -> None:
        super().__init__(fmt=fmt, datefmt=datefmt)

    def format(self, record: logging.LogRecord) -> str:
        for key in ("session_id", "task_id", "source", "step"):
            record.__dict__.setdefault(key, "-")
        return super().format(record)


def ctx_fields(ctx: Any) -> dict[str, Any]:
    """从 agent 上下文提取日志字段，供 extra 注入。无 ctx 返回空字典。"""
    if ctx is None:
        return {}
    return {
        "session_id": getattr(ctx, "session_id", "-") or "-",
        "task_id": getattr(ctx, "task_id", None) or "-",
        "source": getattr(ctx, "source", "-") or "-",
        "step": getattr(ctx, "step", "-"),
    }


def get_logger(name: str) -> logging.Logger:
    """按层命名取 logger，名字自动加 chorus 前缀。"""
    if not name.startswith("chorus"):
        name = f"chorus.{name}"
    return logging.getLogger(name)


def setup_logging(
        *,
        level: str = "INFO",
        log_dir: Path,
        max_bytes: int = 5_000_000,
        backup_count: int = 5,
) -> None:
    """配置 root logger：文件滚动 + stderr 双通道，幂等。"""
    log_dir.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    _reset_handlers(root)
    root.setLevel(level.upper())

    # 第三方 HTTP 客户端库的 INFO 太吵（每次模型调用一条），压到 WARNING 让业务日志突出
    for noisy in ("httpx", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    formatter = ContextFormatter()
    file_handler = RotatingFileHandler(
        log_dir / "chorus.log", maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    root.addHandler(stream_handler)


def _reset_handlers(root: logging.Logger) -> None:
    """幂等：清掉旧 handler 避免重复装配后双份输出。"""
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()


def cleanup_old_logs(log_dir: Path, retention_days: int) -> int:
    """删除超保留天数的旧日志文件，不动活跃文件。返回删除数。"""
    if retention_days <= 0:
        return 0
    cutoff = time.time() - retention_days * 86400
    removed = 0
    for entry in log_dir.glob("*.log*"):
        if entry.name == "chorus.log":
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                entry.unlink()
                removed += 1
        except OSError:
            continue
    return removed
