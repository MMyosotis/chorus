---
name: web-blog
description: 网页博客（web-blog）平台创作包。当创作意图的 platform 为网页博客，或用户未指定平台而需要默认长文渲染时使用。提供长文结构、配图规格、PostCard 装配策略和浏览器式网页阅读预览；各子 Agent 只读取自己的 references 文件。
---

# 网页博客（web-blog）

把创作意图转成可由 Chorus 统一 PostCard 渲染的网页博客长文。预览采用固定横向浏览器卡片：浏览器顶部和站点导航固定，正文区域在卡片内纵向滚动，呈现真实网页阅读体验。

## 使用原则

- 用户已确认的意图优先于本包默认值。
- system prompt 里的产出协议是后端解析硬约束；本 Skill 只决定网页博客的内容取舍和平台规格。
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
