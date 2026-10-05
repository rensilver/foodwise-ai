import { expect, test, type Page } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import { database, providerCounts } from './database';
async function send(page: Page, message: string) { await page.getByLabel('Message', { exact: true }).fill(message); await page.getByRole('button', { name: 'Send', exact: true }).click(); await expect(page.getByRole('button', { name: 'Stop', exact: true })).toBeHidden({ timeout: 30_000 }); }
function conversation(page: Page) { return new URL(page.url()).pathname.split('/').at(-1)!; }
async function signIn(page: Page) { await page.goto('/admin'); await page.getByLabel('Administrator password').fill('phase9-fixture-password'); await page.getByRole('button', { name: 'Sign in', exact: true }).click(); await expect(page.getByRole('button', { name: 'Sign out', exact: true })).toBeVisible(); }
test('text results, citations, refresh, retained restrictions and explicit corrections persist', async ({ page, browser }, info) => {
  await page.goto('/'); await page.getByRole('radio', { name: 'Cook', exact: true }).check(); await send(page, 'Classic Margherita Pizza');
  await expect(page.getByRole('heading', { name: 'Classic Margherita Pizza', exact: true })).toBeVisible();
  const id = conversation(page); const before = providerCounts().profile_calls;
  expect(database('SELECT count(*) FROM messages WHERE conversation_id=%s', [id])).toEqual([[2]]);
  await page.getByText('Sources (', { exact: false }).first().click(); await expect(page.locator('blockquote').first()).toContainText('Classic Margherita Pizza');
  await page.screenshot({ path: info.outputPath('real-text-sources.png'), fullPage: true });
  await page.reload(); await expect(page.getByRole('heading', { name: 'Classic Margherita Pizza', exact: true })).toBeVisible(); expect(providerCounts().profile_calls).toBe(before);
  const stranger = await browser.newContext(); const foreign = await stranger.request.get(`http://127.0.0.1:3100/api/v1/conversations/${id}`); expect(foreign.status()).toBe(404); await stranger.close();
  await page.getByText('Edit preferences', { exact: true }).click(); await page.getByLabel('Restriction', { exact: true }).fill('milk'); await page.getByRole('button', { name: 'Add restriction', exact: true }).click();
  await expect(page.getByText('Pending changes apply', { exact: false })).toBeVisible(); await send(page, 'Classic Margherita Pizza');
  await expect(page.getByText('No supported matches.', { exact: false }).last()).toBeVisible();
  expect(database("SELECT preferences->'constraints'->0->>'value' FROM profiles WHERE conversation_id=%s", [id])).toEqual([['milk']]);
  await send(page, 'another pizza'); await expect(page.getByText('milk (allergen, explicit)')).toBeVisible();
  await page.getByRole('button', { name: 'Remove milk', exact: true }).click(); await send(page, 'Classic Margherita Pizza');
  expect(database("SELECT jsonb_array_length(preferences->'constraints') FROM profiles WHERE conversation_id=%s", [id])).toEqual([[0]]);
  await expect(page.getByRole('heading', { name: 'Classic Margherita Pizza', exact: true }).last()).toBeVisible();
  await page.getByRole('button', { name: 'Delete conversation', exact: true }).click(); await page.getByRole('button', { name: 'Confirm deletion', exact: true }).click(); await expect(page).toHaveURL('http://127.0.0.1:3100/');
  expect(database('SELECT count(*) FROM messages WHERE conversation_id=%s', [id])).toEqual([[0]]);
});
test('image recommendations use real CLIP, owned uploads and matching catalog imagery on mobile', async ({ page, browser }, info) => {
  await page.setViewportSize({ width: 390, height: 844 }); await page.goto('/'); await page.getByRole('radio', { name: 'Cook', exact: true }).check();
  let uploaded: string | undefined;
  page.on('response', async (response) => { if (response.url().endsWith('/api/v1/media') && response.request().method() === 'POST' && response.status() === 201) uploaded = (await response.json()).id; });
  await page.getByLabel('Message', { exact: true }).fill('Classic Margherita Pizza');
  await page.getByLabel('Add image', { exact: true }).setInputFiles({ name: 'broken.png', mimeType: 'image/png', buffer: Buffer.from('invalid image') }); await expect(page.getByRole('main').getByRole('alert')).toContainText('request is invalid'); await expect(page.getByRole('button', { name: 'Send', exact: true })).toBeDisabled(); await expect(page.getByLabel('Message', { exact: true })).toHaveValue('Classic Margherita Pizza');
  await page.getByLabel('Add image', { exact: true }).setInputFiles('../data/synthetic_recipe_images/recipe1.png'); await expect(page.getByText('Image ready.', { exact: true })).toBeVisible();
  await send(page, 'Classic Margherita Pizza'); await expect(page.getByRole('heading', { name: 'Classic Margherita Pizza', exact: true })).toBeVisible();
  const image = page.getByRole('img', { name: 'Catalog image associated with Classic Margherita Pizza' }); await expect(image).toBeVisible(); await expect(image).toHaveAttribute('src', /recipes\/1\/images\/course-recipe1-image/);
  await expect.poll(() => image.evaluate((node) => (node as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
  const id = conversation(page); const history = await (await page.request.get(`/api/v1/conversations/${id}`)).json();
  expect(history.messages.at(-1).payload.evidence.some((e: { image_score?: number }) => typeof e.image_score === 'number')).toBe(true);
  expect(database('SELECT count(*) FROM conversation_media WHERE conversation_id=%s', [id])).toEqual([[1]]);
  const stranger = await browser.newContext(); await stranger.request.post('http://127.0.0.1:3100/api/v1/conversations'); expect((await stranger.request.get(`http://127.0.0.1:3100/api/v1/media/${uploaded}`)).status()).toBe(404); await stranger.close();
  expect((await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze()).violations).toEqual([]);
  await page.screenshot({ path: info.outputPath('real-image-mobile.png'), fullPage: true });
  await page.getByRole('button', { name: 'Delete conversation', exact: true }).click(); await page.getByRole('button', { name: 'Confirm deletion', exact: true }).click(); await expect(page).toHaveURL('http://127.0.0.1:3100/');
  expect((await page.request.get(`/api/v1/media/${uploaded}`)).status()).toBe(404);
});
test('stop and page disconnect cancel upstream work; refresh never replays inference', async ({ page }, info) => {
  await page.goto('/'); await page.getByLabel('Message', { exact: true }).fill('Pause this request'); await page.getByRole('button', { name: 'Send', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Understanding your request' })).toBeVisible(); const id = conversation(page); const before = providerCounts();
  const blocked = await page.request.post(`/api/v1/conversations/${id}/messages`, { data: { message: 'concurrent', client_request_id: crypto.randomUUID() } }); expect(blocked.status()).toBe(409); expect((await page.request.delete(`/api/v1/conversations/${id}`)).status()).toBe(409);
  await page.screenshot({ path: info.outputPath('real-pending.png'), fullPage: true }); await page.getByRole('button', { name: 'Stop', exact: true }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Request stopped'); await expect(page.getByLabel('Message', { exact: true })).toHaveValue('Pause this request');
  await expect.poll(() => providerCounts().cancelled_calls).toBeGreaterThan(before.cancelled_calls);
  expect(database('SELECT count(*) FROM messages WHERE conversation_id=%s', [id])).toEqual([[1]]);
  await page.reload(); await expect(page.locator('.message')).toContainText('Pause this request'); await expect(page.getByLabel('Message', { exact: true })).toHaveValue('Pause this request'); expect(providerCounts().profile_calls).toBe(before.profile_calls);
  await send(page, 'Clarify this request'); await expect(page.getByText('Which city would you like?', { exact: true })).toBeVisible();
  await page.getByLabel('Message', { exact: true }).fill('Pause second request'); await page.getByRole('button', { name: 'Send', exact: true }).click(); await expect(page.getByRole('status').filter({ hasText: 'Understanding your request' })).toBeVisible(); const second = providerCounts();
  await page.reload(); await expect.poll(() => providerCounts().cancelled_calls).toBeGreaterThan(second.cancelled_calls); expect(providerCounts().profile_calls).toBe(second.profile_calls);
});
test('real administrator preview/create/edit/conflict/delete changes become searchable and atomic', async ({ page }) => {
  const name = `Phase9 basil rice ${Date.now()}`; await signIn(page); await page.getByLabel('Entry category').selectOption('recipe');
  await page.getByText('Extract fields from a description', { exact: true }).click(); await page.getByLabel('Unstructured description').fill(`${name}. Italian.`); await page.getByRole('button', { name: 'Preview fields', exact: true }).click();
  await expect(page.getByLabel('Name', { exact: true })).toHaveValue(name); expect(database('SELECT count(*) FROM recipes WHERE name=%s', [name])).toEqual([[0]]);
  await page.getByLabel('Ingredients (one per line)').fill('rice\ntomato\nbasil'); await page.getByLabel('Directions (one per line)').fill('Simmer rice with tomato and basil.'); await page.getByRole('button', { name: 'Create recipe', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: `Saved ${name}` })).toBeVisible(); const rows = database('SELECT id, version FROM recipes WHERE name=%s', [name]) as [string, number][]; const [id, version] = rows[0]; expect(version).toBe(1);
  expect(database('SELECT count(*) FROM text_embeddings e JOIN documents d ON e.document_id=d.id JOIN source_records r ON d.source_record_id=r.id WHERE r.recipe_id=%s', [id])[0]).toEqual([1]);
  const search = await page.request.post('/api/v1/conversations'); const conversationId = (await search.json()).id;
  const result = await page.request.post(`/api/v1/conversations/${conversationId}/messages`, { data: { message: name, categories: ['recipe'], client_request_id: crypto.randomUUID() } }); expect(result.status()).toBe(200); expect(await result.text()).toContain(id);
  await page.getByLabel('Name', { exact: true }).fill(`${name} edited`); await page.getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(page.getByRole('status').filter({ hasText: 'version 2' })).toBeVisible();
  // A separate authorized browser creates a real optimistic-version conflict.
  const context = await page.context().browser()!.newContext(); const other = context.request; const grant = await other.post('http://127.0.0.1:3100/api/v1/admin/session', { headers: { origin: 'http://127.0.0.1:3100' }, data: { password: 'phase9-fixture-password' } });
  expect((await other.patch(`http://127.0.0.1:3100/api/v1/admin/recipes/${id}`, { headers: { origin: 'http://127.0.0.1:3100', 'x-csrf-token': (await grant.json()).csrf_token }, data: { expected_version: 2, fields: { cuisine: 'Californian' } } })).status()).toBe(200); await context.close();
  await page.getByLabel('Name', { exact: true }).fill(`${name} draft`); await page.getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(page.getByRole('heading', { name: /Latest record:.*version 3/ })).toBeVisible(); await expect(page.getByLabel('Name', { exact: true })).toHaveValue(`${name} draft`);
  await page.getByRole('button', { name: 'Keep my draft with latest version' }).click(); await page.getByRole('button', { name: 'Save changes', exact: true }).click(); await expect(page.getByRole('status').filter({ hasText: 'version 4' })).toBeVisible();
  const updated = await page.request.post(`/api/v1/conversations/${conversationId}/messages`, { data: { message: `${name} draft`, categories: ['recipe'], client_request_id: crypto.randomUUID() } }); expect(await updated.text()).toContain(`${name} draft`);
  await page.getByRole('button', { name: `Delete ${name} draft`, exact: true }).click(); await expect(page.getByRole('dialog')).toContainText(name); await page.getByRole('button', { name: 'Confirm deletion', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: `Deleted ${name} draft` })).toBeVisible(); expect(database('SELECT count(*) FROM recipes WHERE id=%s', [id])).toEqual([[0]]);
  expect(database('SELECT count(*) FROM documents d JOIN source_records r ON d.source_record_id=r.id WHERE r.recipe_id=%s', [id])).toEqual([[0]]);
  const afterDelete = await page.request.post(`/api/v1/conversations/${conversationId}/messages`, { data: { message: `${name} draft`, categories: ['recipe'], client_request_id: crypto.randomUUID() } });
  const frames = (await afterDelete.text()).split('\n\n').map((frame) => frame.split('\n').find((line) => line.startsWith('data: '))).filter(Boolean).map((line) => JSON.parse(line!.slice(6)));
  expect(frames.find((event) => event.event === 'recommendations').result.recommendations.some((item: { entity: { id: string } }) => item.entity.id === id)).toBe(false);
  await page.getByRole('button', { name: 'Sign out', exact: true }).click(); await expect(page.getByRole('button', { name: 'Sign in', exact: true })).toBeVisible();
});
