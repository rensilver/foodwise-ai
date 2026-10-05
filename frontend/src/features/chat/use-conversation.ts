"use client";
import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, type Schema, type StreamEvent } from '../../lib/api/client';
import { consumeEvents } from '../../lib/api/sse';
export function useConversation(initialId?: string) {
  const [id, setId] = useState(initialId);
  const [history, setHistory] = useState<Schema['HistoryResponse']>();
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(!!initialId);
  const [error, setError] = useState('');
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const locked = useRef(false); const controller = useRef<AbortController | null>(null);
  const refresh = useCallback(async (identity: string, signal?: AbortSignal) => {
    const saved = await api('/api/v1/conversations/{conversation_id}', 'get', { params: { conversation_id: identity }, signal });
    setHistory(saved); return saved;
  }, []);
  useEffect(() => {
    const abort = new AbortController();
    if (initialId) void Promise.resolve().then(() => refresh(initialId, abort.signal)).catch((e) => { if (!abort.signal.aborted) setError(e instanceof Error ? e.message : 'Conversation unavailable.'); }).finally(() => { if (!abort.signal.aborted) setLoading(false); });
    return () => { abort.abort(); controller.current?.abort(); };
  }, [initialId, refresh]);
  async function send(categories: Schema['Category'][], explicit?: Schema['PreferenceUpdate'], mediaId?: string) {
    if (locked.current || loading || !draft.trim()) return;
    locked.current = true; setBusy(true); setError(''); setEvents([]);
    const abort = new AbortController(); controller.current = abort;
    let identity = id;
    try {
      if (!identity) { identity = (await api('/api/v1/conversations', 'post', { signal: abort.signal })).id; setId(identity); window.history.replaceState(null, '', `/conversations/${identity}`); }
      const body: Schema['MessageSubmission'] = { message: draft, categories, client_request_id: crypto.randomUUID(), ...(explicit ? { explicit } : {}), ...(mediaId ? { media_id: mediaId } : {}) };
      const response = await fetch(`/api/v1/conversations/${encodeURIComponent(identity)}/messages`, { method: 'POST', credentials: 'same-origin', headers: { 'content-type': 'application/json', accept: 'text/event-stream' }, body: JSON.stringify(body), signal: abort.signal });
      await consumeEvents(response, identity, (event) => setEvents((previous) => [...previous, event]));
      await refresh(identity); setDraft(''); return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : abort.signal.aborted ? 'Request stopped. Your draft is available to send again.' : 'Connection interrupted. Checking saved conversation.');
      if (identity) await refresh(identity).catch(() => setError('Saved conversation could not be loaded. Try loading history before sending again.'));
    } finally { locked.current = false; controller.current = null; setBusy(false); }
  }
  function startNew() { if (locked.current) return; setId(undefined); setHistory(undefined); setEvents([]); setError(''); setDraft(''); window.history.replaceState(null, '', '/'); }
  async function deleteConversation() {
    if (!id || locked.current) return;
    try { const result = await api('/api/v1/conversations/{conversation_id}', 'delete', { params: { conversation_id: id } }); startNew(); if (result.cleanup_pending) setError('Conversation deleted. Some image file cleanup is still pending.'); } catch (e) { setError(e instanceof Error ? e.message : 'Deletion failed.'); }
  }
  return { id, history, draft, setDraft, busy, loading, error, events, send, startNew, deleteConversation, stop: () => controller.current?.abort() };
}
