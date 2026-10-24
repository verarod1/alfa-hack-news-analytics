import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // TODO: При локальном запуске реального backend запросы /api/v1 проксируются на порт 8000.
  // Если backend работает на другом адресе, укажите его через VITE_DEV_API_TARGET.
  server: {
    proxy: {
      '/api': {
        target: process.env.VITE_DEV_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
