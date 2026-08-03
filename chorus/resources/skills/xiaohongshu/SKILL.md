---
name: xiaohongshu
description: 小红书（xiaohongshu）图文笔记创作包。当创作意图的 platform 为小红书、红书或 XHS 时使用。提供竖版轮播图、短标题短文案、话题标签和小红书网页端左右分栏详情预览；各子 Agent 只读取自己的 references 文件。
---

# 小红书（xiaohongshu）

把创作意图转成适合小红书图文笔记发布的 PostCard。成品以一组可横向滑动阅读的竖版图片为主，文字承担钩子、补充说明与互动引导；预览采用小红书网页端的左右分栏笔记详情弹窗。不要把网页长文原样搬运过来：小红书成品只表达标题、扁平正文和图片，不把 Markdown 富文本当作可见样式。

## 使用原则

- 用户已经确认的主题、受众、语气、图片数量和商业信息优先于本包默认值。
- system prompt 里的产出协议是后端解析硬约束；本 Skill 只决定小红书的平台内容取舍和视觉规格。
- 默认制作**图文笔记**。账号是否拥有“写长文”等功能并不确定，不把该功能作为必要前提。
- 内容应真实、可核验且具备具体价值；不虚构体验、数据、价格、效果或身份背书，也不使用夸大承诺替代内容。
- 只读取当前角色的参考文件，不加载其它角色的细节。

## 按角色读取

- idea：`references/planning.md`
- script：`references/script.md`
- image：`references/image.md`
- finalize：`references/finalize.md`

## 预览资源

- `preview/desktop.html`
- `preview/desktop.css`

预览文件由前端读取。子 Agent 不读它们的内容，汇总官只按 `references/finalize.md` 把资源引用写入成品 front matter。

预览模板自行提供带 `data-preview-close` 属性的关闭按钮；外层预览宿主统一接收该动作并关闭弹窗。
