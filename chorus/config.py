import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# 对话模型配置表：每条含展示名、兼容端点、密钥环境变量与真实模型名。
# 密钥值写 .env，配置表只存变量名。新增删除模型改这里。
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
# 标题生成固定使用的模型，须为上表某条展示名，不随用户当前设置变动
TITLE_MODEL = "DeepSeek V4 Flash"
MAX_TOKENS = 2048

# 运行时数据根目录，数据库落点，启动自动创建
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 生图模型配置表：展示名 + 厂商 + 厂商私有参数。
# 厂商决定用哪个构造器，私有参数只由对应构造器读。
# 新增厂商需写客户端、注册构造器并在此标厂商。
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

# 百度智能搜索 API
BAIDU_SEARCH_API_KEY = os.environ.get("BAIDU_SEARCH_API_KEY", "")
BAIDU_SEARCH_BASE_URL = os.environ.get(
    "BAIDU_SEARCH_BASE_URL",
    "https://qianfan.baidubce.com/v2/ai_search/chat/completions",
)

# 各角色工具白名单：角色查表取名，再交工具包筛 schema。
# 工具名是字符串约定，改名需同步本表。
TOOL_WHITELISTS: dict[str, tuple[str, ...]] = {
    "supervisor": ("create_plan", "load_skill", "baidu_search", "output_plan"),
    "idea": ("baidu_search", "load_skill"),
    "script": ("baidu_search", "load_skill"),
    "image": ("baidu_search", "generate_image", "load_skill"),
    "finalize": ("baidu_search", "load_skill"),
}

# 后台调度器参数
SCHEDULER_INTERVAL = 1.0   # 轮询周期（秒）
ZOMBIE_TIMEOUT = 120       # 运行中任务心跳超时阈值（秒）
POOL_SIZE = 4              # 子 agent 线程池大小



