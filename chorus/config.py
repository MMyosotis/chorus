"""配置常量：对话与生图模型表、标题模型、数据目录、工具白名单与外部 API 密钥。

密钥值写 .env，配置表只存变量名；新增生图厂商需写客户端、注册构造器并在此标厂商。
单组件硬编码实现参数（调度间隔与僵死超时、模型调用超时与生成令牌上限）住使用方模块，不进此文件。
"""
import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(override=True)


class ChatModelConfig(BaseModel):
    """对话模型配置条目：展示名兼存储键，密钥只存环境变量名。"""

    model_name: str
    base_url: str
    model_id: str
    api_key_env: str
    input_price: Optional[float] = None
    output_price: Optional[float] = None


class ImageModelOptions(BaseModel):
    """生图厂商私有连接参数。"""

    base_url: str
    api_key_env: str
    model_id: str


class ImageModelConfig(BaseModel):
    """生图模型配置条目：厂商选构造器，options 为厂商私有参数。"""

    model_name: str
    provider: str
    options: ImageModelOptions


CHAT_MODELS: list[ChatModelConfig] = [
    ChatModelConfig(
        model_name="DeepSeek V4 Flash",
        base_url="https://api.deepseek.com",
        model_id="deepseek-v4-flash",
        api_key_env="DEEPSEEK_API_KEY",
    ),
    ChatModelConfig(
        model_name="DeepSeek V4 Pro",
        base_url="https://api.deepseek.com",
        model_id="deepseek-v4-pro",
        api_key_env="DEEPSEEK_API_KEY",
    ),
]
BYPASS_MODEL = "DeepSeek V4 Flash"

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

IMAGE_MODELS: list[ImageModelConfig] = [
    ImageModelConfig(
        model_name="Seedream 4",
        provider="ark",
        options=ImageModelOptions(
            base_url="https://ark.cn-beijing.volces.com/api/v3/images/generations",
            api_key_env="ARK_API_KEY",
            model_id="doubao-seedream-4-0-250828",
        ),
    ),
    ImageModelConfig(
        model_name="Seedream 5 Lite",
        provider="ark",
        options=ImageModelOptions(
            base_url="https://ark.cn-beijing.volces.com/api/v3/images/generations",
            api_key_env="ARK_API_KEY",
            model_id="doubao-seedream-5-0-260128",
        ),
    ),
]

BAIDU_SEARCH_API_KEY = os.environ.get("BAIDU_SEARCH_API_KEY", "")
BAIDU_SEARCH_BASE_URL = "https://qianfan.baidubce.com/v2/ai_search/chat/completions"

TOOL_WHITELISTS: dict[str, tuple[str, ...]] = {
    "supervisor": ("update_intent_state", "create_plan", "present_options"),
    "idea": ("baidu_search", "list_skill", "load_skill"),
    "script": ("baidu_search", "list_skill", "load_skill"),
    "image": ("generate_image", "list_skill", "load_skill"),
    "finalize": ("list_skill", "load_skill"),
}

# 日志：级别 / 目录 / 单文件滚动 / 跨时间清理
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
LOG_DIR = DATA_DIR / "logs"
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", "5000000"))
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", "5"))
LOG_RETENTION_DAYS = int(os.environ.get("LOG_RETENTION_DAYS", "7"))
LOG_CLEANUP_INTERVAL = int(os.environ.get("LOG_CLEANUP_INTERVAL", "21600"))
