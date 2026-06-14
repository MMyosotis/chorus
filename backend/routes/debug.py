"""调试相关 endpoint：图像测试模式开关等。

测试模式开关有两层状态：
- config 内存值（is_image_test_mode / set_image_test_mode）— generate_image 工具读取
- settings KV 持久化（key="image_test_mode"）— 进程重启后回灌内存
PATCH 时同时写两层，保证立即生效且持久化。
"""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import (
    is_image_test_mode,
    set_image_test_mode,
)
from backend.settings import get_settings_store

router = APIRouter(prefix="/api/debug")


class TestModeView(BaseModel):
    enabled: bool


class TestModePatch(BaseModel):
    enabled: bool


@router.get("/test-mode", response_model=TestModeView)
def get_test_mode():
    return TestModeView(enabled=is_image_test_mode())


@router.patch("/test-mode", response_model=TestModeView)
def patch_test_mode(req: TestModePatch):
    set_image_test_mode(req.enabled)
    get_settings_store().set("image_test_mode", bool(req.enabled))
    return TestModeView(enabled=is_image_test_mode())
