# 配置说明

Chorus 的全部配置分两层：

- **密钥值**写项目根目录的 `.env`（gitignored，不会提交）；
- **模型表与其余常量**在 `chorus/config.py` 中以字面量维护，改表需提交代码。

配置表里只存**环境变量名**（`api_key_env`），不存密钥本身——这样模型表可以安全提交，密钥值留在本地 `.env`。

## 环境变量一览

复制根目录的 `.env.example` 为 `.env` 并按需填入：

```bash
# 对话模型（必需）：CHAT_MODELS 各条 api_key_env 指向的变量，用到哪条配哪条
DEEPSEEK_API_KEY=sk-...

# 生图模型（使用配图功能时必需）：IMAGE_MODELS 各条 options.api_key_env 指向的变量
ARK_API_KEY=...

# 联网搜索（可选）：工具可见性由设置面板的联网搜索开关控制，开启开关时需此密钥
BAIDU_SEARCH_API_KEY=...

# 日志（可选，均有默认值）
LOG_LEVEL=INFO
LOG_MAX_BYTES=5000000
LOG_BACKUP_COUNT=5
LOG_RETENTION_DAYS=7
LOG_CLEANUP_INTERVAL=21600
```

> `.env` 缺失或缺 key 时，应用仍能启动，但对话 / 生图会在对应调用处报错；联网搜索工具是否可见由设置面板开关控制，开关开启但未配置密钥时搜索调用会报错。

## 对话模型（`CHAT_MODELS`）

每条是一个 OpenAI 兼容接口的对话模型配置：

| 字段 | 说明 |
| --- | --- |
| `model_name` | 展示名，同时是前端设置面板与数据库中保存的存储键 |
| `base_url` | API 地址（OpenAI 兼容接口） |
| `model_id` | 厂商侧真实模型名，随请求发出 |
| `api_key_env` | 指向 `.env` 中哪个环境变量取密钥 |
| `input_price` / `output_price` | 可选，入出单价（元 / 百万 token），两个都配了才在 trace 控制台显示费用 |

当前默认配置两条 DeepSeek 模型。新增对话模型即在 `CHAT_MODELS` 列表加一条，前提是厂商提供 OpenAI 兼容接口；新增后前端设置面板可直接切换。

### 旁路模型（`BYPASS_MODEL`）

字面量，**必须是 `CHAT_MODELS` 中某条的 `model_name`**。标题生成、输入建议、旁白、摘要、记忆提取等非流式旁路调用共用此模型，要求便宜且快，不参与前端切换。若从 `CHAT_MODELS` 删除了它指向的条目，须同步更换 `BYPASS_MODEL`，否则启动后旁路调用会失败。

## 生图模型（`IMAGE_MODELS`）

每条配置：

| 字段 | 说明 |
| --- | --- |
| `model_name` | 展示名兼存储键 |
| `provider` | 选哪个构造器，当前支持 `ark`（火山方舟） |
| `options.base_url` | 厂商生图接口地址 |
| `options.api_key_env` | 指向 `.env` 中哪个环境变量取密钥（默认用 `ARK_API_KEY`，也可指向独立变量） |
| `options.model_id` | 厂商侧真实模型名 |

生图密钥与对话密钥解耦——对话模型换厂商不影响生图配置。

**新增生图厂商**：在 `tools/clients/` 写对应 client、在 `tools/builtin/generate_image.py` 的构造器表（`_BUILDERS`）注册、在 `IMAGE_MODELS` 条目标 `provider`，三步缺一不可。

**生图测试模式**：前端设置面板可开关（后端 `SettingsService` 持久化），开启后生图返回固定测试 URL，不产生真实调用费用，适合先跑通流程。

## 联网搜索

`baidu_search` 工具使用百度智能搜索生成服务（千帆 endpoint 固定在 `config.BAIDU_SEARCH_BASE_URL`），在 `.env` 配 `BAIDU_SEARCH_API_KEY`，并需在百度千帆控制台单独开通该服务。

工具对 agent 是否可见由**前端设置面板的联网搜索开关**控制（后端 `SettingsService` 持久化）：开关关闭时搜索工具不出现在工具列表中；开关开启但 `.env` 缺少密钥时，agent 仍可能发起搜索调用并收到错误结果。该工具仅暴露给选题与文案两个子 agent（见 `config.TOOL_WHITELISTS`）。

## 日志

日志写 `data/logs/`（数据目录下），按大小滚动：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_MAX_BYTES` | `5000000` | 单文件最大字节数 |
| `LOG_BACKUP_COUNT` | `5` | 保留的滚动文件数 |
| `LOG_RETENTION_DAYS` | `7` | 超期日志清理天数 |
| `LOG_CLEANUP_INTERVAL` | `21600` | 清理检查间隔（秒） |

## 常见问题

- **前端设置面板里看不到某个模型**：确认它已在 `CHAT_MODELS` / `IMAGE_MODELS` 中配置，改动后重启后端。
- **标题 / 输入建议等不工作但对话正常**：检查 `BYPASS_MODEL` 是否仍指向 `CHAT_MODELS` 中存在的 `model_name`。
- **调用报密钥错误**：配置表存的是变量名，先确认 `.env` 里对应变量已填值，且 `.env` 位于项目根目录。
- **费用显示不出现**：`input_price` 与 `output_price` 必须同时配置才显示。
- **数据与日志去哪了**：都在 `data/` 下（`chorus.db` 与 `logs/`），目录 gitignored，启动时自动创建。重置数据库用 `python scripts/reset_db.py`（会清空全部数据）。
