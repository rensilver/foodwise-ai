import type { components, paths } from './generated';
export type Schema = components['schemas'];
export type StreamEvent = Schema['StreamContract'];
type Verb = 'get' | 'post' | 'patch' | 'delete';
type Operation<P extends keyof paths, M extends Verb> = M extends keyof paths[P] ? NonNullable<paths[P][M]> : never;
type Success<O> = O extends { responses: infer R } ? R[Extract<keyof R, 200 | 201 | 204>] extends { content: { 'application/json': infer T } } ? T : undefined : never;
type Body<O> = O extends { requestBody?: { content: { 'application/json': infer T } } } ? T : never;
export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}
export async function requireOk(response: Response): Promise<Response> {
  if (!response.ok) {
    let message = 'The request failed. Please try again.'; let code = 'transport_error';
    try { const envelope: Schema['ErrorEnvelope'] = await response.json(); if (envelope.error?.message) { message = envelope.error.message; code = envelope.error.code; } } catch { /* Non-JSON gateway failure. */ }
    throw new ApiError(response.status, code, message);
  }
  return response;
}
export async function api<P extends keyof paths, M extends Verb>(path: P, method: M, options: { params?: Record<string, string>; query?: URLSearchParams; body?: Body<Operation<P, M>>; csrf?: string; signal?: AbortSignal } = {}): Promise<Success<Operation<P, M>>> {
  let url: string = path;
  for (const [key, value] of Object.entries(options.params ?? {})) url = url.replace(`{${key}}`, encodeURIComponent(value));
  if (options.query?.size) url += `?${options.query}`;
  const response = await requireOk(await fetch(url, { method: method.toUpperCase(), credentials: 'same-origin', cache: 'no-store', signal: options.signal, headers: { ...(options.body ? { 'content-type': 'application/json' } : {}), ...(options.csrf ? { 'x-csrf-token': options.csrf } : {}) }, body: options.body ? JSON.stringify(options.body) : undefined }));
  return (response.status === 204 ? undefined : await response.json()) as Success<Operation<P, M>>;
}
