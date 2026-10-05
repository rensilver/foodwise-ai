import { expect, test } from '@playwright/test';
import { PRODUCT_NAME } from '../../src/lib/product';
test('production workspace serves local fonts, branding and liveness', async ({ page, request }) => {
  const browserErrors: string[] = []; page.on('pageerror', (error) => browserErrors.push(error.message));
  await page.goto('/'); await expect(page).toHaveTitle(PRODUCT_NAME); await expect(page.getByRole('heading', { name: 'What sounds good?' })).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  expect(await page.evaluate(async () => { await document.fonts.ready; return document.fonts.check('600 40px Bricolage') && document.fonts.check('400 16px "Source Sans"'); })).toBe(true);
  expect(browserErrors).toEqual([]); expect(await (await request.get('/health/live')).json()).toEqual({ status: 'alive' });
});
