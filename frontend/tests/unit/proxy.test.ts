import { expect, test, vi, afterEach } from "vitest";
import { proxy } from "../../src/app/api/v1/proxy";
afterEach(() => vi.unstubAllGlobals());
test("proxy preserves cookies, origin, CSRF, errors and separate Set-Cookie headers", async () => {
  const upstream = vi.fn(async () => new Response('invalid', { status: 409, headers: { 'set-cookie': 'foodwise_admin=x; Path=/api/v1/admin; HttpOnly; SameSite=Strict', 'x-request-id': 'opaque-id' } }));
  vi.stubGlobal('fetch', upstream);
  const response = await proxy(new Request('http://localhost:3000/api/v1/admin/recipes', { method: 'POST', headers: { origin: 'http://localhost:3000', cookie: 'foodwise_admin=x', 'x-csrf-token': 'csrf' }, body: '{}' }), ['admin','recipes']);
  expect(response.status).toBe(409);
  expect(response.headers.get('set-cookie')).toContain('Path=/api/v1/admin');
  expect(response.headers.get('x-request-id')).toBe('opaque-id');
  const options = upstream.mock.calls[0] as unknown as [URL, RequestInit];
  expect(new Headers(options[1].headers).get('origin')).toBe('http://localhost:3000');
  expect(new Headers(options[1].headers).get('x-csrf-token')).toBe('csrf');
});
test("SSE stays unbuffered and cancelling response aborts upstream", async () => {
  let signal: AbortSignal | undefined;
  vi.stubGlobal('fetch', vi.fn(async (_url, options) => { signal = options.signal; return new Response(new ReadableStream({ start(c) { c.enqueue(new TextEncoder().encode(': heartbeat\n\n')); } }), { headers: { 'content-type': 'text/event-stream' } }); }));
  const response = await proxy(new Request('http://localhost:3000/api/v1/conversations/c/messages'), ['conversations','c','messages']);
  expect(response.headers.get('x-accel-buffering')).toBe('no');
  const reader = response.body!.getReader();
  expect(new TextDecoder().decode((await reader.read()).value)).toContain('heartbeat');
  await reader.cancel();
  expect(signal?.aborted).toBe(true);
});
test("proxy rejects traversal and cannot redirect to arbitrary hosts", async () => {
  const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
  expect((await proxy(new Request('http://localhost:3000/api/v1/media'), ['..','media'])).status).toBe(400);
  expect(fetcher).not.toHaveBeenCalled();
});
