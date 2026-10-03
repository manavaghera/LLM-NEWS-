import path from 'node:path'
import { defineConfig, devices } from '@playwright/test'

// Browser tests against the real backend and frontend, using the fixed news in e2e/fixtures/static.
// No AI key is passed, so nothing costs money and the AI features show their "not configured" states.
// Python: set PYTHON to the backend's interpreter, relative to this folder, e.g.
// PYTHON=../.venv/Scripts/python on Windows. Defaults to `python` on the PATH.
const python = process.env.PYTHON ? JSON.stringify(path.resolve(process.env.PYTHON)) : 'python'
const BACKEND_PORT = 8010
const WEB_PORT = 5180

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --app-dir ../../.. --host 127.0.0.1 --port ${BACKEND_PORT}`,
      cwd: './e2e/fixtures',
      url: `http://127.0.0.1:${BACKEND_PORT}/api/health`,
      env: {
        CACHE_DIR: '../.cache',
        AI_RATE_LIMIT: '1000',
        // Empty keys win over any real ones in ../.env (dotenv never overrides set variables)
        OPENROUTER_API_KEY: '', OPENAI_API_KEY: '', ALIBABA_LLM_KEY: '', GEMINI_API_KEY: '', PERPLEXITY_API_KEY: '',
      },
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      env: { BACKEND_URL: `http://127.0.0.1:${BACKEND_PORT}` },
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
