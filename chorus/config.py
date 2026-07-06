"""配置常量：对话与生图模型表、标题模型、数据目录、调度参数、工具白名单与外部 API 密钥。

密钥值写 .env，配置表只存变量名；新增生图厂商需写客户端、注册构造器并在此标厂商。
"""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

CHAT_MODELS = [
    {
        "model_name": "DeepSeek V4 Flash",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model_id": "deepseek-v4-flash",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    {
        "model_name": "DeepSeek V4 Pro",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model_id": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    {
        "model_name": "MiniMax M3",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model_id": "minimax-m3",
        "api_key_env": "MINIMAX_API_KEY",
    }
]
TITLE_MODEL = "DeepSeek V4 Flash"
MAX_TOKENS = 2048

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

IMAGE_MODELS = [
    {
        "model_name": "Seedream 4",
        "provider": "ark",
        "options": {
            "base_url": "https://ark.cn-beijing.volces.com/api/v3/images/generations",
            "api_key_env": "ARK_IMAGE_API_KEY",
            "model_id": "doubao-seedream-4-0-250828",
        },
    },
    {
        "model_name": "Seedream 5 Lite",
        "provider": "ark",
        "options": {
            "base_url": "https://ark.cn-beijing.volces.com/api/v3/images/generations",
            "api_key_env": "ARK_IMAGE_API_KEY",
            "model_id": "doubao-seedream-5-0-litenew",
        },
    },
]

BAIDU_SEARCH_API_KEY = os.environ.get("BAIDU_SEARCH_API_KEY", "")
BAIDU_SEARCH_BASE_URL = os.environ.get(
    "BAIDU_SEARCH_BASE_URL",
    "https://qianfan.baidubce.com/v2/ai_search/chat/completions",
)

TOOL_WHITELISTS: dict[str, tuple[str, ...]] = {
    "supervisor": ("update_intent_state", "create_plan", "load_skill", "baidu_search", "output_plan"),
    "idea": ("baidu_search", "load_skill"),
    "script": ("baidu_search", "load_skill"),
    "image": ("baidu_search", "generate_image", "load_skill"),
    "finalize": ("baidu_search", "load_skill"),
}

SCHEDULER_INTERVAL = 1.0
ZOMBIE_TIMEOUT = 120


