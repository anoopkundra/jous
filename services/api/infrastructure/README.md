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
`cae08d9cf548480fb5d064becca1e89ca2dd898b`. Its pin must undergo code review if that
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

Policy verification uses direct pg_policy/pg_class/pg_namespace inventory, including
policy/relation/owner OIDs, exact namespace/name, numeric role OIDs, command and
permissiveness, and raw nullable pg_node_tree text. Clauses are opaque exact data:
no parser, normalization, formatter, planning or expression execution is used.
The runner and runtime share the same structural verifier. Unexpected policies,
wrong typed values, duplicates and NULL/non-NULL changes fail closed.

The amendment base remains immutable at SHA256
`60efef97d11e85a0be679a32f5aa3163f35017f4bebf8d6120bdb183731734e0`.
The old `step7_public_compat_amendment_candidate.json` is retained historical,
non-executable evidence and is never a production input. The mandatory
`step7_operator514_amendment.json` adds only the two independently observed
strict booleans for operator 514. Its exact hash and evidence/query linkage are
checked before composition. The base bytes remain unchanged; the standalone
base cannot satisfy the current execution schema.

The mandatory `step7_policy_template_contract.json` combines the 19 exact raw
clauses, seven NULL positions, 31 finite OID slots, fixed built-in closure,
ordered column contracts and created helper/schema expectations. Its exact
bytes are verified before parsing. It hash-links the installed PG17.11 BKI and
headers used as inert offline provenance; installed files are not execution
inputs. Historical golden evidence is provenance, never an execution fallback.

`step7_execution_contract.py` issues distinct immutable contract, independently
verified binding, expected-policy, actual-policy and continuity objects. Binding
constructors reject unissued/forged objects. Expected trees are instantiated
before policy collection, using byte-offset substitutions only. No parser,
normalization, deparser or live learning is used. All positive attribute rows
are inventoried: dropped placeholders and extra columns fail. Fixed referents,
columns, type I/O relationships and helper/schema ACLs are checked independently.

The atomic runner freezes preflight identities, applies unchanged pinned 0002
in the outer transaction and checks the exact expected policy set. Policy OIDs
are opaque positive unique identifiers, retained in the first verified snapshot
and required unchanged on the second pass after temporary membership removal.
Existing identities/layouts, built-ins and created helper/schema metadata/ACLs
are revalidated on both passes. Every mismatch rolls back before the sole commit.
The legacy `APPROVED_POLICY_CONTRACT=None` concrete-record interface is not an
atomic-runner approval input; runtime activation remains separately unapproved.

Both new artifacts retain migration/runtime approval false. This implementation
does not supply an approved execution SHA, commit source or authorize mutation.
All new source/artifacts are covered by the runner's committed-source gate.

Offline verification: run `.venv\Scripts\python.exe -I -B tests/run_step7_offline.py`.
The harness denies network and all external process creation, .env reads and repository
writes. It uses a socket-free timer-only event loop; the source-import integration
case uses an isolated in-memory import namespace and fake DBAPI.

Helper identity includes exact schema/name/type sequence, parameter names/order,
argument modes/defaults, return type, language, owner, SECURITY DEFINER, volatility,
parallel mode, fixed search_path and reviewed textual body. Alternate SQL-body storage
is rejected. Helper ACLs and effective EXECUTE/grant-option state are verified.

Privilege audits exclude only exact pg_catalog/information_schema/pg_toast and numeric
PostgreSQL pg_temp_/pg_toast_temp_ namespaces. User schemas such as pgx/pga/pg1 are
included in schema CREATE, relation, sequence and routine audits. All non-system
pg_proc kinds are audited for both Jous roles. Direct EXECUTE is limited to the two
exact helpers after migration, with implicit owner grant authority only for their
owner. PUBLIC compatibility is a separate exact reviewed contract below, never a
schema-name exception. Default ACL audits explicitly include PUBLIC/OID 0 and both
Jous roles for all catalog object classes; unexpected future-object grants fail closed.

### Reviewed managed PUBLIC compatibility

`step7_public_compat_manifest.json` is data-only reviewed configuration, converted
offline from the independently reviewed candidate evidence. It contains exactly two
pg_stat_statements views and 96 routines (48 C and 48 SQL/PLpgSQL). Its exact UTF-8
bytes are pinned by SHA256 in the runner and included in the externally approved Git
execution identity. No path override, live learning, hash regeneration or alternate
manifest version is supported. Byte/hash, duplicate-key, unknown-key, type, Unicode,
finite-value and closed-schema failures stop before credential access. Routine source
and raw catalog node text remain data only and are never executed or planned.
Deparsed view/default text is no longer a live security requirement in V2.
Production JSON uses sorted keys, compact separators, UTF-8 and no literal newline
or terminal newline so Git autocrlf cannot change its pinned bytes. Escaped source
newlines decode to the exact reviewed prosrc bytes; no source normalization occurs.

Every verification inventories the complete PUBLIC relation and routine ACL surface
across non-system namespaces, including NULL ACL built-in defaults and all pg_proc
kinds. Unknown/missing objects, overloads, wrappers, sequences, duplicate identities,
PUBLIC column grants and unexpected default ACLs fail closed. Independent direct ACL
audits cover databases, schemas, relations/sequences, columns and routines; an allowed
PUBLIC ACL never masks a direct grant. Only migration 0002's exact Jous grants are
allowed after migration.

Object ACL authority remains inventoried when ordinary schema lookup is blocked.
Each entry separately pins effective schema USAGE for both roles: platform entries
are lookup-blocked; public is reachable. This is not a general proof against indirect
calls, cached plans or privileged wrappers. Newly reachable schemas stop execution.
The helper owner retains its stricter NOLOGIN, no-membership-expansion, narrow Jous
SELECT and exact two-helper ownership checks; shared PUBLIC ACLs do not equate its
role contract with runtime authorization.

Option B uses target-specific, nonportable catalog evidence. Manifest V2 pins
PostgreSQL 17.11 / 170011 and the current database OID/name, numeric encoding,
ICU provider, locale/rules, COLLATE/CTYPE and recorded collation version exactly.
No locale normalization or automatic upgrade acceptance is permitted.

The two reviewed views use exact raw pg_rewrite _RETURN association, flags,
ev_qual and ev_action bytes with local SHA256. Eleven reviewed default-bearing
routines use exact raw proargdefaults and argument/default binding metadata.
There is no AST parser and no native view/expression deparser or type/signature
formatter in PUBLIC compatibility collection. Catalog joins map raw type OIDs
to namespace/name directly; column OIDs, typmods, collations and composite linkage
are separately compared. The obsolete CONST-only deparser guard is removed.

Unchanged embedded OIDs are protected by finite reviewed referents: 20 types,
17 functions, five namespaces, PL/pgSQL language/support-function linkage, two
extensions, one operator, one collation and three relation/column layouts.
All outgoing pg_depend rows for the bounded selected roots must equal the
reviewed 47-edge set. Added, missing or duplicate edges fail closed. These are
built-in catalog scalar/array/text values; referenced routines, type output,
typmod output, handlers and providers are never invoked by verification.
Database-default collation context is read directly from exactly one current
pg_database row, without a provider-aware actual-version function.

Internal PostgreSQL "char" catalog scalars are explicitly projected as
pg_catalog.text under their original aliases. Installed asyncpg decodes raw
internal "char" as bytes; these built-in casts provide str without Python byte
normalization, custom codecs, referenced type output or provider invocation.
Raw pg_node_tree text handling remains unchanged. Manifest validation enforces
unsigned OID domains with positive real identities/owners and field-specific zero
sentinels. Dependency subobjects are nonnegative; selected user-column numbers
are positive int2 values. Negative typmods, lengths and encoding are preserved.

Database rebuilds, target-local OID changes, PostgreSQL version changes and
catalog-visible semantic/provenance changes require explicit re-review.
Evidence candidates are review inputs only, never runtime dependencies.
The reviewed production manifest bytes have an independent SHA256 pin in the
runner, checked before parsing and credential access. Hosted PostgreSQL, ICU,
OS and extension binary integrity remain platform trust assumptions; recorded
catalog version checks do not prove loaded binary integrity. For selected C/internal
referents, a prosrc digest identifies the catalog entry-point symbol, not a C body
or binary-security fingerprint.

The statistics views can contain sensitive operational metadata; compatibility does not
classify that data as harmless. Routine checks pin stable catalog type identities,
parameter binding/modes/defaults, return type, owner/security posture, language,
SECURITY DEFINER, volatility/parallel/strict/leakproof, proconfig, ACL and reachability.
SQL/PLpgSQL source is SHA256(UTF8(prosrc)) with no normalization. C routines instead
pin library and entry-point symbol plus exact extension identity/version: pgcrypto 1.3,
uuid-ossp 1.1 and pg_stat_statements 1.11. This does not prove hosted binary integrity.

`public.rls_auto_enable()` is a dedicated REVIEWED_EVENT_CALLBACK_PUBLIC_ACL exception,
not an ordinary privileged API or generic platform allowance. Its exact body hash,
event_trigger return type, postgres owner, SECURITY DEFINER and pg_catalog search_path
are checked, along with exactly one ensure_rls/ddl_command_end/O binding and the exact
CREATE TABLE, CREATE TABLE AS, SELECT INTO tags. The installed callback logs/suppresses
errors; independent migration RLS/FORCE checks remain mandatory. Any changed body,
security property or binding requires review. New platform/extension versions or ACL,
definition, ownership, reachability and provenance drift fail closed.

This compatibility patch does not revoke platform privileges or authorize managed
execution. A separately founder-approved committed execution SHA and explicit managed
mutation authorization are still required. Never use this operator at application startup.

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

### Read-only collection evidence retention

`step7_readonly_evidence.py` is a data-only boundary, not a connection launcher.
The previous managed collection scripts were ephemeral; future separately
authorized collectors must wrap their single reviewed connection in
`EvidenceConnection` AFTER verifying client-facing pinned TLS, intended target,
and transaction read-only state. Pass the reviewed `text` statement factory and
only independently approved routine source bodies for optional source disclosure.
Do not call the migration pipeline/preflight or acquire its advisory lock.

Run the complete reviewed SELECT-only pre-migration collection through
`connection.collect(callback, Stop)`. Every successful SELECT's primitive rows
are retained before caller assertions. The production PUBLIC routine collector
records exact expected/observed identities and deterministic added/missing sets
before enforcing its existing set/duplicate checks. Unknown routine bodies and
configuration are hash-only, not arbitrary sensitive text disclosure.

On `EvidenceFailure`, retain `error.document` in memory, perform rollback and
connection cleanup, then persist it only as an `INCOMPLETE_FAIL_CLOSED` candidate.
Its completion, execution approval, and migration-readiness flags are false.
Unexpected exception messages are never serialized. A complete candidate may
supersede an incomplete candidate only after ALL reviewed pre-migration gates
and cleanup pass. Neither outcome approves amendment execution or supplies
unobserved post-0002 policy trees. This boundary does not authorize a connection.

### Post-cleanup evidence finalization

Future authorized collectors must use `step7_readonly_finalize.run_lifecycle`
instead of duplicating artifact finalization in an ephemeral script. Construct
`FinalizationState` with the verified evidence connection and non-secret metadata;
record each named required gate only after its reviewed assertion passes. The
state initializes every primary/amendment input and retains the authoritative
snapshot independently of the collection callback's return value.

The lifecycle attempts rollback, close, and engine dispose in order, even when
one fails. Only after all cleanup succeeds does it serialize and publish primary
evidence. Failed cleanup retains an incomplete in-memory snapshot and explicitly
withholds publication. Primary serialization/write failures report fixed failure
codes, retain observations, and never claim successful publication. Recovery from
an unavailable destination requires operator action; no secondary artifact can
substitute for the lost current snapshot.

Only after confirmed primary publication may secondary amendment processing run.
Missing/invalid amendment input, serialization failure, or write failure leaves
the primary bytes intact and reports a separate failure. Incomplete collection
never processes an amendment. All approval/readiness flags remain false, including
for complete pre-migration collection; unobserved post-0002 trees remain unresolved.
Writers must use `atomic_publish` with an expected destination preimage hash (or
`None` for a new destination), at caller-owned local paths. It uses a verified,
flushed sibling temporary file and atomic replacement; it is not a hostile-writer
filesystem compare-and-swap. Retain the state until publication has been confirmed.
No connection, credential acquisition, or execution authorization is supplied by
this lifecycle.

### Reviewed realtime.authorize inventory amendment

`step7_realtime_authorize_amendment.json` is a compact, SHA-pinned supplement to
the unchanged 96-routine Manifest V2. It recognizes only the independently
reviewed target-specific `realtime.authorize(text,text,text,text,text,text[],text[])`
inventory drift. `step7_realtime_authorize_amendment.py` composes a 97-routine
candidate in memory and verifies it using the existing production exact-set and
metadata comparator, together with mandatory exact supplemental evidence checks.
Numeric OIDs, exact body, argument/return metadata, raw/effective ACL provenance,
dependency edges/bindings, and both Jous roles' reachability remain pinned.
Catalog sets are compared as complete multisets; argument arrays remain ordered.
Unexpected/missing routines and relaxed schema/owner reachability fail closed.

Production now requires `verify_public_compatibility` as the authoritative gate:
the exact composed 97 inventory and `collect_snapshot`'s full supplemental catalog
contract are mandatory together. `verify_grants` and `verify_routines` both enter
this gate; `public_inventory` also always collects and verifies the supplement.
The old metadata comparator is private and is not an approval API. No flag or
96-routine fallback exists. Startup verifies both frozen inputs before credential
access; the supplement's implementation is included in committed-source coverage.
The historical 96-row base parser remains a data loader, never sufficient approval.
The unresolved M1/post-0002 raw-policy gates remain unchanged. Execution, migration
and runtime activation approval are false.
Neither the base manifest nor the separate unresolved M1 amendment is rewritten.
This routine performs transactional authorization probes, including INSERT against
realtime.messages and transaction-local role/context/GUC changes. Inventory
compatibility does not approve invocation or describe it as side-effect-free.
Independent review must assess the production integration before execution is
considered. This patch does not authorize a connection or migration.

### F1/F2/F3 offline catalog remediation

The final policy contract pins catalog character values as characters (`prokind=f`),
booleans as strict booleans, and lengths as integers. The frozen Windows AMD64
`internal` representation is length 8 / alignment `d`. Retained `pg_config.h`
(`SIZEOF_VOID_P=8`, `ALIGNOF_DOUBLE=8`) and `pg_type.h` (`TYPALIGN_DOUBLE=d`)
establish the reviewed platform resolution; `pg_config_manual.h` establishes
64-bit float-by-value. Unresolved macros are rejected by the review-only generator.

Every finite built-in type, function (including support/selectivity functions),
operator and collation now verifies bootstrap owner OID 10 and target stable role
`supabase_admin`. The OID comes from BKI and `pg_authid_d.h`; the target role name
comes from the immutable base's already pinned function-141 owner binding. This
is independent of public-table owner `postgres`. SQL collects both owner fields.

The review-only generator is `tests/step7_bki_regenerate.py`. Pinned inert BKI and
headers are retained under `tests/fixtures/step7_pg17_11_catalog/`, with source
hashes in `AUTHORITY.json`. Ordinary production execution never reads installed
PostgreSQL source. Test observations are retained in a separate catalog JSON
fixture and authenticated by an independent BKI reader; they are not copied
from the final contract or generated by its generator. Authority tests and
verifier mutation tests are separate. Reversing only this remediation's expected
value/owner/provenance changes reproduces the old policy artifact SHA exactly.

Current policy-contract SHA256:
`1d212a755e951be68094981e97486c8cbf10d8c28bf8d845e9b252f183391648`.
M1, approved raw templates/slots, frozen parent evidence and execution ordering
remain unchanged. Migration execution and runtime activation remain unapproved.
