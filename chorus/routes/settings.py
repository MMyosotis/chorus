"""调试与设置路由：图像测试模式开关、模型选项列表与当前选择。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from chorus.config import CHAT_MODELS, IMAGE_MODELS
from chorus.routes.providers import provide_settings_service
from chorus.services.settings import SettingsService

router = APIRouter(prefix="/api/debug")
settings_router = APIRouter(prefix="/api/settings")


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


class ModelItem(BaseModel):
    id: str


class ModelListsView(BaseModel):
    chat_models: list[ModelItem]
    image_models: list[ModelItem]


class OptionsView(BaseModel):
    chat_model: str
    image_model: str
    web_search: bool


class OptionsPatch(BaseModel):
    chat_model: Optional[str] = None
    image_model: Optional[str] = None
    web_search: Optional[bool] = None


@settings_router.get("/models", response_model=ModelListsView)
def get_model_lists():
    # 仅暴露展示名，连接细节不外露
    chat_models = [ModelItem(id=m["model_name"]) for m in CHAT_MODELS]
    image_models = [ModelItem(id=m["model_name"]) for m in IMAGE_MODELS]
    return ModelListsView(chat_models=chat_models, image_models=image_models)


@settings_router.get("/options", response_model=OptionsView)
def get_options(settings: SettingsService = Depends(provide_settings_service)):
    return OptionsView(
        chat_model=settings.get_chat_model(),
        image_model=settings.get_image_model(),
        web_search=settings.get_web_search(),
    )


@settings_router.patch("/options", response_model=OptionsView)
def patch_options(
    req: OptionsPatch,
    settings: SettingsService = Depends(provide_settings_service),
):
    if req.chat_model is not None:
        settings.set_chat_model(req.chat_model)
    if req.image_model is not None:
        settings.set_image_model(req.image_model)
    if req.web_search is not None:
        settings.set_web_search(req.web_search)
    return OptionsView(
        chat_model=settings.get_chat_model(),
        image_model=settings.get_image_model(),
        web_search=settings.get_web_search(),
    )
