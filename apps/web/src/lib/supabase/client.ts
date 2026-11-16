"use client";
import { createBrowserClient } from "@supabase/ssr";
import { authFetch } from "../security";
export function browserClient() {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) throw new Error("Sign-in configuration unavailable");
  return createBrowserClient(url, key, { global: { fetch: authFetch() }, cookieOptions: { path: "/", sameSite: "lax", secure: process.env.NODE_ENV === "production" } });
}
