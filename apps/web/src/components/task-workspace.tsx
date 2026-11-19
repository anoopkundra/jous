'use client';
import { useCallback, useEffect, useState } from 'react';
import { Card } from './ui/card';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';

type Route={route_id:string;logical_model_id:string;real_execution_eligible:boolean};
type Summary={id:string;prompt_preview:string;status:string};
type Task={id:string;prompt:string;status:string;execution:null|{response_text:string|null;status:string;usage:Record<string,number>|null;usage_status:string;error_code:string|null}};
export function TaskWorkspace({projectId}:{projectId:string}) {
  const base=`/api/projects/${projectId}/tasks`;
  const [route,setRoute]=useState<Route|null>(null);
  const [tasks,setTasks]=useState<Summary[]>([]);
  const [selected,setSelected]=useState<Task|null>(null);
  const [nextCursor,setNextCursor]=useState<string|null>(null);
  const [prompt,setPrompt]=useState(''); const [context,setContext]=useState('');
  const [busy,setBusy]=useState(false); const [error,setError]=useState('');
  const detail=useCallback(async(id:string)=>{
    const response=await fetch(base+'/'+encodeURIComponent(id),{cache:'no-store',signal:AbortSignal.timeout(45000)});
    if(!response.ok)throw Error();setSelected(await response.json());
  },[base]);
  const load=useCallback(async()=>{
    try {
      const [a,b]=await Promise.all([fetch(base+'/options',{cache:'no-store',signal:AbortSignal.timeout(45000)}),fetch(base,{cache:'no-store',signal:AbortSignal.timeout(45000)})]);
      if (!a.ok||!b.ok) throw Error();
      const options=await a.json(); const history=await b.json();
      setRoute(options.routes?.[0]??null); setTasks(history.tasks??[]);setNextCursor(history.next_cursor??null);
      if(history.tasks?.length)await detail(history.tasks[0].id);else setSelected(null);
    } catch {setError('Tasks are unavailable. Your project is still saved.');}
  },[base,detail]);
  async function more(){
    if(!nextCursor)return;
    try{const response=await fetch(base+'?after='+encodeURIComponent(nextCursor),{cache:'no-store',signal:AbortSignal.timeout(45000)});
      if(!response.ok)throw Error();const history=await response.json();
      setTasks(old=>[...old,...history.tasks.filter((t:Summary)=>!old.some(x=>x.id===t.id))]);setNextCursor(history.next_cursor??null);
    }catch{setError('Tasks are unavailable. Your project is still saved.');}
  }
  useEffect(()=>{void load();},[load]);
  async function submit(event:React.FormEvent) {
    event.preventDefault(); if(busy||!route?.real_execution_eligible)return;
    setBusy(true);setError('');
    try {
      const response=await fetch(base,{method:'POST',signal:AbortSignal.timeout(45000),headers:{'Content-Type':'application/json'},body:JSON.stringify({
        prompt,task_context:context||null,logical_model_id:route.logical_model_id,route_id:route.route_id,client_request_id:crypto.randomUUID()})});
      if(!response.ok)throw Error();
      const task:Task=await response.json();setSelected(task);setTasks(old=>[{id:task.id,prompt_preview:task.prompt.slice(0,256),status:task.status},...old.filter(t=>t.id!==task.id)]);
    }catch{setError('Task outcome unavailable. Refresh tasks before submitting another request.');}
    finally{setBusy(false);}
  }
  return <div className="mt-10 space-y-5">
    <Card><h2 className="text-xl font-semibold">Project tasks</h2><p className="mt-3 text-sm text-slate-500">Keep each task focused. Only this project and the context you enter are included.</p>
    {!route?.real_execution_eligible&&<p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">Execution is unavailable while supplier admission is pending. No task will be dispatched.</p>}
    <form onSubmit={submit} className="mt-5 space-y-4"><label htmlFor="future-task">What would you like to work on?</label>
    <Textarea id="future-task" value={prompt} onChange={e=>setPrompt(e.target.value)} disabled={!route?.real_execution_eligible||busy} placeholder="AI execution is coming in the next build." />
    <label htmlFor="task-context">Task context (optional)</label><Textarea id="task-context" value={context} onChange={e=>setContext(e.target.value)} disabled={!route?.real_execution_eligible||busy} />
    <Button type="submit" disabled={!route?.real_execution_eligible||busy||!prompt.trim()}>{busy?'Submitting...':'Run task'}</Button></form>
    {error&&<p role="alert" className="mt-4 text-sm text-red-700">{error}</p>}</Card>
    <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Saved tasks</h2><Button variant="outline" onClick={()=>void load()}>Refresh tasks</Button></div>
    {tasks.length===0&&<p className="text-sm text-slate-500">No saved tasks yet.</p>}
    {tasks.map(task=><Card key={task.id}><h3 className="whitespace-pre-wrap break-words font-medium">{task.prompt_preview}</h3>
      <Button variant="outline" onClick={()=>void detail(task.id).catch(()=>setError('Task detail unavailable.'))}>Open task {task.prompt_preview}</Button></Card>)}
    {nextCursor&&<Button variant="outline" onClick={()=>void more()}>Load older tasks</Button>}
    {selected&&<Card><h3 className="whitespace-pre-wrap break-words font-medium">{selected.prompt}</h3><p className="mt-3 text-sm text-slate-500">{selected.status==='claimed'?'Claimed - outcome pending':selected.status==='unknown'?'Unknown outcome - this task will not be retried':selected.status==='known_error'?'Task could not be completed':selected.status==='refused'?'Request declined':'Completed'}</p>
    {selected.execution?.response_text!==null&&selected.execution?.response_text!==undefined&&<pre className="mt-5 whitespace-pre-wrap break-words font-sans text-sm leading-7">{selected.execution.response_text}</pre>}
    {selected.execution&&<p className="mt-4 text-xs text-slate-500">Usage: {selected.execution.usage?Object.entries(selected.execution.usage).map(([k,v])=>`${k}: ${v}`).join(', '):'Unavailable'} ({selected.execution.usage_status})</p>}</Card>}
  </div>;
}
