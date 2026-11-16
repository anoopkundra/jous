import Link from "next/link";
import { redirect } from "next/navigation";
import { readApi, ApiError } from "@/lib/api";
import { AccessUnavailable } from "@/components/session-controls";
import { LoginForm } from "@/components/login-form";
import { Card } from "@/components/ui/card";
export const dynamic = "force-dynamic";
export default async function Login() {
  let usable = false;
  try { await readApi("/api/me"); usable = true; }
  catch (error) { if (!(error instanceof ApiError && error.sessionMissing)) return <AccessUnavailable />; }
  if (usable) redirect("/projects");
  return <main className="mx-auto flex min-h-screen max-w-6xl flex-col px-6 py-8"><Link href="/" className="brand">jous<span>.</span></Link><div className="grid flex-1 items-center gap-12 py-14 md:grid-cols-2"><div><p className="eyebrow">YOUR AI WORKSPACE</p><h1 className="mt-5 max-w-lg text-4xl font-semibold leading-tight tracking-tight md:text-5xl">A clear home for<br />your next idea.</h1><p className="mt-6 max-w-md text-lg leading-8 text-slate-500">Bring your work into focus. Start with a project, and build from there.</p><p className="mt-12 text-sm text-slate-400">Thoughtful work. Better economics.</p></div><Card className="w-full max-w-md justify-self-center p-8"><h2 className="text-2xl font-semibold tracking-tight">Welcome back</h2><p className="mb-8 mt-2 text-sm text-slate-500">Sign in to your Jous workspace.</p><LoginForm /></Card></div></main>;
}
