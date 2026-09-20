"""CreatePlanTool.run 契约：成功→Suspend + 整图落库；参数错/校验错/落库失败→Reply(correction)。

建图副作用已收进工具，成功 outcome 为 Suspend，副作用验 tasks 表落库。
"""
from __future__ import annotations

from chorus.domain.task import ACTIVE_STATUSES, CANCELLABLE_STATUSES, PostCard, Task
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.intent_confirmation import IntentConfirmationRepository
from chorus.repo.intent_state import IntentStateRepository
from chorus.repo.session import SessionRepository
from chorus.services.intent_state import IntentStateService
from chorus.services.session import SessionService
from chorus.services.task import TaskService
from chorus.tests._helpers import fresh_engine, seed_session
from chorus.tests._helpers import stub_memory_service
from chorus.tools.builtin.create_plan import CreatePlanTool
from chorus.tools.framework import Reply, Suspend, ToolContext


def _args(topic="夏日晚风", steps=None, intent_extras=None):
    if steps is None:
        steps = [
            {"agent_type": "idea", "deps": [], "focus": "选题"},
            {"agent_type": "finalize", "deps": [0], "focus": "排版"},
        ]
    intent = {"topic": topic, "style": "轻松", "image_count": 2}
    if intent_extras:
        intent.update(intent_extras)
    return {"thought": "x", "intent": intent, "steps": steps}


def _build():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = TaskRepository(engine)
    content_repo = TaskContentRepository(engine)
    art_repo = TaskArtifactsRepository(engine)
    session_service = SessionService(SessionRepository(engine))
    intent = IntentStateService(IntentStateRepository(engine), IntentConfirmationRepository(engine), session_service)
    intent.patch_status("s1", "confirmed")
    task_service = TaskService(
        repo, art_repo, TaskProgressRepository(engine), content_repo,
        session_service, stub_memory_service(),
    )
    tool = CreatePlanTool(repo, task_service, content_repo, art_repo, intent)
    ctx = ToolContext(session_id="s1", message_id="m-plan")
    return engine, repo, content_repo, art_repo, tool, ctx


def test_success_returns_terminal_and_persists_tasks():
    engine, repo, content_repo, art_repo, tool, ctx = _build()
    outcome = tool.run(_args(), ctx).outcome
    assert isinstance(outcome, Suspend)
    assert isinstance(outcome.content, str) and outcome.content  # 如实建图摘要
    assert "pipeline=" in outcome.content  # 携真实流水线标识，非写死话术
    # 整图落库：两个活跃任务，会话标识回填
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 2
    tasks = repo.find_by_session_statuses("s1", ACTIVE_STATUSES)
    assert {t.agent_type for t in tasks} == {"idea", "finalize"}
    assert all(t.session_id == "s1" for t in tasks)
    assert all(t.message_id == "m-plan" for t in tasks)
    assert all(t.created_at > 0 for t in tasks)  # 时间戳已落库
    # 内容行同落：每条任务对应一条内容
    contents = content_repo.load_many([t.id for t in tasks])
    assert set(contents.keys()) == {t.id for t in tasks}
    idea_id = next(t.id for t in tasks if t.agent_type == "idea")
    assert "夏日晚风" in contents[idea_id].invoke_message


def test_unconfirmed_intent_blocks_plan_creation():
    engine = fresh_engine()
    seed_session(engine, sid="s1")
    repo = TaskRepository(engine)
    content_repo = TaskContentRepository(engine)
    art_repo = TaskArtifactsRepository(engine)
    session_service = SessionService(SessionRepository(engine))
    intent = IntentStateService(IntentStateRepository(engine), IntentConfirmationRepository(engine), session_service)
    task_service = TaskService(
        repo, art_repo, TaskProgressRepository(engine), content_repo,
        session_service, stub_memory_service(),
    )
    tool = CreatePlanTool(repo, task_service, content_repo, art_repo, intent)
    outcome = tool.run(_args(), ToolContext(session_id="s1")).outcome
    assert isinstance(outcome, Reply)
    assert "blocked" in outcome.content
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 0


def test_missing_intent_key_returns_reply():
    _, _, _, _, tool, ctx = _build()
    outcome = tool.run({"thought": "x", "steps": []}, ctx).outcome
    assert isinstance(outcome, Reply)
    assert "create_plan" in outcome.content or "参数" in outcome.content


def test_bad_step_returns_reply_with_correction():
    """末步非 finalize → validate_steps 抛 ValidationError → Reply(correction)，不落库。"""
    _, repo, _, _, tool, ctx = _build()
    bad = _args(steps=[{"agent_type": "idea", "deps": [], "focus": "选题"}])  # 末步非 finalize
    outcome = tool.run(bad, ctx).outcome
    assert isinstance(outcome, Reply)
    assert "finalize" in outcome.content
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 0  # 校验失败不落库


def test_circular_deps_returns_reply():
    _, repo, _, _, tool, ctx = _build()
    # 不能构造真环，构造前向依赖错
    bad = _args(steps=[
        {"agent_type": "idea", "deps": [1], "focus": "x"},  # 依赖后续索引非法
        {"agent_type": "finalize", "deps": [0], "focus": "y"},
    ])
    outcome = tool.run(bad, ctx).outcome
    assert isinstance(outcome, Reply)
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 0


def _seed_product(engine, art_repo, task_id="t-final", title="夏日晚风"):
    """落一个已完成的排版任务加成品卡，供底稿校验与回执判定取材。"""
    TaskRepository(engine).insert(Task(
        id=task_id, session_id="s1", pipeline_id="p-old", agent_type="finalize",
        status="finished", dependencies=[], created_at=1.0, updated_at=1.0,
    ))
    art_repo.upsert(task_id, "finalize", PostCard(
        markdown=f"---\ntitle: {title}\n---\n\n旧稿正文",
        meta={"title": title},
    ))
    return task_id


def test_invalid_base_product_id_lists_products():
    """底稿标识指向不存在/非成品的任务 → Reply 列出可用成品供模型重填。"""
    engine, repo, content_repo, art_repo, tool, ctx = _build()
    product_id = _seed_product(engine, art_repo)
    args = _args()
    args["base_product_id"] = "nonexistent"
    outcome = tool.run(args, ctx).outcome
    assert isinstance(outcome, Reply)
    assert product_id in outcome.content
    assert "夏日晚风" in outcome.content
    assert repo.count_by_session_statuses("s1", ACTIVE_STATUSES) == 0  # 不落库


def test_valid_base_product_id_freezes_draft_into_skeleton():
    """合法底稿 → 建图成功且底稿原文冻进每个步骤的调用消息。"""
    engine, repo, content_repo, art_repo, tool, ctx = _build()
    product_id = _seed_product(engine, art_repo)
    args = _args()
    args["base_product_id"] = product_id
    args["steps"][0]["note"] = "标题保留，只换语气"
    outcome = tool.run(args, ctx).outcome
    assert isinstance(outcome, Suspend)
    tasks = repo.find_by_session_statuses("s1", ACTIVE_STATUSES)
    contents = content_repo.load_many([t.id for t in tasks])
    for content in contents.values():
        assert "旧稿正文" in content.invoke_message
        assert "<base_card>" in content.invoke_message
    idea_id = next(t.id for t in tasks if t.agent_type == "idea")
    assert "<step_note>\n标题保留，只换语气\n</step_note>" in contents[idea_id].invoke_message


def test_resolve_external_delivers_finished_product():
    """图收敛后回执：末步完成则成品全文直给，携成品标识与标题。"""
    engine, repo, content_repo, art_repo, tool, ctx = _build()
    assert isinstance(tool.run(_args(), ctx).outcome, Suspend)
    tasks = repo.find_by_session_statuses("s1", ACTIVE_STATUSES)
    finalize_id = next(t.id for t in tasks if t.agent_type == "finalize")
    repo.transition(finalize_id, "finished")
    art_repo.upsert(finalize_id, "finalize", PostCard(
        markdown="---\ntitle: 夏日晚风\n---\n\n成品正文",
        meta={"title": "夏日晚风"},
    ))
    receipt = tool.resolve_external("s1", "finish")
    assert finalize_id in receipt
    assert "夏日晚风" in receipt
    assert "成品正文" in receipt


def test_resolve_external_cancelled_pipeline_short_receipt():
    """图被放弃后回执一句话，不带成品。"""
    engine, repo, content_repo, art_repo, tool, ctx = _build()
    assert isinstance(tool.run(_args(), ctx).outcome, Suspend)
    tasks = repo.find_by_session_statuses("s1", ACTIVE_STATUSES)
    repo.cancel_pipeline(tasks[0].pipeline_id, CANCELLABLE_STATUSES)
    receipt = tool.resolve_external("s1", "finish")
    assert receipt == "创作流水线已被用户放弃，本次未交付成品"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
