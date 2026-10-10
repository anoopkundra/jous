# JOUS.CORE.1A Step 7 runtime canary fixture plan

Status: PROPOSED OPERATIONAL CONTRACT FOR INDEPENDENT REVIEW. This document
authorizes no managed access, provisioning, credential work, canary execution,
deployment or runtime activation. All fixture names below are symbolic. No actual
subjects, UUIDs, customer identifiers or production observations are supplied.

## Authority and scope

The implementation authority is commit
`7e316a6e1fdfae72c93ce0beb4a90df487baf5e2`, tree
`e8e4edc1f4bd98b9f5b64796b8588cdd26e31150`. Its canary script blob is
`0d9f00a47b782182d8a402178a87ba807e56f82c`.

Reviewed committed sources: `services/api/infrastructure/validate_runtime_canary.py`
(`load_manifest`, `scoped`, all seven stages, `main`);
`docs/decisions/JOUS.CORE.1A.runtime-canary-procedure.md`;
`services/api/src/jous_api/access.py` (identity and active relationships);
`permissions.py` (member actions); `models.py` and `persistence.py` (fields);
`database.py` (runtime checks, scoped transactions and disposal);
`runtime_transport.py`, `runtime_policy.py`, `runtime_resolution.py`, `config.py`;
and `tests/test_runtime_readiness_remediation.py` canary/cleanup regressions.
Paths abbreviated above are under `services/api/src/jous_api/`.

This plan adds operational prerequisites, not a second policy authority or a
change to the canary. Migration 0002 is already applied and must not be rerun.
The existing runtime configuration finding is outside provisioning scope here
and remains an independent gate. Approval of this plan alone closes no managed
configuration or fixture-evidence gate.

## Exactly two dedicated synthetic fixtures

| Fixture | Actor | User | Organization | Membership | Existing project |
| --- | --- | --- | --- | --- | --- |
| A | ACTOR_A | USER_A | ORG_A | MEMBERSHIP_A | PROJECT_A |
| B | ACTOR_B | USER_B | ORG_B | MEMBERSHIP_B | PROJECT_B |

Each user, organization, membership and project will receive its own newly
allocated, independently recorded UUID under a later provisioning authorization.
USER_A != USER_B; ORG_A != ORG_B; PROJECT_A != PROJECT_B; membership IDs and
immutable actor subjects are also distinct. No prior real record is repurposed.

ACTOR_A resolves only to USER_A; ACTOR_B resolves only to USER_B. Each actor has
exactly its own active `member` membership, with no other organization membership
(including inactive cross-membership). MEMBERSHIP_A links USER_A to ORG_A;
MEMBERSHIP_B links USER_B to ORG_B. PROJECT_A references only ORG_A and PROJECT_B
only ORG_B. Organizations have no dedicated owner field in this schema; the
relationship is represented by memberships, not an invented owner column.

Use role `member`, not `owner`: committed MEMBER_ACTIONS includes CREATE_PROJECT
and UPDATE_PROJECT, the two positive write permissions exercised. Actors/users,
organizations, memberships and projects are dedicated canary assets, never
customer assets and never eligible for ordinary production traffic.

## Actor identity provenance

For ACTOR_A and ACTOR_B require separate reviewed evidence of: explicitly
synthetic identity; creation specifically for Jous production security canary;
approved authentication issuer; unique immutable subject; corresponding new
fixture-only user UUID; creation time in UTC; creating operator/process and exact
authorization reference; no real customer's email, account or subject; never
assigned/transferred to a customer; and canary-only retention/lifecycle class.

Identity-provider creation, if necessary, is a separately enumerated provisioning
action, not implied by database provisioning. No sign-in, token minting or real
person impersonation is required by this script: it constructs VerifiedPrincipal
from the approved issuer/subject. It does not validate a bearer token or JWKS.
The evidence must identify whether a subject is issued by an approved synthetic
identity process; a made-up identifier is not evidence of approved provenance.

Record prior-use status: newly allocated for this fixture, or previously used
solely by this same reviewed canary with a retained run history. Any unknown prior
assignment, customer association or reassignment fails the gate.

## Database record provenance and baseline

Maintain a separate evidence ledger, not extra manifest keys or new database
columns. Every eventual record entry must contain symbolic name, eventual UUID,
record type, synthetic purpose, creation timestamp, creator/process and authority
reference, expected status and relationships, expected issuer/subject where
applicable, membership role where applicable, classification `customer_data=NONE`,
`production_traffic_eligibility=NEVER`, `canary_only=true`, lifecycle state, retention
deadline/review date, and exact retirement/deletion authority. These classification
fields are evidence metadata, not columns in the committed schema.

| Record | Required persisted fields/relationships |
| --- | --- |
| USER_A / USER_B | id; approved auth_issuer and distinct auth_subject; status `active` |
| ORG_A / ORG_B | id; dedicated nonblank synthetic name; status `active` |
| MEMBERSHIP_A / MEMBERSHIP_B | id; corresponding user_id and organization_id; role `member`; status `active` |
| PROJECT_A / PROJECT_B | id; corresponding organization_id; dedicated nonblank synthetic name; status `active`; recorded description baseline |

Record created_at and updated_at for each record. Names/descriptions must contain
only approved synthetic text; no customer content. The future provisioning plan
must specify their exact values and record the actual approved timestamps. Prefer
description NULL for the two existing fixture projects and preserve that baseline.
No memberships, users or organizations are created by the canary itself.

Immediately before a run, all eight database records must still match the ledger;
all statuses must equal lower-case `active`. Issuer/subject mappings, member roles
and organization/project relationships must be unchanged. No other memberships,
cross-memberships, customer association, traffic, concurrent run or pending
maintenance may exist. Lifecycle must be approved for canary use, not retirement.

The positive stage inserts a NEW random-UUID project per actor, with name
`jous-canary-rollback` and description `bounded control`, then updates that new
project to `updated rollback control`. It never needs to update the existing
PROJECT_A/PROJECT_B for its positive test. Defaults must produce an active new
project and the committed constraints/grants/policies must remain compatible.
Cross-tenant UPDATE attempts target the existing other project with `must rollback`
and must affect zero rows. Denied INSERT attempts use new UUIDs and name
`must rollback`. No sequence-based test identity is required. No new schema field,
extra privilege, constraint relaxation or fixture-specific trigger is permitted.

## Exact canary manifest

The only accepted keys are `schema`, `project`, `issuer`, `actors`. The schema is
`jous.runtime-canary-fixtures.v1`; project must equal the fixed project in the
committed loader/transport. The issuer must match approved runtime authentication
configuration. There are exactly two actor objects, each with exactly `subject`,
`user`, `organization`, `project`. UUID fields must parse as UUIDs; subjects must
be nonempty and at most 255 characters. Corresponding fields must be distinct.
Duplicate JSON keys, unknown keys and hash mismatch fail the committed loader.

Symbolic example only; THIS IS NOT AN EXECUTABLE MANIFEST (UUID/project/issuer
placeholders intentionally cannot pass the production loader):

```json
{
  "schema": "jous.runtime-canary-fixtures.v1",
  "project": "<SOURCE_DEFINED_APPROVED_PROJECT_REF>",
  "issuer": "<APPROVED_AUTH_ISSUER>",
  "actors": [
    {"subject": "<ACTOR_A_IMMUTABLE_SUBJECT>", "user": "<USER_A_UUID>", "organization": "<ORG_A_UUID>", "project": "<PROJECT_A_UUID>"},
    {"subject": "<ACTOR_B_IMMUTABLE_SUBJECT>", "user": "<USER_B_UUID>", "organization": "<ORG_B_UUID>", "project": "<PROJECT_B_UUID>"}
  ]
}
```

After separately authorized provisioning and independent provenance verification,
an authorized operator generates the real manifest from approved fixture records,
not by learning expected identities during a canary. Keep provenance, membership
IDs and lease data in companion evidence, not this closed schema. Independently
review its exact bytes and values; compute SHA256 of those bytes; bind that exact
hash in the approval record. Do not edit/normalize it after approval. Retain the
approved manifest and review reference with the run evidence, access-controlled
as synthetic identity metadata. No credentials, tokens or customer information.

Both `--fixture-manifest <path>` AND
`--approved-fixture-sha256 <exact independently approved hash>` are mandatory.
Supplying a freshly computed hash without independent approval is not authorization.
No real manifest is generated by this plan.

## Mandatory cross-tenant preconditions

Before authorization, establish no membership from USER_A into ORG_B or USER_B
into ORG_A, and no other memberships for either fixture user. Neither user may
resolve as the other. Neither project may belong to the other organization.
Neither actor may read/write the other project's row or read the other organization
through the restricted runtime boundary. These are mandatory preconditions, not
facts inferred solely from a later PASS or a hidden row returning no result.

Layer A negative visibility is evidence of observed isolation; it is not proof
that an RLS-hidden cross-membership record is absent. Layer B must prove that
absence. No changes to RLS or grants may be made to obtain evidence.

## Freshness: two layers and a hard expiry

Proposed conservative window: at most FIVE MINUTES from the earliest material
precondition observation/attestation, with run completion also required before
expiry. This limits drift exposure while allowing the script's bounded checks
and cancellation test. It is an operational proposal, not an enforced CLI timer.
If independent review or run duration cannot fit, renew evidence under separate
authority rather than extend the window implicitly. Authorization may be reviewed
conditionally in advance and released only after fresh evidence is complete.

Each package records UTC observation start/end, issued_at, expires_at, exact
approved manifest SHA256, exact eventual fixture IDs including memberships,
statuses, issuer/subject/role/relationship checks, traffic/exclusivity attestation,
operator and authorization references, and PASS/FAIL for every fact. Expiry is
the earliest material evidence timestamp plus five minutes; no later signing
time may reset it. Any changed fixture, config, identity, manifest, maintenance,
traffic use or competing run invalidates evidence immediately. Operator time must
be trustworthy; ambiguity fails closed. Stale evidence is invalid automatically.

LAYER A: restricted runtime verification, separately authorized and rollback-only
where it precedes the canary. Establish own user resolution, active own membership,
own active organization/project relationship and visibility, negative other-tenant
visibility. The exact committed canary repeats these within its scoped stages;
it does not itself prove every Layer B fact. If a separate preliminary check is
needed, its finite query/code/credential/cleanup boundary needs independent review
and explicit authorization; do not improvise a new tool or extra connection.

LAYER B: separately authorized finite administrative read and operator attestation.
Verify all eight exact rows, complete membership absence outside the approved pair,
issuer/subject uniqueness, statuses/relationships/baselines, and no unexpected
canary-owned persisted project/membership. Administrative read authorization must
name exact identifiers and bounded queries, use no repair/mutation, and rollback/
close. Operational evidence establishes synthetic creation history, no customer
association, no real traffic, no concurrent canary/maintenance and lease ownership.
Those external facts cannot be proved by an SQL result alone. No Layer B admin
credential enters the runtime canary process. Neither layer is collected now.

## Operational exclusivity lease

Use ONE authoritative durable operational lease register outside the Jous
production database, with ONE serialized issuer/service/process controlling all
reservations and state transitions. Its exact identity, ownership and access
controls must be independently approved before use. It is the sole authority:
operators must not create independent/local competing lease records. No database
advisory lock, new table, schema change or canary-code change is introduced.
All operators/processes able to provision, maintain, retire or run these fixtures
must participate; an uncontrolled writer invalidates this mechanism. No register,
service, lease or managed access is provisioned by this document.

Only the serialized issuer may transition the fixture set from AVAILABLE to
LEASED or QUARANTINED, or return it to AVAILABLE after the recovery gates below.
The control-store implementation may use durable single-writer serialization or
atomic compare-and-set; no vendor is mandated. A read showing "no active lease"
is NOT a reservation. Availability check and durable lease creation must be one
serialized atomic operation from the operators' perspective:

```text
IF fixture set is AVAILABLE
AND no unexpired lease exists
AND no quarantine or unresolved execution exists
AND no provisioning, retirement or maintenance is active
AND requested manifest hash matches the registered approved fixture set
THEN atomically create exactly one LEASED record and acknowledge it
ELSE reject with CONFLICT / REJECTED
```

For simultaneous otherwise eligible requests, exactly one may succeed and all
others must receive CONFLICT / REJECTED. There is no check-then-create race or
silent delayed acquisition. Durable reservation must precede acknowledgement;
issuer restart/failover must preserve exclusivity, never introduce another writer.
A lost response, unavailable register or uncertain durable outcome is NOT success:
reconcile the original request with the issuer without launching or creating a
competing reservation. Acknowledgement alone is not canary execution authorization.

Every acknowledged record contains lease_id, fixture_manifest_sha256,
fixture_set_identifier, requesting_operator, authorization_reference,
reservation_requested_at, lease_started_at, lease_expires_at and status.
Lease status is exactly one of LEASED, RELEASED, EXPIRED, QUARANTINED. The fixture
set has a separate availability state AVAILABLE, LEASED or QUARANTINED; historical
EXPIRED/RELEASED records do not themselves prove availability. The set identifier
binds the complete exact fixture identities, including memberships, so a different
manifest cannot establish an independent reservation over overlapping fixtures.
The issuer must reject overlap with an already reserved set. Operational execution
start/completion and cleanup evidence are recorded separately from lease status.

Acknowledgement evidence must contain lease_id, authoritative register identity/
reference, exact manifest hash, lease start/expiry, requesting operator and status.
The operator independently checks that it matches the approved authorization and
fixture set. Require ACKNOWLEDGED + ACTIVE (status LEASED) + UNEXPIRED, confirmed
by the authoritative issuer, before launch. A submitted request, local note,
stale register read or another operator's acknowledgement is insufficient.

Conflicts include another active lease, quarantine, active provisioning/retirement/
maintenance, a mismatched manifest, overlapping fixture IDs, and uncertainty about
prior execution or cleanup. Reject explicitly. Do not queue and acquire silently,
steal ownership, replace the owner, shorten an existing lease or override quarantine.
After the blocking condition is resolved, a new explicit reservation attempt and
fresh authorization/evidence are required. No automatic retry or owner handover.

Reserve before collecting freshness evidence. Keep the five-minute freshness
window unchanged: its expiry is based on the earliest material observation, not
lease creation or acknowledgement. The lease expiry must be STRICTLY LATER than
both freshness evidence expiry AND the planned completion deadline/authorized
execution window. Plan completion before freshness expiry, including cancellation/
cleanup allowance. The previous five-minute lease-duration cap is replaced only
to permit this strict later-expiry requirement: use a fixed reviewed lease end
with a short explicit cleanup margin, never an open-ended or automatically renewed
lease. If these deadlines cannot fit, do not launch; obtain new evidence and a new
explicit reservation. Operator must also confirm no prior live process, traffic
routing or pending maintenance. No actual lease is created here.

Expiry during execution must NOT automatically make the fixtures AVAILABLE.
Record EXPIRED for history and atomically quarantine the fixture set when execution
or cleanup is incomplete/unknown. Stop further work, use the committed cancellation/
cleanup behavior under the execution authorization, and block successor reservations.
Do not extend a running lease or restart the canary. Expiry is not proof of rollback,
connection closure or stopped execution. Lease monitoring and enforcement are
operator responsibilities outside the unchanged script; no nonexistent timer or
register integration is claimed. Extra managed evidence requires separate authority.

After normal completion, the owner submits the exact lease reference, result,
execution-stop/cleanup evidence and separately authorized unchanged-state evidence
to the issuer. Only the issuer records RELEASED and returns the set to AVAILABLE
when all release gates are satisfied. An unused expired reservation may return to
AVAILABLE only after the issuer verifies no execution started and no maintenance
or uncertainty exists. Unknown outcomes remain QUARANTINED. Recovery requires
independent review and separately authorized diagnosis/verification, accountable
operator evidence of stopped processes and disposed connections, unchanged fixture/
security state and no conflicting activity; only then may the issuer clear quarantine.
No repair, database mutation, credential work or new canary follows from recovery
approval alone. Preserve the register's durable conflict/release/recovery history.
No overlapping provisioning, retirement or credential maintenance.

## Mutation boundary: CANARY IS NOT SELECT-ONLY

| Category | Expected outcome / protection | Persistent-state expectation |
| --- | --- | --- |
| Positive project INSERT/UPDATE in each own organization | Allowed; outer scoped transaction always rolled back | No new project or update committed |
| Other-tenant project UPDATE | Zero affected rows; outer rollback even on unexpected success | Existing project unchanged |
| Other-tenant project INSERT | Denied with 42501 inside savepoint; outer rollback | No project committed |
| Missing/malformed/mismatched user/org context and INSERT | Empty/invalid local GUCs; hidden read and 42501 write denial; outer rollback | No project committed |
| SET ROLE to helper owner or postgres | Expected 42501; savepoint plus outer rollback | Runtime identity unchanged |
| ALTER ROLE runtime BYPASSRLS | Expected 42501; savepoint plus outer rollback | Role attributes unchanged |
| ALTER TABLE projects DISABLE RLS | Expected 42501; savepoint plus outer rollback | RLS unchanged |
| CREATE TABLE forbidden canary relation | Expected 42501; savepoint plus outer rollback | No table created |
| UPDATE users; UPDATE memberships; DELETE projects; DELETE alembic_version | Expected 42501; savepoint plus outer rollback | Rows/bookkeeping unchanged |
| Transaction-local user/org GUCs; verification search_path | Allowed local settings; rollback-only verification savepoints and outer cleanup | No pooled local-context override |
| Physical-reuse read/context-only transaction | One deliberate COMMIT, then baseline and same-backend checks; second branch ROLLBACK | No domain writes in committed transaction |
| Cancellation during pg_sleep SELECT | Cancel task; scoped rollback/disposal and subsequent runtime check | No domain writes |

The denied operations include broad statements: they are NOT constrained to the
fixture UUIDs. Authorization must name their exact committed definitions; privilege
denial and outer rollback are the protection. An unexpected successful operation
must fail, not become permission to continue. Runtime remains restricted; no admin
credential substitution. Negative DDL/role attempts are authorized only under a
separate exact-script canary authorization, never under a read-only preflight.

Transactional rollback protects the reviewed database changes. It is not a blanket
guarantee against external/nontransactional side effects. Future prerequisite
review must exclude unexpected triggers, audit hooks or schema drift capable of
such effects; do not add fixture-specific hooks. Operational logs may persist.

## Post-run evidence and cleanup

Retain the script's closed `jous.runtime-canary-result.v1` JSON, exit status,
stage PASS/FAIL values, disposal result, exact source/manifest identities,
authorization and lease references, start/end times, and operator disposition.
No raw exceptions or secrets. PASS requires all seven stages and disposal; exit
zero. FAIL has exit one and finite evidence; pre-run failure may omit stage detail.
The script does not expose every rollback result independently. Never manufacture
proof of successful rollback from `disposal=true` alone.

After PASS, FAIL or cancellation, record transaction rollback evidence separately
from a bounded post-run state verification. That verification must be explicitly
authorized in advance or separately afterward; it is not an extra connection
implicitly granted by canary authorization. Require all original fixture IDs,
relationships, roles, statuses and baseline fields unchanged; no unexpected
project/membership persisted; no schema/role/policy or migration bookkeeping
change; and lease release/expiry disposition. Because broad negative statements
exist, anomalous success requires a separately reviewed wider impact check rather
than assuming fixture-only scope. Unknown cleanup/state means quarantine and FAIL.

Maintain a canary ownership ledger and pre/post approved inventories so any new
synthetic canary project can be detected without broad deletion. The script does
not emit its ephemeral random project IDs: exact ID-level correlation, if required,
needs a separately reviewed evidence mechanism, not invented script output or raw
SQL logging. No automatic fixture delete, repair, canary retry or migration rerun.
Retirement is separate from rollback and needs exact-ID authority; it must respect
project/membership foreign keys and explicitly review authentication-identity
retirement. Never delete by prefix, name pattern or an unbounded predicate.

## Fail-closed release checklist

Do not launch if manifest/hash or source identity differs; provenance approval is
missing; evidence/lease is stale; relationships/status/roles/mappings differ;
cross-membership exists; customer association/traffic is suspected; concurrent
run or maintenance exists; credential identity cannot be independently established;
approved CA/auth configuration is absent; any gate is ambiguous; or cleanup from
a prior run is uncertain. No best-effort override. Stop on first failure; no repair
or rerun inside canary authority. Any future retry needs a new evidence package and
authorization. Runtime activation and public traffic remain prohibited even on PASS.

Runtime configuration is an independent prerequisite: environment production;
JOUS_DATABASE_URL authenticating directly as restricted jous_runtime; approved
CA file/pin and hostname verification; approved issuer/JWKS and audience
authenticated. Presence alone proves none of these values. Migration/admin
credentials and helper-owner identity must not be substituted. No credential value
belongs in manifest, provenance, attestation or result artifacts.

## Future provisioning authorization (not granted here)

The request must specify exact synthetic identities and eventually allocated
UUIDs, all eight records/field values/relationships, fixed source-approved target
project, operator, exact provisioning role and authority, finite allowed mutations,
identity-provider actions if any, collision checks and expected committed records.
The provisioning role is not inferred or chosen here; it must be independently
approved, separate from the runtime login and absent from the canary process.

Supply reviewed finite verification queries and evidence artifact schema. Prefer
one database transaction with verification before commit and rollback on failure.
Identity-provider operations may not share that transaction: require an explicit
failure/partial-completion reconciliation plan with no automatic speculative repair.
Define record timestamp capture, complete provenance ledger, independent verification,
retention, restricted access, and exact-ID retirement/cleanup authority. No grants,
schema changes or security weakening are implied by fixture creation authority.

## Future canary authorization package

Require all of the following before releasing exactly one canary invocation:

1. Exact production SHA/tree and reviewed script blob; clean local/deployment source.
2. Exact real fixture manifest bytes/path and independently approved SHA256.
3. Independently approved provenance ledger, fixture-plan revision and creation authority.
4. Both freshness layers, timestamps/expiry and exact fixture IDs within the window.
5. Exclusive operational lease and no traffic/maintenance attestation.
6. Separately obtained evidence of direct restricted runtime identity, without secrets.
7. Approved CA DER pin, CERT_REQUIRED, hostname/target and trust-root verification.
8. Approved issuer, JWKS configuration and authenticated audience verification.
9. Reviewed interpreter/package/artifact layout, timeout budget and exact command below.
10. Explicit scope for every allowed/denied operation and the read/context-only COMMIT.
11. Cleanup/expiry/cancellation handling, result retention and post-run verification authority.
12. Finite stop conditions; no fallback, repair, automatic retry, deployment or activation.

```text
<REVIEWED_INTERPRETER> -I -B services/api/infrastructure/validate_runtime_canary.py \
  --confirm-production-canary --production-canary \
  --fixture-manifest <APPROVED_MANIFEST_PATH> \
  --approved-fixture-sha256 <INDEPENDENTLY_APPROVED_EXACT_SHA256>
```

This is a command template, not authorization to execute it. The script enforces
manifest/startup/runtime gates, not this plan's lease/provenance/expiry approvals.
Those must be enforced by the accountable operator and independent authorization
review before invocation; no nonexistent CLI flags or machine enforcement is claimed.

## Proposed sequence and remaining gates

1. Independently approve this fixture provenance/freshness/exclusivity plan.
2. Separately authorize and provision dedicated synthetic fixtures only.
3. Independently verify their provenance and approve the exact manifest.
4. Separately provision/verify restricted runtime credential and CA/auth configuration.
5. Reserve exclusivity and collect both bounded freshness layers.
6. Independently review/release the complete canary package within its expiry.
7. Separately authorize one exact production canary and required post-run checks.
8. Independently review result, cleanup and unchanged fixture-state evidence.
9. Only then consider separately authorized deployment/runtime activation.

No source evidence requires changing this order. If evidence expires between steps,
repeat only the separately authorized evidence collection, not the canary itself.
Current configuration, actual fixture existence/provenance and freshness findings
remain open until their respective evidence is approved. This offline plan is a
candidate for review, not a claim that operational prerequisites are satisfied.
