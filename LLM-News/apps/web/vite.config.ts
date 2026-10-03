/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The FastAPI backend; in Docker, nginx does the same proxying (see nginx.conf).
// changeOrigin: false keeps the browser's Host header, so share previews and RSS links point at this site
// (Vite's plain-string shorthand would rewrite it to the backend's address).
const backend = { target: process.env.BACKEND_URL ?? 'http://127.0.0.1:8000', changeOrigin: false }

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': backend,
      '/static': backend,
      '/share': backend,
      '/feed.xml': backend,
    },
  },
  test: {
    include: ['src/**/*.test.ts'],
  },
})
