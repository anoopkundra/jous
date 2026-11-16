import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";
import { authFetch, withinDeadline } from "../security";
export async function serverClient(signal: AbortSignal) {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return null;
  const jar = await cookies();
  return createServerClient(url, key, { global: { fetch: authFetch(signal) }, cookieOptions: { path: "/", sameSite: "lax", secure: process.env.NODE_ENV === "production" }, cookies: {
    getAll: () => jar.getAll(),
    setAll: (values) => { if (signal.aborted) return; try { for (const { name, value, options } of values) jar.set(name, value, options); }
      catch { /* Server Components cannot write; Proxy owns refresh publication. */ } },
  } });
}
export async function accessToken(parent?: AbortSignal) {
  try {
    return await withinDeadline(async (signal) => {
      const client = await serverClient(signal); if (!client) return null;
      const { data: claims, error } = await client.auth.getClaims();
      if (error?.status === 408) throw new Error("Authentication unavailable");
      if (error || !claims?.claims) return null;
      const { data, error: sessionError } = await client.auth.getSession();
      signal.throwIfAborted();
      return sessionError ? null : data.session?.access_token ?? null;
    }, undefined, parent);
  } catch { throw new Error("Authentication unavailable"); }
}
