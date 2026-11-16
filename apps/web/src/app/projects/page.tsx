import Link from "next/link";
import { redirect } from "next/navigation";
import { readApi, ApiError, type Me, type ProjectPage } from "@/lib/api";
import { ProjectCreateForm } from "@/components/project-create-form";
import { SessionControls, AccessUnavailable } from "@/components/session-controls";
import { Card } from "@/components/ui/card";
export const dynamic = "force-dynamic";
export default async function Projects({ searchParams }: { searchParams: Promise<{ after?: string }> }) {
  let me: Me; let page: ProjectPage;
  try { me = await readApi<Me>("/api/me"); const { after } = await searchParams;
    page = await readApi<ProjectPage>("/api/projects" + (after ? "?after=" + encodeURIComponent(after) : ""));
  } catch (error) { if (error instanceof ApiError && error.sessionMissing) redirect("/login");
    return <AccessUnavailable />; }
  return <main className="mx-auto max-w-7xl px-6 py-8"><header className="flex items-center justify-between border-b border-slate-200 pb-7"><Link href="/projects" className="brand">jous<span>.</span></Link><div className="flex items-center gap-5"><span className="hidden text-sm text-slate-500 sm:block">{me.organization.name}</span><SessionControls /></div></header><div className="mb-10 mt-12"><p className="eyebrow">YOUR WORKSPACE</p><h1 className="mt-3 text-3xl font-semibold tracking-tight">Projects</h1><p className="mt-3 text-slate-500">A focused space for every piece of work.</p></div><div className="grid items-start gap-10 lg:grid-cols-[1fr_360px]"><section aria-label="Your projects"><div className="grid gap-4 sm:grid-cols-2">{page.projects.map((project) => <Link href={`/projects/${project.id}`} key={project.id} className="group rounded-2xl focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-teal-700"><Card className="h-full min-h-44 transition-colors group-hover:border-teal-600"><div className="mb-6 h-9 w-9 rounded-lg bg-teal-50 text-center text-lg leading-9 text-teal-800">{project.name.charAt(0).toUpperCase()}</div><h2 className="break-words text-lg font-semibold">{project.name}</h2><p className="mt-2 line-clamp-3 break-words text-sm leading-6 text-slate-500">{project.description || "Your next idea starts here."}</p><p className="mt-6 text-sm font-medium text-teal-800">Open workspace</p></Card></Link>)}</div>{!page.projects.length && <div className="rounded-2xl border border-dashed border-slate-300 px-8 py-16 text-center"><h2 className="text-lg font-semibold">Make room for your first idea</h2><p className="mt-3 text-sm text-slate-500">Create a project to give your work a home.</p></div>}{page.next_cursor && <Link className="mt-6 inline-block text-sm underline" href={`/projects?after=${page.next_cursor}`}>More projects</Link>}</section><Card><h2 className="text-lg font-semibold">Create a project</h2><p className="mb-6 mt-2 text-sm text-slate-500">Start simple. You can give it a clear name and a little context.</p><ProjectCreateForm /></Card></div></main>;
}
