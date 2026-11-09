import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/*
 * VITE_API_BASE 默认直接指向后端 http://127.0.0.1:8000/api/v1。
 * 如果后端不方便开 CORS，可以把 VITE_API_BASE 设成相对路径 /api/v1，
 * 由下面的 dev proxy 转发到 VITE_PROXY_TARGET。
 */
const proxyTarget = process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api/v1': {
        target: proxyTarget,
        changeOrigin: true,
      },
    },
  },
})
