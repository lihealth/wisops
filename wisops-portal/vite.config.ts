import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/dify-api': {
        target: 'http://localhost:5002',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/dify-api/, ''),
      },
      '/graph-api': {
        target: 'http://localhost:8021',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/graph-api/, ''),
      },
    },
  },
})
