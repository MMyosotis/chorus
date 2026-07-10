"""任务运行期进度快照：字数、结构单元、临时信号与意图旁白。

易失状态，一任务一行覆盖更新，为将来迁 KV 留路。纯数据形状，不碰数据库。
"""
from __future__ import annotations

from pydantic import ConfigDict, TypeAdapter
from pydantic.dataclasses import dataclass as pydataclass


@pydataclass(config=ConfigDict(frozen=True, extra="forbid"))
class TaskProgress:
    """一个任务的运行期进度快照,一任务一行,覆盖更新。"""

    task_id: str
    composing_chars: int = 0
    composing_units: int = 0
    composing_label: str = ""
    last_signal: str = ""
    aside: str = ""


_PROGRESS_ADAPTER = TypeAdapter(TaskProgress)


def dump_progress(progress: TaskProgress) -> dict:
    """把进度快照序列化为可 JSON 化的 dict。"""
    return _PROGRESS_ADAPTER.dump_python(progress)
