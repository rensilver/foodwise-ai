import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, test, vi } from 'vitest';
import { ImageAttachment } from '../../src/features/chat/image-attachment';
afterEach(() => vi.unstubAllGlobals());
test('only a completed media receipt can be sent; draft removal detaches without deleting', async () => {
  URL.createObjectURL = vi.fn(() => 'blob:preview'); URL.revokeObjectURL = vi.fn();
  const fetcher = vi.fn(async () => Response.json({ id: 'owned-image', width: 2, height: 2, mime_type: 'image/png', byte_size: 10 }));
  vi.stubGlobal('fetch', fetcher); const change = vi.fn();
  render(<ImageAttachment onChange={change} />);
  fireEvent.change(screen.getByLabelText('Add image'), { target: { files: [new File(['png'], 'meal.png', { type: 'image/png' })] } });
  await waitFor(() => expect(screen.getByText('Image ready.')).toBeVisible());
  expect(change).toHaveBeenLastCalledWith('owned-image', false);
  fireEvent.click(screen.getByRole('button', { name: 'Remove image' }));
  expect(change).toHaveBeenLastCalledWith(undefined, false);
  expect(fetcher).toHaveBeenCalledTimes(1); expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview');
});
test('unsupported and oversized attachments block send and offer removal', () => {
  const change = vi.fn(); render(<ImageAttachment onChange={change} />);
  fireEvent.change(screen.getByLabelText('Add image'), { target: { files: [new File(['svg'], 'bad.svg', { type: 'image/svg+xml' })] } });
  expect(screen.getByRole('alert')).toHaveTextContent('JPEG, PNG or WebP');
  expect(change).toHaveBeenLastCalledWith(undefined, true);
});
