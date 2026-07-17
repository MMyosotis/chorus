#!/usr/bin/env python3
"""E2E 意图链路：真实 LLM 跑创作场景，验证意图状态机 + 表写入 + 卡片数据。

非交互，供自动化端到端验证。跑完打印事件序列摘要 + intent_states 表内容。临时库隔离且跑完自动清理，不写 data/chorus.db。
"""

import atexit
import shutil
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
atexit.register(lambda: shutil.rmtree(_tmp, ignore_errors=True))
with patch.object(app_module, "DATA_DIR", _tmp):
    _app = app_module.create_app()

sup = _app.state.supervisor_service
sess = _app.state.session_service
isvc = _app.state.intent_state_service
run_startup(_app.state.scheduler)

DB = _tmp / "chorus.db"


def run_one(label: str, query: str) -> None:
    s = sess.create(f"E2E-{label}")
    sid = s.id
    print(f"\n{'='*70}\n[场景] {label}\n[session] {sid}\n[query] {query}\n{'-'*70}")

    counts: dict[str, int] = {}
    turn = 0
    tool_seq: list[str] = []
    text_parts: list[str] = []
    t0 = time.time()

    for ev in sup.stream(sid, query):
        counts[ev.type] = counts.get(ev.type, 0) + 1
        if ev.type == "message_start":
            turn += 1
            print(f"  [turn {turn}] message_start")
        elif ev.type == "tool_call":
            tool_seq.append(ev.name)
            args_short = str(ev.arguments)
            if len(args_short) > 120:
                args_short = args_short[:120] + "…"
            print(f"    tool_call: {ev.name}({args_short})")
        elif ev.type == "tool_result":
            dur = getattr(ev, "duration_ms", "?")
            print(f"    tool_result: {ev.name} ({dur}ms)")
        elif ev.type == "intent_state":
            st = ev.state
            print(f"    intent_state: status={st.get('intent_status')} "
                  f"goal={st.get('goal','')[:40]!r} "
                  f"known={list(st.get('known_slots',{}).keys())} "
                  f"missing={st.get('missing_slots')} "
                  f"next_action={st.get('next_action')}")
        elif ev.type == "token":
            text_parts.append(ev.content)
        elif ev.type == "task_plan_created":
            tasks = ", ".join(f"{t['agent_type']}#{t['seq']}" for t in ev.tasks)
            print(f"    task_plan_created: pipeline={ev.pipeline_id} [{tasks}]")
        elif ev.type == "done":
            print(f"  [done] turn 结束")
        elif ev.type == "error":
            print(f"  [error] {ev.content}")

    elapsed = time.time() - t0
    full = "".join(text_parts)
    print(f"\n[耗时] {elapsed:.1f}s")
    print(f"[事件计数] {counts}")
    print(f"[message_start 轮数] {turn}  (>=2 说明多轮 ReAct 循环)")
    print(f"[工具调用序列] {tool_seq}")
    print(f"[正文] {full[:200]!r}{'…' if len(full)>200 else ''}")

    # 查表
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE name='intent_states'").fetchone()
    print(f"\n[intent_states DDL]\n{ddl[0] if ddl else 'TABLE NOT FOUND'}")
    row = conn.execute("SELECT * FROM intent_states WHERE session_id=?", (sid,)).fetchone()
    if row:
        cols = row.keys()
        print(f"[表行] 列数={len(cols)} 列={list(cols)}")
        print(f"  intent_status={row['intent_status']} version={row['version']}")
        print(f"  goal={row['goal'][:60]!r}")
        print(f"  known_slots={row['known_slots']}")
        print(f"  missing_slots={row['missing_slots']}")
    else:
        print("[表行] 无 (update_intent_state 未被调用)")

    # public_dict 结构校验
    state = isvc.get(sid)
    pd = state.public_dict()
    expected = {"session_id", "intent_status", "goal", "known_slots",
                "missing_slots", "confirmation_summary", "version",
                "updated_at", "next_action"}
    actual = set(pd.keys())
    print(f"\n[public_dict keys] {sorted(actual)}")
    missing = expected - actual
    extra = actual - expected
    if missing:
        print(f"  [FAIL] 缺字段: {missing}")
    if extra:
        print(f"  [FAIL] 多字段(应为空): {extra}")
    if not missing and not extra:
        print(f"  [OK] 字段集合正好 = 期望(8 存储 + 1 派生 next_action)")
    # 验证 next_action 是派生的,不在存储里
    if row and "next_action" in cols:
        print(f"  [FAIL] next_action 不该在表里")
    elif row:
        print(f"  [OK] next_action 不在表里(派生字段),public_dict 里 = {pd.get('next_action')!r}")
    conn.close()


# 场景1: 闲聊 —— 不触发意图识别，单轮 done
run_one("闲聊", "你好呀,你能帮我做什么?")

# 场景2: 创作请求 —— 意图捕获 + 搜索补信息 + 追问缺失槽位
run_one("创作", "帮我做一篇图文,主题是2026年春节档电影票房预测")

# 场景3: 信息明确的创作请求 —— 槽位更全，可能直接确认
run_one("明确创作", "帮我写一篇小红书风格的图文笔记，主题是2026年春节档电影推荐，配3张图")

print("\n" + "=" * 70)
print("E2E 完成")
