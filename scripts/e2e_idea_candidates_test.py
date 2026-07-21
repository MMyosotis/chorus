#!/usr/bin/env python3
"""E2E：真实 LLM 跑 idea 子 agent，验证选题候选标题/视角/理由均有实际内容。

直插 idea 任务由调度器真实派发，跑完读产物校验候选数量与内容。临时库隔离且跑完自动清理，不写 data/chorus.db。
"""
import atexit
import shutil
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chorus.app as app_module
from chorus.domain.intent import Intent
from chorus.domain.task import StepSpec, TaskPlan
from chorus.repo.connection import ConnectionFactory
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.startup import run_startup

_TOPIC = "2026年春节档电影票房预测"
_STYLE = "小红书图文笔记"
_TIMEOUT = 120

_tmp = Path(tempfile.mkdtemp())
atexit.register(lambda: shutil.rmtree(_tmp, ignore_errors=True))
with patch.object(app_module, "DATA_DIR", _tmp):
    _app = app_module.create_app()


def main() -> None:
    session_service = _app.state.session_service
    scheduler = _app.state.scheduler
    run_startup(scheduler)

    conn = ConnectionFactory(_tmp / "chorus.db")
    task_repo = TaskRepository(conn)
    content_repo = TaskContentRepository(conn)
    artifacts_repo = TaskArtifactsRepository(conn)

    session = session_service.create("E2E-idea-candidates")
    sid = session.id
    intent = Intent(topic=_TOPIC, style=_STYLE, image_count=3)
    # TaskPlan 要求末步是 finalize，这里加 dummy finalize 满足校验，只插入 idea
    steps = [
        StepSpec(agent_type="idea", deps=[]),
        StepSpec(agent_type="finalize", deps=[0]),
    ]
    pairs = TaskPlan(session_id=sid, intent=intent, steps=steps).expand()
    idea_task_id = pairs[0][0].id
    # 只插 idea，不插 finalize
    task, content = pairs[0]
    task_repo.insert(task)
    content_repo.insert(content)

    print(f"[session] {sid}")
    print(f"[idea task] {idea_task_id}")
    print(f"[invoke]\n{pairs[0][1].invoke_message}\n")
    print("等待调度器派发与子 agent 跑 ReAct...")

    deadline = time.time() + _TIMEOUT
    status = task_repo.get(idea_task_id).status
    while time.time() < deadline and status not in ("awaiting_confirm", "failed", "cancelled"):
        time.sleep(1)
        status = task_repo.get(idea_task_id).status

    print(f"[最终状态] {status}")
    if status != "awaiting_confirm":
        content = content_repo.load(idea_task_id)
        print(f"[FAIL] idea 未到待确认，error={content.error}")
        sys.exit(1)

    candidates = artifacts_repo.load(idea_task_id).artifacts.candidates
    print(f"\n[候选数量] {len(candidates)}")
    all_pass = len(candidates) >= 1
    for idx, cand in enumerate(candidates):
        title_ok = cand.title.strip() != "" and "候选标题" not in cand.title
        angle_ok = cand.angle.strip() != ""
        reason_ok = cand.reason.strip() != ""
        passed = title_ok and angle_ok and reason_ok
        all_pass = all_pass and passed
        mark = "OK" if passed else "FAIL"
        print(f"  [{mark}] #{idx} title={cand.title!r}")
        print(f"        angle={cand.angle!r}")
        print(f"        reason={cand.reason!r}")

    print()
    if all_pass:
        print(f"[PASS] {len(candidates)} 个候选均有实际标题/视角/理由，无占位词")
    else:
        print("[FAIL] 存在候选内容缺失或占位词未消除")
        sys.exit(1)


if __name__ == "__main__":
    main()
