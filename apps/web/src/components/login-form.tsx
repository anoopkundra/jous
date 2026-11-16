"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { browserClient } from "@/lib/supabase/client";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
export function LoginForm() {
  const router = useRouter(); const [error, setError] = useState(""); const [pending, setPending] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setError(""); setPending(true);
    const form = event.currentTarget; const data = new FormData(form);
    try { const { error } = await browserClient().auth.signInWithPassword({ email: String(data.get("email")), password: String(data.get("password")) });
      if (error) { setError("We couldn't sign you in. Check your details and try again."); return; }
      form.reset(); router.replace("/projects"); router.refresh();
    } catch { setError("Sign-in is temporarily unavailable. Please try again."); }
    finally { setPending(false); }
  }
  return <form onSubmit={submit} className="grid gap-5"><div><label htmlFor="email">Email address</label><Input id="email" name="email" type="email" autoComplete="username" required maxLength={254} /></div><div><label htmlFor="password">Password</label><Input id="password" name="password" type="password" autoComplete="current-password" required maxLength={1024} /></div>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}<Button disabled={pending}>{pending ? "Signing in..." : "Sign in"}</Button><p className="text-xs leading-5 text-slate-500">Access is currently available to approved Jous accounts.</p></form>;
}
