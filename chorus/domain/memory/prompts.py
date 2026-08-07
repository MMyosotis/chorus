"""创作者记忆旁路 LLM 的 prompt 构造与响应解析。"""
from __future__ import annotations

import json
import time
from typing import Any

from chorus.domain.memory.models import CreatorMemory, MemoryDigest
from chorus.domain.message import Message


def _history_to_text(history: list[Message]) -> str:
    """把消息序列压成可读文本，工具调用与结果内联标注。"""
    return "\n".join(msg.to_history_line() for msg in history)


def build_recall_prompt(digest: MemoryDigest, task_hint: str) -> str:
    """目录 + 任务描述，要求返回最相关 5 条标识。"""
    lines: list[str] = []
    for entry in digest.entries:
        platform = "/".join(entry.platform) if entry.platform else "通用"
        mark = "已验证" if entry.kind == "performance" else "参考"
        lines.append(f"- {entry.id} [{platform}] [{mark}] {entry.description}")
    catalog = "\n".join(lines) if lines else "（暂无记忆）"
    return (
        "你是创作者记忆召回助手。以下是与当前任务可能相关的创作者记忆目录：\n\n"
        f"{catalog}\n\n"
        f"当前任务：{task_hint}\n\n"
        "请从中选出最相关的 5 条记忆，返回它们的 id 组成的 JSON 字符串数组，"
        "格式如 [\"id1\", \"id2\"]。performance 类（已验证）优先纳入。仅返回 JSON，不要其他文字。"
    )


def build_extract_prompt(history: list[Message], existing: list[CreatorMemory]) -> str:
    """对话历史 + 已有目录，要求提取新 reference 记忆，由模型判定可见角色。"""
    history_text = _history_to_text(history)
    existing_lines = [f"- {mem.description}" for mem in existing]
    existing_text = "\n".join(existing_lines) if existing_lines else "（暂无）"
    return (
        "你是创作者记忆提取助手。请从以下对话历史中提取关于这个创作者的长期记忆。\n\n"
        "## 对话历史\n\n"
        f"{history_text}\n\n"
        "## 已有记忆（避免重复）\n\n"
        f"{existing_text}\n\n"
        "## 要求\n\n"
        "1. 只提取 reference 类（参考性）记忆：身份/边界/偏好/文风/选题模式/栏目骨架等\n"
        "2. description 要写进平台/栏目/是否当前活跃等召回需要的关键上下文\n"
        "3. 返回 JSON 数组，每条包含 description, content, platform, visible_to\n"
        "4. platform 为空表示通用；visible_to 为空表示全员可见，"
        "否则填可见角色（supervisor/idea/script/image/finalize）\n"
        "5. 仅返回 JSON，不要其他文字"
    )


def build_consolidate_prompt(memories: list[CreatorMemory]) -> str:
    """全部记忆要求合并去重、删过时矛盾，并把验证过的晋升为 performance。"""
    lines: list[str] = []
    for mem in memories:
        platform = "/".join(mem.platform) if mem.platform else "通用"
        visible = ", ".join(mem.visible_to) if mem.visible_to else "全员"
        mark = "已验证" if mem.kind == "performance" else "参考"
        created = time.strftime("%Y-%m-%d %H:%M", time.localtime(mem.created_at))
        lines.append(
            f"- {mem.description}\n"
            f"  正文：{mem.content}\n"
            f"  平台：{platform} | 可见：{visible} | 类型：{mark} | 时间：{created}"
        )
    catalog = "\n".join(lines) if lines else "（暂无）"
    return (
        "你是创作者记忆整理助手。以下是当前全部创作者记忆：\n\n"
        f"{catalog}\n\n"
        "请整理这些记忆：\n"
        "1. 合并重复条目\n"
        "2. 删除过时或矛盾的条目\n"
        "3. 把已被发布作品验证、可作为长期范本的 reference 晋升为 performance；其余保持 reference\n"
        "4. 整理到 20 条以内\n"
        "5. 合并多条时取来源里最新的时间；未合并的保留原时间；created_at 原样抄回\n"
        "6. 返回整理后的 JSON 数组，每条包含 description, content, platform, visible_to, kind, created_at\n"
        "7. kind 只能是 \"performance\" 或 \"reference\"；created_at 格式 YYYY-MM-DD HH:MM；仅返回 JSON，不要其他文字"
    )


def parse_json_array(raw: str) -> list[Any]:
    """从响应文本提取 JSON 数组，容忍 markdown 代码块包裹；失败抛 ValueError。"""
    start = raw.find("[")
    end = raw.rfind("]")
    if not (0 <= start <= end):
        raise ValueError("响应无 JSON 数组括号")
    return json.loads(raw[start : end + 1])
