---
name: web-blog
description: 网页博客（web-blog）平台创作包。当创作意图的 platform 为网页博客，或用户未指定平台而需要默认长文渲染时使用。提供长文结构、配图规格、PostCard 装配策略和预览资源引用；各子 Agent 只读取自己的 references 文件。
---

# 网页博客（web-blog）

把创作意图转成可由 Chorus 统一 PostCard 渲染的网页博客长文。

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

预览文件由前端读取。子 Agent 不读它们的内容，汇总官只按 `references/finalize.md` 抄写资源引用。
