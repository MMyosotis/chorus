# kitty/domain/prompt/subagent.py
"""子 Agent system prompt 模板：idea/script/image/finalize 四角色。

纯字符串 + 槽位填充，不 import repos/services/hooks/tools/agents。
每个 prompt 含：角色职责 + 产出协议（分隔符切段 + JSON 段）+ 禁 emoji 指令。
"""
from __future__ import annotations

from chorus.domain.task.profiles import AGENT_PROFILES

_BASE = (
    "你是爆款图文博文创作团队的{role_name}。{role_desc}\n\n"
    "禁用任何 emoji 字符——产出话术与产物文本一律纯文本。\n\n"
    "## 产出协议\n"
    "完成创作后，在最后一轮（不再调用工具时）按以下分隔符段格式输出，段外可加少量引导语：\n\n"
    "<<<ARTIFACTS:json>>>\n{artifacts_shape}\n<<<ARTIFACTS_END>>>\n\n"
    "<<<NARRATIVE:json>>>\n"
    '{{"awaiting_line":"等用户确认时的引导语","done_line":"完成总结一句话"}}\n'
    "<<<NARRATIVE_END>>>\n\n"
    "{task_guidance}\n"
    "JSON 必须合法，不要用代码块包裹，不要在段内加注释。"
)

_SHAPES = {
    "idea": (
        '{"candidates":[{"index":0,"title":"标题","angle":"切入角度","reason":"为何能爆"},...],'
        '"selected":null}'
    ),
    "script": (
        '{"blocks":[{"kind":"heading","text":"小标题"},{"kind":"paragraph","text":"段落"},'
        '{"kind":"list","text":"要点1\\n要点2"}]}'
    ),
    "image": '{"images":[{"url":"图片url","caption":"图注"}]}',
    "postcard": (
        '{"title":"标题","cover":{"url":"封面url","caption":""},'
        '"sections":[{"kind":"paragraph","text":"..."},{"kind":"image","image":{"url":"...","caption":""}}],'
        '"tags":["#话题"],"summary":"一句话摘要"}'
    ),
}

_GUIDANCE = {
    "idea": "给出 3-5 个候选标题与切入角度。",
    "script": "把正文拆成有序 blocks（heading/paragraph/list），不要塞成单个长字符串。",
    "image": "调用 generate_image 生成配图，把返回的 url 填进 images，配图数量按意图要求。",
    "postcard": "你是唯一成品出口：装配前三步原料成整棵 PostCard。"
    "从 idea 选标题、从 script 整理 sections、从 image 选封面并散布进 sections。"
    "cover 选一张最合适的图，tags 给 2-4 个话题标签，summary 一句话。",
}


def build_subagent_system_prompt(agent_type: str) -> str:
    """按 agent_type 返回子 Agent system prompt。用 artifacts_schema 作键（finalize→postcard）。"""
    p = AGENT_PROFILES[agent_type]
    return _BASE.format(
        role_name=p.display_name,
        role_desc=p.role_desc,
        artifacts_shape=_SHAPES[p.artifacts_schema],
        task_guidance=_GUIDANCE[p.artifacts_schema],
    )
