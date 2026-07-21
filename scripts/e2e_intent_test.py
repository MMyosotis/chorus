#!/usr/bin/env python3
"""E2E 意图链路：真实 LLM 跑创作场景，验证新意图状态机 + 表写入 + 卡片数据。

新契约要点（对齐 6213c62 重构）：
- IntentState 字段 = topic/platform/format/style/image_count/extra/intent_status/
  missing_slots/session_id/version/updated_at；已删 next_action/confirmation_summary/
  skill_ref/public_dict。
- update_intent_state 在 ready_to_confirm 返 Terminal 终止本轮，模型无法同轮建图；
  其它状态返 Reply 续跑。
- create_plan 有 intent_gate：未 confirmed 返 Reply 阻塞，confirmed 后 resume 才建图。

非交互，供自动化端到端验证。临时库隔离且跑完自动清理，不写 data/chorus.db。
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

# 新契约字段集：10 存储 + session_id，无 next_action/confirmation_summary/skill_ref
EXPECTED_STATE_FIELDS = {
    "topic", "platform", "format", "style", "image_count", "extra",
    "intent_status", "missing_slots", "session_id", "version", "updated_at",
}
FORBIDDEN_FIELDS = {"next_action", "confirmation_summary", "skill_ref"}


def _run_stream(sid, query):
    """跑一轮 supervisor 流，返回事件计数、工具序列、意图事件列表、正文。"""
    counts = {}
    turn = 0
    tool_seq = []
    intent_events = []
    text_parts = []
    for ev in sup.stream(sid, query):
        counts[ev.type] = counts.get(ev.type, 0) + 1
        if ev.type == "message_start":
            turn += 1
        elif ev.type == "tool_call":
            tool_seq.append(ev.name)
        elif ev.type == "intent_state":
            intent_events.append(ev.state)
        elif ev.type == "token":
            text_parts.append(ev.content)
    return counts, turn, tool_seq, intent_events, "".join(text_parts)


def _check_state_contract(state, label):
    """校验单条 IntentState 契约：字段集合 + 无禁字段。"""
    actual = set(state.keys())
    missing = EXPECTED_STATE_FIELDS - actual
    extra = actual - EXPECTED_STATE_FIELDS
    bad_forbidden = actual & FORBIDDEN_FIELDS
    ok = not missing and not extra and not bad_forbidden
    mark = "✓" if ok else "✗"
    print(f"  [{mark}] {label} 字段集合")
    if missing:
        print(f"      缺字段: {missing}")
    if extra:
        print(f"      多字段: {extra}")
    if bad_forbidden:
        print(f"      含已删字段: {bad_forbidden}")
    return ok


def _check_table_schema(sid):
    """校验 intent_states 表列契约：10 列、无 next_action/confirmation_summary。"""
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cols = [r[1] for r in conn.execute("PRAGMA table_info(intent_states)").fetchall()]
    row = conn.execute("SELECT * FROM intent_states WHERE session_id=?", (sid,)).fetchone()
    conn.close()
    expected_cols = {
        "session_id", "intent_status", "topic", "platform", "format", "style",
        "image_count", "extra", "missing_slots", "version", "updated_at",
    }
    cols_ok = set(cols) == expected_cols
    no_forbidden = not (set(cols) & FORBIDDEN_FIELDS)
    mark = "✓" if cols_ok and no_forbidden else "✗"
    print(f"  [{mark}] intent_states 表列契约 ({len(cols)} 列)")
    if not cols_ok:
        print(f"      期望 {sorted(expected_cols)}")
        print(f"      实际 {sorted(cols)}")
    if not no_forbidden:
        print(f"      表里残留已删列: {set(cols) & FORBIDDEN_FIELDS}")
    return cols_ok and no_forbidden, row


def run_one(label, query):
    """单轮场景：跑流 -> 校验意图契约 -> 校验表。"""
    s = sess.create(f"E2E-{label}")
    sid = s.id
    print(f"\n{'=' * 70}\n[场景] {label}\n[session] {sid}\n[query] {query}\n{'-' * 70}")

    counts, turn, tool_seq, intent_events, text = _run_stream(sid, query)
    print(f"[事件计数] {counts}")
    print(f"[轮数] {turn}  [工具序列] {tool_seq}")
    print(f"[正文] {text[:160]!r}{'…' if len(text) > 160 else ''}")

    all_ok = True
    if intent_events:
        last = intent_events[-1]
        print(f"[末次意图] status={last.get('intent_status')} "
              f"topic={last.get('topic', '')[:36]!r} "
              f"missing={last.get('missing_slots')} "
              f"version={last.get('version')}")
        all_ok &= _check_state_contract(last, "SSE intent_state 事件")
    else:
        print("[意图] 未发意图事件（闲聊场景允许）")

    if "update_intent_state" in tool_seq:
        schema_ok, row = _check_table_schema(sid)
        all_ok &= schema_ok
        if row:
            print(f"  [✓] 表行落库 version={row['version']} status={row['intent_status']}")
    return sid, all_ok, intent_events, tool_seq


def run_confirm_to_plan(sid):
    """场景 4：在 ready_to_confirm 基础上确认 -> resume -> 验证 create_plan 建图。

    验证 intent_gate：confirmed 后 create_plan 不再被阻塞，建图后 intent 转 dispatched。
    """
    print(f"\n{'=' * 70}\n[场景] 确认 -> 建图（续跑链路）\n[session] {sid}\n{'-' * 70}")
    state = isvc.get(sid)
    if state.intent_status != "ready_to_confirm":
        print(f"  [✗] 前置不是 ready_to_confirm（实际 {state.intent_status}），跳过续跑")
        return False

    isvc.patch_status(sid, "confirmed")
    print(f"  [确认] intent_status -> confirmed (version={isvc.get(sid).version})")

    counts, turn, tool_seq, intent_events, text = _run_stream_resume(sid)
    print(f"[续跑事件] {counts}")
    print(f"[续跑工具序列] {tool_seq}")

    all_ok = True
    built = "create_plan" in tool_seq
    mark = "✓" if built else "✗"
    print(f"  [{mark}] create_plan 在 confirmed 后被调用")
    all_ok &= built

    final = isvc.get(sid)
    dispatched = final.intent_status == "dispatched"
    mark = "✓" if dispatched else "✗"
    print(f"  [{mark}] 建图后 intent_status -> dispatched (实际 {final.intent_status})")
    all_ok &= dispatched

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    n = conn.execute(
        "SELECT COUNT(*) AS c FROM tasks WHERE session_id=?", (sid,)
    ).fetchone()["c"]
    conn.close()
    has_tasks = n > 0
    mark = "✓" if has_tasks else "✗"
    print(f"  [{mark}] tasks 表落库 {n} 条任务")
    all_ok &= has_tasks
    return all_ok


def _run_stream_resume(sid):
    """续跑：模拟 /intent:confirm 路由的 resume 调用。"""
    counts = {}
    turn = 0
    tool_seq = []
    intent_events = []
    text_parts = []
    for ev in sup.resume(sid, "update_intent_state",
                         "用户已同意，意图进入 confirmed，等待建图"):
        counts[ev.type] = counts.get(ev.type, 0) + 1
        if ev.type == "message_start":
            turn += 1
        elif ev.type == "tool_call":
            tool_seq.append(ev.name)
        elif ev.type == "intent_state":
            intent_events.append(ev.state)
        elif ev.type == "token":
            text_parts.append(ev.content)
    return counts, turn, tool_seq, intent_events, "".join(text_parts)


# 场景 1：闲聊 -- 不触发意图识别，单轮 done
run_one("闲聊", "你好呀,你能帮我做什么?")

# 场景 2：模糊创作 -- 意图捕获 + 追问缺失槽位（capturing/needs_clarification，Reply 续跑）
run_one("模糊创作", "帮我做一篇图文")

# 场景 3：明确创作 -- 槽位齐全，直奔 ready_to_confirm -> Terminal 终止本轮
sid3, ok3, events3, tools3 = run_one(
    "明确创作",
    "帮我写一篇网页博客风格的图文，主题是2026年春节档电影推荐，配3张图，风格轻松",
)

# 场景 4：确认 -> 建图续跑（仅当场景 3 到达 ready_to_confirm）
if any(e.get("intent_status") == "ready_to_confirm" for e in events3):
    run_confirm_to_plan(sid3)
else:
    print("\n[场景 4] 跳过：场景 3 未到达 ready_to_confirm，无法验证续跑建图")

print("\n" + "=" * 70)
print("E2E 意图链路完成")
