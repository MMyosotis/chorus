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
