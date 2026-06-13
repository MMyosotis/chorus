"""会话持久化存储：每个会话一个 JSON 文件，按 id 隔离 history / assistant_messages。"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_HEX32 = re.compile(r"^[0-9a-f]{32}$")


class ConversationStore:
    def __init__(
        self,
        data_dir: Path,
        ttl_days: int = 30,
        max_bytes: int = 1024 * 1024,
        max_count: int = 100,
    ):
        self.data_dir = Path(data_dir)
        self.ttl_days = ttl_days
        self.max_bytes = max_bytes
        self.max_count = max_count

        self.data_dir.mkdir(parents=True, exist_ok=True)

        self._global_lock = threading.Lock()
        self._conv_locks: dict[str, threading.Lock] = {}
        self._cache: dict[str, dict] = {}
        self._last_cleanup_at: float = 0.0

    # ------------------------------------------------------------------
    # 路径与基础 IO
    # ------------------------------------------------------------------
    def _path(self, conv_id: str) -> Path:
        if not _HEX32.match(conv_id):
            raise KeyError(conv_id)
        return self.data_dir / f"{conv_id}.json"

    def _atomic_write(self, conv_id: str, conv: dict) -> None:
        path = self._path(conv_id)
        tmp = path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(conv, f, ensure_ascii=False)
        os.replace(tmp, path)

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------
    def load_all(self) -> None:
        with self._global_lock:
            self._cache.clear()
            self._conv_locks.clear()
            for p in self.data_dir.glob("*.json"):
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    cid = data.get("id")
                    if not cid or not _HEX32.match(cid):
                        continue
                    self._cache[cid] = data
                    self._conv_locks[cid] = threading.Lock()
                except Exception as e:
                    logger.warning("failed to load %s: %s", p, e)
        # 启动后做一次清理
        try:
            self.cleanup(force=True)
        except Exception as e:
            logger.warning("cleanup on startup failed: %s", e)

    # ------------------------------------------------------------------
    # 查询
    # ------------------------------------------------------------------
    def list_meta(self) -> list[dict]:
        with self._global_lock:
            items = [
                {
                    "id": c["id"],
                    "title": c.get("title", "新对话"),
                    "created_at": c.get("created_at", 0),
                    "updated_at": c.get("updated_at", 0),
                }
                for c in self._cache.values()
            ]
        items.sort(key=lambda x: x["updated_at"], reverse=True)
        return items

    def get(self, conv_id: str) -> dict:
        with self._global_lock:
            conv = self._cache.get(conv_id)
            if conv is None:
                raise KeyError(conv_id)
            return conv

    def has(self, conv_id: str) -> bool:
        with self._global_lock:
            return conv_id in self._cache

    # ------------------------------------------------------------------
    # 写操作
    # ------------------------------------------------------------------
    def create(self, title: str = "新对话") -> dict:
        cid = uuid.uuid4().hex
        now = time.time()
        conv = {
            "id": cid,
            "title": title,
            "title_generated": False,
            "created_at": now,
            "updated_at": now,
            "history": [],
            "assistant_messages": {},
        }
        with self._global_lock:
            self._cache[cid] = conv
            self._conv_locks[cid] = threading.Lock()
        self._atomic_write(cid, conv)
        return {
            "id": cid,
            "title": conv["title"],
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
        }

    def delete(self, conv_id: str) -> None:
        with self._global_lock:
            if conv_id not in self._cache:
                raise KeyError(conv_id)
            self._cache.pop(conv_id, None)
            self._conv_locks.pop(conv_id, None)
        path = self._path(conv_id)
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            logger.warning("failed to remove %s: %s", path, e)

    def rename(self, conv_id: str, title: str) -> dict:
        title = (title or "").strip()
        if not title:
            raise ValueError("title 不能为空")
        if len(title) > 60:
            raise ValueError("title 长度不能超过 60")
        conv = self.get(conv_id)
        with self.get_lock(conv_id):
            conv["title"] = title
            conv["title_generated"] = True
            conv["updated_at"] = time.time()
            self._atomic_write(conv_id, conv)
        return {
            "id": conv_id,
            "title": conv["title"],
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
        }

    def set_title_if_unset(self, conv_id: str, title: str) -> bool:
        """仅在 title_generated=False 时更新；返回是否更新。"""
        title = (title or "").strip()
        if not title:
            return False
        if len(title) > 60:
            title = title[:60]
        conv = self.get(conv_id)
        with self.get_lock(conv_id):
            if conv.get("title_generated"):
                return False
            conv["title"] = title
            conv["title_generated"] = True
            conv["updated_at"] = time.time()
            self._atomic_write(conv_id, conv)
        return True

    def save(self, conv_id: str) -> None:
        conv = self.get(conv_id)
        self._atomic_write(conv_id, conv)
        # 触发节流清理
        try:
            self.cleanup()
        except Exception as e:
            logger.warning("cleanup after save failed: %s", e)

    # ------------------------------------------------------------------
    # 锁
    # ------------------------------------------------------------------
    def get_lock(self, conv_id: str) -> threading.Lock:
        with self._global_lock:
            lock = self._conv_locks.get(conv_id)
            if lock is None:
                if conv_id not in self._cache:
                    raise KeyError(conv_id)
                lock = threading.Lock()
                self._conv_locks[conv_id] = lock
            return lock

    # ------------------------------------------------------------------
    # 给前端的 view（过滤 system / tool）
    # ------------------------------------------------------------------
    def get_history_view(self, conv_id: str) -> list[dict]:
        conv = self.get(conv_id)
        history = conv.get("history", [])
        meta = conv.get("assistant_messages", {})
        result = []
        for m in history:
            if m.get("role") in ("system", "tool"):
                continue
            item = {"role": m["role"], "content": m.get("content") or ""}
            if m["role"] == "assistant":
                mid = m.get("_meta_message_id")
                am = meta.get(mid) if mid else None
                if am:
                    item["thinking"] = am.get("thinking", [])
                    item["tools"] = am.get("tools", [])
                else:
                    item["thinking"] = []
                    item["tools"] = []
            result.append(item)
        return result

    # ------------------------------------------------------------------
    # 清理
    # ------------------------------------------------------------------
    def cleanup(self, force: bool = False) -> None:
        now = time.time()
        if not force and (now - self._last_cleanup_at) < 60:
            return
        self._last_cleanup_at = now

        with self._global_lock:
            if len(self._cache) <= 1:
                return
            convs = list(self._cache.values())

        ttl_seconds = self.ttl_days * 86400 if self.ttl_days > 0 else 0
        ttl_cut = now - ttl_seconds if ttl_seconds > 0 else None

        ttl_targets: list[str] = []
        oversize_targets: list[str] = []
        for c in convs:
            cid = c["id"]
            if ttl_cut is not None and c.get("updated_at", 0) < ttl_cut:
                ttl_targets.append(cid)
                continue
            try:
                size = os.path.getsize(self._path(cid))
            except OSError:
                continue
            if size > self.max_bytes:
                oversize_targets.append(cid)

        # overflow: 在剩余的会话里按 updated_at 升序删除最旧
        already = set(ttl_targets) | set(oversize_targets)
        with self._global_lock:
            remaining = [c for c in self._cache.values() if c["id"] not in already]
        remaining.sort(key=lambda x: x.get("updated_at", 0))
        overflow_targets: list[str] = []
        excess = len(remaining) - self.max_count
        if excess > 0:
            for c in remaining[:excess]:
                overflow_targets.append(c["id"])

        ttl_done = oversize_done = overflow_done = 0
        for cid, group in (
            *((c, "ttl") for c in ttl_targets),
            *((c, "oversize") for c in oversize_targets),
            *((c, "overflow") for c in overflow_targets),
        ):
            # 保护：剩余 <=1 不再删
            with self._global_lock:
                if len(self._cache) <= 1:
                    break
                lock = self._conv_locks.get(cid)
            if lock is None:
                continue
            if not lock.acquire(blocking=False):
                continue
            try:
                self.delete(cid)
                if group == "ttl":
                    ttl_done += 1
                elif group == "oversize":
                    oversize_done += 1
                else:
                    overflow_done += 1
            except Exception as e:
                logger.warning("cleanup delete %s failed: %s", cid, e)
            finally:
                lock.release()

        total = ttl_done + oversize_done + overflow_done
        if total > 0:
            logger.info(
                "cleanup: deleted %d conversations (ttl=%d, oversize=%d, overflow=%d)",
                total,
                ttl_done,
                oversize_done,
                overflow_done,
            )
