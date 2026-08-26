"""创作者记忆编排服务：摘要目录、召回、提取、整理与人工确认三钩点。"""
from __future__ import annotations

from chorus.domain.log import get_logger
from chorus.domain.memory.llm import MemoryLLMService
from chorus.domain.memory.models import CreatorMemory, Kind, MemoryDigest, MemoryDigestEntry, MemoryDraft, MemoryRecall, draft_to_memory
from chorus.domain.memory.predicates import memories_to_digest_entries
from chorus.repo.creator_memory import CreatorMemoryRepository
from chorus.repo.message import MessageRepository
from chorus.repo.task_artifacts import TaskArtifactsRepository
from chorus.services.settings import SettingsService

_logger = get_logger("service.memory")
_CONSOLIDATE_THRESHOLD = 30
_EXTRACT_WINDOW = 10


class MemoryService:
    """取数据 -> 调领域/LLM -> 存数据，记忆开关关闭时全部短路。"""

    def __init__(
        self,
        memory_repo: CreatorMemoryRepository,
        llm_service: MemoryLLMService,
        settings_service: SettingsService,
        message_repo: MessageRepository,
        task_artifacts_repo: TaskArtifactsRepository,
    ):
        self._repo = memory_repo
        self._llm = llm_service
        self._settings = settings_service
        self._message_repo = message_repo
        self._artifacts_repo = task_artifacts_repo

    def recall_for(self, agent_type: str, task_hint: str) -> MemoryRecall:
        """召回一次:摘要进系统段、命中条目进用户回合,开关关闭全短路。"""
        if not self._settings.get_memory_enabled():
            return MemoryRecall()
        digest = MemoryDigest(entries=self._visible_entries(agent_type))
        try:
            ids = self._llm.select(digest, task_hint)
        except Exception:
            _logger.warning("memory recall failed, skip")
            return MemoryRecall(digest=digest)
        items = self._repo.get_many(ids)
        _logger.debug("memory recall", extra={"agent": agent_type, "digest": len(digest.entries), "hits": len(items)})
        return MemoryRecall(digest=digest, items=items)

    def extract(self, session_id: str) -> None:
        if not self._settings.get_memory_enabled():
            return
        history = self._message_repo.list_by_session(session_id)[-_EXTRACT_WINDOW:]
        existing = self._repo.list_all()
        try:
            drafts = self._llm.extract(history, existing)
        except Exception:
            _logger.warning("memory extract failed, skip")
            drafts = []
        for draft in drafts:
            self._store_draft(draft)
        _logger.debug("memory extract", extra={"session": session_id, "drafts": len(drafts)})
        self.consolidate()

    def consolidate(self) -> None:
        all_memories = self._repo.list_all()
        if len(all_memories) < _CONSOLIDATE_THRESHOLD:
            _logger.debug("memory consolidate skip, below threshold", extra={"count": len(all_memories)})
            return
        try:
            drafts = self._llm.merge(all_memories)
        except Exception:
            _logger.warning("memory consolidate failed, skip")
            return
        if not drafts:
            _logger.debug("memory consolidate empty result, skip")
            return
        memories = [draft_to_memory(draft) for draft in drafts]
        self._repo.replace_all(memories)
        _logger.info("memory consolidate", extra={"before": len(all_memories), "after": len(memories)})

    def record_selection(self, task_id: str, agent_type: str) -> None:
        if not self._settings.get_memory_enabled():
            return
        loaded = self._artifacts_repo.load(task_id)
        if not loaded or not loaded.artifacts:
            return
        candidate = loaded.artifacts.selected_candidate()
        if candidate is None:
            return
        draft = MemoryDraft(
            kind="reference",
            description=f"选题偏好：选中角度「{candidate.angle}」",
            content=f"用户在选题阶段选中角度：{candidate.angle}（标题：{candidate.title}），理由：{candidate.reason}",
            visible_to=[agent_type],
        )
        self._store_draft(draft)
        _logger.info("memory record selection", extra={"agent": agent_type, "draft": draft.description})

    def record_publication(self, task_id: str, agent_type: str) -> None:
        if not self._settings.get_memory_enabled():
            return
        loaded = self._artifacts_repo.load(task_id)
        if not loaded or not loaded.artifacts:
            return
        draft = MemoryDraft(
            kind="reference",
            description="已发布作品登记：成品已确认发布",
            content=f"用户确认发布成品，正文摘录：\n{loaded.artifacts.markdown[:500]}",
            visible_to=[agent_type],
        )
        self._store_draft(draft)
        _logger.info("memory record publication", extra={"agent": agent_type})

    def record_correction(self, task_id: str, agent_type: str, feedback: str) -> None:
        if not self._settings.get_memory_enabled():
            return
        draft = MemoryDraft(
            kind="reference",
            description=f"改稿反馈：{feedback[:30]}",
            content=f"用户对任务 {task_id} 给出改稿反馈：{feedback}",
            visible_to=[agent_type],
        )
        self._store_draft(draft)
        _logger.info("memory record correction", extra={"agent": agent_type, "draft": draft.description})

    def list_all(self) -> list[CreatorMemory]:
        """手动管理用：不受记忆开关影响，关闭时仍可查看编辑。"""
        return self._repo.list_all()

    def create_memory(
        self, description: str, content: str,
        platform: list[str], visible_to: list[str], kind: Kind = "reference",
    ) -> CreatorMemory:
        """手动新增：用户明确给出，默认参考记忆。"""
        draft = MemoryDraft(
            kind=kind,
            description=description,
            content=content,
            platform=list(platform),
            visible_to=list(visible_to),
        )
        memory = draft_to_memory(draft)
        self._repo.upsert(memory)
        return memory

    def update_memory(
        self, memory_id: str,
        description: str, content: str,
        platform: list[str], visible_to: list[str], kind: Kind,
    ) -> CreatorMemory | None:
        """全量覆盖：替换该记忆全部字段；记忆不存在则跳过。"""
        existing = self._repo.get(memory_id)
        if existing is None:
            return None
        updated = existing.model_copy(update={
            "description": description,
            "content": content,
            "platform": list(platform),
            "visible_to": list(visible_to),
            "kind": kind,
        })
        self._repo.upsert(updated)
        return updated

    def delete_memory(self, memory_id: str) -> None:
        """幂等删除：删 0 行也视为成功。"""
        self._repo.delete(memory_id)

    def _visible_entries(self, agent_type: str) -> list[MemoryDigestEntry]:
        return memories_to_digest_entries(self._repo.list_all(), agent_type)

    def _store_draft(self, draft: MemoryDraft) -> None:
        self._repo.upsert(draft_to_memory(draft))
