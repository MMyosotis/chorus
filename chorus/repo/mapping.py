"""Record 与领域对象间的同名字段投影:取交集,特殊字段由调用方显式覆盖。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel
from sqlalchemy.orm import DeclarativeBase


def _field_names(model: type[Any]) -> set[str]:
    """取模型字段名集合,兼容领域模型(pydantic/数据类)与 Record。"""
    if issubclass(model, BaseModel):
        return set(model.model_fields)
    if hasattr(model, "__dataclass_fields__"):
        return set(model.__dataclass_fields__)
    if issubclass(model, DeclarativeBase):
        return set(model.__table__.columns.keys())
    raise TypeError(f"unsupported model: {model.__name__}")


def shared_fields(source: Any, target: type, *, exclude: set[str] | None = None) -> dict[str, Any]:
    """返回源与目标同名字段的值(排除指定项),供构造目标模型。"""
    excluded = exclude or set()
    names = _field_names(type(source)) & _field_names(target)
    return {name: getattr(source, name) for name in names if name not in excluded}
