import { expect, test } from 'vitest';
import { consumeEvents } from '../../src/lib/api/sse';
const event = { event: 'clarification', conversation_id: 'c', run_id: 'r', question: 'What cuisine? 🍚' };
test('POST stream handles split UTF-8, CRLF, heartbeats and terminal event', async () => {
  const data = new TextEncoder().encode(`: heartbeat\r\n\r\nevent: clarification\r\ndata: ${JSON.stringify(event)}\r\n\r\nevent: done\ndata: ${JSON.stringify({ event: 'done', conversation_id: 'c', run_id: 'r', outcome: 'clarification' })}\n\n`);
  const stream = new ReadableStream<Uint8Array>({ start(c) { for (const byte of data) c.enqueue(new Uint8Array([byte])); c.close(); } });
  const received: unknown[] = [];
  await consumeEvents(new Response(stream), 'c', (e) => received.push(e));
  expect(received).toHaveLength(2); expect(received[0]).toEqual(event);
});
test('unterminated streams and mismatched correlation cannot count as completion', async () => {
  await expect(consumeEvents(new Response(`data: ${JSON.stringify(event)}\n\n`), 'c', () => {})).rejects.toThrow('interrupted');
  await expect(consumeEvents(new Response(`data: ${JSON.stringify(event)}\n\n`), 'stranger', () => {})).rejects.toThrow('correlation');
});
