"use client";
import { useState } from "react";
import { browserClient } from "@/lib/supabase/client";
import { Button } from "./ui/button";
export function SessionControls() {
  const [pending, setPending] = useState(false); const [error, setError] = useState("");
  async function logout() { setPending(true); setError(""); try { const { error } = await browserClient().auth.signOut({ scope: "local" });
    if (error) { setError("Sign-out unavailable. Please retry."); setPending(false); return; }
    window.location.replace("/login");
  } catch { setPending(false); setError("Sign-out unavailable. Please retry."); } }
  return <div className="text-right"><Button variant="ghost" size="sm" disabled={pending} onClick={logout}>{pending ? "Signing out..." : "Sign out"}</Button>{error && <p role="alert" className="text-xs text-red-700">{error}</p>}</div>;
}

export function AccessUnavailable() {
  return <main className="mx-auto max-w-3xl px-6 py-12"><div className="flex justify-between"><span className="brand">jous<span>.</span></span><SessionControls /></div><section className="mt-16 rounded-2xl border border-slate-200 bg-white p-8"><h1 className="text-2xl font-semibold">Workspace access unavailable</h1><p className="mt-3 text-slate-500">We cannot open your workspace right now. Contact your Jous administrator or try again later.</p></section></main>;
}
