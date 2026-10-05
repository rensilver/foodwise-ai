import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";
import { useConversation } from "../../src/features/chat/use-conversation";
afterEach(() => vi.unstubAllGlobals());
const id = "11111111-1111-4111-8111-111111111111";

test("an API rejection keeps its specific explanation after history recovery", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.endsWith("/messages")
        ? Response.json(
            {
              error: {
                code: "conflict",
                message: "Another turn is already active.",
              },
            },
            { status: 409 },
          )
        : Response.json({ id, preferences: null, messages: [] }),
    ),
  );
  const { result } = renderHook(() => useConversation(id));
  await waitFor(() => expect(result.current.loading).toBe(false));
  act(() => result.current.setDraft("pizza"));
  await act(async () => {
    await result.current.send(["recipe"]);
  });
  expect(result.current.error).toContain("Another turn is already active.");
  expect(result.current.draft).toBe("pizza");
});

test("deletion locks the conversation until the owned delete finishes", async () => {
  let finish: (value: Response) => void = () => {};
  const pending = new Promise<Response>((resolve) => {
    finish = resolve;
  });
  const fetcher = vi.fn(async (_url: string, options?: RequestInit) =>
    options?.method === "DELETE"
      ? pending
      : Response.json({ id, preferences: null, messages: [] }),
  );
  vi.stubGlobal("fetch", fetcher);
  const { result } = renderHook(() => useConversation(id));
  await waitFor(() => expect(result.current.loading).toBe(false));
  act(() => result.current.setDraft("pizza"));
  let deletion: Promise<unknown>;
  act(() => {
    deletion = result.current.deleteConversation();
  });
  expect(result.current.busy).toBe(true);
  await act(async () => {
    await result.current.send(["recipe"]);
    await result.current.deleteConversation();
  });
  expect(
    fetcher.mock.calls.filter(([, options]) => options?.method === "DELETE"),
  ).toHaveLength(1);
  expect(
    fetcher.mock.calls.filter(([, options]) => options?.method === "POST"),
  ).toHaveLength(0);
  await act(async () => {
    finish(Response.json({ cleanup_pending: false }));
    await deletion;
  });
  expect(result.current.id).toBeUndefined();
  expect(result.current.busy).toBe(false);
});
