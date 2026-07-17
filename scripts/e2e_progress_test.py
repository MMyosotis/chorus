#!/usr/bin/env python3
"""E2E 进度与旁白：真实 LLM 跑全四角色流水线，验证流式进度写入、入口旁白与 markdown 协议产物。

直接种子化四步流水线（建图链路已由 e2e_intent_test 覆盖，本轮聚焦 subagent 路径），
真实 scheduler 派发 + 真实 LLM 子 agent，逐角色程序化确认解锁，每步校验进度快照与产物落库。
临时库隔离且跑完自动清理，不写 data/chorus.db。
"""

import atexit
import json
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
from chorus.domain.task import CreationIntent, StepSpec
from chorus.domain.task.profiles import AGENT_PROFILES

_tmp = Path(tempfile.mkdtemp())
atexit.register(lambda: shutil.rmtree(_tmp, ignore_errors=True))
with patch.object(app_module, "DATA_DIR", _tmp):
    _app = app_module.create_app()

sess = _app.state.session_service
tsk = _app.state.task_service
task_repo = tsk._task_repo
content_repo = tsk._content_repo
run_startup(_app.state.scheduler)

DB = _tmp / "chorus.db"

EXPECT_LABEL = {agent_type: AGENT_PROFILES[agent_type].composing_label
                for agent_type in AGENT_PROFILES}
STEPS = [
    ("idea", "awaiting_confirm", 0),
    ("script", "awaiting_confirm", None),
    ("image", "awaiting_confirm", None),
    ("finalize", "finished", None),
]


def _conn():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def task_of(session_id, pipeline_id, agent_type):
    """查某角色任务的标识与当前态。"""
    row = _conn().execute(
        "SELECT id, status FROM tasks WHERE session_id=? AND pipeline_id=? AND agent_type=?",
        (session_id, pipeline_id, agent_type),
    ).fetchone()
    return (row["id"], row["status"]) if row else (None, None)


def wait_for(session_id, pipeline_id, agent_type, target, timeout=180):
    """轮询至目标态或失败态，超时返回最后态。"""
    deadline = time.time() + timeout
    last = (None, None)
    while time.time() < deadline:
        last = task_of(session_id, pipeline_id, agent_type)
        if last[1] == target or last[1] in ("failed", "cancelled"):
            return last
        time.sleep(1.5)
    return last


def progress_of(task_id):
    row = _conn().execute(
        "SELECT * FROM task_progress WHERE task_id=?", (task_id,)).fetchone()
    return dict(row) if row else None


def artifacts_of(task_id):
    row = _conn().execute(
        "SELECT artifacts, narrative FROM task_artifacts WHERE task_id=?",
        (task_id,)).fetchone()
    return dict(row) if row else None


def _mark(verdict):
    return {"OK": "✓", "FAIL": "✗", "WARN": "~"}[verdict]


def check_role(session_id, pipeline_id, agent_type, target):
    """单角色校验：等到达 -> 验进度快照 -> 验产物落库，返回是否通过。"""
    label = EXPECT_LABEL[agent_type]
    print(f"\n{'=' * 60}\n[{agent_type}] 等待到达 {target} ...")
    task_id, status = wait_for(session_id, pipeline_id, agent_type, target)
    print(f"  task_id={task_id} status={status}")
    if status != target:
        print(f"  [✗] 未到达 {target}（实际 {status}），中止后续")
        return False, task_id

    prog = progress_of(task_id)
    art = artifacts_of(task_id)
    verdicts = []

    if prog is None:
        verdicts.append(("进度行", "FAIL", "无 task_progress 行"))
    else:
        print(f"  进度: aside={prog['aside']!r} chars={prog['composing_chars']} "
              f"units={prog['composing_units']} label={prog['composing_label']!r} "
              f"signal={prog['last_signal']!r}")
        verdicts.append(("composing_label", "OK" if prog["composing_label"] == label else "FAIL",
                         f"期望 {label!r}"))
        verdicts.append(("composing_chars>0", "OK" if prog["composing_chars"] > 0 else "WARN",
                         f"实际 {prog['composing_chars']}"))
        verdicts.append(("composing_units>=1", "OK" if prog["composing_units"] >= 1 else "WARN",
                         f"实际 {prog['composing_units']}"))
        verdicts.append(("aside 非空", "OK" if prog["aside"] else "WARN",
                         "fail-open 可能空"))

    if not art or not art.get("artifacts"):
        verdicts.append(("产物 artifacts", "FAIL", "无产物，markdown 协议未往返"))
    else:
        print(f"  产物: artifacts={art['artifacts'][:90]}…")
        verdicts.append(("产物 artifacts", "OK", "markdown 协议往返成功"))
        verdicts.append(("产物 narrative", "OK" if art.get("narrative") else "FAIL",
                         "" if art.get("narrative") else "缺话术注释"))

    # 选题额外交叉校验：流式计数与解析出的候选数应吻合
    if agent_type == "idea" and art and art.get("artifacts") and prog:
        try:
            candidates = json.loads(art["artifacts"]).get("candidates", [])
            verdicts.append(("units≈候选数", "OK" if prog["composing_units"] == len(candidates) else "WARN",
                             f"units={prog['composing_units']} 候选={len(candidates)}"))
        except Exception:
            pass

    for name, verdict, note in verdicts:
        line = f"  [{_mark(verdict)}] {name}"
        if note:
            line += f"  ({note})"
        print(line)

    failed = [v for _, v, _ in verdicts if v == "FAIL"]
    return (not failed), task_id


s = sess.create("E2E-进度旁白")
sid = s.id
print(f"[session] {sid}")

intent = CreationIntent(
    topic="2026春节档电影推荐",
    style="小红书种草",
    image_count=3,
)
spec = [
    StepSpec(agent_type="idea", deps=[], focus="围绕2026春节档影片，给出3个图文选题候选，含切入角度与理由"),
    StepSpec(agent_type="script", deps=[0], focus="依选中的选题撰写小红书风格图文正文，拆成有序段落"),
    StepSpec(agent_type="image", deps=[1], focus="为正文生成3张配图，给每张图配图注"),
    StepSpec(agent_type="finalize", deps=[2], focus="装配选题/文案/配图为完整 PostCard 成品"),
]
pairs = intent.expand_to_tasks(spec, sid, time.time())
for task, content in pairs:
    task_repo.insert(task)
    content_repo.insert(content)
pipeline_id = pairs[0][0].pipeline_id
order = ", ".join(f"{task.agent_type}#{i}" for i, (task, _) in enumerate(pairs, 1))
print(f"[种子化] pipeline={pipeline_id} [{order}]")

all_ok = True
for agent_type, target, selected in STEPS:
    ok, task_id = check_role(sid, pipeline_id, agent_type, target)
    if not ok:
        all_ok = False
        break
    if agent_type != "finalize":
        print(f"  -> 确认 {agent_type}(selected={selected}) 解锁下游")
        tsk.confirm(task_id, selected)

print(f"\n{'=' * 60}\nE2E 结论: {'全部通过 ✓' if all_ok else '存在失败 ✗'}")
print(f"[session] {sid}")
