# 稿搭｜多 Agent 图文创作助手

告诉稿搭你想写什么，主编辑会与你确认需求、安排创作，并请你审阅关键产出，最后交付可继续修改的图文成品。
## 亮点

| 能力 | 说明 |
| --- | --- |
| 🧭 **模型自主编排** | 主编辑确认需求后，自主决定创作任务和执行顺序。 |
| 👥 **创作团队协作** | 团队多位成员按需分工、各展所长，共同完成一篇图文。 |
| ✅ **成果可审阅** | 关键产出可确认或要求重做；选题、文案和成品也能直接编辑。 |
| 📊 **进度可追踪** | 工作展板展示任务进度、角色状态与阶段产出，随时了解创作进展。 |
| 💬 **对话式修改** | 成品交付后继续对话提出修改，在已有成果上创作新版本。 |
| 🧠 **创作者记忆** | 记录历史作品和创作偏好，让后续创作更贴近你的习惯。 |

### 如何用稿搭创作图文

1. **提出需求并确认意图**：与主编辑对话，确认主题、平台、风格和配图等要求。
2. **由主编辑安排创作**：主编辑根据已确认的需求决定需要哪些任务，并交给创作角色执行。
3. **审阅局部成品**：确认或要求重做；选题和文案还可以直接编辑。
4. **确认图文成品**：审阅汇总后的图文成品；交付后仍可通过对话提出修改要求。
## 截图

以下截图来自同一次创作，展示从意图确认到成品确认的关键界面。

### 确认创作意图

![意图确认卡片](docs/assets/real-run/01-theme-and-intent.png)

### 选择或修改选题

![选题确认卡片](docs/assets/real-run/02-idea-confirmation.png)

### 审阅标题与正文

![文案确认卡片](docs/assets/real-run/03-script-confirmation.png)

### 确认配图

![配图确认卡片](docs/assets/real-run/04-image-confirmation.png)

### 确认最终成品

![最终成品确认卡片](docs/assets/real-run/05-final-product-confirmation.png)
## 安装与启动

前置条件：[uv](https://docs.astral.sh/uv/)（Python 依赖管理）、Node.js（含 npm）。

1. 克隆并配置密钥：

   ```bash
   git clone https://github.com/MMyosotis/chorus.git && cd chorus
   cp .env.example .env
   ```

   在 `.env` 中填入：

   ```bash
   DEEPSEEK_API_KEY=sk-...      # 对话模型（必需）
   ARK_API_KEY=...              # 生图模型（完整跑通配图必需；暂无密钥可先在设置面板开启生图测试模式）
   BAIDU_SEARCH_API_KEY=...     # 联网搜索（可选）
   ```

2. 启动（首次运行会自动安装前后端依赖）：

   ```bash
   ./scripts/start.sh
   ```

   打开 **http://localhost:5173**，新建一个会话即可开始。

3. 试一个示例主题：`帮我写一篇秋日城市漫步主题的小红书图文笔记`。确认意图后，界面会展示角色任务与需要你审阅的产出。

调整模型或搜索配置请看[配置说明](docs/configuration.md)。
## 成品示例

以「秋冬通勤穿搭」为主题创作的小红书图文笔记：

![秋冬通勤穿搭 PostCard 成品](docs/assets/real-run/06-postcard-preview.png)
## 技术与开发

前端使用 Vue 3 + Vite，后端使用 FastAPI + SQLite。主编辑负责对话与任务编排，调度器派发任务，创作角色写回进度和产物。详细设计见[系统架构](docs/architecture.md)，模型与外部服务设置见[配置说明](docs/configuration.md)。

从仓库根目录运行：

```bash
uv run python -m chorus.tests     # 后端测试
npm --prefix web test             # 前端测试
npm --prefix web run build        # 前端构建
```
## 项目状态与许可

稿搭当前面向单机使用。生图依赖配置的图像服务，联网搜索需另行配置并开启；模型调用可能产生费用，实际成品质量也会随模型和需求变化。

仓库暂未附带开源许可证。反馈与问题请提 [GitHub Issue](https://github.com/MMyosotis/chorus/issues)。
