import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const assignedPort = process.env.PORT ? Number(process.env.PORT) : 5173

export default defineConfig({
  plugins: [vue()],
  server: {
    port: assignedPort,
    strictPort: !!process.env.PORT,
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
})
