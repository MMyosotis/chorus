import { defineConfig } from '@playwright/test'

// 前端 E2E：依赖外部已起服务（./scripts/start.sh），文本断言不截图。
// 跑真 LLM 需 .env 配齐 key；跑前先 ./scripts/start.sh，不自起避免误杀在跑服务。
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  use: {
    baseURL: 'http://localhost:5173',
    actionTimeout: 10_000,
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
})
