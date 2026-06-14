import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

API_KEY = os.environ.get("OPENAI_API_KEY", "")
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
MODEL_ID = os.environ.get("MODEL_ID", "gpt-4o")

SYSTEM_PROMPT = "你是一个友好、健谈的 AI 助手。记住对话中提到过的信息，保持上下文连贯。"
MAX_TOKENS = 2048

SKILLS_DIR = Path(__file__).parent / "skills_data"
MAX_TOOL_ITERATIONS = int(os.environ.get("MAX_TOOL_ITERATIONS", "10"))

# 会话持久化目录
CONVERSATIONS_DIR = Path(__file__).parent / "data" / "conversations"

# 会话清理策略
CONV_TTL_DAYS = int(os.environ.get("CONV_TTL_DAYS", "30"))
CONV_MAX_BYTES = int(os.environ.get("CONV_MAX_BYTES", str(1024 * 1024)))
CONV_MAX_COUNT = int(os.environ.get("CONV_MAX_COUNT", "100"))

# 火山方舟图像生成（与对话客户端解耦，便于后续接入更多模型）
ARK_IMAGE_API_KEY = os.environ.get("ARK_IMAGE_API_KEY", "")
ARK_IMAGE_BASE_URL = os.environ.get(
    "ARK_IMAGE_BASE_URL",
    "https://ark.cn-beijing.volces.com/api/v3",
)

# 逻辑名 -> 真实模型 ID 映射，方便用户在 .env 升级版本号
ARK_IMAGE_MODELS = {
    "seedream-4": os.environ.get(
        "ARK_IMAGE_MODEL_SEEDREAM_4", "doubao-seedream-4-0-250828"
    ),
    "seedream-5-lite": os.environ.get(
        "ARK_IMAGE_MODEL_SEEDREAM_5_LITE", "doubao-seedream-5-0-litenew"
    ),
}

# 百度智能搜索生成 API（baidu_search 工具使用）
BAIDU_SEARCH_API_KEY = os.environ.get("BAIDU_SEARCH_API_KEY", "")
BAIDU_SEARCH_BASE_URL = os.environ.get(
    "BAIDU_SEARCH_BASE_URL",
    "https://qianfan.baidubce.com/v2/ai_search/chat/completions",
)

# 图像生成测试开关：开启后 generate_image 工具不调用真实 API，直接返回写死的 URL。
# 默认关闭，仅可在运行时通过控制台 (PATCH /api/debug/test-mode) 切换，进程重启回到默认。
IMAGE_TEST_FAKE_URL = os.environ.get(
    "IMAGE_TEST_FAKE_URL",
    "https://ark-content-generation-v2-cn-beijing.tos-cn-beijing.volces.com/doubao-seedream-4-0/02178135974958637079cdcc08b35ab782b1fd6e8da4cf02940a7_0.jpeg?X-Tos-Algorithm=TOS4-HMAC-SHA256&X-Tos-Credential=AKLTYWJkZTExNjA1ZDUyNDc3YzhjNTM5OGIyNjBhNDcyOTQ%2F20260613%2Fcn-beijing%2Ftos%2Frequest&X-Tos-Date=20260613T140919Z&X-Tos-Expires=86400&X-Tos-Signature=ce55d8ee11f67e665c0b465df403d734e7304a1489d0b3f4fcfea53f531e59c3&X-Tos-SignedHeaders=host",
)


_image_test_mode: bool = False


def is_image_test_mode() -> bool:
    return _image_test_mode


def set_image_test_mode(enabled: bool) -> None:
    global _image_test_mode
    _image_test_mode = bool(enabled)


def get_image_test_fake_url() -> str:
    return IMAGE_TEST_FAKE_URL
