import { NextResponse } from "next/server";
import { backend, ApiError } from "@/lib/api";
import { allowedRoute, limitedBytes, unsafeRequestAllowed } from "@/lib/security";
export const dynamic = "force-dynamic";
const headers = { "Cache-Control": "private, no-store" };
async function handle(request: Request, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  if (!allowedRoute(path, request.method)) return NextResponse.json({ error: "Resource unavailable" }, { status: 404, headers });
  try {
    const url = new URL(request.url);
    if ([...url.searchParams.keys()].some((key) => !["limit", "after"].includes(key)) || (url.search && !(request.method === "GET" && path.join("/") === "projects"))) throw new ApiError(422);
    let body: string | undefined;
    if (request.method === "POST") {
      if (!unsafeRequestAllowed(request)) throw new ApiError(403);
      if (request.headers.get("content-type")?.split(";")[0].trim().toLowerCase() !== "application/json") throw new ApiError(415);
      try { body = new TextDecoder("utf-8", { fatal: true }).decode(await limitedBytes(request.body, 16384)); } catch { throw new ApiError(413); }
    }
    const result = await backend("/api/" + path.join("/") + url.search, request.method, body);
    return NextResponse.json(result.value, { status: result.status, headers: { ...headers, ...(result.correlation ? { "X-Request-ID": result.correlation } : {}) } });
  } catch (error) { const status = error instanceof ApiError ? error.status : 503;
    return NextResponse.json({ error: { code: status === 401 ? "identity_required" : "resource_unavailable", message: "Project access unavailable" } }, { status, headers }); }
}
export { handle as GET, handle as POST };
