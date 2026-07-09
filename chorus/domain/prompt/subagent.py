"""subagent system prompt 模板：角色各自的提示词。

纯模板填充，不依赖外部层。每条含角色职责、产出格式与要求。
"""
from __future__ import annotations

from chorus.domain.task.profiles import AGENT_PROFILES

_BASE = (
    "你是爆款图文博文创作团队的{role_name}。{role_desc}\n\n"
    "禁用任何 emoji 字符--产出话术与产物文本一律纯文本。\n\n"
    "## 产出协议\n"
    "完成创作后，在最后一轮（不再调用工具时）按以下 Markdown 格式输出：\n\n"
    "先写两行注释话术（等用户确认时的引导语、完成总结一句话）：\n"
    "<!-- chorus:awaiting=等用户确认时的引导语 -->\n"
    "<!-- chorus:done=完成总结一句话 -->\n\n"
    "然后空一行，写产物正文（Markdown）：\n\n"
    "{artifacts_shape}\n\n"
    "{task_guidance}\n"
    "话术注释必须写，正文用 Markdown 标题/列表/引用组织，不要输出 JSON，不要用代码块包裹。"
)

_SHAPES = {
    "idea": (
        "### 候选标题\n- 视角：切入角度\n- 理由：为何能爆\n\n"
        "（重复三到五个 ### 候选）"
    ),
    "script": (
        "## 小标题\n\n段落正文。\n\n- 要点1\n- 要点2\n\n> 引文"
    ),
    "image": (
        "### 图 1\ncaption：图注\n\n（按意图要求重复若干张）"
    ),
    "postcard": (
        "# 博文标题\n\n## 小节\n\n段落。\n\n> 引文\n\n![](图url)\n*图注*\n\n#标签：#话题1 #话题2"
    ),
}

_GUIDANCE = {
    "idea": "给出 3-5 个候选标题与切入角度，每个用 ### 分开，配视角和理由。",
    "script": "用 Markdown 标题/段落/列表/引用组织正文，不要塞成单个长字符串。",
    "image": "调用 generate_image 生成配图，为每张写 caption，用 ### 图 N 分组。",
    "postcard": "你是唯一成品出口：从 idea 选标题、从 script 整理 sections、从 image 选封面并散布进 sections。"
    "tags 用 #标签： 行，给 2-4 个话题标签。",
}


def build_subagent_system_prompt(agent_type: str) -> str:
    """按角色返回对应的 system prompt。"""
    profile = AGENT_PROFILES[agent_type]
    return _BASE.format(
        role_name=profile.display_name,
        role_desc=profile.role_desc,
        artifacts_shape=_SHAPES[profile.artifacts_schema],
        task_guidance=_GUIDANCE[profile.artifacts_schema],
    )
