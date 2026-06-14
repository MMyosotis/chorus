"""调试相关 endpoint：图像测试模式开关等。"""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.config import (
    get_initial_image_test_mode,
    is_image_test_mode,
    set_image_test_mode,
)

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
    return TestModeView(enabled=is_image_test_mode())


@router.get("/test-mode/initial", response_model=TestModeView)
def get_initial_test_mode():
    return TestModeView(enabled=get_initial_image_test_mode())
