// Deterministic loopback services only. These are NOT Supabase/DB certification.
import { test, expect, type Page } from "@playwright/test";
import http from "node:http";
import { spawn, type ChildProcess } from "node:child_process";
import { createECDH, createHash, createPrivateKey, createPublicKey, sign } from "node:crypto";
const uid = "11111111-1111-4111-8111-111111111111";
const projectId = "22222222-2222-4222-8222-222222222222";
const org = "33333333-3333-4333-8333-333333333333";
const base = "http://127.0.0.1:3012";
// Inert deterministic key: worker restarts must not rotate a cached JWKS kid.
const fixtureD = createHash("sha256").update("Jous V1.1 offline-only test key; never operational").digest();
const fixtureCurve = createECDH("prime256v1"); fixtureCurve.setPrivateKey(fixtureD);
const fixturePoint = fixtureCurve.getPublicKey();
const privateKey = createPrivateKey({ key: { kty: "EC", crv: "P-256", d: fixtureD.toString("base64url"), x: fixturePoint.subarray(1, 33).toString("base64url"), y: fixturePoint.subarray(33).toString("base64url") }, format: "jwk" });
const publicKey = createPublicKey(privateKey);
const jwk = { ...publicKey.export({ format: "jwk" }), alg: "ES256", kid: "offline-v1-1-stable", use: "sig" };
let fixtureEligible = true;
let fixtureDisposition = 'succeeded';
let failTaskPost = false;
let tasks: any[] = [];
let rejectIdentity = false;
let stalledAuth = "";
let authRequests: string[] = [];
let abortedAuth = 0;
let auth: http.Server; let api: http.Server; let web: ChildProcess;
let projects: { id: string; name: string; description: string | null; status: string; created_at: string; updated_at: string }[] = [];
let observations: { method: string; url: string; headers: http.IncomingHttpHeaders; body: string }[] = [];
function token(kid = "offline-v1-1-stable", expired = false) {
  const now = Math.floor(Date.now() / 1000);
  const encode = (x: unknown) => Buffer.from(JSON.stringify(x)).toString("base64url");
  const message = encode({ alg: "ES256", kid, typ: "JWT" }) + "." + encode({ iss: "http://127.0.0.1:8793/auth/v1", sub: uid, aud: "authenticated", role: "authenticated", session_id: uid, is_anonymous: false, iat: now, exp: expired ? now - 3600 : now + 3600 });
  return message + "." + sign("sha256", Buffer.from(message), { key: privateKey, dsaEncoding: "ieee-p1363" }).toString("base64url");
}
function json(res: http.ServerResponse, code: number, value: unknown) { res.writeHead(code, { "content-type": "application/json", "access-control-allow-origin": base, "access-control-allow-headers": "authorization,apikey,content-type,x-client-info,x-supabase-api-version", "access-control-allow-methods": "GET,POST,OPTIONS", "x-request-id": "offline-request-1" }); res.end(JSON.stringify(value)); }
function listen(server: http.Server, port: number) { return new Promise<void>((resolve, reject) => { server.once("error", reject); server.listen(port, "127.0.0.1", resolve); }); }
test.beforeAll(async () => {
  test.setTimeout(120000);
  // Only fixture-local origins/keys. No application credential is read.
  Object.assign(process.env, { NEXT_TELEMETRY_DISABLED: "1", NEXT_PUBLIC_SUPABASE_URL: "http://127.0.0.1:8793", NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_local_fixture_only", JOUS_API_INTERNAL_ORIGIN: "http://127.0.0.1:8794", JOUS_APP_ORIGIN: base });
  auth = http.createServer(async (req, res) => {
    if (req.method === "OPTIONS") return json(res, 200, {});
    authRequests.push(req.url!);
    if (stalledAuth && req.url?.includes(stalledAuth)) {
      // No response completion: the application must cancel the actual socket.
      res.on("close", () => { abortedAuth++; });
      if (stalledAuth === "jwks") { res.writeHead(200, { "content-type": "application/json" }); res.write('{"keys":'); }
      return;
    }
    const user = { id: uid, aud: "authenticated", role: "authenticated", email: "first@example.test", app_metadata: {}, user_metadata: {}, created_at: new Date().toISOString() };
    if (req.url?.includes("jwks")) return json(res, 200, { keys: [jwk] });
    if (req.url?.includes("/user")) return json(res, 200, user);
    if (req.url?.includes("/logout")) return json(res, 200, {});
    if (req.url?.includes("/token")) {
      let body = ""; for await (const chunk of req) body += chunk;
      if (body.includes("incorrect")) return json(res, 400, { code: "invalid_credentials", msg: "Invalid login credentials" });
      return json(res, 200, { access_token: token(), refresh_token: "offline-refresh-only", token_type: "bearer", expires_in: 3600, user });
    }
    return json(res, 404, {});
  });
  api = http.createServer(async (req, res) => {
    let body = ""; for await (const chunk of req) body += chunk;
    observations.push({ method: req.method!, url: req.url!, headers: req.headers, body });
    if (!req.headers.authorization?.startsWith("Bearer ey")) return json(res, 401, {});
    if (rejectIdentity) return json(res, 401, { error: { message: "internal_fixture_unmapped_disabled" } });
    const taskBase = "/api/projects/" + projectId + "/tasks";
    if (req.url === taskBase + "/options") return json(res,200,{routes:[{route_id:"offline-fixture",logical_model_id:"offline-fixture",real_execution_eligible:fixtureEligible}],execution_available:fixtureEligible});
    if (req.url === taskBase && req.method === "POST") {
      if (failTaskPost) return json(res,503,{});
      const input=JSON.parse(body);
      const task={id:uid,project_id:projectId,prompt:input.prompt,status:fixtureDisposition,execution:fixtureDisposition === 'claimed'?null:{id:org,status:fixtureDisposition,response_text:fixtureDisposition === 'succeeded'?'<img src=x onerror="window.injected=1">Actual mock result':null,usage:null,usage_status:'unavailable',error_code:fixtureDisposition === 'unknown'?'provider_timeout':fixtureDisposition === 'known_error'?'supplier_rejected':null}};
      tasks=[task];return json(res,200,task);
    }
    if (req.url?.startsWith(taskBase) && req.method === 'GET') {
      const url=new URL(req.url,base);const id=url.pathname.slice(taskBase.length+1);
      if(id){const task=tasks.find(t=>t.id===id);return json(res,task?200:404,task??{});}
      const start=url.searchParams.has('after')?tasks.findIndex(t=>t.id===url.searchParams.get('after'))+1:0;
      const page=tasks.slice(start,start+2);
      return json(res,200,{tasks:page.map(t=>({id:t.id,prompt_preview:t.prompt.slice(0,256),status:t.status})),next_cursor:start+2<tasks.length?page[page.length-1].id:null});
    }
    if (req.url === "/api/me") return json(res, 200, { user_id: uid, organization: { id: org, name: "First organization" } });
    if (req.url === "/api/projects" && req.method === "POST") {
      const data = JSON.parse(body); const stamp = new Date().toISOString();
      const project = { id: projectId, name: data.name, description: data.description, status: "active", created_at: stamp, updated_at: stamp };
      projects = [project]; return json(res, 201, project);
    }
    if (req.url?.startsWith("/api/projects?after=bad")) return json(res, 422, {});
    if (req.url === "/api/projects") return json(res, 200, { projects, next_cursor: null });
    if (req.url === "/api/projects/" + projectId && projects.length) return json(res, 200, projects[0]);
    return json(res, 404, { error: { message: "Resource unavailable" } });
  });
  await listen(auth, 8793); await listen(api, 8794);
  // The supported Next server runs in a fixture-owned Node child so Next's
  // require hooks cannot alter Playwright's own TypeScript loader.
  const serverSource = `
    // Match a normal CLI launch: -e belongs only to this fixture wrapper.
    process.execArgv = [];
    process.argv = [process.execPath, require.resolve('next/dist/bin/next'), 'dev', '--hostname', '127.0.0.1', '--port', '3012'];
    process.on('message', message => {
      if (message !== 'close') return;
      const deadline = setTimeout(() => process.exit(1), 15000); deadline.unref();
      process.emit('SIGTERM', 'SIGTERM');
    });
    require('next/dist/bin/next');
  `;
  web = spawn(process.execPath, ['-e', serverSource], { cwd: process.cwd(), env: { ...process.env }, stdio: ['ignore', 'pipe', 'pipe', 'ipc'] });
  let startupLog = "";
  for (const stream of [web.stdout, web.stderr]) stream?.on("data", data => { startupLog = (startupLog + data.toString()).slice(-2000); });
  await expect.poll(async () => {
    if (web.exitCode !== null) throw new Error('Next fixture exited before readiness: ' + startupLog);
    try { return (await fetch(base + '/login', { signal: AbortSignal.timeout(3000) })).status; } catch { return 0; }
  }, { timeout: 90000 }).toBe(200);
});
test.afterAll(async () => {
  test.setTimeout(30000);
  if (web && web.exitCode === null && web.connected) {
    const exited = new Promise<number | null>(resolve => web.once('exit', resolve));
    web.send('close');
    expect(await exited, 'Next CLI must close its owned server process').toBe(0);
  }
  await Promise.all([auth, api].filter(Boolean).map((s) => new Promise<void>((resolve) => { s.close(() => resolve()); s.closeAllConnections(); })));
});
test.beforeEach(async ({ page }) => { projects = []; tasks=[];fixtureEligible=true;fixtureDisposition="succeeded";failTaskPost=false;observations = []; rejectIdentity = false; stalledAuth = ""; authRequests = []; abortedAuth = 0;
  await page.route("**/*", (route) => { const u = new URL(route.request().url()); return ["127.0.0.1", "localhost"].includes(u.hostname) ? route.continue() : route.abort(); }); });
async function login(page: Page) { await page.goto("/login"); await page.getByLabel("Email address").fill("first@example.test"); await page.getByLabel("Password", { exact: true }).fill("offline-fixture-only"); await page.getByRole("button", { name: "Sign in", exact: true }).click(); await expect(page).toHaveURL(/\/projects$/); }


async function workspace(page:Page) {
  await login(page);
  await page.getByLabel("Project name").fill("My First Project");
  const [created]=await Promise.all([
    page.waitForResponse(r=>r.url().endsWith('/api/projects')&&r.request().method()==='POST'),
    page.getByRole("button",{name:"Create project",exact:true}).click()
  ]);
  expect(created.status()).toBe(201);
  await expect(page).toHaveURL(new RegExp(projectId),{timeout:15000});
  await expect(page.getByRole("heading",{name:"My First Project",exact:true})).toBeVisible();
}
test("offline submission persists and reopens safe text without replay",async({page})=>{
  await workspace(page);await expect(page.getByRole('button',{name:'Run task'})).toBeDisabled();
  await page.getByLabel('What would you like to work on?').fill('Summarize project');
  await page.getByRole('button',{name:'Run task'}).click();
  await expect(page.locator('pre')).toContainText('Actual mock result');
  expect(await page.evaluate(()=>('injected' in window))).toBe(false);
  await page.reload();await expect(page.locator('pre')).toContainText('Actual mock result');
  expect(observations.filter(x=>x.method==='POST'&&x.url.endsWith('/tasks'))).toHaveLength(1);
  await expect(page.getByText('Usage: Unavailable (unavailable)')).toBeVisible();
  await expect(page.getByText(/Savings:|Rewards:|\$0/)).toHaveCount(0);
});
for(const disposition of ['claimed','known_error','unknown','refused']) test('renders '+disposition,async({page})=>{
  fixtureDisposition=disposition;await workspace(page);
  await page.getByLabel('What would you like to work on?').fill('Task');await page.getByRole('button',{name:'Run task'}).click();
  await expect(page.getByText(disposition==='claimed'?'Claimed - outcome pending':disposition==='unknown'?'Unknown outcome - this task will not be retried':disposition==='known_error'?'Task could not be completed':'Request declined')).toBeVisible();
  await page.reload();expect(observations.filter(x=>x.method==='POST'&&x.url.endsWith('/tasks'))).toHaveLength(1);
});
test('real admission state has no activation control',async({page})=>{
  fixtureEligible=false;await workspace(page);
  await expect(page.getByRole('button',{name:'Run task'})).toBeDisabled();
  await expect(page.getByText('Execution is unavailable while supplier admission is pending. No task will be dispatched.')).toBeVisible();
  expect(observations.filter(x=>x.method==='POST'&&x.url.endsWith('/tasks'))).toHaveLength(0);
});
test('ambiguous POST failure is never automatically replayed',async({page})=>{
  failTaskPost=true;await workspace(page);await page.getByLabel('What would you like to work on?').fill('Task');
  await page.getByRole('button',{name:'Run task'}).click();await expect(page.getByRole('alert').filter({hasText:'Task outcome unavailable. Refresh tasks before submitting another request.'})).toContainText('Refresh tasks');
  await page.reload();expect(observations.filter(x=>x.method==='POST'&&x.url.endsWith('/tasks'))).toHaveLength(1);
});
test('task bridge strips client authority and enforces origin and allowlist',async({page})=>{
  await workspace(page);const path='/api/projects/'+projectId+'/tasks';
  expect((await page.request.post(path,{data:{}})).status()).toBe(403);
  expect((await page.request.get(path+'/arbitrary')).status()).toBe(404);
  expect((await page.request.get(path+'?organization_id=spoof')).status()).toBe(422);
  expect((await page.request.post(path,{headers:{origin:base,authorization:'Bearer spoof','x-organization-id':'spoof','x-private':'private'},data:{prompt:'Task'}})).status()).toBe(200);
  const request=observations.find(x=>x.method==='POST'&&x.url.endsWith('/tasks'))!;
  expect(request.headers.authorization).toMatch(/^Bearer ey/);expect(request.headers.cookie).toBeUndefined();
  expect(request.headers['x-organization-id']).toBeUndefined();expect(request.headers['x-private']).toBeUndefined();
});

test('older-page task opens persisted detail',async({page})=>{
  await workspace(page);
  tasks=Array.from({length:5},(_,i)=>({id:`44444444-4444-4444-8444-${String(i).padStart(12,'0')}`,prompt:`Saved task ${i}`,status:'succeeded',execution:{response_text:`Persisted older result ${i}`,usage:null,usage_status:'unavailable'}}));
  await page.reload();await expect(page.getByRole('button',{name:'Load older tasks'})).toBeVisible();
  await page.getByRole('button',{name:'Load older tasks'}).click();
  await page.getByRole('button',{name:'Open task Saved task 3',exact:true}).click();
  await expect(page.locator('pre')).toHaveText('Persisted older result 3');
  expect(observations.filter(x=>x.method==='POST'&&x.url.endsWith('/tasks'))).toHaveLength(0);
});
