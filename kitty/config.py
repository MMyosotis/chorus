import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

# 对话模型配置表：每个模型一条，含完整连接信息。
#   id          —— 展示名 + 存储键 + 注册表键（settings.db 存这个；改它已存设置会回退默认）
#   base_url    —— 该 provider 的 OpenAI 兼容 endpoint
#   api_key_env —— 从哪个环境变量取 API key（key 值写在 .env，不进配置明文）
#   model_id    —— 传给 OpenAI API 的真实 model 名（常与 id 不同）
# 新增/删除模型改这里即可；api_key 在 .env 配对应变量。
CHAT_MODELS = [
    {
        "id": "DeepSeek V4 Flash",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model_id": "deepseek-v4-flash",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    {
        "id": "DeepSeek V4 Pro",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model_id": "deepseek-v4-pro",
        "api_key_env": "DEEPSEEK_API_KEY",
    },
    {
        "id": "MiniMax M3",
        "base_url": "https://ark.cn-beijing.volces.com/api/coding/v3",
        "model_id": "minimax-m3",
        "api_key_env": "MINIMAX_API_KEY",
    }
]
# 启动默认对话模型 + 标题生成固定使用的模型（须是 CHAT_MODELS 中某条的 id）
DEFAULT_CHAT_MODEL_ID = os.environ.get("DEFAULT_CHAT_MODEL_ID", "DeepSeek V4 Flash")

MAX_TOKENS = 2048

# 运行时数据根目录（项目根 / data）：db 文件落点，启动自动创建
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 生图模型配置表：与 CHAT_MODELS 同构，每个模型一条独立连接信息。
#   id          —— 展示名 + 存储键 + 注册表键（settings.db 存这个；改它已存设置会回退默认）
#   base_url    —— 该 provider 的图像生成 endpoint
#   api_key_env —— 从哪个环境变量取 API key（key 值写在 .env，不进配置明文）
#   model_id    —— 传给图像 API 的真实 model 名
# 新增/删除模型改这里即可；不同模型可指向不同 provider / key。
IMAGE_MODELS = [
    {
        "id": "Seedream 4",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key_env": "ARK_IMAGE_API_KEY",
        "model_id": "doubao-seedream-4-0-250828",
    },
    {
        "id": "Seedream 5 Lite",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "api_key_env": "ARK_IMAGE_API_KEY",
        "model_id": "doubao-seedream-5-0-litenew",
    },
]
# 启动默认生图模型（须是 IMAGE_MODELS 中某条的 id）
DEFAULT_IMAGE_MODEL_ID = os.environ.get("DEFAULT_IMAGE_MODEL_ID", "Seedream 4")

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

# 子 Agent 按角色独立配置对话模型：agent_type -> CHAT_MODELS 中某条的 id（复用对话模型配置）
SUBAGENT_MODELS = {
    "idea": "DeepSeek V4 Flash",   # 选题：便宜快
    "script": "DeepSeek V4 Pro",   # 文案：强
    "image": "DeepSeek V4 Flash",  # 配图提示词生成
    "finalize": "DeepSeek V4 Pro",  # 汇总：强
}

# 后台调度器参数
SCHEDULER_INTERVAL = 1.0   # 调度器轮询周期（秒）
ZOMBIE_TIMEOUT = 120       # running task 心跳超时阈值（秒），> 单次最长 ReAct 迭代
POOL_SIZE = 4              # subagent 线程池大小



