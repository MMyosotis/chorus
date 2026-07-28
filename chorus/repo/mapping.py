"""行模型与领域对象间的同名字段投影:取交集,特殊字段由调用方显式覆盖。"""

from __future__ import annotations

from dataclasses import fields as dc_fields, is_dataclass
from typing import Any

from pydantic import BaseModel


def _field_names(model: type) -> set[str]:
    """取模型字段名集合,兼容基础模型与数据类。"""
    if issubclass(model, BaseModel):
        return set(model.model_fields.keys())
    if is_dataclass(model):
        return {field.name for field in dc_fields(model)}
    raise TypeError(f"unsupported model: {model}")


def shared_fields(
    source: Any,
    target: type,
    *,
    exclude: set[str] | None = None,
) -> dict[str, Any]:
    """返回源与目标同名字段的值(排除指定项),供构造目标模型。"""
    excluded = exclude or set()
    names = _field_names(target) & _field_names(type(source))
    return {name: getattr(source, name) for name in names if name not in excluded}
