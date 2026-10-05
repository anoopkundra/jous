# Step 7 controlled infrastructure

These artifacts have not been executed. No local PostgreSQL installation is needed.
Use the dedicated managed project and Session Pooler with verified TLS.

## Mandatory managed-change stop

Before any mutation, capture the target fingerprint, PostgreSQL version, migration
revision (0001), actual ownership, existing RLS/policies and effective PUBLIC/role
grants. Have the founder review that evidence and approve execution. Stop if shared
Supabase privileges must change; do not alter managed roles, objects or schemas.

Runtime guards reject effective database CREATE, permanent schema CREATE,
object/database ownership, memberships and unrelated table access. The approved
compatibility exception accepts either no TEMP privilege or TEMP supplied solely
by PUBLIC without grant option. Explicit runtime TEMP grants remain prohibited.
Supabase currently exposes PUBLIC TEMP; do not change shared managed-role ACLs.
The validator reports MANAGED_PUBLIC_TEMP_BASELINE from checked catalog evidence.
Jous's normal runtime does not require or create temporary objects. TEMP retains
resource-exhaustion and name-shadowing risk; objects can survive commit and pooled
session reuse. Privileged helpers must keep hardened search_path and qualified
protected relations to resist pg_temp shadowing. This residual capability does
not change tenant/RLS architecture or application action authorization.

`runtime_roles.sql` refuses any conflicting existing role. It creates no password,
role memberships, or jous_owner. Existing administrative ownership remains. The
administrator must be able to create the private schema, assign helper ownership,
and manage policies on the four Jous tables. Never solve insufficient authority by
giving runtime privileged membership. Record any separately approved admin grants.

## Ordering

1. Complete offline tests and security review.
2. Read-only managed preflight and founder stop/review before mutations.
3. Execute the reviewed role bootstrap; inspect restricted attributes/memberships.
4. With only `JOUS_MIGRATION_DATABASE_URL` in migration tooling, upgrade to
   `0002_runtime_rls`; inspect functions, ACLs, policies and ENABLE/FORCE flags.
5. Activate a runtime password securely outside source, SQL artifacts and logs.
   Export `JOUS_DATABASE_URL` for the actual `jous_runtime` login. Do not reuse admin.
6. Run the explicitly opted-in managed validator with both separately held URLs.
7. Verify fixture cleanup, unchanged managed objects, counts and final revision.
8. Security review and separate PUBLIC CRUD SECURITY GATE. No CRUD is implemented.

The schema owner temporarily grants CREATE on the new private schema to the helper
owner solely to assign function ownership, then revokes it before migration commit.
For a non-superuser PostgreSQL 17 migration admin, ownership transfer also requires
SET capability to jous_security_reader; ADMIN OPTION alone is insufficient. Obtain
that capability only through a separately authorized temporary prerequisite, keeping
INHERIT false. It is not permanent runtime or role-bootstrap authority. Complete
PUBLIC revocation and runtime EXECUTE grants while the admin still owns each helper;
ownership transfer is the final function-management operation for that helper during
upgrade. Verify migration ownership/ACLs, then remove temporary SET authority with
grantor-aware membership cleanup and verify the final membership state. Prefer one
controlled transaction encompassing prerequisite, migration, verification and cleanup;
if separately committed, a migration failure requires explicit prerequisite cleanup.
Future helper changes require bounded owner maintenance: temporary SET capability,
an explicit helper-owner role section where owner commands are needed, restoration
of the admin role, and removal of temporary authority before commit. The admin-owned
helper schema permits the existing PostgreSQL 17 downgrade to drop its contained
helpers without permanent SET capability; verify schema ownership before downgrade.
Helper SELECT policies are role-specific and read-only. Ordinary GUCs are not a
cryptographic boundary against someone executing arbitrary SQL with runtime login.

## Atomic Step 7 operator runner (not executed)

`apply_step7_atomic.py` is operator-only, never an application startup migration.
Import and `--help` do not connect. Use the trusted reviewed CPython virtual environment
with isolated mode and disabled bytecode writes:

```powershell
.\.venv\Scripts\python.exe -I -B services/api/infrastructure/apply_step7_atomic.py --help
```

For a separately authorized mutation, retain `-I -B` and explicitly supply the
confirmation flag, approved execution SHA and approved CA path. Mutation rejects a
non-isolated interpreter. The first bootstrap imports only built-in sys and frozen
os/path, removes repository source/CWD search paths before shadowable standard-library
imports, and defers installed SQLAlchemy/Alembic imports until after the identity gate.
The venv/interpreter, installed dependencies and their startup hooks are trusted operator
prerequisites: -I ignores PYTHONPATH and user site, but does not disable trusted venv
site .pth hooks. sitecustomize, interpreter replacement and any code executed before the
file's first instruction cannot be attested retroactively by this runner. Use a controlled
venv, no unreviewed startup hooks, and exclusive local administrative maintenance.

Infrastructure, migrations and src are audited for untracked executable/importable files,
symlinks and caches before credential access. No caches are silently deleted: STOP and
have the operator remove them separately before an authorized run. -B prevents new cache
writes; it alone does not prevent cache reads. Repository paths stay off sys.path; the
verified Jous package uses a source-only importer. Contract inspection and operator-scoped
Alembic loading compile verified source bytes directly, bypassing cached-code loaders.
Alembic repeats the Git/import-surface gate immediately before loading migrations; source
bytes are rechecked on every repository module load. Thus a later .pyc cannot substitute
for reviewed source even after that gate. No alternate .pyc migration path is accepted.
These controls apply to repository code, not trusted installed dependency bytecode.

A fresh Jous application namespace is mandatory. Before repository verification,
before installing the verified-source importer, after dependency loading but before
credential access, and immediately before Alembic, the runner rejects every existing
sys.modules name equal to jous_api or beginning with jous_api. This includes modules
from the venv or any external origin; installed origin is not source attestation.
Names such as jous_api2 are unrelated. A contaminated interpreter stops; no modules
are silently purged. Start again in a fresh isolated interpreter. Only subsequent
intentional env.py imports may populate the namespace through the verified-source
loader. The offline Alembic regression resolves the actual 0002 revision callback
while retaining a fake-DBAPI caller transaction and forbidding cached repository
loaders; it does not execute migration SQL or connect to PostgreSQL.

Managed execution requires the exact
`--confirm-managed-mutation` flag, an explicit `--ca-file`, and only
`JOUS_MIGRATION_DATABASE_URL`; there is no runtime-credential fallback or .env edit.
Execution requires `--approved-execution-sha <40-lowercase-hex-sha>` with no default.
The founder supplies that immutable commit identity independently after review/commit;
never derive approval from the current HEAD. HEAD and origin/main must both match it,
and the tracked tree must be clean. Git blob contents are compared with working files
for the runner, all migrations, Alembic configuration, runtime_roles.sql, all jous_api
source, backend pyproject.toml and requirements.lock. Unexpected files in audited source
trees fail closed, including every __pycache__ directory and .pyc/.pyo file; only checkout CRLF/LF
conversion is tolerated. Protected documentation artifacts may remain untracked.
Migration 0002 is independently pinned to reviewed Git blob
`0e2cf9e7cefcb40110359eded43e48a3e74f67d7`. Its pin must undergo code review if that
migration intentionally changes. The external execution commit avoids embedding a
runner commit's own SHA in its source. Current uncommitted state cannot execute.

The runner accepts exactly one PEM certificate, with only whitespace outside its block.
Bundles and leading/trailing non-whitespace are rejected. Base64 decoding is strict and
canonical: excess data after padding, extra padding and malformed payloads fail closed. Its DER fingerprint must match
the approved CA; only those same verified DER bytes are loaded into a fresh TLS-client
context with no system-root fallback. CERT_REQUIRED and hostname verification remain
mandatory. URL routing/TLS query overrides are rejected before engine creation.
The runner requires the approved CA fingerprint, certificate and hostname verification,
the Jous project-qualified admin identity, database postgres and Session Pooler port
5432. It uses NullPool, one held connection and one caller-owned outer transaction.
A transaction advisory lock coordinates copies of this runner only; it cannot exclude
unrelated administrators. Schedule exclusive administrative maintenance separately.
Baseline catalog gates must all pass before the first membership grant.

Preserve the automatic bootstrap-superuser membership unchanged. Add only a temporary
postgres-granted membership with ADMIN false, INHERIT false and SET true. Verify that
exact additional row and effective authority, pass the same synchronous Connection
to corrected Alembic 0002, and verify security catalogs inside the transaction. Remove
only the postgres-granted row with GRANTED BY postgres RESTRICT. Require complete
baseline membership restoration, SET false and inherited authority false, then rerun
security assertions. Only afterward perform the single final commit.

Policy names, commands, roles and modes are exact. USING/WITH CHECK clauses are
compared locally using an allow-listed structural recognizer for the four pinned 0002
guards. It retains function identity, arguments, boolean structure, tenant predicates
and meaningful casts. Only bounded PostgreSQL deparser spelling equivalences are
accepted: parentheses/whitespace, catalog-qualified builtins, text coercions on known
text operands, CAST-to-uuid spelling and literal IN/ANY spelling. Unknown syntax fails
closed. No catalog policy text is submitted for SQL execution or EXPLAIN planning;
there is no planning fallback. Offline fixtures are not live deparser/isolation proof:
an unfamiliar benign managed representation must STOP for review, never be accepted by
loosening the comparison during an operator run.

Helper identity includes exact schema/name/type sequence, parameter names/order,
argument modes/defaults, return type, language, owner, SECURITY DEFINER, volatility,
parallel mode, fixed search_path and reviewed textual body. Alternate SQL-body storage
is rejected. Helper ACLs and effective EXECUTE/grant-option state are verified.

Privilege audits exclude only exact pg_catalog/information_schema/pg_toast and numeric
PostgreSQL pg_temp_/pg_toast_temp_ namespaces. User schemas such as pgx/pga/pg1 are
included in schema CREATE, relation, sequence and routine audits. All non-system
pg_proc kinds are audited for both Jous roles; only the two exact helper signatures
are allowed after migration, with implicit owner grant authority only for their owner.
No other user-routine EXECUTE or grant option is silently accepted, including PUBLIC
access. Default ACL audits explicitly include PUBLIC/OID 0 and both Jous roles for all
catalog object classes; unexpected future-object grants fail closed. Existing managed
routine/default privileges may therefore require separate reviewed allowance decisions;
this runner does not alter them or whitelist public-schema routines.

Separate follow-up security debt: production jous_api/database.py still uses the unsafe
namespace pattern NOT LIKE 'pg_%', whose underscore is a wildcard. This runner fixes
its own audit only. Production remediation needs separate authorization/review and
must not be treated as resolved by this patch. This debt does not itself block runner
commit or intrinsically block migration 0002; it DOES block later jous_runtime activation. These catalog checks are not proof of
actual runtime-login isolation; live validation remains separately authorized.

Pre-commit failure rolls back the outer transaction. Cancellation drains rollback and
connection cleanup. Cleanup retains the public asyncpg driver reference and verifies
physical closure, with terminate fallback, rather than trusting swallowed adapter errors.
Rollback/cleanup uncertainty is reported explicitly. A commit error is UNKNOWN, never
automatically retried: reconcile through separately authorized read-only inspection.
An acknowledged commit followed by cleanup failure is reported as committed with
cleanup unconfirmed, not as rolled back. Separate founder authorization is still needed
for post-commit read-only reconciliation, runtime activation and managed behavior tests.
The full managed mutation validator is not invoked by this runner.

## Validation and recovery

Use `tests/validate_managed_runtime_security.py --help` offline for options. Require
a caller-provided target fingerprint and cleanup manifest path. The fingerprint
uses host/port/database/public project reference, excluding credentials; both logins must also identify the
same server-side database. The manifest contains generated UUIDs and target metadata,
never secrets. Fixtures are administratively committed so real runtime connections
can see them. Runtime mutations roll back. Cleanup deletes only recorded rows in
Project, Membership, Organization, User order. Keep manifests until baseline checks
pass; `--cleanup-only` retries exact cleanup after an interrupted process.

Partial bootstrap requires inventory/review, not automatic role replacement.
Migration errors require revision/transaction-state inspection before retry.
Connection, ACL, ownership or recursive-policy failures keep runtime traffic blocked.
Do not disable RLS or add broad policies to make a failing test pass.

An explicitly authorized downgrade targets `0001_identity_project`, never base. It
removes Step 7 objects/grants and FORCE while retaining the required pre-existing
ENABLE RLS state. Role lifecycle and credential deactivation are separate tasks.
Unresolved fixture cleanup is a failure and needs targeted administrative recovery.

Runtime ORM metadata explicitly targets public for all four domain relations;
authorization queries cannot resolve same-named pg_temp relations. Offline compiled
SQL checks are not live isolation evidence. A later separately authorized managed
validator must exercise actual temporary-shadow scenarios before the security gate.
