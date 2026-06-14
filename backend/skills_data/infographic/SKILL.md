---
name: infographic
description: 制作干净、现代、易读的信息图（infographic / 知识卡片 / 步骤图）。当用户说"画一张信息图 / 知识卡片 / 步骤图 / 流程图 / 小红书风格图文 / 把 XX 做成一张图 / 总结成图卡"等，或想把某个主题/教程/流程做成可视化卡片时使用。默认 9:16 竖版，专业教育风。
---

# Infographic 信息图生成

把一个主题（教程、流程、清单、对比、时间线等）做成一张干净易读的信息图。

## 工作流程

收到信息图请求后，按以下顺序执行：

### 1. 先确认细节（如果用户没明确给）

用一两句话快速向用户确认下面这些点，能合并就合并问，不要一个一个慢慢来：

- **主题**：要讲什么？比如"5 步学会 Prompt 工程"、"一杯咖啡从豆到杯的旅程"。如果用户已经给了主题，跳过这条。
- **版式**：默认 9:16 竖版（适合小红书/朋友圈）；如果用户说要做 PPT 配图、横屏壁纸、文档插图，问下要不要换 16:9。
- **语言**：中文 / 英文 / 中英混排。默认看用户用什么语言提的需求。
- **要点条数**（可选，仅当主题模糊时问）：3 条？5 条？7 条？

如果用户的需求已经足够清楚（主题 + 版式 + 语言都能从上下文推断出来），就别再问了，直接进入第 2 步。**不要为了走流程而问问题** —— 这是个常见的体验杀手。

### 2. 在心里规划好内容结构

在调用画图工具之前，先把这些想清楚：

- **标题**：一句话能放进顶部，简短有力。比如"Prompt 工程 5 步速通"，不要"如何系统性地学习 Prompt 工程入门基础知识"。
- **3-7 个分点**：每个点有一个**短标语**（4-10 字）+ **一句解释**（15-30 字）。条数太多会糊，太少撑不起一张图。
- **流程关系**：这些点是"并列"还是"先后顺序"？后者要在描述里强调箭头/编号引导视线流向。
- **图标提示**：每个点用什么样的极简 flat icon 更贴切（咖啡杯、闹钟、灯泡……），让模型在 prompt 里描述出来。

### 3. 组装图像生成 prompt

按以下模板组装，把规划好的内容填进去，**整段用英文写**（图像模型对英文 prompt 响应更稳）。要展示的中文/英文文字本身保留原文，模型会原样渲染。

```
Create a clean, modern, highly readable infographic in {9:16 vertical | 16:9 horizontal} format.
Use a minimalist color palette with 2-3 main colors ({具体配色，例如 deep navy + warm orange + off-white}) and plenty of white space.
Clear hierarchy:
- Large bold title at top: "{标题原文}"
- {N} numbered sections, each with a short headline and one line of explanatory text:
  1. "{要点1标题}" — {要点1解释}
  2. "{要点2标题}" — {要点2解释}
  ...
- Use simple flat / minimal line icons for each section ({每个点对应的 icon 提示，例如: lightbulb, target, stopwatch, ...}).
All text must be perfectly legible with correct spelling, rendered crisply. Text language: {Chinese | English | mixed}.
Include subtle visual separators between sections, {arrows / connecting lines} indicating flow from step to step, no clutter, professional educational style, high contrast for readability.
```

要点：

- 配色给具体颜色名（"deep navy + warm orange + off-white"）比"minimalist palette"更可控。先想好配色再写 prompt。
- 每个分点的标题文字用引号包起来，模型更容易把它们识别为需要原样渲染的字符串。
- 中文文字渲染对图像模型挑战较大，prompt 里要明确"correct spelling, rendered crisply"，并尽量保持文字短、避免生僻字。

### 4. 调用 generate_image 工具

直接用上一步组装好的英文 prompt 调用 `generate_image`，模型选 `seedream-4`（默认），尺寸根据版式选 `1024x1820`（9:16）或 `1820x1024`（16:9）。

如果 generate_image 工具支持的尺寸参数命名不一样（比如只接受预设档），按它实际接受的来；不要硬塞不支持的参数。

### 5. 给用户的回复

把图贴出来，附**一两句**说明这张图讲了什么、用了什么版式/配色。**不要**把刚才那段英文 prompt 全文复述给用户 —— 没人想读。如果用户问了再给。

如果生成的图明显有问题（文字串行、内容缺失、配色翻车），跟用户说"这版有点问题，我换个方向再画一张"，调整 prompt 再来一次，最多两次。两次还不行就把当前最好的版本给用户，说明哪里没达成预期，让用户决定要不要继续调。

## 几个容易踩的坑

- **要点别太多**：超过 7 个就开始挤，文字会糊。多了就归并，或者做成两张图。
- **别堆砌修饰词**：prompt 里反复说 "beautiful, stunning, amazing" 没用，反而稀释关键约束（版式、层级、可读性）。
- **流程图 vs 清单图区别对待**：有先后顺序的（教程、步骤）一定要写 "numbered steps with arrows indicating flow"；并列的（清单、对比）就用 "evenly spaced sections with subtle dividers"。
- **中文文字尽量短**：图像模型对长串中文渲染不稳，每条标语 4-10 字、解释 15-30 字是相对安全的范围。
- **配色别贪多**：2-3 个主色 + 留白，是现代信息图的核心。4 个以上颜色会显得花。

## 配色参考（可直接挑一组用）

- 专业商务：`deep navy #1B2A4E + warm orange #F4A261 + off-white #FAF7F2`
- 清新教育：`forest green #2D6A4F + cream #FEFAE0 + soft coral #E76F51`
- 极简科技：`charcoal #2B2D42 + electric blue #4361EE + light gray #EDF2F4`
- 温暖手账：`warm brown #6F4E37 + butter yellow #F4D35E + paper white #FFF8E7`
- 小红书风：`hot pink #E63946 + cream #F1FAEE + soft mint #A8DADC`

如果用户没特别要求，根据主题氛围挑一组：教程类用清新教育/极简科技，生活类用温暖手账/小红书风，商业类用专业商务。
