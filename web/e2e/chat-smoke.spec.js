// 闲聊路径 smoke：发消息 -> 助手气泡正文到达。
// 真 LLM，需 .env 配齐 key。文本断言不截图。
import { test, expect } from '@playwright/test'

test('闲聊：发送消息后助手正文到达', async ({ page }) => {
  await page.goto('/')
  // 侧栏新建按钮起一个干净会话
  await page.getByRole('button', { name: '新建稿件' }).click()
  // 修改意见输入框填消息
  await page.locator('textarea.input-field').fill('你好，用一句话回答')
  await page.getByRole('button', { name: '发送' }).click()
  // 助手正文落地即视为通路
  await expect(page.locator('.bubble.assistant .text').first()).toBeVisible({ timeout: 60_000 })
})
