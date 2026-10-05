/** Server-only transport. Destination is process configuration, never a request field. */
export async function proxy(
  request: Request,
  segments: string[],
): Promise<Response> {
  if (
    !segments.length ||
    segments.some(
      (part) =>
        !/^[A-Za-z0-9_.:-]+$/.test(part) || part === "." || part === "..",
    )
  )
    return new Response(null, { status: 400 });
  const origin = new URL(
    process.env.FOODWISE_API_ORIGIN ?? "http://127.0.0.1:8000",
  );
  if (
    !["http:", "https:"].includes(origin.protocol) ||
    !["localhost", "127.0.0.1", "backend"].includes(origin.hostname) ||
    origin.username ||
    origin.password ||
    origin.pathname !== "/" ||
    origin.search ||
    origin.hash
  )
    throw new Error("FOODWISE_API_ORIGIN must identify the local backend.");
  const url = new URL(
    `/api/v1/${segments.map(encodeURIComponent).join("/")}`,
    origin,
  );
  url.search = new URL(request.url).search;
  const headers = new Headers();
  for (const name of [
    "content-type",
    "accept",
    "cookie",
    "origin",
    "sec-fetch-site",
    "x-csrf-token",
    "x-request-id",
  ]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  const controller = new AbortController();
  const abort = () => controller.abort();
  request.signal.addEventListener("abort", abort, { once: true });
  if (request.signal.aborted) abort();
  try {
    const options: RequestInit & { duplex: string } = {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method) ? undefined : request.body,
      signal: controller.signal,
      redirect: "manual",
      cache: "no-store",
      duplex: "half",
    };
    const upstream = await fetch(url, options);
    const outgoing = new Headers({
      "cache-control": "private, no-store",
      "x-accel-buffering": "no",
    });
    for (const name of [
      "content-type",
      "x-content-type-options",
      "x-request-id",
    ]) {
      const value = upstream.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    for (const cookie of upstream.headers.getSetCookie())
      outgoing.append("set-cookie", cookie);
    const reader = upstream.body?.getReader();
    let cancelled = false;
    const cleanup = () => request.signal.removeEventListener("abort", abort);
    const body = reader
      ? new ReadableStream<Uint8Array>({
          async pull(stream) {
            try {
              const chunk = await reader.read();
              if (cancelled) return;
              if (chunk.done) {
                cleanup();
                stream.close();
              } else stream.enqueue(chunk.value);
            } catch (error) {
              cleanup();
              if (cancelled) return;
              if (request.signal.aborted) stream.close();
              else stream.error(error);
              controller.abort();
            }
          },
          async cancel() {
            cancelled = true;
            cleanup();
            controller.abort();
            await reader.cancel().catch(() => {});
          },
        })
      : null;
    if (!reader) cleanup();
    return new Response(body, { status: upstream.status, headers: outgoing });
  } catch {
    request.signal.removeEventListener("abort", abort);
    if (request.signal.aborted) return new Response(null, { status: 499 });
    return Response.json(
      {
        error: {
          code: "dependency_unavailable",
          message:
            "The local API is unavailable. Start the backend and try again.",
          retryable: true,
        },
        request_id: null,
      },
      { status: 503, headers: { "cache-control": "no-store" } },
    );
  }
}
