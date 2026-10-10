# JOUS.CORE.1A fixture provisioning lease bootstrap amendment

Status: OFFLINE NORMATIVE CANDIDATE FOR INDEPENDENT REVIEW. This amendment is
not effective operational authority until independently approved and adopted.
It authorizes no register implementation, reservation, credential work, managed
access, auth/database fixture provisioning, canary, deployment or activation.
All fixture identities here are symbolic; no actual UUIDs or issuer/subjects.

## 1. Exact parent authority and narrow effect

Baseline HEAD/origin/main: `bb8bc7281065bfb591f242d4a128e7ec8dd1b640`;
tree: `b65715928682fca4aebde887fb4fa60b8f6a7b88`.

This additive amendment amends ONLY the operation-dependent reservation-binding
rule in the published `docs/decisions/JOUS.CORE.1A.runtime-canary-fixture-plan.md`,
Operational exclusivity lease section. Parent blob:
`f0f3f445c1cdf2151d0c1769989eac48197089a7`; parent SHA256:
`a9223abc6d72edb84895cf75d504ddddad85d82c6441601702af17a3bf51947e`.

That section requires every acknowledged record to contain
fixture_manifest_sha256 and requires the requested manifest hash to match the
registered approved fixture set. Initial provisioning precedes the existence of
a final approved fixture manifest. Refine those binding requirements by explicit
operation type, and ONLY as stated below. No other plan section is weakened.
The published plan itself is not edited by this task.

## 2. Typed authority and distinct bindings

Every reservation has an authoritative, immutable operation_type. Reject missing,
unknown or ambiguous types. The serialized issuer enforces type in acquisition,
acknowledgement, conflict evaluation, transitions, release and recovery.

| operation_type | Required artifact binding | Permitted lifecycle |
| --- | --- | --- |
| FIXTURE_PROVISIONING | provisioning_request_sha256: exact independently approved immutable provisioning request | Initial creation before a final approved canary manifest exists; explicit phases below |
| CANARY | fixture_manifest_sha256: exact independently approved final jous.runtime-canary-fixtures.v1 manifest | Existing published canary acquisition/execution contract |
| FIXTURE_MAINTENANCE | Separate binding authority required; not designed here | Conflict participation only; no operation permitted under this amendment |
| FIXTURE_RETIREMENT | Separate binding authority required; not designed here | Conflict participation only; no operation permitted under this amendment |

For provisioning, the record/acknowledgement carries provisioning_request_sha256,
not a fabricated fixture_manifest_sha256. For CANARY, fixture_manifest_sha256
remains mandatory and provisioning_request_sha256 cannot satisfy it. No untyped
reservation, operation relabeling, automatic conversion or provisioning masquerading
as CANARY. Maintenance/retirement may not inherit provisioning semantics by default.

All existing sole-register/single-issuer, serialized acquisition, durable history,
one-winner, acknowledgement, overlap, expiry, quarantine and release controls remain
in force. The refinement introduces no second register or competing local authority.

## 3. Minimum immutable provisioning-request authority

Proposed closed schema identifier: `jous.runtime-canary-provisioning-request.v1`.
It is an artifact contract, not an implemented parser or real artifact created here.
Before reservation, independently approve its exact bytes and SHA256. Require:

- schema/version; operation_type exactly FIXTURE_PROVISIONING; phase;
  stable fixture_set_identifier; unique request/version identity and UTC created_at;
- exact eight proposed database UUIDs, individually mapped to USER_A, USER_B,
  ORG_A, ORG_B, MEMBERSHIP_A, MEMBERSHIP_B, PROJECT_A and PROJECT_B; all distinct;
- exact proposed synthetic organization/project names, membership relationships
  USER_A->ORG_A and USER_B->ORG_B, project relationships PROJECT_A->ORG_A and
  PROJECT_B->ORG_B, membership role member, all expected statuses active, and
  exact approved remaining persisted-value projections (including descriptions);
- source-approved target/project identity, provisioning-contract artifact identity/
  SHA256, published plan and adopted amendment identities, authorization/package
  identity and independently approved operation/phase scope;
- approved auth issuer(s) if fixed; for the committed canary both actors ultimately
  require the same approved issuer. Actual subjects when known, or explicit
  PRE_AUTH phase plus exact approved generation instructions and scope below;
- deterministic conflict-key specification/value set or immutable hash-bound
  reference, creation authority, actor provenance/customer-exclusion commitments;
- for a later version, predecessor request SHA256, transition identity and its
  independently reviewed approval reference; never overwrite a prior version.

Every referenced artifact must have an exact reviewed identity/hash, not a mutable
URL or display name alone. The future concrete format must reject duplicate/unknown
fields, malformed UUIDs/hashes, missing values and contradictory phases before
reservation. It contains no credentials, bearer tokens or customer data. No actual
request or IDs are generated now. Database IDs are fixed before the first reservation.

## 4. Generated-subject bootstrap phases

PHASE 1: PRE_AUTH_PROVISIONING_REQUEST. This approved immutable request fixes all
eight database UUIDs and all database relationships/values. It identifies ACTOR_A
and ACTOR_B by stable logical actor allocation identifiers, independently assigned
within the approved provider/issuer generation scope. Bind exact synthetic-only
generation instructions, provider scope identity, intended issuer scope, creation
authorization, duplicate-request handling and customer-exclusion evidence.
Unknown subjects must be explicitly UNKNOWN_PENDING_GENERATION, never fabricated
as if provider-issued. No PostgreSQL fixture INSERT is permitted in this phase.
Only separately authorized external generation actions may begin after durable
PRE_AUTH acknowledgement; a reservation does not authorize those actions itself.

If issuer is not fixed, bind the exact approved provider/issuer allocation scope;
unbounded issuer/provider selection is invalid. Generation must not reuse a real
account. Logical actor allocation keys must represent the SAME intended actors
across requests/operators; a new request UUID or display label cannot evade overlap.
If the scope cannot deterministically identify them before subjects exist, reject
reservation until the identity allocation authority supplies that binding.

PHASE 2: AUTH_IDENTITIES_BOUND. After actual generation, independently reconcile
provider results and synthetic provenance. Create a NEW immutable request version
binding exact actual issuer/subject pairs to ACTOR_A/USER_A and ACTOR_B/USER_B.
Require distinct immutable subjects and the common approved issuer required by
the committed canary; no customer association or ambiguous assignment. Review and
authorize those resulting bindings and the exact DB-phase package BEFORE any INSERT.

The serialized issuer atomically advances the SAME acknowledged provisioning
reservation from the exact current PRE_AUTH request hash to the newly approved
AUTH_IDENTITIES_BOUND request hash, conditioned on an active unexpired reservation,
matching owner/authorization and predecessor hash, unchanged operation/set/UUIDs/
database values and no new conflict. Add concrete issuer/subject conflict keys
while retaining PRE_AUTH logical actor/scope keys. All old/new keys remain reserved
for this operation's lifetime; there is no gap between release and reacquisition.

Only actor outputs and explicitly reviewed phase/approval metadata may be refined.
No unrelated identity, UUID, relationship, name/status/role, target or operation
change; reject such changes rather than silently rebind. Issuer and database pairs
must match approved generation scope. Record old/new exact hashes, phase, evidence,
approval, owner, time and durable transition result; preserve immutable history.
Rebinding does not extend expiry or grant database mutation authority by itself.

Require a NEW durable AUTH_IDENTITIES_BOUND acknowledgement before PostgreSQL
INSERT. A submitted transition, PRE_AUTH acknowledgement, local provider result
or uncertain transition response is insufficient. If both actor pairs are already
independently established, the initial request may start AUTH_IDENTITIES_BOUND
with all concrete bindings and the same complete conflict/approval gates.

## 5. Exact-byte hashing and acknowledgement

provisioning_request_sha256 is SHA256(exact independently approved request bytes),
including explicit phase/version and bindings. No post-approval normalization or
editing. A request's self-reported hash or locally computed unapproved hash is not
approval. Referenced identities are immutable and validated against their pins.
The authoritative issuer acknowledges only that exact approved artifact/version.

Each provisioning acknowledgement includes reservation/lease_id, register identity,
operation_type, fixture_set_identifier, provisioning_request_sha256, phase,
conflict-key set or exact immutable reference, owner/requesting_operator,
authorization/package reference, acquired/acknowledged state, issuance/start/expiry
timestamps and status LEASED. Retain published reservation_requested_at metadata.
Require ACKNOWLEDGED + ACTIVE + UNEXPIRED before operation; for DB work require
AUTH_IDENTITIES_BOUND plus separate exact mutation authorization.

For CANARY, fixture_manifest_sha256 remains
SHA256(exact independently approved final fixture manifest bytes). All original
CANARY acknowledgement fields and checks remain mandatory. NO PRE_AUTH, provisional
manifest, wildcard identities, provisioning hash or inferred "same set" substitute.

## 6. Deterministic overlap keys and one-winner acquisition

Within the same target scope, reserve the union of:

1. Stable fixture-set logical identifier (an authoritative allocation, not a label).
2. All eight proposed database UUIDs. Reserve each regardless of record/table type
   so changing a symbolic role or table does not evade an overlapping-ID conflict.
3. Once known, each exact issuer/subject pair, with unambiguous length-delimited
   encoding of the exact strings; no case folding, trimming or lossy concatenation.
4. PRE_AUTH provider/issuer scope plus logical actor allocation identifiers and
   approved generation-request identity; retain logical keys after subjects bind.

The future format must specify deterministic key encoding, including target scope,
UUID canonicalization and string boundaries. Compare the complete sets. Referencing
only a display name, request hash or distinct set label is insufficient. Generation
scope must prevent intentional double allocation of a logical actor; overly broad
scope may conservatively conflict, but under-specified scope must be rejected.

Atomic compare-and-reserve requires AVAILABLE plus no active/unexpired operation,
quarantine, incomplete provisioning or uncertain outcome on ANY overlapping key.
Availability test, all-key reservation and durable acknowledgement form one
serialized issuance. Two otherwise eligible simultaneous overlapping provisioning
requests yield exactly one SUCCESS; all others CONFLICT/REJECTED. Phase advance
also atomically evaluates added keys, retaining the old reservation on rejection.

Mutual exclusion applies across FIXTURE_PROVISIONING, CANARY, FIXTURE_MAINTENANCE
and FIXTURE_RETIREMENT on any overlapping set/key. No CANARY during incomplete
provisioning, no retirement/maintenance during provisioning and no second overlapping
provisioner. No queued silent acquisition, stealing, replacement, lease shortening,
implicit takeover or local competing lease. Unknown operation/binding is rejected.

## 7. Failure, expiry, restart and recovery

QUARANTINE/STOP for uncertain reservation/phase acknowledgement, differing request
hash, ambiguous generated bindings/keys, expired lease with external/DB work
outstanding, incomplete register recovery or uncertain cleanup/commit outcome.
Expiry alone never proves availability, rollback, stopped work or closed resources.
No automatic takeover, retry, repair or deletion. Lost acknowledgement must be
reconciled against the authoritative issuer without starting an operation.

Durable reservation and phase/hash/key history survives operator/process restart.
Local state loss does not release keys or permit a new owner. Recovery reconciles
the exact reservation, current phase, predecessor/current hashes, authorization,
actual operation outcome and cleanup through separately approved evidence. Only
the sole issuer may release or clear quarantine after published recovery gates.
Keep audit history, reject split-writer recovery, and never convert a provisioning
reservation to CANARY during restart. This amendment performs none of those actions.

## 8. Transition to final manifest and other operations

Require this sequence before a CANARY reservation can even be requested:

1. FIXTURE_PROVISIONING completes with known outcome/cleanup.
2. Exact resulting database/auth state is independently verified.
3. Complete synthetic provenance is independently approved.
4. Exact jous.runtime-canary-fixtures.v1 manifest is generated.
5. Exact final manifest bytes/SHA256 are independently approved.

The issuer must also confirm provisioning release and no quarantine/conflict before
new CANARY acquisition. Provisioning request and final manifest remain distinct
immutable artifacts with retained history. The provisioning hash never becomes
the manifest hash; final manifest approval never retroactively redefines a completed
provisioning reservation. A new typed CANARY reservation uses only the approved
final manifest, and retains five-minute freshness and all existing launch gates.

Maintenance/retirement participate in overlap rejection but their artifact bindings
and execution authority require separate design/review. This amendment grants
neither operation and does not assign them provisioning-request semantics.

## 9. Reconciliation and non-implementation boundary

Rejected candidate:
`docs/decisions/JOUS.CORE.1A.runtime-canary-fixture-provisioning-contract.md`, SHA256
`4712a380033c45bf1d897b2ab28fd3135b98eccece6120e87efc7e61838590f6`.
It remains REJECTED pending amendment approval and later bounded reconciliation.
It is not edited or rehabilitated by this document alone. Later remediation must
cite this exact adopted amendment authority, use its request/phase/hash/key gates,
preserve CANARY-only manifest binding, generated-subject review and fail-closed
serialization. Change only section 11 and directly necessary phase/order language;
do not reopen passed schema, topology, atomicity or other contract sections.

The sole normative exception to the published universal manifest binding is initial
FIXTURE_PROVISIONING under this amendment. All other published requirements remain
unchanged unless expressly refined here. The published plan's no operational
authorization rule remains absolute. Approval/adoption sequence must make the
amendment authoritative before any reconciled provisioning package relies on it.

Implementation-neutral: no vendor, database table, filesystem lock, external
service primitive or specific control store is selected or implemented. No schema
change. No lease exists by virtue of this document. No claims are made that IDs
are selected, subjects exist, fixtures exist/are absent, an executor exists,
credentials are ready or managed evidence has been collected. No real identifiers,
secrets, customer information or production-derived fixture data are included.
