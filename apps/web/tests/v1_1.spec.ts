// Deterministic loopback services only. These are NOT Supabase/DB certification.
import { test, expect, type Page } from "@playwright/test";
import http from "node:http";
import { spawn, type ChildProcess } from "node:child_process";
import { createECDH, createHash, createPrivateKey, createPublicKey, sign } from "node:crypto";
const uid = "11111111-1111-4111-8111-111111111111";
const projectId = "22222222-2222-4222-8222-222222222222";
const org = "33333333-3333-4333-8333-333333333333";
const base = "http://127.0.0.1:3009";
// Inert deterministic key: worker restarts must not rotate a cached JWKS kid.
const fixtureD = createHash("sha256").update("Jous V1.1 offline-only test key; never operational").digest();
const fixtureCurve = createECDH("prime256v1"); fixtureCurve.setPrivateKey(fixtureD);
const fixturePoint = fixtureCurve.getPublicKey();
const privateKey = createPrivateKey({ key: { kty: "EC", crv: "P-256", d: fixtureD.toString("base64url"), x: fixturePoint.subarray(1, 33).toString("base64url"), y: fixturePoint.subarray(33).toString("base64url") }, format: "jwk" });
const publicKey = createPublicKey(privateKey);
const jwk = { ...publicKey.export({ format: "jwk" }), alg: "ES256", kid: "offline-v1-1-stable", use: "sig" };
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
  const message = encode({ alg: "ES256", kid, typ: "JWT" }) + "." + encode({ iss: "http://127.0.0.1:8791/auth/v1", sub: uid, aud: "authenticated", role: "authenticated", session_id: uid, is_anonymous: false, iat: now, exp: expired ? now - 3600 : now + 3600 });
  return message + "." + sign("sha256", Buffer.from(message), { key: privateKey, dsaEncoding: "ieee-p1363" }).toString("base64url");
}
function json(res: http.ServerResponse, code: number, value: unknown) { res.writeHead(code, { "content-type": "application/json", "access-control-allow-origin": base, "access-control-allow-headers": "authorization,apikey,content-type,x-client-info,x-supabase-api-version", "access-control-allow-methods": "GET,POST,OPTIONS", "x-request-id": "offline-request-1" }); res.end(JSON.stringify(value)); }
function listen(server: http.Server, port: number) { return new Promise<void>((resolve, reject) => { server.once("error", reject); server.listen(port, "127.0.0.1", resolve); }); }
test.beforeAll(async () => {
  test.setTimeout(120000);
  // Only fixture-local origins/keys. No application credential is read.
  Object.assign(process.env, { NEXT_TELEMETRY_DISABLED: "1", NEXT_PUBLIC_SUPABASE_URL: "http://127.0.0.1:8791", NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: "sb_publishable_local_fixture_only", JOUS_API_INTERNAL_ORIGIN: "http://127.0.0.1:8792", JOUS_APP_ORIGIN: base });
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
  await listen(auth, 8791); await listen(api, 8792);
  // The supported Next server runs in a fixture-owned Node child so Next's
  // require hooks cannot alter Playwright's own TypeScript loader.
  const serverSource = `
    // Match a normal CLI launch: -e belongs only to this fixture wrapper.
    process.execArgv = [];
    process.argv = [process.execPath, require.resolve('next/dist/bin/next'), 'dev', '--hostname', '127.0.0.1', '--port', '3009'];
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
test.beforeEach(async ({ page }) => { projects = []; observations = []; rejectIdentity = false; stalledAuth = ""; authRequests = []; abortedAuth = 0;
  await page.route("**/*", (route) => { const u = new URL(route.request().url()); return ["127.0.0.1", "localhost"].includes(u.hostname) ? route.continue() : route.abort(); }); });
async function login(page: Page) { await page.goto("/login"); await page.getByLabel("Email address").fill("first@example.test"); await page.getByLabel("Password", { exact: true }).fill("offline-fixture-only"); await page.getByRole("button", { name: "Sign in", exact: true }).click(); await expect(page).toHaveURL(/\/projects$/); }

test("unauthenticated redirects and invalid sign-in fails safely", async ({ page }) => {
  await page.goto("/projects"); await expect(page).toHaveURL(/\/login$/);
  await page.getByLabel("Email address").fill("first@example.test"); await page.getByLabel("Password", { exact: true }).fill("incorrect"); await page.getByRole("button", { name: "Sign in", exact: true }).click(); await expect(page.locator('form [role="alert"]')).toHaveText("We couldn't sign you in. Check your details and try again.");
});
test("sign in, create My First Project, reopen workspace and sign out", async ({ page }) => {
  await login(page); await page.getByLabel("Project name").fill("My First Project"); await page.getByLabel("Description", { exact: false }).fill("Our first focused workspace"); const [created] = await Promise.all([page.waitForResponse((r) => r.url().endsWith("/api/projects") && r.request().method() === "POST"), page.getByRole("button", { name: "Create project", exact: true }).click()]);
  expect(created.status()).toBe(201);
  // The first workspace route may still be compiling in the dev-server fixture.
  await expect(page).toHaveURL(new RegExp(projectId), { timeout: 15000 }); await expect(page.getByRole("heading", { name: "My First Project", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run task" })).toBeDisabled(); await expect(page.getByText("Our first focused workspace")).toBeVisible();
  await page.getByRole("link", { name: "Projects" }).click(); await page.getByRole("link", { name: /My First Project/ }).click(); await expect(page).toHaveURL(new RegExp(projectId));
  await page.getByRole("button", { name: "Sign out" }).click(); await expect(page).toHaveURL(/\/login$/); await page.goto("/projects"); await expect(page).toHaveURL(/\/login$/);
});
test("restricted API paths, methods and missing identity deny", async ({ request }) => {
  expect((await request.get("/api/me")).status()).toBe(401);
  expect((await request.get("/api/admin")).status()).toBe(404);
  expect((await request.post("/api/me", { data: {} })).status()).toBe(404);
  expect((await request.delete("/api/projects")).status()).toBe(405);
  expect(observations).toHaveLength(0);
});
test("Origin, JSON, size and tenant query protections", async ({ page }) => {
  await login(page); const client = page.request;
  expect((await client.post("/api/projects", { data: { name: "Blocked" } })).status()).toBe(403);
  expect((await client.post("/api/projects", { headers: { origin: "https://other.invalid" }, data: { name: "Blocked" } })).status()).toBe(403);
  expect((await client.post("/api/projects", { headers: { origin: base, "sec-fetch-site": "cross-site" }, data: { name: "Blocked" } })).status()).toBe(403);
  expect((await client.post("/api/projects", { headers: { origin: base, "content-type": "text/plain" }, data: "Blocked" })).status()).toBe(415);
  expect((await client.post("/api/projects", { headers: { origin: base, "content-type": "application/json" }, data: "x".repeat(16385) })).status()).toBe(413);
  expect((await client.get("/api/projects?organization_id=other")).status()).toBe(422);
  expect(observations.filter((x) => x.method === "POST")).toHaveLength(0);
});
test("API forwards its session bearer only and preserves safe correlation", async ({ page }) => {
  await login(page); const result = await page.request.post("/api/projects", { headers: { origin: base, authorization: "Bearer browser-spoof", "x-organization-id": "spoof", "x-unapproved": "private" }, data: { name: "My First Project", description: null } });
  expect(result.status()).toBe(201); expect(result.headers()["x-request-id"]).toBe("offline-request-1"); expect(result.headers()["cache-control"]).toBe("private, no-store");
  const request = observations.find((x) => x.method === "POST")!;
  expect(request.headers.authorization).not.toContain("browser-spoof"); expect(request.headers.authorization).toMatch(/^Bearer ey/);
  expect(request.headers.cookie).toBeUndefined(); expect(request.headers["x-organization-id"]).toBeUndefined(); expect(request.headers["x-unapproved"]).toBeUndefined();
  await page.goto("/projects/44444444-4444-4444-8444-444444444444"); await expect(page.getByRole("heading", { name: "Project unavailable" })).toBeVisible();
});
test("responsive workspace shell has no fake economics", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 }); await login(page);
  await page.getByLabel("Project name").fill("My First Project"); await page.getByRole("button", { name: "Create project", exact: true }).click();
  await expect(page.getByRole("heading", { name: "My First Project", exact: true })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  await expect(page.getByPlaceholder("AI execution is coming in the next build.")).toBeDisabled();
  await expect(page.getByText(/\$0|Savings:|Rewards:/)).toHaveCount(0);
});

async function fixtureSession(page: Page, expired = false, kid = "offline-v1-1-stable") {
  const session = { access_token: token(kid, expired), refresh_token: "offline-refresh-only", token_type: "bearer", expires_in: 3600, expires_at: Math.floor(Date.now() / 1000) + (expired ? -3600 : 3600), user: { id: uid } };
  await page.context().addCookies([{ name: "sb-127-auth-token", value: "base64-" + Buffer.from(JSON.stringify(session)).toString("base64url"), url: base, sameSite: "Lax" }]);
}
test("external session with rejected Jous identity has stable generic recovery and sign out", async ({ page }) => {
  rejectIdentity = true;
  await login(page);
  await expect(page.getByRole("heading", { name: "Workspace access unavailable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign out", exact: true })).toBeVisible();
  await expect(page.getByLabel("Project name")).toHaveCount(0);
  await expect(page.getByText(/internal_fixture|unmapped|disabled|First organization/)).toHaveCount(0);
  await page.goto("/login");
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "Workspace access unavailable" })).toBeVisible();
  await page.goto("/projects/" + projectId);
  await expect(page.getByRole("heading", { name: "Workspace access unavailable" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run task" })).toHaveCount(0);
  expect(observations.length).toBeLessThan(8); // Reaching stable UI must not hide a redirect cycle.
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeVisible();
});
for (const operation of ["token", "jwks"]) {
  test(`stalled auth ${operation} cancels transport, denies unsafe bridge and never calls FastAPI or retries`, async ({ page }) => {
    await fixtureSession(page, operation === "token", operation === "jwks" ? "uncached-stall-key" : undefined);
    stalledAuth = operation;
    const started = Date.now();
    const response = await page.request.post("/api/projects", { headers: { origin: base }, data: { name: "Never created" } });
    expect([401, 503]).toContain(response.status());
    expect(Date.now() - started).toBeLessThan(6500);
    await expect.poll(() => abortedAuth, { timeout: 1500 }).toBe(1);
    expect(authRequests.filter(url => url.includes(operation))).toHaveLength(1);
    expect(observations).toHaveLength(0);
    const message = await response.text();
    expect(message).not.toMatch(/8791|8792|refresh|offline|Bearer|127\.0\.0\.1/);
    expect(response.headers()["cache-control"]).toBe("private, no-store");
  });
}
test("stalled browser sign in aborts and returns a generic usable form", async ({ page }) => {
  await page.goto("/login"); stalledAuth = "token";
  await page.getByLabel("Email address").fill("first@example.test");
  await page.getByLabel("Password", { exact: true }).fill("offline-fixture-only");
  const started = Date.now();
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page.locator('form [role="alert"]')).toHaveText("We couldn't sign you in. Check your details and try again.", { timeout: 6500 });
  expect(Date.now() - started).toBeLessThan(6500);
  await expect.poll(() => abortedAuth, { timeout: 1500 }).toBe(1);
  expect(authRequests.filter(url => url.includes("token"))).toHaveLength(1);
  expect(observations).toHaveLength(0);
  await expect(page.getByRole("button", { name: "Sign in", exact: true })).toBeEnabled();
});
test("server page navigation with stalled refresh is bounded and fails closed", async ({ page }) => {
  await fixtureSession(page, true); stalledAuth = "token";
  const started = Date.now();
  await page.goto("/projects");
  await expect(page.getByRole("heading", { name: "Workspace access unavailable" })).toBeVisible({ timeout: 15000 });
  expect(Date.now() - started).toBeLessThan(15000);
  expect(observations).toHaveLength(0);
  expect(abortedAuth).toBeGreaterThan(0);
  await expect(page.getByLabel("Project name")).toHaveCount(0);
});
