import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { expect, test, vi, afterEach } from 'vitest';
import { AdminWorkspace } from '../../src/features/catalog/admin-workspace';
afterEach(() => vi.unstubAllGlobals());
test('extraction preview never saves automatically, login token stays in memory', async () => {
  const calls: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string) => { calls.push(url); if (url.endsWith('/session')) return Response.json({ csrf_token: 'csrf', expires_at: '2099-01-01T00:00:00Z' }); if (url.includes('/preview')) return Response.json({ status: 'validated', fields: { name: 'Basil cafe', cuisine: 'Italian' } }); return Response.json({ items: [], total: 0, limit: 100, offset: 0 }); }));
  render(<AdminWorkspace />);
  fireEvent.change(screen.getByLabelText('Administrator password'), { target: { value: 'local-test' } }); fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  await waitFor(() => expect(screen.getByRole('button', { name: 'Sign out' })).toBeVisible());
  fireEvent.change(screen.getByLabelText('Unstructured description'), { target: { value: 'Basil cafe serves Italian food.' } });
  fireEvent.click(screen.getByRole('button', { name: 'Preview fields' }));
  await waitFor(() => expect(screen.getByLabelText('Name')).toHaveValue('Basil cafe'));
  expect(calls.filter((url) => url === '/api/v1/admin/restaurants')).toHaveLength(0);
  expect(localStorage.getItem('csrf')).toBeNull();
});
test('version conflicts keep unsaved fields and require explicit review', async () => {
  let patched = false;
  const entry = { data: { id: 'cafe', name: 'Original cafe', source_id: 'fixture', source_record_id: 'cafe' }, version: 1, citations: [], images: [], synthetic: true };
  vi.stubGlobal('fetch', vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith('/session')) return Response.json({ csrf_token: 'csrf', expires_at: '2099-01-01T00:00:00Z' });
    if (options?.method === 'PATCH') { patched = true; return Response.json({ error: { code: 'conflict', message: 'Conflict' } }, { status: 409 }); }
    if (url.endsWith('/cafe')) return Response.json(patched ? { ...entry, version: 2, data: { ...entry.data, name: 'Latest cafe' } } : entry);
    return Response.json({ items: [entry], total: 1, limit: 100, offset: 0 });
  }));
  render(<AdminWorkspace />); fireEvent.change(screen.getByLabelText('Administrator password'), { target: { value: 'local-test' } }); fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
  await waitFor(() => expect(screen.getByLabelText('Existing entry')).toBeVisible());
  fireEvent.change(screen.getByLabelText('Existing entry'), { target: { value: 'cafe' } });
  await waitFor(() => expect(screen.getByLabelText('Name')).toHaveValue('Original cafe'));
  fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'My draft' } }); fireEvent.click(screen.getByRole('button', { name: 'Save changes' }));
  await waitFor(() => expect(screen.getByRole('heading', { name: 'Latest record: Latest cafe, version 2' })).toBeVisible());
  expect(screen.getByLabelText('Name')).toHaveValue('My draft'); expect(screen.getByRole('button', { name: 'Save changes' })).toBeDisabled();
  fireEvent.click(screen.getByRole('button', { name: 'Keep my draft with latest version' })); expect(screen.getByLabelText('Name')).toHaveValue('My draft'); expect(screen.getByRole('button', { name: 'Save changes' })).toBeEnabled();
});
