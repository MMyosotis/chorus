# kitty/domain/task/profiles.py
"""AgentProfile 角色注册表：四角色单一真源（display_name/role_desc/tools 白名单/
enter_line 静态出场语/artifacts_schema/expected_sections）。

工具白名单是单一真源——PlanNode 不再独立声明 tools，subagent 按 task.agent_type 查
此表筛 schema。加角色只加一条 AgentProfile。全部文案纯文本禁 emoji。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentProfile:
    agent_type: str
    display_name: str
    role_desc: str
    tools: tuple[str, ...]                # 工具名白名单（单一真源）
    enter_line: str                       # 静态出场语（进度气泡 enter）
    artifacts_schema: str                 # 产物 schema 名（parse_output 校验分支用）
    expected_sections: tuple[str, ...]    # 产出协议期望段名


AGENT_PROFILES: dict[str, AgentProfile] = {
    "idea": AgentProfile(
        agent_type="idea",
        display_name="选题官",
        role_desc="调研热点、琢磨选题，给出多个候选标题与切入角度",
        tools=("baidu_search", "load_skill"),
        enter_line="选题官接单啦，先去翻翻最近的热点",
        artifacts_schema="idea",
        expected_sections=("artifacts", "narrative"),
    ),
    "script": AgentProfile(
        agent_type="script",
        display_name="文案官",
        role_desc="依据选题撰写图文博文正文，拆成有序块草稿",
        tools=("baidu_search", "load_skill"),
        enter_line="文案官接单啦，开始码字",
        artifacts_schema="script",
        expected_sections=("artifacts", "narrative"),
    ),
    "image": AgentProfile(
        agent_type="image",
        display_name="配图官",
        role_desc="为博文生成配图，给出图片列表与图注",
        tools=("baidu_search", "generate_image", "load_skill"),
        enter_line="配图官接单啦，准备出图",
        artifacts_schema="image",
        expected_sections=("artifacts", "narrative"),
    ),
    "finalize": AgentProfile(
        agent_type="finalize",
        display_name="汇总官",
        role_desc="装配前三步原料成整棵 PostCard 成品，作为唯一成品出口",
        tools=("baidu_search", "load_skill"),
        enter_line="汇总官接单啦，开始组装成品",
        artifacts_schema="postcard",
        expected_sections=("artifacts", "narrative"),
    ),
}
