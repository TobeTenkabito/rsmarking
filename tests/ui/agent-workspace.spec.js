import { test, expect } from '@playwright/test';

test('desktop: visible history, Markdown, keyboard modes and autosave', async ({ page }) => {
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/tests/ui/agent-preview.html');
    await expect(page.locator('.ai-history')).toBeVisible();
    await page.locator('[data-ai-open-chat]').first().click();
    await expect(page.locator('.ai-markdown table')).toBeVisible();
    await expect(page.locator('.ai-markdown ol ul')).toBeVisible();
    await page.screenshot({ path: 'test-results/agent-desktop.png' });
    await page.locator('[data-ai-new-chat]').click();
    const input = page.locator('#ai-prompt-input');
    await input.fill('hello'); await input.press('Control+Enter');
    await expect(input).toHaveValue('hello\n');
    await input.press('Enter');
    await expect(page.locator('.ai-message-assistant h2')).toHaveText('已完成');
    await expect(page.locator('#ai-save-status')).toHaveText('已保存');
    await page.selectOption('#ai-send-mode', 'ctrl-enter');
    await input.fill('second'); await input.press('Enter');
    await expect(input).toHaveValue('second\n');
    await input.press('Control+Enter');
    await expect(page.locator('.ai-message-assistant')).toHaveCount(2);
    await expect.poll(() => page.evaluate(() => window.__calls.length)).toBe(2);
    expect(errors).toEqual([]);
});

test('mobile: history stays accessible and composer remains inside viewport', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/tests/ui/agent-preview.html');
    await page.locator('[data-ai-open-chat]').first().click();
    await expect(page.locator('.ai-history')).toBeVisible();
    await expect(page.locator('#ai-execute-btn')).toBeVisible();
    const box = await page.locator('#ai-window').boundingBox();
    expect(box.width).toBeLessThanOrEqual(390);
    const send = await page.locator('#ai-execute-btn').boundingBox();
    expect(send.x + send.width).toBeLessThanOrEqual(390);
    expect(send.y + send.height).toBeLessThanOrEqual(844);
    await page.screenshot({ path: 'test-results/agent-mobile.png' });
});
