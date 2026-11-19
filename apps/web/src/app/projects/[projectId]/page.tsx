import { TaskWorkspace } from "@/components/task-workspace";
import Link from "next/link";
import { redirect } from "next/navigation";
import { readApi, ApiError, type Project } from "@/lib/api";
import { SessionControls, AccessUnavailable } from "@/components/session-controls";
import { Card } from "@/components/ui/card";
export const dynamic = "force-dynamic";
export default async function Workspace({ params }: { params: Promise<{ projectId: string }> }) {
  const { projectId } = await params; let project: Project;
  try { project = await readApi<Project>(`/api/projects/${projectId}`); }
  catch (error) { if (error instanceof ApiError && error.sessionMissing) redirect("/login");
    if (error instanceof ApiError && [401, 403].includes(error.status)) return <AccessUnavailable />;
    return <main className="mx-auto max-w-3xl px-6 py-12"><Link href="/projects" className="text-sm text-teal-800">Projects</Link><Card className="mt-10"><h1 className="text-2xl font-semibold">Project unavailable</h1><p className="mt-3 text-slate-500">This project is unavailable to your account. Return to Projects to continue.</p></Card></main>; }
  return <main className="mx-auto max-w-7xl px-6 py-8"><header className="flex items-center justify-between border-b border-slate-200 pb-7"><Link href="/projects" className="brand">jous<span>.</span></Link><SessionControls /></header><div className="grid gap-10 py-10 lg:grid-cols-[220px_1fr]"><aside><Link href="/projects" className="text-sm font-medium text-slate-500 hover:text-teal-800">Projects</Link><div className="mt-9 rounded-lg bg-teal-50 px-4 py-3 text-sm font-semibold text-teal-900">Workspace</div><p className="mt-5 px-4 text-xs leading-5 text-slate-400">Your project is ready.<br />AI execution arrives next.</p></aside><section className="min-w-0"><p className="eyebrow">PROJECT WORKSPACE</p><h1 className="mt-3 break-words text-3xl font-semibold tracking-tight">{project.name}</h1>{project.description && <p className="mt-4 max-w-2xl whitespace-pre-wrap break-words leading-7 text-slate-500">{project.description}</p>}<TaskWorkspace projectId={project.id} /></section></div></main>;
}
