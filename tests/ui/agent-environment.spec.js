import { test, expect } from '@playwright/test';

test('round environment button opens provider settings, saves without a model request, and restores .env', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto('/tests/ui/agent-preview.html');
    const button = page.locator('[data-ai-environment]');
    await expect(button).toBeVisible();
    expect(await button.evaluate(element => getComputedStyle(element).borderRadius)).toBe('50%');
    await button.click();
    const dialog = page.locator('#ai-environment-dialog');
    await expect(dialog).toBeVisible();
    await expect(page.locator('#ai-environment-source')).toContainText('.env');
    await page.locator('#ai-environment-provider').selectOption('deepseek');
    await expect(page.locator('#ai-environment-base')).toHaveValue('https://api.deepseek.com');
    await page.locator('#ai-environment-model').fill('test-model');
    await page.locator('#ai-environment-key').fill('fake-ui-key-never-used');
    await page.locator('#ai-environment-save').click();
    await expect(page.locator('#ai-environment-status')).toContainText('已保存');
    await expect(page.locator('#ai-environment-key')).toHaveValue('');
    expect(await page.evaluate(() => window.__environmentCalls[0].provider)).toBe('deepseek');
    expect(await page.evaluate(() => window.__calls.length)).toBe(0);
    expect(await page.evaluate(() => JSON.stringify(localStorage))).not.toContain('fake-ui-key');
    await page.screenshot({ path: 'test-results/agent-environment-desktop.png' });
    await page.keyboard.press('Escape');
    await expect(dialog).not.toBeVisible();
    await expect(button).toBeFocused();
    await expect(page.locator('#ai-modal')).toBeVisible();
    await button.click();
    await expect(page.locator('#ai-environment-provider')).toHaveValue('deepseek');
    await page.locator('#ai-environment-reset').click();
    await expect(page.locator('#ai-environment-source')).toContainText('.env');
    await expect(page.locator('#ai-environment-key')).toHaveValue('');
});

test('environment dialog fits the mobile viewport and retains an accessible circular launcher', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.goto('/tests/ui/agent-preview.html');
    await page.locator('[data-ai-environment]').click();
    const dialog = page.locator('#ai-environment-dialog');
    await expect(dialog).toBeVisible();
    await expect(page.locator('#ai-environment-save')).toBeEnabled();
    const bounds = await dialog.boundingBox();
    expect(bounds.x).toBeGreaterThanOrEqual(0);
    expect(bounds.x + bounds.width).toBeLessThanOrEqual(390);
    expect(bounds.y + bounds.height).toBeLessThanOrEqual(844);
    await page.screenshot({ path: 'test-results/agent-environment-mobile.png' });
    await page.locator('[data-environment-close]').click();
    await expect(page.locator('[data-ai-environment]')).toBeFocused();
});
