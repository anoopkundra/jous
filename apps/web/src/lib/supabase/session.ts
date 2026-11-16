import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { authFetch, withinDeadline } from "../security";
export async function updateSession(request: NextRequest) {
  const nonce = btoa(crypto.randomUUID());
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL; const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  const connectOrigin = url ? new URL(url).origin : "'self'";
  const csp = `default-src 'self'; script-src 'self' 'nonce-${nonce}' 'strict-dynamic'${process.env.NODE_ENV !== "production" ? " 'unsafe-eval'" : ""}; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self' ${connectOrigin}${process.env.NODE_ENV !== "production" ? " ws://127.0.0.1:* ws://localhost:*" : ""}; frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'`;
  request.headers.set("Content-Security-Policy", csp);
  let response = NextResponse.next({ request });
  // API routes acquire/refresh their own session inside one total bridge budget.
  if (url && key && !request.nextUrl.pathname.startsWith("/api/")) {
    try { await withinDeadline(async (signal) => {
    const client = createServerClient(url, key, { global: { fetch: authFetch(signal) }, cookieOptions: { path: "/", sameSite: "lax", secure: process.env.NODE_ENV === "production" }, cookies: {
      getAll: () => request.cookies.getAll(),
      setAll: (values) => {
        if (signal.aborted) return;
        for (const { name, value } of values) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of values) response.cookies.set(name, value, options);
      },
    } });
    await client.auth.getClaims();
    }); } catch { /* Page checks independently fail closed; no late cookie publication. */ }
  }
  response.headers.set("Cache-Control", "private, no-store");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("Referrer-Policy", "same-origin");
  response.headers.set("X-Frame-Options", "DENY");
  response.headers.set("Content-Security-Policy", csp);
  return response;
}
