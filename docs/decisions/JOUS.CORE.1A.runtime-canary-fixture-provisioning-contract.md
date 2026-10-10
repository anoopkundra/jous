# JOUS.CORE.1A Step 7 runtime canary fixture provisioning contract

Status: OFFLINE CANDIDATE FOR INDEPENDENT REVIEW. This document grants no managed
access or mutation authority. Fixtures are NOT provisioned by this task; the lease
is NOT implemented or reserved; runtime credentials are NOT provisioned; no managed
evidence is collected; canary execution is NOT authorized; runtime is NOT activated.
All fixture identities below are symbolic. No real UUIDs, subjects, tokens,
credentials, customer data or production-derived fixture values are supplied.

## 1. Source authority and boundaries

Committed baseline: HEAD/origin/main
`bb8bc7281065bfb591f242d4a128e7ec8dd1b640`, tree
`b65715928682fca4aebde887fb4fa60b8f6a7b88`.
Published plan: `docs/decisions/JOUS.CORE.1A.runtime-canary-fixture-plan.md`, blob
`f0f3f445c1cdf2151d0c1769989eac48197089a7`, SHA256
`a9223abc6d72edb84895cf75d504ddddad85d82c6441601702af17a3bf51947e`.
That plan's freshness, serialized register, quarantine and activation boundaries
remain authoritative and unchanged.

Initial FIXTURE_PROVISIONING lease/bootstrap behavior additionally requires the
operation-specific refinement in
`docs/decisions/JOUS.CORE.1A.runtime-canary-fixture-provisioning-bootstrap-amendment.md`:
independently approved amendment candidate, 15708 bytes, SHA256
`2aec6ebeddd4267548981a76d017cd2001417bad33804a246ed6264646d64ef3`, prospective blob
`1713898695d32b04ccd26833b68e94fa4a1c0545`. It is not yet published/committed.
The amendment and this reconciled contract must be independently approved and
adopted together before operational use; this candidate grants no such authority.

Derivation sources at this commit:

- `services/api/migrations/versions/0001_identity_project.py`: actual table DDL,
  defaults, primary/foreign keys, constraints and indexes. It is inspected only.
- `services/api/src/jous_api/models.py` and `persistence.py`: current field mapping;
  important distinction between ORM UUID defaults and database server defaults.
- `services/api/migrations/versions/0002_runtime_rls.py`: applied FORCE RLS,
  policies, helper identity resolution and restricted column grants. Never rerun.
- `services/api/src/jous_api/access.py`, `permissions.py`: issuer/subject resolution,
  active relationships and member permissions.
- `services/api/src/jous_api/database.py`, `runtime_policy.py`,
  `step7_execution_contract.py`, `runtime_resolution.py`, `runtime_transport.py`:
  frozen runtime verification, context lifecycle and separate secure runtime path.
- `services/api/infrastructure/validate_runtime_canary.py` and
  `docs/decisions/JOUS.CORE.1A.runtime-canary-procedure.md`: exact consumer contract.
- `tests/test_runtime_readiness_remediation.py`: confirmation, manifest, identity,
  rollback and isolation regressions; no tests or application code are executed here.

Four distinct contracts must remain separate:

| Class | Contents | Storage/authority |
| --- | --- | --- |
| Persisted database fields | Only columns of the four public tables below | Committed schema plus exact future approved row values |
| External provenance | Synthetic purpose, creation authority, history, classification, approvals | Access-controlled evidence ledger; never invented DB columns |
| Future credentials/auth configuration | Provisioning access, separate runtime login, issuer/JWKS/audience and CA | Separate authorization/configuration; secrets excluded from documents/evidence |
| Operational lease | Request/set hashes, IDs, owner, expiry, operation state, acknowledgement | Sole external durable register and serialized issuer; no Jous schema change |

This contract is a specification, not a provisioning harness or executable SQL
approval. The exact parameterized query/mutation texts, secure executor and concrete
identities must be supplied and independently reviewed in the future package.

## 2. Exact fixture topology and actor inputs

| Tenant | Actor | User | Organization | Membership | Project |
| --- | --- | --- | --- | --- | --- |
| A | ACTOR_A | USER_A | ORG_A | MEMBERSHIP_A | PROJECT_A |
| B | ACTOR_B | USER_B | ORG_B | MEMBERSHIP_B | PROJECT_B |

Allocate eight distinct UUIDs offline as future package inputs, never at this design
stage. They must be distinct across all eight records, not merely within each table.
Subjects for ACTOR_A and ACTOR_B must be distinct, immutable, nonblank, synthetic,
dedicated to this canary, and never customer-assigned. Each actor input consists of
approved issuer, immutable subject, corresponding proposed USER UUID and external
synthetic-identity evidence. Neither email nor password nor bearer token is a Jous
fixture column or a required input to the committed canary.

The approved issuer must satisfy runtime authentication configuration and match
both users and the eventual manifest. Issuer/subject lengths are 1..255 characters,
nonblank after trimming; exact approved strings are preserved. The helper resolves
an active user by this exact pair. AccessService binds its UUID and then validates
active membership/organization/project relationships. No actor may resolve as the
other user. VerifiedPrincipal is constructed by the canary; it does not perform
auth-provider sign-in or bearer/JWKS verification.

MEMBERSHIP_A links only USER_A to ORG_A; MEMBERSHIP_B only USER_B to ORG_B.
PROJECT_A references ORG_A; PROJECT_B references ORG_B. Each user has exactly one
membership, its own, with no inactive or active membership anywhere else. No
cross-tenant membership, shared project, customer relationship or reused customer
record is permitted. Projects have an organization_id, not a user owner column.
Organizations have no owner column; do not fabricate one.

## 3. Exact minimum database record values

Every table is explicitly in `public`. All IDs are UUID primary keys, NOT NULL.
The migration defines no database UUID default; the ORM's Python uuid4 default
does not apply to direct provisioning SQL. Supply every approved ID explicitly.
Every record has NOT NULL timestamptz created_at and updated_at, each with server
default now(). Omit these two columns on INSERT, RETURN their values and record
them in evidence. They should equal the transaction-start timestamp for this one
transaction. ORM onupdate for updated_at is not a database update trigger.

All status columns are NOT NULL varchar(32), default `active`, with a nonblank
check. Supply `active` explicitly, rather than treating any nonblank status as valid.
The exact future INSERT projections and values are:

| Symbols / table | INSERT columns and values | Default/generated output |
| --- | --- | --- |
| USER_A, USER_B / public.users | id = proposed USER UUID; auth_issuer = approved common issuer; auth_subject = corresponding immutable subject; status = active | created_at, updated_at from server defaults |
| ORG_A, ORG_B / public.organizations | id = proposed ORG UUID; name = approved synthetic nonblank name; status = active | created_at, updated_at |
| MEMBERSHIP_A, MEMBERSHIP_B / public.organization_memberships | id = proposed MEMBERSHIP UUID; user_id = own USER UUID; organization_id = own ORG UUID; role = member; status = active | created_at, updated_at |
| PROJECT_A, PROJECT_B / public.projects | id = proposed PROJECT UUID; organization_id = own ORG UUID; name = approved synthetic nonblank name; description = SQL NULL; status = active | created_at, updated_at |

Other schema facts relevant to provisioning:

- Users: nullable varchar(255) auth_issuer/auth_subject; the pair must be both NULL
  or both non-NULL/nonblank. This fixture requires the latter. Unique constraint
  on (auth_issuer, auth_subject) must hold for both approved pairs.
- Organizations/projects: name is NOT NULL varchar(255) with nonblank check.
  Neither table has a unique-name constraint. Names cannot establish ownership
  or identity and must never drive reconciliation/deletion.
- Memberships: user_id and organization_id are NOT NULL foreign keys with
  ON DELETE RESTRICT; role is NOT NULL varchar(32), default member and nonblank.
  Unique (organization_id, user_id); user_id index is not a uniqueness guarantee.
- Projects: organization_id is NOT NULL FK with ON DELETE RESTRICT and indexed;
  description is nullable text with no specified server default.

Choose actual UUIDs, issuer/subjects, approved synthetic names and external request
ID at future package construction. Timestamps are captured outputs, not invented
fixed observations. No auth-provider UUID is assumed to equal the Jous USER UUID.
No generated sequence ID, extra JSON column, synthetic flag, tenant owner or
provisioning-status column is introduced.

## 4. Least privilege and synthetic data

Require role `member` for both memberships. MEMBER_ACTIONS includes CREATE_PROJECT
and UPDATE_PROJECT; those are the positive canary writes. PermissionService also
rechecks the exact active relationships. Applied RLS permits own-tenant project
INSERT/UPDATE with the approved runtime column privileges; it does not grant user,
organization or membership provisioning authority. `owner` is unnecessary.

Proposed deterministic naming rule for future concrete review: organizations use
`JOUS SYNTHETIC CANARY <APPROVED_SET_LABEL> ORG_A` / `ORG_B`; existing projects use
`JOUS SYNTHETIC CANARY <APPROVED_SET_LABEL> PROJECT_A` / `PROJECT_B`. The set label
must be a non-personal opaque operator-issued label and names must fit 255 characters.
These are templates, not chosen production names. Subject allocation follows the
approved synthetic identity process; do not infer an identity-provider format.
No real person, customer email, organization/project name or copied customer metadata.

Classification customer_data=NONE, production_traffic_eligibility=NEVER and
canary_only=true lives in evidence and operational routing/access controls, not DB
columns. Names alone do not enforce traffic exclusion. Record lifetime customer
exclusion and never transfer synthetic assets to customer ownership.

## 5. Future provisioning authority and transport

Use a separately approved provisioning administrative identity/process, explicitly
different from jous_runtime and its application credential. Never use the NOLOGIN
helper owner as a login. Never automatically reuse the migration credential or an
admin connection merely because it works. This document chooses no actual role,
credential carrier or credential value; the future package must name the identity,
credential acquisition boundary and finite capability evidence.

Required capabilities are authenticated access to the fixed approved project,
USAGE on public, bounded SELECT for collision/relationship/verification predicates,
INSERT on the explicit projections above, and SELECT for returned persisted fields.
Critically, the four tables have FORCE RLS. Ownership alone does not establish
effective INSERT/SELECT access. Current runtime/helper policies do not constitute
an administrative provisioning policy. The future review must prove how the
selected existing authority legitimately obtains effective access under unchanged
RLS (including any pre-existing administrative bypass), and inventory its actual
capabilities rather than pretend a row-bounded admin grant exists.

Require only the authority needed, bounded by the reviewed execution method and
exact parameter inventory. If no suitable existing identity/capability boundary
exists, STOP: separately review its establishment; do not create roles, change
policies, grant privileges, disable FORCE/RLS or assume a new role in this operation.
Any broader existing admin capability requires explicit risk review and containment;
it is not license for arbitrary SQL or customer reads. No UPDATE/DELETE authority
is exercised in provisioning. Future retirement has separate authority.

Future transport must bind the source-approved managed project/target/database
and verified hostname TLS with the approved CA pin; no fallback. Exact role-specific
connection representation and secure credential handling need future independent
review. Runtime's jous_runtime-only transport is not a provisioning connector.
No secret may appear in arguments visible to process listings, shell history,
SQL logs, exceptions, source, manifest or evidence. Reviewed local gates precede
credential acquisition; never ingest unrelated credentials or start public traffic.

## 6. Exact future mutation inventory and order

Eight single-row INSERTs only. Each must RETURN the approved row projection,
report exactly one inserted row and match the expected record before proceeding.
No ON CONFLICT, UPSERT, silent skip, UPDATE, DELETE or auto-adoption of existing rows.

| Order | Table / symbol | Operation / count | Dependency |
| --- | --- | --- | --- |
| 1 | public.users / USER_A | INSERT exactly 1 | approved ACTOR_A issuer/subject evidence |
| 2 | public.users / USER_B | INSERT exactly 1 | approved ACTOR_B issuer/subject evidence |
| 3 | public.organizations / ORG_A | INSERT exactly 1 | synthetic authorization |
| 4 | public.organizations / ORG_B | INSERT exactly 1 | synthetic authorization |
| 5 | public.organization_memberships / MEMBERSHIP_A | INSERT exactly 1 | USER_A and ORG_A |
| 6 | public.organization_memberships / MEMBERSHIP_B | INSERT exactly 1 | USER_B and ORG_B |
| 7 | public.projects / PROJECT_A | INSERT exactly 1 | ORG_A |
| 8 | public.projects / PROJECT_B | INSERT exactly 1 | ORG_B |

Total expected new records: 2 users, 2 organizations, 2 memberships, 2 projects.
No schema, DDL, roles, grants, policies, triggers, helper modifications, migrations,
bookkeeping writes or unrelated data mutations. External auth operations are not
part of this SQL inventory and require their own exact approved operation list.

## 7. Bounded pre-provision reads

Future authorization must supply exact finite parameterized SELECT texts with
explicit schema/catalog resolution and returned-field limits. This document
specifies predicates/results; it does not execute or authorize those queries.

1. For each of the four target tables, check id membership in the exact eight
   proposed UUIDs (cross-type collision avoidance); require zero returned records.
2. Users: match only the two proposed (issuer, subject) pairs; require zero. Do not
   search arbitrary customer identities or return colliding customer field values.
3. Memberships: predicate user_id in {USER_A, USER_B} OR organization_id in
   {ORG_A, ORG_B}; require no rows, including either own/cross pair. Projects:
   organization_id in {ORG_A, ORG_B}; require no rows. Any row means partial/collision.
4. Verify the exact target and session authority/capability gate, applied migration
   0002 and unchanged relevant table/column/default/FK/security assumptions through
   a separately reviewed finite catalog projection; no exploratory SQL.
5. Register/provider/operator evidence: no conflicting canary, provisioning,
   maintenance, retirement, prior uncertain attempt or customer association. Auth
   identity uniqueness/assignment is provider evidence, not a query to invented
   auth tables in this schema.

All collision observations are fail-closed categories/counts; if unexpected rows
could be customer data, STOP without dumping their values or claiming ownership.
No partial fixture set may be completed opportunistically. Unique constraints
remain the final collision backstop; an insert conflict rolls back, never retries.
These preconditions are repeated inside the write transaction; an earlier read
does not substitute for execution-time checks. No database advisory/table lock is
added; normal transactional/constraint locking from the exact INSERTs is inherent.

## 8. Database atomicity and uncertain outcomes

The committed schema permits all eight records in ONE transaction on ONE bounded
administrative connection. The future executor must explicitly establish BEGIN,
run approved target/preconditions, perform the eight INSERTs in order, verify all
returned fields/counts and complete relationship/state predicates, then COMMIT only
if every fact and operational gate holds. Otherwise ROLLBACK and close/dispose.
The exact isolation, timeouts, cancellation and transaction-control surface must
be independently approved with the executor; do not imply an existing runner.

Approved IDs and natural-key uniqueness plus serialized participating writers
avoid blind collision adoption. No concurrent fixture writer is allowed. Any
lease loss/expiry, cancellation, connection failure, mismatched return or unknown
state prevents further INSERTs/COMMIT and requires cleanup. Commit uncertainty
means QUARANTINED, no retry: a separately authorized bounded reconciliation must
establish the actual committed state. Do not infer rollback from a lost response.
Retain finite per-step and commit/rollback/close outcomes without raw exceptions.

Database atomicity is all-or-nothing for these eight transactional rows only.
It does not guarantee external auth atomicity or absence of nontransactional
side effects. The future prerequisite catalog review must exclude unexpected
trigger/hooks or schema drift affecting the bounded operation. Operational audit
logs and external evidence may persist intentionally.

## 9. External authentication and partial failure

Determine first whether the approved synthetic actor process requires provider
creation. The canary needs issuer/subject mappings, not an auth sign-in. Do not
create real provider accounts by inference. If identities must be created, use
exact separately reviewed provider actions for ACTOR_A/B, dedicated synthetic
provenance and no customer reuse. Before generation, require the approved
PRE_AUTH_PROVISIONING_REQUEST and durable acknowledgement specified in section 11;
it fixes database identities while unknown subjects remain explicitly pending.
Record generated subjects, independently reconcile the actual issuer/subject pairs,
then approve a new immutable AUTH_IDENTITIES_BOUND request and atomically advance
the same reservation with durable acknowledgement before any database INSERT.

External creation is a distinct phase under the same mutually exclusive fixture
operation, with a reviewed phase deadline. It does not share PostgreSQL atomicity.
If PRE_AUTH is acknowledged, A succeeds and B fails, remain in the same provisioning
lifecycle, record PARTIALLY_PROVISIONED and quarantine; no database phase.
If both actors exist but the AUTH_IDENTITIES_BOUND transition/acknowledgement is
uncertain, NO database provisioning: quarantine and reconcile under separate
authorization. If AUTH_IDENTITIES_BOUND is acknowledged but database work rolls
back/fails, existing database rollback/quarantine rules apply; retain identity
evidence, with no automatic deletion or new identities.
If an external response is uncertain, do not repeat creation: reconcile exact
request/identity through separately authorized provider evidence.

Compensation requires independent exact-identity review, customer-exclusion proof,
current state and separate explicit provider/DB retirement authority. It may be
retention in quarantine or exact-ID retirement, never broad deletion. No distributed
transaction, automatic rollback of auth identities or speculative repair is claimed.

## 10. Retry/idempotency state model

States are evidence/control metadata, not new database columns:

| State | Meaning | Next permitted action |
| --- | --- | --- |
| NOT_STARTED | Proven no external or DB creation began; exact inputs still unused | New explicit authorization/reservation after fresh collision checks |
| PARTIALLY_PROVISIONED | Known external partial creation or unexpected partial DB state | Quarantine; independent reconciliation, no inserts |
| PROVISIONED_VERIFIED | Exact eight rows committed, independent state/provenance verification complete | No repeat provisioning; proceed only to manifest review |
| QUARANTINED | Any ambiguity, mismatch, expiry with work outstanding or uncertain commit/cleanup | Separately authorized diagnosis/recovery; no blind retry |

PARTIALLY_PROVISIONED always blocks the register's availability. A matching row
is not idempotent success without creation authority/history and exact set review.
No retry within an execution authorization. A reconciled DB rollback may permit
a new DB-only request reusing proven dedicated auth identities, but requires a
new reviewed concrete package/reservation. An unexpected subset of DB rows cannot
result from a confirmed all-or-nothing operation; investigate rather than fill gaps.

## 11. Provisioning exclusivity and manifest bootstrap

Use the published plan's ONE authoritative register/serialized issuer. Provisioning
must atomically exclude CANARY, FIXTURE_MAINTENANCE, FIXTURE_RETIREMENT and another
FIXTURE_PROVISIONING request on the same or overlapping component identities.
Apply the exact approved bootstrap amendment identified in section 1 after adoption.
No local lease or availability observation is sufficient. Atomic compare-and-reserve
must issue exactly one winner for simultaneous otherwise eligible overlapping
requests; all others are rejected, never silently queued or acquired later.

For FIXTURE_PROVISIONING, require an independently approved immutable
`jous.runtime-canary-provisioning-request.v1` artifact, bound by
provisioning_request_sha256 = SHA256(exact approved request bytes). Before initial
reservation, PRE_AUTH_PROVISIONING_REQUEST fixes USER_A, USER_B, ORG_A, ORG_B,
MEMBERSHIP_A, MEMBERSHIP_B, PROJECT_A and PROJECT_B UUIDs, all distinct, the logical
fixture-set identity, synthetic database values, membership/project relationships,
member roles and active statuses. It also binds stable logical actor/provider
allocation scope, approved generation instructions, contract/amendment identities,
authorization/package identity and the remaining minimum fields in amendment
section 3. Independently review/approve exact bytes/hash before acquisition.
No actual values are chosen here; unknown subjects are not fabricated.

Require durable authoritative acknowledgement identifying reservation ID, operation
FIXTURE_PROVISIONING, set identity, provisioning_request_sha256, phase, conflict-key
set/reference, owner, authorization/package, issuance/start/expiry and active state.
Require ACKNOWLEDGED + ACTIVE + UNEXPIRED before any separately authorized external
creation or database access. PRE_AUTH acknowledgement permits only the separately
authorized external actor-generation phase; it DOES NOT authorize PostgreSQL
fixture INSERTs. No database fixture mutation may occur in PRE_AUTH.

After generation, independently reconcile actual issuer/subject pairs and approve
new immutable AUTH_IDENTITIES_BOUND request bytes/hash. The sole serialized issuer
must atomically advance the SAME reservation from the exact PRE_AUTH predecessor
hash to that new provisioning_request_sha256, preserving operation, fixture-set
identity, all eight UUIDs, approved database values and all prior conflict keys.
Add actual issuer/subject keys without releasing old keys or creating a reservation
gap. Preserve predecessor request/hash history, approval and transition audit.
Require a new durable AUTH_IDENTITIES_BOUND acknowledgement, not merely a submitted
transition or local provider result. If actors are already independently established,
the amendment permits initial AUTH_IDENTITIES_BOUND acquisition under all its gates.

Before ANY of the eight PostgreSQL INSERTs require BOTH authoritative reservation
phase AUTH_IDENTITIES_BOUND AND separately approved exact managed fixture-provisioning
mutation authorization. Lease acknowledgement alone never authorizes mutation.

Conflict keys cover logical fixture-set identity, every proposed UUID regardless of
table, stable logical actor/provider allocation keys during PRE_AUTH, and actual
issuer/subject pairs after binding. Retain all PRE_AUTH keys for the operation's
lifetime; enforce the amendment's deterministic encoding/scope and reject ambiguous
allocation. All overlapping operation types conflict; maintenance/retirement binding
artifacts require separate authority, not implicit provisioning semantics.

For CANARY an already-generated, independently reviewed, exact approved final
`jous.runtime-canary-fixtures.v1` manifest remains mandatory. Its NEW reservation
binds fixture_manifest_sha256 to exact approved bytes. Neither hash substitutes for
the other; no PRE_AUTH canary, provisional manifest, automatic conversion or launch.
The future separately reviewed register must enforce these typed bindings and
phase/overlap rules; support for final canary manifests alone is insufficient.

Provisioning expiry is a concrete reviewed duration covering external/DB phases,
verification and cleanup; it is not the five-minute canary freshness window.
No automatic renewal, silent queued acquisition, owner replacement or lease steal.
On expiry with possible work in progress, atomically quarantine; never make the
set AVAILABLE merely because time passed. Lost acknowledgement is uncertainty,
not success. Issuer release requires stopped execution, closed resources, known
outcome and approved evidence. Release/recovery follows the published quarantine
rules; nothing here establishes or reserves an actual operational lease.
Apply amendment section 7: uncertain reservation, phase acknowledgement, external
actor creation, hash/key mismatch or recovery means QUARANTINE/STOP. Expiry does
not establish availability. No automatic takeover or blind retry; restart reconciles
against authoritative durable phase/hash/key history, never local state alone.

## 12. Exact post-provision verification

Within the transaction verify the exact eight intended rows, required fields and
defaults, and these bounded predicates. After confirmed COMMIT, an independently
authorized verifier must establish durable resulting state with the same exact
predicates before marking PROVISIONED_VERIFIED. A new verification connection is
not implicitly authorized; name it in the future package with read-only cleanup.

- Exactly USER_A/USER_B, ORG_A/ORG_B, MEMBERSHIP_A/MEMBERSHIP_B and PROJECT_A/PROJECT_B
  in the fixture inventory: two records of each type, not a global table count.
- All eight statuses active; both membership roles member; timestamps captured;
  exact synthetic names and NULL existing-project descriptions unchanged.
- Two exact issuer/subject mappings match the approved USER UUIDs uniquely.
- Membership rows with user_id in the two users OR organization_id in the two
  organizations are exactly the approved two; no cross or extra relationship.
- Projects with organization_id in the two organizations are exactly the approved
  two, each in its own organization; no shared project or unexpected fixture row.
- No security/role/schema/bookkeeping change attributable to this operation;
  collision-free exact source/target state and cleanup/commit outcome retained.

Database reads prove persisted fields and relationships only. Provider evidence
proves synthetic auth identity creation/subject provenance. Operator evidence
proves authority, customer exclusion, no traffic/maintenance, prior-use history
and exclusivity. No database field alone proves synthetic provenance. Unexpected
data is a stop category; do not dump potentially customer-bearing content.

## 13. External provenance evidence format

Proposed evidence format label: `jous.runtime-canary-provisioning-evidence.v1`;
not the canary manifest schema or an implemented parser. Future concrete package
must specify its closed serialization, access-controlled evidence directory and
exact retention/approval references. Never choose a public log or secret store
as evidence output by default.

Envelope fields: schema label, fixture_set_identifier, production/source identities,
plan/contract/request hashes, operation_id, authorization/reference, operator,
lease acknowledgement/reference, UTC phase times, finite step/count/result gates,
commit/rollback/close outcome including UNKNOWN, independent verifier/review
reference, lifecycle/retention classification, quarantine/retirement status.

Each of the ten components (two actors plus eight DB records) records component
symbol, actual allocated identifier, component type, synthetic purpose,
creation authority/process/time, authorization reference, issuer/subject when
applicable, exact database mapping, initial status/role/relationship, baseline
field values and recorded timestamps where applicable, customer_data=NONE,
production_traffic_eligibility=NEVER, canary_only=true, customer-exclusion attestation,
prior-use history, lifecycle state and retirement authority/status. Non-applicable
fields are explicitly absent or marked NOT_APPLICABLE under the future schema.
Actor identifiers may be immutable subjects; they are not assumed to be UUIDs.

No credentials, token, password, complete DSN, raw exception or arbitrary provider/
server response. Actual synthetic identifiers enter controlled evidence only under
future authority. Identity assignment evidence must not contain real customer data.

## 14. Manifest production, retention and freshness

Only after identities exist, confirmed provisioning, provenance evidence and
independent post-provision verification PASS, generate exact manifest bytes:
schema `jous.runtime-canary-fixtures.v1`; fixed approved project; approved issuer;
exactly two actors with subject/user/organization/project. No membership IDs or
provenance/lease fields may be added to that closed schema. Independently approve
exact bytes/SHA256 and retain them with provenance; no live canary observation
becomes expected identity authority. No production manifest is generated here.

Lifecycle: approved provisioning request/reservation -> PRE_AUTH -> separately
authorized external actor generation -> reconciled, approved AUTH_IDENTITIES_BOUND
request and same-reservation acknowledgement -> separately authorized DB provisioning
-> independent DB/auth resulting-state verification -> provenance approval -> final
manifest generation -> independent exact-byte/SHA256 manifest approval -> provisioning
completion/release under the adopted authority -> later separate CANARY reservation
bound to fixture_manifest_sha256. Execution must first complete with known outcome
and cleanup before resulting-state verification, as amendment section 8 requires.
The provisioning_request_sha256 never becomes the manifest hash, and the final
manifest never retroactively redefines provisioning history. No release/launch
while quarantine or conflict remains.

Provisioning establishes creation history/baseline, NOT future five-minute freshness.
Before every separately authorized canary repeat the published Layer A/Layer B
checks under a new acknowledged lease. Expiry starts at the earliest material
observation, not provenance approval or provisioning time; require completion
before freshness expiry and a strictly later lease end. No waiver for new fixtures.

Retain dedicated fixtures for repeated canaries without customer reassignment or
ordinary product traffic. Preserve creation/provenance, lease and result history;
recheck each run. Uncertainty quarantines. No automatic deletion after PASS/FAIL.

Retirement needs exact separate authority covering auth identities, projects,
memberships, users, organizations and evidence/register disposition. With committed
ON DELETE RESTRICT constraints, a future exact-ID database retirement would remove
projects/memberships before referenced organizations/users, after checking all
dependents; no CASCADE or broad name/prefix deletion. Auth retirement is separate
and may fail independently. Retain historical provenance, lease/audit/results after
retirement; do not erase history to make IDs appear unused.

## 15. Hard customer-safety and release stops

STOP/QUARANTINE on a real-user/customer association, customer traffic, previous
non-canary use, ambiguous provenance, identity collision, partial set, mismatched
relationship/status, unknown capability/target, missing approval, lease conflict/
expiry, unexpected hook/schema drift, unconfirmed cleanup or uncertain commit.
No best-effort reuse, credential substitution, silent privilege escalation,
source changes or security weakening to make provisioning pass.

## 16. Future concrete authorization package

Before any managed mutation may be considered, require:

1. Published plan, adopted bootstrap-amendment and reconciled provisioning-contract
   exact identities/SHA256 and current approved production SHA/tree.
2. Independently approved PRE_AUTH request exact bytes/provisioning_request_sha256,
   stable logical actor/provider allocation keys, exact external generation authority
   and customer-exclusion provenance; expected same-reservation phase transition.
3. All eight proposed distinct UUIDs fixed before reservation and exact row/name/value
   projections; once generated, actual issuer/subject pairs, independent reconciliation
   and approved AUTH_IDENTITIES_BOUND request exact bytes/provisioning_request_sha256.
4. Exact finite SQL/provider mutation inventory, dependencies/counts and expected outputs.
5. Named provisioning identity and independently proven effective capability under
   unchanged FORCE RLS; separate credential carrier/acquisition/TLS target boundary.
6. Exact bounded pre-read and catalog/collision plans with sanitized failure categories.
7. Reviewed executor identity, confirmation, timeouts/isolation, transaction/rollback,
   commit uncertainty and connection cleanup model; no arbitrary SQL interface.
8. External-auth partial failure, compensation/quarantine and no-automatic-retry rules.
9. Reservation ID, authoritative register identity and durable phase acknowledgements;
   predecessor/current request hashes, retained complete conflict-key set plus resulting
   issuer/subject keys, deadline and lease conflict/quarantine/recovery rules. DB work
   requires AUTH_IDENTITIES_BOUND acknowledgement AND separate exact mutation authority.
10. Exact in-transaction and independent post-commit read verification authority.
11. Provenance serialization, controlled output path, reviewer, retention and retirement.
12. Explicit stop/rollback criteria and any separately authorized reconciliation scope.
13. Accountable operator confirmation and independent review approval of the concrete
   operation; no broad permission phrased only as "provision fixtures".

This candidate supplies no executable provisioning approval. All inputs that are
symbolic here must be fixed before their relevant execution phase, not improvised
from collisions or learned during mutation. No provider, register, executor or
credential mechanism is implemented by this design task.

## 17. Safest future order

1. Adopt the independently approved bootstrap amendment together with step 2 before
   any operational use; approval does not imply publication or implementation here.
2. Independently approve/adopt this narrowly reconciled provisioning contract.
3. Separately review/design/approve and implement the authoritative lease mechanism.
4. Define all eight exact proposed DB identities/values and PRE_AUTH request, including
   stable logical actor/provider allocation keys and exact generation instructions.
5. Independently approve exact PRE_AUTH request bytes/hash and external generation
   package/authority; do not fabricate unknown subjects.
6. Acquire durable acknowledged FIXTURE_PROVISIONING exclusivity under that request.
7. Perform only separately authorized external actor generation, if required.
8. Independently reconcile actual actor issuer/subject bindings and provenance.
9. Independently approve immutable AUTH_IDENTITIES_BOUND request exact bytes/hash.
10. Atomically advance the SAME reservation, retain old keys/add actual pair keys,
    and obtain durable AUTH_IDENTITIES_BOUND acknowledgement.
11. Independently approve/authorize exact DB provisioning package, secure executor,
    capability evidence, pre-reads, transaction/verification and cleanup boundaries.
12. Perform bounded DB provisioning; complete execution with known outcome/cleanup.
13. Independently verify exact durable DB/auth resulting state.
14. Independently approve complete provenance.
15. Generate exact final jous.runtime-canary-fixtures.v1 manifest bytes.
16. Independently approve exact manifest bytes/SHA256; complete/release provisioning
    under the adopted authority with required evidence and no uncertainty/quarantine.
17. Separately provision/verify restricted runtime credential, CA/auth configuration.
18. Later acquire a NEW CANARY reservation bound to fixture_manifest_sha256 and
    collect fresh five-minute evidence under the published contract.
19. Independently review/release the complete canary package within expiry.
20. Separately authorize one exact CANARY and required post-run verification.
21. Independently review result, cleanup and unchanged-state evidence.
22. Deployment/public traffic/runtime activation remain separate explicit decisions.

Already-established independently approved actors may use the amendment's initial
AUTH_IDENTITIES_BOUND alternative with all equivalent gates; no generation or phase
shortcut is inferred from local observations. Neither path grants operational authority.

This expands the published order only to make the previously required exclusivity
mechanism and possible external subject generation explicit before provisioning.
It does not bypass any published canary lease or freshness prerequisite. Existing
actual credential/configuration, fixture/provenance and freshness facts remain
unverified. No operational claim of readiness or current fixture absence is made.
