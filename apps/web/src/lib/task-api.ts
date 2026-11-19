import { accessToken } from './supabase/server';
import { limitedBytes, withinDeadline } from './security';

export class TaskApiError extends Error {
  constructor(public status: number) { super('Task access unavailable'); }
}
export const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
export function taskPathAllowed(project: string, tail: string[], method: string) {
  if (!uuidPattern.test(project)) return false;
  return (tail.length === 0 && ['GET','POST'].includes(method)) ||
    (method === 'GET' && tail.length === 1 && (tail[0] === 'options' || uuidPattern.test(tail[0])));
}
export async function taskBackend(path: string, method: string, body?: string) {
  return withinDeadline(async signal => {
    const token = await accessToken(signal);
    signal.throwIfAborted(); if (!token) throw new TaskApiError(401);
    const raw = process.env.JOUS_API_INTERNAL_ORIGIN;
    if (!raw) throw new TaskApiError(503);
    const origin = new URL(raw);
    if (origin.origin !== raw || origin.username || origin.password || !['http:','https:'].includes(origin.protocol)) throw new TaskApiError(503);
    const response = await fetch(raw + path, { method, body, signal, redirect: 'error', cache: 'no-store',
      headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type':'application/json' }) } });
    const bytes = await limitedBytes(response.body,1048576);
    signal.throwIfAborted();
    if (!response.ok) throw new TaskApiError([401,403,404,409,413,415,422].includes(response.status) ? response.status : 503);
    const value: unknown = JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(bytes));
    const correlation=response.headers.get('x-request-id');
    return { value, status:response.status, location:response.headers.get('location'), correlation:correlation && /^[A-Za-z0-9._-]{1,64}$/.test(correlation) ? correlation : null };
  },45000);
}
