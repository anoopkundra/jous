import { NextResponse } from 'next/server';
import { taskBackend, taskPathAllowed, TaskApiError } from '@/lib/task-api';
import { limitedBytes, unsafeRequestAllowed } from '@/lib/security';
export const dynamic='force-dynamic';
const headers={'Cache-Control':'private, no-store'};
async function handle(request: Request, context: {params:Promise<{projectId:string;taskPath?:string[]}>}) {
  const {projectId,taskPath=[]}=await context.params;
  if (!taskPathAllowed(projectId,taskPath,request.method)) return NextResponse.json({error:'Task unavailable'},{status:404,headers});
  try {
    const url=new URL(request.url);
    if (url.search && !(request.method==='GET' && taskPath.length===0)) throw new TaskApiError(422);
    if ([...url.searchParams.keys()].some(k=>!['limit','after'].includes(k))) throw new TaskApiError(422);
    let body: string|undefined;
    if (request.method==='POST') {
      if (!unsafeRequestAllowed(request)) throw new TaskApiError(403);
      if (request.headers.get('content-type')?.split(';')[0].trim().toLowerCase()!=='application/json') throw new TaskApiError(415);
      try { body=new TextDecoder('utf-8',{fatal:true}).decode(await limitedBytes(request.body,65536)); }
      catch { throw new TaskApiError(413); }
    }
    const result=await taskBackend(`/api/projects/${projectId}/tasks${taskPath.length?'/'+taskPath[0]:''}${url.search}`,request.method,body);
    return NextResponse.json(result.value,{status:result.status,headers:{...headers,...(result.location===`/api/projects/${projectId}/tasks/${(result.value as {id?:string})?.id}`?{'Location':result.location}:{}),...(result.correlation?{'X-Request-ID':result.correlation}:{})}});
  } catch(error) {
    return NextResponse.json({error:{message:'Task access unavailable'}},{status:error instanceof TaskApiError?error.status:503,headers});
  }
}
export {handle as GET,handle as POST};
