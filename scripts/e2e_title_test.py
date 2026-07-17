#!/usr/bin/env python3
"""E2E 标题生成：真实 LLM 跑一轮纯对话，验证 title_update 事件与入库。

非交互，供自动化验证。跑完打印事件序列与会话标题字段。临时库隔离，不写 data/chorus.db。
"""
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chorus.app as app_module
from chorus.startup import run_startup

_tmp = Path(tempfile.mkdtemp())
with patch.object(app_module, "DATA_DIR", _tmp):
    _app = app_module.create_app()

sup = _app.state.supervisor_service
sess = _app.state.session_service
run_startup(_app.state.scheduler)

DB = _tmp / "chorus.db"

query = "用一句话告诉我，小红书爆款文案开头怎么写最抓人？"

s = sess.create("E2E-标题验证")
sid = s.id
print(f"[session] {sid}")
print(f"[query] {query}")
print("-" * 60)

events = []
title_from_event = None
done_seen = False
t0 = time.time()

for ev in sup.stream(sid, query):
    events.append(ev.type)
    if ev.type == "title_update":
        title_from_event = ev.title
        print(f"  [title_update] {ev.title!r}")
    elif ev.type == "done":
        done_seen = True
        print(f"  [done] @ {time.time()-t0:.2f}s")
    elif ev.type == "token":
        print(ev.content, end="", flush=True)
    elif ev.type == "error":
        print(f"\n  [error] {ev.content}")

print()
print("=" * 60)
print(f"[事件序列] {events}")
print(f"[done 出现] {done_seen}")
print(f"[title_update 出现] {title_from_event is not None}")

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT title, title_generated FROM sessions WHERE id=?", (sid,)).fetchone()
print(f"[db title] {row['title']!r}")
print(f"[db title_generated] {row['title_generated']}")
conn.close()

ok = title_from_event is not None and row["title_generated"] == 1
print()
print(f"[临时库] {DB}  (测试数据留库待清理)")
print(">>> 通过" if ok else ">>> 失败：标题未生成")
sys.exit(0 if ok else 1)
