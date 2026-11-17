import { defineConfig } from '@playwright/test';
import { existsSync } from 'node:fs';

const systemChromium = '/usr/bin/chromium';
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 20_000,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:8765',
    browserName: 'chromium',
    launchOptions: existsSync(systemChromium) ? { executablePath: systemChromium, args: ['--no-sandbox'] } : {},
  },
  webServer: {
    command: `${process.env.ARCHMIND_PYTHON ?? (existsSync('../.venv/bin/python') ? '../.venv/bin/python' : 'python')} ../scripts/e2e_server.py`,
    url: 'http://127.0.0.1:8765/api/v1/projects',
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
