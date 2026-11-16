import { accessToken } from "./supabase/server";
import { allowedRoute, limitedBytes, withinDeadline, API_DEADLINE_MS } from "./security";
export class ApiError extends Error { constructor(public status: number, public sessionMissing = false) { super("Project access unavailable"); } }
export type Project = { id: string; name: string; description: string | null; status: string; created_at: string; updated_at: string };
export type ProjectPage = { projects: Project[]; next_cursor: string | null };
export type Me = { user_id: string; organization: { id: string; name: string } };
export async function backend(path: string, method = "GET", body?: string) {
  const parsed = new URL(path, "http://internal.invalid");
  if (!path.startsWith("/api/") || !allowedRoute(parsed.pathname.slice(5).split("/"), method)) throw new ApiError(404);
  try { return await withinDeadline(async (signal) => {
  const token = await accessToken(signal); signal.throwIfAborted(); if (!token) throw new ApiError(401, true);
  const rawOrigin = process.env.JOUS_API_INTERNAL_ORIGIN;
  if (!rawOrigin) throw new ApiError(503);
  const origin = new URL(rawOrigin);
  if (origin.origin !== rawOrigin || origin.username || origin.password || !["http:", "https:"].includes(origin.protocol)) throw new ApiError(503);

    const response = await fetch(rawOrigin + path, { method, body, headers: { Authorization: `Bearer ${token}`, ...(body !== undefined ? { "Content-Type": "application/json" } : {}) }, redirect: "error", cache: "no-store", signal });
    const bytes = await limitedBytes(response.body, 1048576);
    let value: unknown;
    try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); } catch { throw new ApiError(503); }
    const correlation = response.headers.get("x-request-id");
    if (!response.ok) throw new ApiError([401, 403, 404, 413, 415, 422].includes(response.status) ? response.status : 503);
    return { value, status: response.status, correlation: correlation && /^[A-Za-z0-9._-]{1,64}$/.test(correlation) ? correlation : null };
  }, API_DEADLINE_MS); } catch (error) { if (error instanceof ApiError) throw error; throw new ApiError(503); }
}
export async function readApi<T>(path: string): Promise<T> { return (await backend(path)).value as T; }
