import { defineConfig } from '@playwright/test'

const baseURL = process.env.LAB_BASE_URL || 'http://127.0.0.1:8765'
export default defineConfig({
  testDir: './tests',
  retries: 0,
  use: {
    baseURL,
    channel: process.env.LAB_BROWSER_CHANNEL || undefined,
    viewport: { width: 390, height: 844 },
  },
  webServer: process.env.LAB_BASE_URL ? undefined : {
    command: `${process.env.LAB_PYTHON || 'python'} -m uvicorn lab.api:app --host 127.0.0.1 --port 8765`,
    cwd: '..',
    url: baseURL + '/healthz',
    timeout: 60_000,
  },
})
