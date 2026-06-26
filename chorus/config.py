import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# 对话模型配置表：每个模型一条，含完整连接信息。
#   model_name  —— 展示名 + 存储键 + 注册表键（settings 表存这个；改它已存设置会回退默认）
#   base_url    —— 该 provider 的 OpenAI 兼容 endpoint
#   api_key_env —— 从哪个环境变量取 API key（key 值写在 .env，不进配置明文）
#   model_id    —— 传给 OpenAI API 的真实 model 名（常与 model_name 不同）
# 新增/删除模型改这里即可；api_key 在 .env 配对应变量。
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
# 标题生成固定使用的小模型（须是 CHAT_MODELS 中某条的 model_name；不随用户当前对话设置变动）
TITLE_MODEL = "DeepSeek V4 Flash"
MAX_TOKENS = 2048

# 运行时数据根目录（项目根 / data）：db 文件落点，启动自动创建
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 生图模型配置表：公共字段 + 厂商私有 options。
#   model_name  —— 展示名 + 存储键 + 注册表键（settings 表存这个；改它已存设置会回退默认）
#   provider    —— 选哪个 builder（image 各厂商协议不同，按此 dispatch；见 tools/builtin/generate_image.py）
#   options     —— 厂商私有黑箱：含 model_id 与该 builder 需要的一切，只由对应 builder 读
# 新增厂商 = 写 client + 注册 builder + config 条目标 provider；新增同厂商模型照抄 options。
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

# 百度智能搜索生成 API（baidu_search 工具使用）
BAIDU_SEARCH_API_KEY = os.environ.get("BAIDU_SEARCH_API_KEY", "")
BAIDU_SEARCH_BASE_URL = os.environ.get(
    "BAIDU_SEARCH_BASE_URL",
    "https://qianfan.baidubce.com/v2/ai_search/chat/completions",
)

# 各 agent 的工具白名单单一真源：supervisor + 四子角色能用的工具名。
#   各 agent 查表取名字，再由 tools 包按 (名字 + web_search 开关) 筛 schema。
#   supervisor 是调度者（非子角色），其工具配置独立于此表，不寄生 AgentProfile。
#   工具名是字符串约定（非 import 依赖），改名时同步改本表。加角色只加一条。
TOOL_WHITELISTS: dict[str, tuple[str, ...]] = {
    "supervisor": ("create_plan", "load_skill", "baidu_search"),
    "idea": ("baidu_search", "load_skill"),
    "script": ("baidu_search", "load_skill"),
    "image": ("baidu_search", "generate_image", "load_skill"),
    "finalize": ("baidu_search", "load_skill"),
}

# 后台调度器参数
SCHEDULER_INTERVAL = 1.0   # 调度器轮询周期（秒）
ZOMBIE_TIMEOUT = 120       # running task 心跳超时阈值（秒），> 单次最长 ReAct 迭代
POOL_SIZE = 4              # subagent 线程池大小



