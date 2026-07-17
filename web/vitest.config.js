import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  test: {
    environment: 'node',
    globals: false,
    include: ['src/tests/**/*.test.js'],
    exclude: ['e2e/**', 'node_modules/**'],
  },
})
