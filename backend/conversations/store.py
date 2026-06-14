"""会话与 trace 持久化（SQLite）。

对外保持原 API 与内存模型不变：
- 内存里的 conv dict 仍是 {id, title, title_generated, created_at, updated_at,
  history, assistant_messages}，上层 chat / hooks / routes 不感知存储细节。
- 底层把 history 拆为「一问一答」turn 行（按 role=="user" 切分），落到 turns 表；
  trace 走 add_trace 单条 INSERT 进 traces 表。
- system 消息不持久化（每次 LoopStart hook 由 SYSTEM_PROMPT + skill 摘要重建）。
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_HEX32 = re.compile(r"^[0-9a-f]{32}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    title_generated INTEGER NOT NULL DEFAULT 0,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at DESC);

CREATE TABLE IF NOT EXISTS turns (
    conv_id         TEXT NOT NULL,
    idx             INTEGER NOT NULL,
    user_content    TEXT NOT NULL,
    assistant_json  TEXT NOT NULL,
    meta_json       TEXT NOT NULL,
    created_at      REAL NOT NULL,
    PRIMARY KEY (conv_id, idx),
    FOREIGN KEY (conv_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS traces (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    conv_id     TEXT NOT NULL,
    turn_idx    INTEGER,
    iteration   INTEGER,
    message_id  TEXT,
    phase       TEXT NOT NULL,
    ts          REAL NOT NULL,
    payload     TEXT NOT NULL,
    FOREIGN KEY (conv_id) REFERENCES conversations(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_traces_conv ON traces(conv_id, ts);
"""


def _split_turns(history: list[dict], assistant_messages: dict) -> list[dict]:
    """按 user 消息切分 history 为 turn 列表。

    每个 turn = {idx, user_content, assistant_messages: [...], meta: {...}}
    跳过 role==system；role==assistant/tool 归入当前 turn。
    若 history 在第一条 user 之前有 assistant/tool（异常），整体丢弃这些前缀。
    """
    turns: list[dict] = []
    current: Optional[dict] = None
    for m in history:
        role = m.get("role")
        if role == "system":
            continue
        if role == "user":
            if current is not None:
                turns.append(current)
            current = {
                "idx": len(turns),
                "user_content": m.get("content") or "",
                "assistant_messages": [],
                "meta": {},
            }
            continue
        if current is None:
            continue
        current["assistant_messages"].append(m)
        if role == "assistant":
            mid = m.get("_meta_message_id")
            if mid and mid in assistant_messages:
                current["meta"][mid] = assistant_messages[mid]
    if current is not None:
        turns.append(current)
    return turns


def _restore_history(turn_rows: list[tuple]) -> tuple[list[dict], dict]:
    """从 turn 行还原 history（不含 system）+ assistant_messages 字典。"""
    history: list[dict] = []
    assistant_messages: dict = {}
    for _, _, user_content, assistant_json, meta_json in turn_rows:
        history.append({"role": "user", "content": user_content})
        try:
            msgs = json.loads(assistant_json) if assistant_json else []
        except json.JSONDecodeError:
            msgs = []
        history.extend(msgs)
        try:
            meta = json.loads(meta_json) if meta_json else {}
        except json.JSONDecodeError:
            meta = {}
        assistant_messages.update(meta)
    return history, assistant_messages


class ConversationStore:
    def __init__(
        self,
        data_dir: Path,
        ttl_days: int = 30,
        max_bytes: int = 1024 * 1024,
        max_count: int = 100,
    ):
        # data_dir 历史上是 backend/data/conversations/，把 DB 放到其父目录
        # （backend/data/little-kitty.db），避免与已有 JSON 残留混在一起。
        self.data_dir = Path(data_dir)
        self.db_path = self.data_dir.parent / "little-kitty.db"
        self.ttl_days = ttl_days
        self.max_bytes = max_bytes
        self.max_count = max_count

        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._global_lock = threading.Lock()
        self._conv_locks: dict[str, threading.Lock] = {}
        self._cache: dict[str, dict] = {}
        self._last_cleanup_at: float = 0.0

        self._tls = threading.local()
        self._init_schema()

    # ------------------------------------------------------------------
    # 连接 / Schema
    # ------------------------------------------------------------------
    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._tls, "conn", None)
        if conn is None:
            conn = sqlite3.connect(self.db_path, isolation_level=None)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._tls.conn = conn
        return conn

    def _init_schema(self) -> None:
        conn = self._connect()
        conn.executescript(_SCHEMA)

    # ------------------------------------------------------------------
    # 加载
    # ------------------------------------------------------------------
    def load_all(self) -> None:
        conn = self._connect()
        with self._global_lock:
            self._cache.clear()
            self._conv_locks.clear()

            convs = conn.execute(
                "SELECT id, title, title_generated, created_at, updated_at FROM conversations"
            ).fetchall()

            turn_rows_by_conv: dict[str, list[tuple]] = {}
            for row in conn.execute(
                "SELECT conv_id, idx, user_content, assistant_json, meta_json "
                "FROM turns ORDER BY conv_id, idx"
            ):
                turn_rows_by_conv.setdefault(row[0], []).append(row)

            for cid, title, title_generated, created_at, updated_at in convs:
                if not _HEX32.match(cid or ""):
                    continue
                history, assistant_messages = _restore_history(turn_rows_by_conv.get(cid, []))
                self._cache[cid] = {
                    "id": cid,
                    "title": title,
                    "title_generated": bool(title_generated),
                    "created_at": created_at,
                    "updated_at": updated_at,
                    "history": history,
                    "assistant_messages": assistant_messages,
                }
                self._conv_locks[cid] = threading.Lock()

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
        conn = self._connect()
        conn.execute(
            "INSERT INTO conversations(id, title, title_generated, created_at, updated_at) "
            "VALUES (?, ?, 0, ?, ?)",
            (cid, title, now, now),
        )
        with self._global_lock:
            self._cache[cid] = conv
            self._conv_locks[cid] = threading.Lock()
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
        conn = self._connect()
        # CASCADE 自动清理 turns / traces
        conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,))

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
            conn = self._connect()
            conn.execute(
                "UPDATE conversations SET title=?, title_generated=1, updated_at=? WHERE id=?",
                (conv["title"], conv["updated_at"], conv_id),
            )
        return {
            "id": conv_id,
            "title": conv["title"],
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
        }

    def set_title_if_unset(self, conv_id: str, title: str) -> bool:
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
            conn = self._connect()
            conn.execute(
                "UPDATE conversations SET title=?, title_generated=1, updated_at=? WHERE id=?",
                (conv["title"], conv["updated_at"], conv_id),
            )
        return True

    def save(self, conv_id: str) -> None:
        """把内存 conv 落库：会话元信息 + turn 行全量重写。"""
        conv = self.get(conv_id)
        history = conv.get("history", [])
        assistant_messages = conv.get("assistant_messages", {})
        turns = _split_turns(history, assistant_messages)

        now = time.time()
        conn = self._connect()
        try:
            conn.execute("BEGIN")
            conn.execute(
                "UPDATE conversations SET title=?, title_generated=?, updated_at=? WHERE id=?",
                (
                    conv.get("title", "新对话"),
                    1 if conv.get("title_generated") else 0,
                    conv.get("updated_at", now),
                    conv_id,
                ),
            )
            conn.execute("DELETE FROM turns WHERE conv_id=?", (conv_id,))
            if turns:
                conn.executemany(
                    "INSERT INTO turns(conv_id, idx, user_content, assistant_json, meta_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        (
                            conv_id,
                            t["idx"],
                            t["user_content"],
                            json.dumps(t["assistant_messages"], ensure_ascii=False),
                            json.dumps(t["meta"], ensure_ascii=False),
                            now,
                        )
                        for t in turns
                    ],
                )
            conn.execute("COMMIT")
        except Exception:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
            raise

        try:
            self.cleanup()
        except Exception as e:
            logger.warning("cleanup after save failed: %s", e)

    # ------------------------------------------------------------------
    # Trace
    # ------------------------------------------------------------------
    def add_trace(
        self,
        conv_id: str,
        phase: str,
        payload: dict,
        *,
        turn_idx: Optional[int] = None,
        iteration: Optional[int] = None,
        message_id: Optional[str] = None,
        ts: Optional[float] = None,
    ) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT INTO traces(conv_id, turn_idx, iteration, message_id, phase, ts, payload) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                conv_id,
                turn_idx,
                iteration,
                message_id,
                phase,
                ts if ts is not None else time.time(),
                json.dumps(payload, ensure_ascii=False),
            ),
        )

    def list_traces(self, conv_id: str) -> list[dict]:
        if not self.has(conv_id):
            raise KeyError(conv_id)
        conn = self._connect()
        rows = conn.execute(
            "SELECT iteration, message_id, phase, ts, payload "
            "FROM traces WHERE conv_id=? ORDER BY ts ASC, id ASC",
            (conv_id,),
        ).fetchall()
        result = []
        for iteration, message_id, phase, ts, payload in rows:
            try:
                payload_obj = json.loads(payload) if payload else {}
            except json.JSONDecodeError:
                payload_obj = {}
            result.append({
                "type": "trace",
                "phase": phase,
                "iteration": iteration,
                "message_id": message_id,
                "ts": ts,
                "payload": payload_obj,
            })
        return result

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

        # 单会话字节数 = 该会话所有 turns 的 user_content + assistant_json + meta_json 长度之和
        conn = self._connect()
        size_rows = conn.execute(
            "SELECT conv_id, COALESCE(SUM("
            "  LENGTH(user_content) + LENGTH(assistant_json) + LENGTH(meta_json)"
            "), 0) FROM turns GROUP BY conv_id"
        ).fetchall()
        size_by_conv = {cid: sz for cid, sz in size_rows}

        ttl_targets: list[str] = []
        oversize_targets: list[str] = []
        for c in convs:
            cid = c["id"]
            if ttl_cut is not None and c.get("updated_at", 0) < ttl_cut:
                ttl_targets.append(cid)
                continue
            if size_by_conv.get(cid, 0) > self.max_bytes:
                oversize_targets.append(cid)

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
