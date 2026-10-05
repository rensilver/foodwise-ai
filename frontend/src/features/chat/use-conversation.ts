"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  api,
  ApiError,
  type Schema,
  type StreamEvent,
} from "../../lib/api/client";
import { consumeEvents } from "../../lib/api/sse";
export function useConversation(initialId?: string) {
  const [id, setId] = useState(initialId);
  const [history, setHistory] = useState<Schema["HistoryResponse"]>();
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(!!initialId);
  const [recoveryNeeded, setRecoveryNeeded] = useState(false);
  const [error, setError] = useState("");
  const [resume, setResume] = useState<Schema["MessageSubmission"]>();
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const locked = useRef(false);
  const controller = useRef<AbortController | null>(null);
  const refresh = useCallback(
    async (identity: string, signal?: AbortSignal) => {
      const saved = await api(
        "/api/v1/conversations/{conversation_id}",
        "get",
        { params: { conversation_id: identity }, signal },
      );
      setHistory(saved);
      return saved;
    },
    [],
  );
  useEffect(() => {
    const abort = new AbortController();
    if (initialId)
      void Promise.resolve()
        .then(() => refresh(initialId, abort.signal))
        .then((saved) => {
          if (abort.signal.aborted) return;
          const last = saved.messages.at(-1);
          const user = saved.messages.findLast(
            (message) => message.role === "user",
          );
          if (
            user &&
            (last?.role === "user" || last?.payload?.event === "error")
          ) {
            setDraft(user.content ?? "");
            setResume(user.payload as Schema["MessageSubmission"] | undefined);
            setError(
              "No completed response is saved for the last request. Its draft is restored; sending again requires an explicit action.",
            );
          }
        })
        .catch((e) => {
          if (!abort.signal.aborted) {
            setError(
              e instanceof Error ? e.message : "Conversation unavailable.",
            );
            setRecoveryNeeded(true);
          }
        })
        .finally(() => {
          if (!abort.signal.aborted) setLoading(false);
        });
    return () => {
      abort.abort();
      controller.current?.abort();
    };
  }, [initialId, refresh]);
  async function send(
    categories: Schema["Category"][],
    explicit?: Schema["PreferenceUpdate"],
    mediaId?: string,
  ) {
    if (locked.current || loading || recoveryNeeded || !draft.trim()) return;
    locked.current = true;
    setBusy(true);
    setError("");
    setEvents([]);
    const abort = new AbortController();
    controller.current = abort;
    let identity = id;
    try {
      if (!identity) {
        identity = (
          await api("/api/v1/conversations", "post", { signal: abort.signal })
        ).id;
        setId(identity);
        window.history.replaceState(null, "", `/conversations/${identity}`);
      }
      const body: Schema["MessageSubmission"] = {
        message: draft,
        categories,
        client_request_id: crypto.randomUUID(),
        ...(explicit ? { explicit } : {}),
        ...(mediaId ? { media_id: mediaId } : {}),
      };
      const response = await fetch(
        `/api/v1/conversations/${encodeURIComponent(identity)}/messages`,
        {
          method: "POST",
          credentials: "same-origin",
          headers: {
            "content-type": "application/json",
            accept: "text/event-stream",
          },
          body: JSON.stringify(body),
          signal: abort.signal,
        },
      );
      let outcome: Schema["DoneEvent"]["outcome"] | undefined;
      await consumeEvents(response, identity, (event) => {
        setEvents((previous) => [...previous, event]);
        if (event.event === "done") outcome = event.outcome;
      });
      await refresh(identity);
      if (outcome === "completed" || outcome === "clarification") {
        setDraft("");
        setResume(undefined);
        return true;
      }
      setError(
        "The request did not complete. Your draft is available for explicit resubmission.",
      );
      return false;
    } catch (e) {
      setError(
        e instanceof ApiError
          ? e.message
          : abort.signal.aborted
            ? "Request stopped. Your draft is available to send again."
            : "Connection interrupted. Checking saved conversation.",
      );
      if (identity) {
        try {
          const saved = await refresh(identity);
          const final = saved.messages.at(-1);
          setError(
            `${e instanceof ApiError ? e.message : abort.signal.aborted ? "Request stopped." : "Connection interrupted."} ${final?.role === "assistant" ? "A saved response is shown below." : "No completed response is saved."} Your draft is preserved. Sending again requires an explicit action.`,
          );
        } catch {
          setRecoveryNeeded(true);
          setError(
            "Saved conversation could not be loaded. Load history before sending again.",
          );
        }
      }
    } finally {
      locked.current = false;
      controller.current = null;
      setBusy(false);
    }
  }
  function startNew() {
    if (locked.current) return;
    setId(undefined);
    setHistory(undefined);
    setResume(undefined);
    setEvents([]);
    setError("");
    setRecoveryNeeded(false);
    setDraft("");
    window.history.replaceState(null, "", "/");
  }
  async function deleteConversation() {
    if (!id || locked.current || loading) return false;
    locked.current = true;
    setBusy(true);
    try {
      const result = await api(
        "/api/v1/conversations/{conversation_id}",
        "delete",
        { params: { conversation_id: id } },
      );
      locked.current = false;
      startNew();
      if (result.cleanup_pending)
        setError(
          "Conversation deleted. Some image file cleanup is still pending.",
        );
      return true;
    } catch (e) {
      setError(e instanceof Error ? e.message : "Deletion failed.");
      return false;
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  async function recover() {
    if (!id) return;
    setLoading(true);
    try {
      await refresh(id);
      setRecoveryNeeded(false);
      setError("Saved history loaded. Your draft is available to send.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "History unavailable.");
    } finally {
      setLoading(false);
    }
  }
  return {
    resume,
    recoveryNeeded,
    recover,
    id,
    history,
    draft,
    setDraft,
    busy,
    loading,
    error,
    events,
    send,
    startNew,
    deleteConversation,
    stop: () => controller.current?.abort(),
  };
}
