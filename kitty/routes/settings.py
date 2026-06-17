"""调试 / 设置路由：图像测试模式开关（Depends 注入 SettingsService）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from kitty.routes.providers import provide_settings_service
from kitty.services.settings import SettingsService

router = APIRouter(prefix="/api/debug")


class TestModeView(BaseModel):
    enabled: bool


class TestModePatch(BaseModel):
    enabled: bool


@router.get("/test-mode", response_model=TestModeView)
def get_test_mode(settings: SettingsService = Depends(provide_settings_service)):
    return TestModeView(enabled=settings.get_image_test_mode())


@router.patch("/test-mode", response_model=TestModeView)
def patch_test_mode(
    req: TestModePatch,
    settings: SettingsService = Depends(provide_settings_service),
):
    settings.set_image_test_mode(req.enabled)
    return TestModeView(enabled=settings.get_image_test_mode())
