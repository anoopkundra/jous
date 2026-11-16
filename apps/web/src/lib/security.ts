// Shared strict configuration/path validation for the product boundary.
export function appOrigin() {
  const value = process.env.JOUS_APP_ORIGIN;
  if (!value) throw new Error("Application configuration unavailable");
  const url = new URL(value);
  if (url.origin !== value || (url.protocol !== "https:" && !(process.env.NODE_ENV !== "production" && url.protocol === "http:" && ["localhost", "127.0.0.1"].includes(url.hostname)))) throw new Error("Application configuration unavailable");
  return value;
}
export function unsafeRequestAllowed(request: Request) {
  return request.headers.get("origin") === appOrigin() &&
    (!request.headers.get("sec-fetch-site") || request.headers.get("sec-fetch-site") === "same-origin");
}
export function allowedRoute(path: string[], method: string) {
  const joined = path.join("/");
  return (method === "GET" && (joined === "me" || joined === "projects" || /^projects\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(joined))) || (method === "POST" && joined === "projects");
}
export async function limitedBytes(body: ReadableStream<Uint8Array> | null, limit: number) {
  if (!body) return new Uint8Array();
  const reader = body.getReader(); const chunks: Uint8Array[] = []; let count = 0;
  try {
    while (true) { const part = await reader.read(); if (part.done) break; count += part.value.length;
      if (count > limit) throw new Error("Size bound exceeded"); chunks.push(part.value); }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
  const result = new Uint8Array(count); let offset = 0;
  for (const chunk of chunks) { result.set(chunk, offset); offset += chunk.length; }
  return result;
}

// A scope bounds the whole operation, not just receipt of HTTP headers.
export const AUTH_DEADLINE_MS = 4000;
export const API_DEADLINE_MS = 8000;
export async function withinDeadline<T>(operation: (signal: AbortSignal) => Promise<T>, milliseconds = AUTH_DEADLINE_MS, parent?: AbortSignal): Promise<T> {
  const controller = new AbortController();
  const signal = parent ? AbortSignal.any([parent, controller.signal]) : controller.signal;
  const timer = setTimeout(() => controller.abort(), milliseconds);
  let rejectOnAbort: (() => void) | undefined;
  try {
    signal.throwIfAborted();
    const aborted = new Promise<never>((_, reject) => {
      rejectOnAbort = () => reject(new Error("Authentication unavailable"));
      signal.addEventListener("abort", rejectOnAbort, { once: true });
    });
    const value = await Promise.race([aborted, operation(signal)]);
    signal.throwIfAborted();
    return value;
  } finally {
    clearTimeout(timer);
    if (rejectOnAbort) signal.removeEventListener("abort", rejectOnAbort);
    controller.abort(); // Any outstanding scoped transport must stop, including on failure.
  }
}
export function authFetch(parent?: AbortSignal): typeof fetch {
  return async (input, init) => {
    try {
      return await withinDeadline(async (signal) => {
        const original = init?.signal ?? (input instanceof Request ? input.signal : undefined);
        const combined = original ? AbortSignal.any([signal, original]) : signal;
        combined.throwIfAborted();
        const response = await fetch(input, { ...init, signal: combined, redirect: "error", cache: "no-store" });
        const bytes = await limitedBytes(response.body, 1048576);
        combined.throwIfAborted();
        return new Response([204, 205, 304].includes(response.status) ? null : bytes, { status: response.status, statusText: response.statusText, headers: response.headers });
      }, AUTH_DEADLINE_MS, parent);
    } catch {
      // Local transport failure, never an identity verdict. A non-retryable error
      // response prevents the SDK refresh backoff from issuing another request.
      return Response.json({ message: "Authentication unavailable" }, { status: 408 });
    }
  };
}
