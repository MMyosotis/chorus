"""Repository 基类:收 Engine 注入与短 Session 事务样板,各表 repo 继承。"""
from __future__ import annotations

from contextlib import contextmanager
from functools import wraps
from typing import Callable, TypeVar

from sqlalchemy import Engine
from sqlalchemy.orm import Session as DbSession
from typing_extensions import Concatenate, ParamSpec

_P = ParamSpec("_P")
_R = TypeVar("_R")
_T = TypeVar("_T", bound="BaseRepository")


class BaseRepository:
    """各 repo 共享 Engine 注入与事务样板:读用 _session(),写用 _session(commit=True)。"""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    @contextmanager
    def _session(self, *, commit: bool = False):
        with DbSession(self._engine) as db:
            yield db
            if commit:
                db.commit()


def read(method: Callable[Concatenate[_T, DbSession, _P], _R]) -> Callable[Concatenate[_T, _P], _R]:
    """读方法装饰器:开短 Session 注入 db,不提交。"""
    @wraps(method)
    def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        with self._session() as db:
            return method(self, db, *args, **kwargs)
    return wrapper


def write(method: Callable[Concatenate[_T, DbSession, _P], _R]) -> Callable[Concatenate[_T, _P], _R]:
    """写方法装饰器:开短 Session 注入 db,方法返回后提交。"""
    @wraps(method)
    def wrapper(self: _T, *args: _P.args, **kwargs: _P.kwargs) -> _R:
        with self._session(commit=True) as db:
            return method(self, db, *args, **kwargs)
    return wrapper
