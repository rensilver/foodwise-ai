import { requireOk, type StreamEvent } from './client';
/** Framing only; the API owns culinary validation. Never replay POSTs. */
export async function consumeEvents(response: Response, conversation: string, receive: (event: StreamEvent) => void): Promise<void> {
  await requireOk(response);
  if (!response.body) throw new Error('Connection interrupted.');
  const reader = response.body.getReader(); const decoder = new TextDecoder();
  let pending = ''; let run: string | undefined; let done = false;
  try {
    while (!done) {
      const chunk = await reader.read();
      pending += decoder.decode(chunk.value, { stream: !chunk.done });
      if (pending.length > 2_000_000) throw new Error('Response exceeds the stream limit.');
      let boundary: RegExpExecArray | null;
      while ((boundary = /\r?\n\r?\n/.exec(pending))) {
        const frame = pending.slice(0, boundary.index); pending = pending.slice(boundary.index + boundary[0].length);
        const lines = frame.split(/\r?\n/);
        const data = lines.filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trimStart()).join('\n');
        if (!data) continue;
        const value: unknown = JSON.parse(data);
        if (!value || typeof value !== 'object' || !('event' in value) || !['progress','clarification','recommendations','error','done'].includes(String(value.event))) throw new Error('Invalid stream event.');
        const event = value as StreamEvent;
        const named = lines.find((line) => line.startsWith('event:'))?.slice(6).trim();
        if (named && named !== event.event) throw new Error('Invalid stream event.');
        if (event.conversation_id !== conversation || typeof event.run_id !== 'string' || (run && run !== event.run_id)) throw new Error('Invalid stream correlation.');
        run = event.run_id; receive(event); done = event.event === 'done';
        if (done) break;
      }
      if (chunk.done && !done) throw new Error('Connection interrupted.');
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
