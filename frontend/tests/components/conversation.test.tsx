import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { MealWorkspace } from '../../src/features/chat/meal-workspace';
afterEach(() => vi.unstubAllGlobals());
test('examples edit draft without sending; duplicate submits create one turn and load saved history', async () => {
  const id = '11111111-1111-4111-8111-111111111111';
  const question = { event: 'clarification', conversation_id: id, run_id: 'run', question: 'Which city?' };
  const fetcher = vi.fn(async (url: string, options?: RequestInit) => {
    if (url.endsWith('/messages')) return new Response(`data: ${JSON.stringify(question)}\n\ndata: ${JSON.stringify({ event: 'done', conversation_id: id, run_id: 'run', outcome: 'clarification' })}\n\n`);
    if (options?.method === 'POST') return Response.json({ id });
    return Response.json({ id, preferences: null, messages: [{ id: 'm', role: 'assistant', run_id: 'run', payload: question }] });
  });
  vi.stubGlobal('fetch', fetcher); render(<MealWorkspace />);
  fireEvent.click(screen.getByRole('button', { name: 'Find Italian restaurants in San Francisco' }));
  expect(screen.getByLabelText('Message')).toHaveValue('Find Italian restaurants in San Francisco'); expect(fetcher).not.toHaveBeenCalled();
  await act(async () => { fireEvent.submit(screen.getByLabelText('Message').closest('form')!); fireEvent.submit(screen.getByLabelText('Message').closest('form')!); });
  await waitFor(() => expect(screen.getByText('Which city?')).toBeVisible());
  expect(fetcher.mock.calls.filter(([url]) => url.endsWith('/messages'))).toHaveLength(1);
  expect(screen.getByRole('button', { name: 'Delete conversation' })).toBeVisible();
});
