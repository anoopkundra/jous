import { redirect } from "next/navigation";
import { accessToken } from "@/lib/supabase/server";
import { AccessUnavailable } from "@/components/session-controls";
export const dynamic = "force-dynamic";
export default async function Home() {
  let token: string | null;
  try { token = await accessToken(); } catch { return <AccessUnavailable />; }
  redirect(token ? "/projects" : "/login");
}
