import { defineConfig } from '@playwright/test';

export default defineConfig({
    testDir: './tests/ui',
    workers: 1,
    use: { baseURL: 'http://127.0.0.1:4178', channel: 'msedge', headless: true },
    webServer: { command: 'node tests/ui/serve.mjs', url: 'http://127.0.0.1:4178/tests/ui/agent-preview.html', reuseExistingServer: false },
});
