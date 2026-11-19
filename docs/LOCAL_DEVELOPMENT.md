# CORE.1A Steps 1–5 local development

Use Node 22.22.0 / npm 10.9.4 and Python 3.12.10. Python metadata currently targets
3.12 only; widening support requires validation. Run commands from the repository
root. On Windows use `npm.cmd` if PowerShell blocks `npm.ps1`.

## Frontend

```text
npm ci
npm run typecheck:web
npm run build:web
npm run dev:web
```

The static foundation page runs on localhost:3000. No external fonts or services
are requested. `package-lock.json` pins transitive packages and integrity values.

## Backend

Create an isolated environment; do not install into system Python:

```text
python -m venv .venv
```

On Windows use `.venv\Scripts\python.exe` for the following `python` commands;
on POSIX use `.venv/bin/python`.

```text
python -m pip install -r services/api/requirements.lock
python -m pip install --no-deps --no-build-isolation -e services/api -e packages/provider-adapters
python -m pip check
python -m unittest discover -s tests -v
python -m jous_api.main
```

The API exposes `GET /health/live`, returning `{"status":"alive"}`. It does not
claim database, supplier, or inference readiness. `GET /health/ready` separately
checks PostgreSQL connectivity with `SELECT 1`: HTTP 200 reports `ready` and
`database: reachable`; HTTP 503 reports `not_ready` and `database: unavailable`.
Both readiness responses include `request_id`, matching `X-Request-ID`.
Missing configuration, connectivity failure, or timeout returns the same generic
503. It does not verify migrations, domain tables, suppliers, or inference.
The module launcher applies `JOUS_API_HOST`/`JOUS_API_PORT` and disables Uvicorn
access logs. If using Uvicorn's CLI instead, pass host/port explicitly and use
`--no-access-log`; CLI bind options are independent of Jous settings.
The provider package has no runtime dependencies or implementations. Editable
installs use the build backend pinned in the lock, avoiding a second resolver.

Environment examples contain placeholders only. Export values in your shell;
`.env` files are not automatically loaded. Never copy placeholder values into
an active environment. No secrets are required for local process-health checks.

| Variable | Default / requirement |
| --- | --- |
| JOUS_ENVIRONMENT | development; accepts development, test, production |
| JOUS_SERVICE_NAME | jous-api; 1–64 ASCII letters, digits, underscore or hyphen |
| JOUS_LOG_LEVEL | INFO; DEBUG, INFO, WARNING, ERROR, CRITICAL |
| JOUS_API_HOST | 127.0.0.1; bind hostname/IP |
| JOUS_API_PORT | 8000; integer 1–65535 |
| JOUS_DATABASE_URL | optional locally; required in production, PostgreSQL URL with host/database |
| JOUS_DATABASE_TIMEOUT_SECONDS | 5 seconds; finite number from 0.1 to 30 |
| JOUS_DATABASE_SECURITY_VALIDATION_TIMEOUT_SECONDS | 20 seconds; finite number from 0.1 to 30; bounds mandatory runtime security certification only |

Database configuration is masked and validated syntactically. Settings, imports,
app creation and startup do not connect; readiness or explicit database work
requests connectivity. For tests,
`load_settings({ ... })` avoids process-environment inheritance, and
`create_app(Settings(environment="test"))` allows explicit application setup.
Production configuration errors report variable names, not supplied values.
No CORS middleware is needed by the current static frontend, which does not
call the API. Origin configuration will be introduced with actual connectivity.

Application logs are JSON with UTC timestamp, severity, service, environment,
event, request ID and status where applicable. Startup/shutdown events and
request success/failure events are logged. Arbitrary log messages, exception
text/tracebacks, request bodies, query strings, paths and credentials are omitted.
Uvicorn's own lifecycle logs remain separate from application JSON logs.

`X-Request-ID` is an untrusted correlation label, never identity/authorization.
Exactly one incoming ASCII identifier of 1–64 characters is accepted when it
starts with a letter/digit and contains only letters, digits, dots, underscores
or hyphens. Missing, duplicate, oversized or malformed IDs are replaced by UUID
hex values. The ID is returned in responses and exposed through request state
and a task-local logging context. Clients must not put secrets in IDs.

Unexpected exceptions before response headers produce HTTP 500 with
`{"error":{"code":"internal_error","message":"Internal server error"},"request_id":"..."}`.
Failures after headers cannot replace the response/status; the boundary logs a
failure and terminates any unfinished body without internal details. Request
context is reset in all cases. More detailed diagnostics and streaming semantics
require a later bounded review; this gate does not implement streaming inference.

## PostgreSQL foundation

Use a dedicated managed development/test Jous PostgreSQL project, never production
credentials or another application's database. Supabase Session Pooler connectivity
is supported. Development does not require PostgreSQL or other persistent services
installed directly on Windows. No PostgreSQL service is created or started by
this checkout. Supply a `postgresql://` or `postgres://` URL through
`JOUS_DATABASE_URL`; the infrastructure selects SQLAlchemy's asyncpg dialect.
Percent-encode URL credentials as needed. Driver URL options must be compatible
with asyncpg (for example `ssl=require`, rather than libpq's `sslmode=require`).
Production TLS/certificate policy and deployment connection budget require a
deployment review; do not assume a successful probe proves secure deployment.

The app owns one async engine and async session factory. The pool is capped at
two connections per process with no overflow; timeout configuration bounds pool
checkout/connection establishment and the whole readiness probe. Shutdown
disposes the pool. SQL echo is disabled and SQL parameters are hidden.
`async with database.transaction() as session` explicitly scopes a unit of work:
commit on success, rollback on failure, and close the session on either path.
An empty transaction does not connect. Sessions must not be shared across tasks.
The unit suite uses actual empty SQLAlchemy sessions and mocked driver/probe
boundaries; it requires neither PostgreSQL nor SQLite.

For a real connectivity check, export your managed development database URL,
launch the API, and request `/health/ready`. Ordinary unit tests stay offline.

## Schema and migrations

Alembic uses the same Settings and asyncpg engine as the API. There is no URL in
`alembic.ini`, no extra driver, and no automatic environment-file loading. Export
private configuration through your shell or trusted development launcher; never
print it or put credentials in command arguments. New configuration variables are
not required. PostgreSQL's default application schema/search path must be `public`.
Migration SQL explicitly qualifies that schema.

Run from the repository root:

```text
python -m alembic -c services/api/alembic.ini history
python -m alembic -c services/api/alembic.ini heads
python -m alembic -c services/api/alembic.ini upgrade head --sql
python -m alembic -c services/api/alembic.ini upgrade head
python -m alembic -c services/api/alembic.ini current
python -m alembic -c services/api/alembic.ini check
```

Offline SQL rendering requires no credentials or network. Online commands require
an explicitly configured dedicated Jous database and appropriate migration-role
permissions. No model import, API import or startup runs migrations or `create_all`.
Initial revision `0001_identity_project` creates only `users`, `organizations`,
`organization_memberships`, and `projects` in `public`; Alembic maintains its own
`public.alembic_version` tracking table. Revisions are frozen, reviewed definitions
independent of current ORM models and become canonical history when committed.
Autogeneration/check comparison is limited to the explicitly registered Jous tables;
Supabase schemas and unrelated tables are excluded. Review every future revision.

Every record has an application-generated UUID, status, and timezone-aware
`created_at`/`updated_at`. Insert timestamps default to database `now()`. SQLAlchemy
updates `updated_at` on ORM-generated updates; direct SQL writers must set it
explicitly. No timestamp trigger or business workflow is installed.
User's optional `(auth_issuer, auth_subject)` linkage must be both absent or both
nonblank, and is unique when present. It has no foreign key to Supabase Auth.
Organization has a required nonblank name. Membership has required organization,
user, role and status; `(organization_id, user_id)` is unique. Role defaults to
`member`; statuses default to `active`. These bounded nonblank strings do not
implement RBAC, status transitions, or authorization. Project has required
Organization ownership/name/status and optional description. Names need not be
unique. Foreign keys use RESTRICT; no cascading deletes or soft-delete machinery.
Project's UUID remains the neutral context and economic attribution boundary.

Supabase automatic RLS was observed enabled on all four tables and Alembic's
version table during Step 4 validation. This code neither disables RLS nor adds
policies. The privileged migration connection can validate constraints; ordinary
client access is not implemented or authorized. Future runtime-role/policy design
requires its own scope and review.

For a destructive migration round-trip, use only a confirmed empty, disposable,
dedicated managed test project:

```text
python tests/validate_managed_migrations.py --target-fingerprint <verified-target-fingerprint>
```

This separate opt-in validator refuses production settings, a target mismatch or
any existing public relations. The fingerprint is the first 16 hex characters of
SHA-256 over `host:port/database/username`; it contains no credentials and must be
verified against the intended project before execution. The validator upgrades,
compares metadata and constraints, rolls back test rows, checks for unexpected
objects/data, downgrades to base, confirms removal, and upgrades again to head.
Managed relations/extensions are checked for changes. Downgrade removes only the
four domain tables and their indexes; Alembic's empty version table remains at base.
Never run this cycle on a populated/shared database. Do not use `CASCADE` or alter
managed objects to bypass a safety failure. A failed stage stops further changes;
inspect the current revision securely before proceeding.

## Non-public identity and tenant access

Step 5 implements `VerifiedPrincipal(issuer, subject)` as a trusted-adapter output
contract; it does not verify tokens. Issuer/subject values are matched exactly to
an active Jous User. They are omitted from repr. `RequestIdentity(user_id)` contains
only the internal User UUID, separate from request correlation. Unknown identities
fail closed, with no provisioning, account linking or email-based matching.

`AccessService` performs read-only SQLAlchemy queries. Organization access requires
the exact active User, active Organization, active membership joining both, and
recognized roles `member` or `owner`. Unknown statuses and roles deny
access; action permissions are centralized, with no admin or membership-management
behavior. Project access
additionally requires an active Project with both the requested Project UUID and
authorized Organization UUID. It rechecks the entire membership/active-record
relationship, so a previously constructed scope does not bypass revocation checks.
Immutable Organization/Project scope values contain verified identifiers; they
are not bearer capabilities. Internal services must continue scoped checks for
later operations. No identity or scope is stored in mutable global state.

FastAPI dependencies provide trusted principal resolution, one transaction/session
per request, identity mapping, and Organization/Project scopes. The default
`get_verified_principal` dependency verifies Bearer credentials through the Step 6
replaceable adapter; without configured issuer/JWKS it rejects with HTTP 401.
There is no impersonation configuration switch or trusted identity header. Test applications
can override dependencies in-process; temporary test routes are defined only in
tests and never registered in the normal app. Its only routes remain health routes.

Access failures return generic correlated JSON: HTTP 401 `identity_required` for
unresolved identity, HTTP 404 `resource_unavailable` for inaccessible resources.
Missing and cross-tenant Project errors are identical. Logs contain only bounded
events/status/correlation, never principal values, credentials or tokens. Client
Organization/Project identifiers select resources; they never establish authority.

Application-layer checks are the explicit Step 5 enforcement boundary. Existing
Supabase RLS remains enabled, with no new policies or role/grant changes. Controlled
tests use a privileged connection to prove application checks despite RLS bypass;
they do not prove runtime database-role isolation. Public CRUD remains blocked
until both Step 6 credential/action validation and Step 7 runtime database
role/RLS validation pass. Domain services contain no
Supabase-specific authorization semantics.

After securely exporting the managed test database configuration, run the separate
non-migrating validation:

```text
python tests/validate_managed_access.py --target-fingerprint <verified-target-fingerprint>
```

Use the fingerprint procedure above. The validator refuses production settings,
target mismatch, unexpected revision, nonempty domain tables or inability to see
unfiltered row counts. It creates unique temporary A/B/C identities and A/B tenant
records inside one transaction, checks positive and negative access, inactive and
unknown states, wrong ownership and stale/forged scopes, then rolls everything
back. It confirms empty tables, unchanged table/RLS/policy state and revision
`0001_identity_project`. It never runs migrations or alters managed schemas.
Managed PostgreSQL remains the development path; no local server installation is
required. Ordinary tests remain offline.

## Step 6 credential verification and action authorization

Export `JOUS_AUTH_ISSUER`, `JOUS_AUTH_AUDIENCE` and `JOUS_AUTH_JWKS_URL` through the
existing settings boundary. For the approved Jous project, issuer is
`https://aqcixpoorbhjgvdkdjqd.supabase.co/auth/v1`, audience is `authenticated`, and
JWKS is that issuer plus `/.well-known/jwks.json`. The example file contains only
placeholders. Omit both issuer/JWKS to reject all credentials; partial or unsafe
configuration fails validation. Settings/app construction makes no network request.

The provider-neutral verifier returns only `VerifiedPrincipal(issuer, subject)`.
Read-only identity resolution requires the exact mapping to an active pre-provisioned
internal User. No accounts, organizations, memberships or projects are provisioned;
no email linking exists. Supabase's enabled signup setting grants no Jous access.
Disabling signup before production-like controlled testing is a separate authorized
dashboard task. No dashboard settings are changed by this code.

The adapter permits ES256 only: trusted EC P-256 JWKS key, matching kid, exact issuer,
authenticated audience/role, canonical nonzero subject/session UUIDs and boolean
`is_anonymous=false`. It rejects HS256 without fallback, API/service-role profiles,
unsupported algorithms and malformed credentials. Exp/iat must be nonnegative integer
timestamps, exp must exceed iat, lifetime must not exceed 3600 seconds. Future iat,
optional nbf and expiration use 30 seconds of clock skew; no extra lifetime tolerance.
Old sessions must refresh or reauthenticate for new ES256 tokens. Local verification
does not establish real-time session existence or immediate logout revocation.

JWKS fetch uses only the configured HTTPS URL, no redirects or token-supplied URLs,
5-second network timeout and a 6-second async wait bound, 64 KiB maximum response,
1–16 keys, 300-second cache and at most one refresh attempt per adapter per 30 seconds.
A lazily created dedicated executor has one worker per verifier. The actual fetch
future remains tracked until fetching and validation finish; caller timeout or
cancellation never cancels or forgets shared work. Even after the refresh throttle
expires, no replacement fetch starts while that work is outstanding. Concurrent
callers coalesce around a shielded shared future. The state lock is never held during
network I/O; valid cached-key requests take a fast path without waiting for refresh.
Validated completion publishes the cache atomically on the application event loop,
including when all original callers have departed. Failure never extends cached
trust. Still-valid cached keys remain usable during outages; expired or absent keys
deny. App shutdown closes the verifier, denies new work, clears cached trust and
shuts down its executor without blocking the event loop. Late results cannot publish
after close. Blocking stdlib networking cannot forcibly terminate a stalled worker;
it remains tracked and capped at one until it finishes, and can delay interpreter
exit. Cache is app-local; identity/scopes remain request-local. No credential/claims/
exception details are logged.

`PermissionService.authorize(scope, action)` rechecks active membership and scoped
Project ownership before reading the persisted role. Member actions are Organization
read, Project list/create/read/update and own Membership read. Owner additionally
permits Organization name update and Project archive/deactivate. Project read/update/
archive require ProjectScope. Own Membership means the scope's user only; future
read APIs must use that identifier, never an arbitrary requested user. Unknown roles,
unknown actions and deferred administration/destruction/billing/ownership actions deny.
Scopes and action names do not authorize public endpoints: only health routes exist.
No write workflow, Step 7 role/context/RLS implementation or schema change is included.

## Repository safety

Existing untracked backup/review/website artifacts are outside Step 1. Preserve
them. Review explicit paths before any future staging; never use broad staging.
No CI is introduced in this step; full gate CI follows the verification suite.


## Step 7 offline security foundation (managed execution pending)

Runtime uses only `JOUS_DATABASE_URL` for the restricted `jous_runtime` login.
Alembic/admin tools require `JOUS_MIGRATION_DATABASE_URL`; neither falls back to the
other. Normal settings never ingest the admin secret. Configuration/engine imports
stay lazy; a configured API startup now explicitly validates runtime safety, and
readiness uses only that runtime connection. Without a DB the development/test
health-only shell starts, liveness succeeds and readiness returns 503.

Step 7 code and revision `0002_runtime_rls` are offline artifacts, not completed
managed infrastructure. Follow `services/api/infrastructure/README.md`; founder
review is mandatory before the first managed mutation. No local PostgreSQL is
required. Never run the retired Step 4 full downgrade cycle on the Step 7 database.

Protected transactions verify credential before checkout, validate runtime role and
clean baseline, initialize local `jous.user_id`/`jous.organization_id`, resolve exact
active identity, then validate membership before binding one Organization. Context
and sessions are request-local; uncertain connections are invalidated. No Project
context, onboarding or CRUD exists. Two privileged helpers read only Users and
Organization status. Membership/role decisions use ordinary RLS, and product actions
remain centrally authorized. Ordinary GUCs cannot prevent impersonation by an
attacker executing arbitrary SQL with a stolen runtime DB credential.

Offline inspection only (no credentials/connections):

```text
python -m unittest discover -s tests -v
python -m alembic -c services/api/alembic.ini heads
python -m alembic -c services/api/alembic.ini history
python tests/validate_managed_runtime_security.py --help
```

Only after managed preflight, founder execution approval, role bootstrap, migration
and secure runtime activation, explicitly invoke:

```text
python tests/validate_managed_runtime_security.py --opt-in-managed-validation --target-fingerprint <approved-fingerprint> --manifest <new-cleanup-manifest.json>
```

The fingerprint is SHA-256 of host:port/database/project-reference truncated to 16 hex characters,
excluding username/password. The approved public project reference is also checked
against the direct host or pooler username; a regional pooler host alone does not
identify a project. The validator also compares server identity. Use a new
manifest path; it refuses overwrite and records UUIDs/baseline before writes.
Temporary fixtures are committed administratively, runtime mutations rolled back,
and exact marked rows cleaned in reverse order. An interrupted run requires:

```text
python tests/validate_managed_runtime_security.py --opt-in-managed-validation --target-fingerprint <approved-fingerprint> --manifest <existing-cleanup-manifest.json> --cleanup-only
```

Cleanup-only needs the admin configuration, not a functioning runtime credential.
Retain manifest until baseline/revision verification succeeds. No unresolved cleanup
or skipped managed isolation evidence can pass the PUBLIC CRUD SECURITY GATE.


## V1.1 product candidate

V1.1 adds only approved-user sign-in, project list/create/read and a workspace
shell. Inference, tasks, pricing, ledger, savings and rewards are not enabled.
It creates no migration and leaves the foundation app/security modules unchanged.

Run the additive product factory (with the existing approved backend environment):

```powershell
$env:PYTHONPATH = "services/api/src"
.\.venv\Scripts\python.exe -m uvicorn jous_api.product_app:create_product_app --factory --host 127.0.0.1 --port 8000
```

This command is runtime activity: use it with a real database/Supabase account
only at a separately authorized acceptance gate. Startup uses the existing
restricted runtime safety checks; never substitute admin/migration credentials.
A valid Supabase identity must already map to an active internal User with exactly
one active eligible organization membership. Zero/multiple memberships deny;
there is no signup or provisioning workflow.

Frontend environment variable names (see apps/web/.env.example):

- NEXT_PUBLIC_SUPABASE_URL
- NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
- JOUS_API_INTERNAL_ORIGIN
- JOUS_APP_ORIGIN

The first two are public configuration. The latter two are server-only origins.
No service-role/database/migration/provider key belongs in frontend configuration.
Use an explicit writable temporary npm cache outside the repository on this
Windows checkout. Do not change user/global npm config or PowerShell policy.

```powershell
npm.cmd --cache "<approved-temporary-cache>" run dev:web
npm.cmd --cache "<approved-temporary-cache>" run build:web
npm.cmd --cache "<approved-temporary-cache>" run test:v1.1 --workspace=@jous/web
```

The browser uses same-origin /api/*; a restricted Next.js handler forwards only
approved methods/paths and its verified session bearer to the configured FastAPI
origin. It strips client authority/tenant headers and cookies. Product POSTs need
the exact application Origin and JSON. No failed write is automatically replayed.
Host-only SDK session cookies use SameSite=Lax and Secure in production; browser
SDK cookies are JavaScript-readable. Authenticated responses are not shared-cacheable.
Logout clears the browser session but does not promise immediate revocation of
already-issued access JWTs. Tokens, credentials and project contents must not be logged.

Focused backend tests (no database/network):

```powershell
$env:PYTHONPATH = "services/api/src;tests"
$env:PYTHONDONTWRITEBYTECODE = "1"
.\.venv\Scripts\python.exe -B -m unittest test_project_service test_product_api -v
```

The Playwright suite owns loopback-only synthetic Auth/API servers and a Next.js
development server. It does not certify real Supabase, PostgreSQL/RLS or deployment.
Reports go to the OS temporary directory. Playwright owns startup and teardown;
do not use privileged process inspection. Next dev may generate apps/web/AGENTS.md
and development next-env.d.ts imports; these are toolchain changes, not product
source. The reviewed candidate excludes the generated AGENTS file and keeps the
canonical production-build type declarations after the final build.

Before real V1.1 acceptance, separately authorize configuration and restricted
DB use, verify the controlled user's existing identity/membership, then prove
create/list/reopen and cross-organization denial against the actual database.
No inference-provider or authority-provider adoption is part of that acceptance.

V1.1 auth availability: Supabase auth transports (including JWKS, refresh,
sign-in and sign-out) use a 4-second application deadline and abort their
network request, including response acquisition. Server auth operations also
have a 4-second scope. Auth transport errors are fail-closed and not retried.
The restricted API skips Proxy refresh and owns an 8-second total budget from
token acquisition through FastAPI response acquisition; it never replays writes.
Page Proxy refresh and page authorization are separately bounded; a page may
traverse more than one auth scope. A valid external session with unavailable
Jous access shows generic recovery with sign-out, not an identity-specific reason.
# V1.2 offline candidate: task/context/execution

The additive product factory remains `jous_api.product_app:create_product_app`.
It now mandates the product successor validator at readiness and before scoped
transactions. Default `jous_api.main:create_app` keeps foundation validation.
Do not start either against a real database without separate runtime authority.

For offline tests use the existing Python 3.12 environment and source paths:

```powershell
$env:PYTHONPATH = "services/api/src;packages/provider-adapters/src;tests"
$env:PYTHONDONTWRITEBYTECODE = "1"
python -B -m unittest test_task_context test_token_budget test_supply_adapter test_execution_service test_task_service test_task_api test_product_schema test_product_runtime_validation
```

Use the exact reviewed requirements lock and local package declarations when
preparing an authorized environment. No global installation is required.
The HF route is unconditionally unavailable for real execution; there is no
activation variable, credential override, client override or test-result override.
No provider credential is required by this offline candidate.

Offline browser fixtures own loopback Auth/API/Next processes. Run V1.1 using
its unchanged Playwright config and V1.2 with `playwright.v1_2.config.ts` from
`apps/web`, using the approved `npm.cmd` temporary-cache launcher. No real Auth,
database or supplier service belongs in those fixtures. They use synthetic
identities/responses, not operational admission evidence. No POST is replayed.

Migration FILE `0003_project_tasks_executions.py` is present but NOT applied.
Do not run Alembic online or the disposable PostgreSQL tests at this gate.
`services/api/infrastructure/validate_v1_2_product_schema.py` requires explicit
future disposable authorization and a dedicated loopback database; it does not
apply migrations. The integration test module is separately gated and is not
part of offline discovery. These local/disposable-environment instructions are
not the managed-target status: managed Jous Supabase Dev later applied 0003 and
0004 and passed post-migration/runtime acceptance, as recorded in the final
status addendum in `docs/build-journey/V1.2-task-context-execution.md`.

Before operational adoption: independently review the candidate, separately
authorize disposable PostgreSQL role/catalog/RLS/cross-tenant certification,
resolve hosted token/template authority, and admit account executability.
Managed database acceptance does not establish provider readiness or authorize
deployment/publication. Mock success proves none of those operational
prerequisites.
