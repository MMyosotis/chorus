"""SessionViewService 装配 smoke：真 repo 链取数喂领域装配，产出一屏渲染结构。"""
from __future__ import annotations

from chorus.domain.intent import IntentSnapshot
from chorus.domain.message import AssistantMessage
from chorus.domain.option import OptionAnswer, OptionItem, OptionQuestion
from chorus.domain.task import Task, TaskContent
from chorus.repo.engine import build_engine
from chorus.repo.intent_confirmation import IntentConfirmationRepository
from chorus.repo.intent_state import IntentStateRepository
from chorus.repo.message import MessageRepository
from chorus.repo.option import OptionPromptRepository
from chorus.repo.provider_message import ProviderMessageRepository
from chorus.repo.session import SessionRepository
from chorus.repo.task import TaskRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.repo.task_content import TaskContentRepository
from chorus.repo.task_progress import TaskProgressRepository
from chorus.repo.trace import TraceRepository
from chorus.services.intent_state import IntentStateService
from chorus.services.message import MessageService
from chorus.services.option import OptionPromptService
from chorus.services.session import SessionService
from chorus.services.session_view import SessionViewService
from chorus.services.task import TaskService
from chorus.services.trace import TraceService
from chorus.tests._helpers import build_compact_service, fresh_engine, seed_session, stub_memory_service


def _service(session_id: str = "s1"):
    engine = fresh_engine()
    seed_session(engine, session_id)
    session_svc = SessionService(SessionRepository(engine))
    message_svc = MessageService(
        MessageRepository(engine), ProviderMessageRepository(engine),
        TraceService(TraceRepository(engine)), build_compact_service(engine),
    )
    intent_svc = IntentStateService(
        IntentStateRepository(engine), IntentConfirmationRepository(engine), session_svc,
    )
    option_svc = OptionPromptService(OptionPromptRepository(engine), session_svc)
    task_repo = TaskRepository(engine)
    task_svc = TaskService(
        task_repo, TaskArtifactsRepository(engine),
        TaskProgressRepository(engine), TaskContentRepository(engine), session_svc,
        memory_service=stub_memory_service(),
    )
    return SessionViewService(message_svc, task_svc, intent_svc, option_svc), message_svc, intent_svc, option_svc, task_repo


def test_empty_session_view():
    """空会话给空对话结构，阶段自由对话，意图状态是占位。"""
    svc, *_ = _service()
    view = svc.collect("s1")
    assert view["bubbles"] == []
    assert view["stage"] == "自由对话"
    assert view["graph"]["tasks"] == []
    assert view["intent_state"]["session_id"] == "s1"
    assert view["open_confirmation"] is None
    assert view["open_option_prompt"] is None


def test_consecutive_assistant_messages_merge():
    """连续助手消息合并成单气泡，正文按空行衔接。"""
    svc, message, *_ = _service()
    message.append_user_message("s1", "写一篇夜骑笔记")
    message.append_assistant_message(AssistantMessage(id="m2", session_id="s1", created_at=0.0, content="第一段"))
    message.append_assistant_message(AssistantMessage(id="m3", session_id="s1", created_at=0.0, content="第二段"))
    bubbles = svc.collect("s1")["bubbles"]
    assert len(bubbles) == 2
    assert bubbles[0]["role"] == "user"
    assert bubbles[1]["content"] == "第一段\n\n第二段"
    assert bubbles[1]["message_ids"] == ["m2", "m3"]


def test_open_gate_records_and_awaiting_task():
    """打开的意图确认与选项单进信箱字段，待确认任务投影成审核卡且不折回看。"""
    svc, message, intent, option, task_repo = _service()
    message.append_user_message("s1", "写一篇")
    message.append_assistant_message(AssistantMessage(id="m2", session_id="s1", created_at=0.0, content="请确认方向。"))
    intent.open_confirmation("s1", IntentSnapshot(
        topic="夜骑", platform="小红书", format="图文笔记", style="轻松", image_count=3,
    ), message_id="m2")
    option.create("s1", [OptionQuestion(question="选平台", options=[
        OptionItem(signal="1", label="小红书", description="图文种草"),
        OptionItem(signal="2", label="公众号", description="长文阅读"),
        OptionItem(signal="3", label="微博", description="热点讨论"),
    ])], message_id="m2")
    task_repo.insert(Task(
        id="t1", session_id="s1", pipeline_id="p1", agent_type="idea",
        status="awaiting_confirm", dependencies=[], created_at=0.0, updated_at=0.0,
        message_id="m2",
    ))
    view = svc.collect("s1")
    assert view["open_confirmation"]["message_id"] == "m2"
    assert view["open_option_prompt"]["message_id"] == "m2"
    bubbles = view["bubbles"]
    assert bubbles[1]["kind"] == "assistant"
    assert bubbles[1]["recaps"] == []
    assert bubbles[2]["kind"] == "hil"
    assert bubbles[2]["task"]["id"] == "t1"


def test_answered_option_prompt_folds_recap():
    """已作答的选项单折进锚点气泡作回看。"""
    svc, message, intent, option, _task_repo = _service()
    message.append_user_message("s1", "写一篇")
    message.append_assistant_message(AssistantMessage(id="m2", session_id="s1", created_at=0.0, content="请选择平台。"))
    option.create("s1", [OptionQuestion(question="选平台", options=[
        OptionItem(signal="1", label="小红书", description="图文种草"),
        OptionItem(signal="2", label="公众号", description="长文阅读"),
        OptionItem(signal="3", label="微博", description="热点讨论"),
    ])], message_id="m2")
    option.mark_answered("s1", [OptionAnswer(signal="1", label="小红书")])
    bubbles = svc.collect("s1")["bubbles"]
    assert bubbles[1]["recaps"][0]["id"].startswith("option:")
    assert bubbles[1]["recaps"][0]["option_prompt"]["answers"][0]["label"] == "小红书"


def main():
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"[{name}] 通过")
    print("\n全部用例通过")


if __name__ == "__main__":
    main()
