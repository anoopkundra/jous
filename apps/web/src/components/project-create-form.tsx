"use client";
import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
export function ProjectCreateForm() {
  const router = useRouter(); const [pending, setPending] = useState(false); const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setPending(true); setError(""); const data = new FormData(event.currentTarget);
    try { const response = await fetch("/api/projects", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: String(data.get("name")).trim(), description: String(data.get("description")) || null }) });
      if (!response.ok) { setError(response.status === 401 ? "Workspace access unavailable. Sign out and try again." : "We couldn't create your project. Check the details or try again."); return; }
      const project = await response.json(); if (typeof project.id !== "string" || !/^[0-9a-f-]{36}$/.test(project.id)) throw new Error();
      router.push(`/projects/${project.id}`); router.refresh();
    } catch { setError("The request could not be confirmed. Check Projects before trying again."); }
    finally { setPending(false); }
  }
  return <form onSubmit={submit} className="grid gap-5"><div><label htmlFor="project-name">Project name</label><Input id="project-name" name="name" placeholder="My First Project" required maxLength={255} /></div><div><label htmlFor="project-description">Description <span className="font-normal text-slate-400">(optional)</span></label><Textarea id="project-description" name="description" maxLength={2000} placeholder="What are you working on?" /></div>{error && <p role="alert" className="text-sm text-red-700">{error}</p>}<Button disabled={pending}>{pending ? "Creating project..." : "Create project"}</Button></form>;
}
