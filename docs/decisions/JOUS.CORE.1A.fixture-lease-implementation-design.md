# JOUS.CORE.1A operational fixture lease implementation design

Status: DESIGN AUTHORITY CANDIDATE FOR INDEPENDENT REVIEW. Normative requirements
below describe a future implementation; they authorize no implementation or operation.
No host/provider, register, activation record, credentials, fixture identities or
managed evidence is selected or created here. No claim is made about fixture existence
or CANARY readiness. Only this document is created; no production/schema change.

## 1. Authority and architecture

Baseline HEAD/origin/main: `2ef05f8c4af7c6c440ee56631fda9b8bdde720ba`;
tree: `75273904f944b70e51848d8f495b7c0e033d61fa`.
The following published authorities govern this design (all under docs/decisions):

| Document | Git blob | SHA256 |
| --- | --- | --- |
| JOUS.CORE.1A.runtime-canary-fixture-plan.md | f0f3f445c1cdf2151d0c1769989eac48197089a7 | a9223abc6d72edb84895cf75d504ddddad85d82c6441601702af17a3bf51947e |
| JOUS.CORE.1A.runtime-canary-fixture-provisioning-bootstrap-amendment.md | 1713898695d32b04ccd26833b68e94fa4a1c0545 | 2aec6ebeddd4267548981a76d017cd2001417bad33804a246ed6264646d64ef3 |
| JOUS.CORE.1A.runtime-canary-fixture-provisioning-contract.md | b56eac61bd120b0ae81d610fb63f2fdae1343d22 | 87657d5347cd15882dd860b47105f875c392c81f5185599914541734df04222c |

Their historical candidate wording does not authorize execution. This specification
preserves their typed bindings, exact eight-row contract, FORCE RLS executor gate,
independent approvals, five-minute canary freshness and separate execution authority.
It defines operational metadata, never additional Jous application columns.

Exactly one issuer owns exactly one authoritative SQLite register on one separately
approved host. Register and journal live outside Git and outside the Jous production
database. Operators use the issuer, never direct register access or local copies.
No network-shared SQLite, client fallback, automatic failover or replica acquisition.
Copied/restored registers are non-authoritative. Availability is sacrificed on doubt.
Maintenance/retirement conflict types exist but acquisitions are disabled until their
separate artifact-binding authorities are adopted; this design does not invent them.

## 2. M1: frozen SQLite/storage profile

Version policy: SQLite 3.45.0 or newer is the compatibility floor, not an approval of
every later version. Operational activation requires an independently approved exact
sqlite_version, sqlite_source_id, Python/driver build and binary/package identity,
with the complete durability/concurrency suite passing. No unreviewed upgrades.
Required SQLite features include STRICT tables, foreign keys and rollback journaling.
Build must support thread safety; connection ownership remains one service thread.
No extensions, custom SQL functions, arbitrary SQL endpoint or attached databases.

Profile on EVERY connection, read back and require exact values before serving:

| Setting | Frozen value |
| --- | --- |
| journal_mode | DELETE (rollback journal, not WAL/MEMORY/OFF/PERSIST/TRUNCATE) |
| synchronous | EXTRA (numeric 3) |
| foreign_keys | ON (numeric 1) |
| busy_timeout | 0; no hidden wait/retry |
| locking_mode | NORMAL |
| read_uncommitted | OFF |
| transaction start | BEGIN IMMEDIATE for every state-changing command |

One process-local dispatcher serializes commands; SQLite's write transaction is the
storage serialization backstop. Competing connections returning BUSY/LOCKED produce
BUSY_REJECTED, never wait then silently acquire. No automatic command replay.

Use an absolute approved path on fixed durable local storage with verified filesystem
locking, atomic operations, flush/barrier behavior and power-loss qualification.
Disallow SMB/NFS/cloud-mounted storage, removable media, RAM disks, ephemeral container
layers, synchronized folders, Git checkout and symlink/reparse redirection. Database,
journal and parent directory share the approved filesystem. Service account owns
restricted directory; operators cannot copy/replace/edit files. Encryption at rest
and backup access/retention require operational qualification, not a secret here.

SQLite transaction atomicity/recovery depends on its VFS and functioning OS/filesystem/
hardware. EXTRA adds the rollback-journal deletion directory synchronization behavior;
it does not prove faulty storage honors flushes or protect against privileged tampering.
No acknowledgement until COMMIT is confirmed AND the checkpoint gate in section 6
succeeds. These are separate persistence systems, not a distributed transaction.

Startup: open existing approved register only (never silently create on missing file),
check activation identity, exact runtime/profile, integrity_check = exactly ok,
foreign_key_check = no rows, schema/version, event chain, state digest, command/event
consistency and all blocking-claim invariants. Journal recovery is SQLite's responsibility;
do not delete a hot journal manually. Any error enters RECOVERY_ONLY.
Disk full/I/O errors before or during COMMIT: withhold acknowledgement, attempt bounded
rollback/close, suspend writes and reconcile durable outcome. Never infer rollback
from an exception. Corruption suspends the issuer; no repair/vacuum/rebuild in service.
Orderly shutdown stops intake, completes or reconciles the current command, publishes
a checkpoint and closes storage. Failure leaves a recovery condition, not availability.
Backup: pause transitions, checkpoint, use SQLite's consistent backup facility, verify
backup integrity/content digest, record protected checkpoint and copy identity, then
resume only after success. Never raw-copy a live database/journal pair. Every backup
copy is marked non-authoritative outside the database; backup failure blocks transitions
until reconciliation. No backup/restore provider is selected here.

## 3. M1: logical schema and immutable domains

All tables are STRICT. Required fields are NOT NULL unless explicitly optional below.
Hashes are 32-byte BLOBs, IDs are bounded nonblank UTF-8 operational identifiers,
UTC times are signed 64-bit microseconds since Unix epoch, revisions nonnegative integers.
Text enums have CHECK constraints. Foreign keys use RESTRICT, never cascading history
deletion. Mutable projections can change only through issuer transactions below.
Operational IDs/references are 1..255 UTF-8 bytes; payload/artifact bytes are bounded
to 1 MiB per record; unknown versions reject. Optional quarantine/release/recovery
fields are NULL until applicable; required successful acknowledgements are non-NULL.

| Table / authoritative key | Fields and constraints | Mutation rules |
| --- | --- | --- |
| REGISTER_METADATA / singleton key 1 | schema_version, register_id UNIQUE, issuer_generation, activation_id, authority-pin hashes, last_event_sequence, last_event_digest, state_digest, last_valid_utc, recovery_required | register_id/schema/authority pins immutable per approved schema; generation/activation only activation ceremony; head/time projections advance transactionally |
| APPROVED_ARTIFACTS / artifact_id | artifact_type, exact_bytes, sha256, approval_record_bytes/hash, approver identity, authorization_ref, operation_type, phase, optional predecessor_artifact_id FK | UNIQUE(artifact_type,sha256); append-only; reject differing bytes under same identity/hash; predecessor immutable; no overwrite |
| RESERVATIONS / reservation_id | register_id, fixture_set_id, operation_type, phase, binding_kind, binding_artifact_id FK, binding_sha256, immutable_db_projection_hash, owner, authorization_ref, requested/acquired/acknowledged_at, expires_at, completion_deadline, revision, lease_status, expired_condition, execution_state, optional release_evidence_artifact_id FK, quarantine_reason, recovery_evidence_artifact_id FK | reservation_id UNIQUE/PK; operation/set/owner/UUID/value projection/times/deadlines immutable; phase/binding advance only allowed transition; revision +1 per change; status/evidence via approved transitions |
| BLOCKING_CLAIMS / canonical_key BLOB PK | reservation_id FK, introduced_revision, originating_artifact_id FK | globally unique complete canonical bytes; no expiry column/TTL; insert at acquisition/advance, delete only approved release/recovery transaction |
| COMMANDS / command_id PK | authenticated_principal, command_kind, canonical_payload_bytes/hash, expected_revision, optional reservation_id FK, outcome_code, durable_ack_bytes, transition_event_sequence FK | append-only complete outcomes; command_id UNIQUE; identity/payload/outcome never overwritten; rejected commands may have no reservation/ack |
| EVENTS / event_sequence PK | command_id, optional reservation_id FK, register_id/generation/activation, event_type, UTC time, prior_digest, event_bytes/digest, revision, artifact/evidence refs | append-only, contiguous sequence; UNIQUE event_digest; command link FK deferred until same transaction closes; event names closed |

Successful commands' reservation/events/outcome/acknowledgement are one transaction;
deferred COMMANDS/EVENTS references cannot leave dangling rows. Each command has one
outcome; each successful command has one acknowledgement referencing all its events.
SQL constraints enforce unique IDs/keys, enums, revision domains, phase/binding matching,
deadline ordering and required successful ack presence. Store procedures in application
transactions enforce cross-row equality and event-chain invariants; startup independently
rechecks them. Schema has no direct operator write interface.

Closed domains:
- operation: FIXTURE_PROVISIONING, CANARY, FIXTURE_MAINTENANCE, FIXTURE_RETIREMENT;
- phase: PRE_AUTH_PROVISIONING_REQUEST, AUTH_IDENTITIES_BOUND, NOT_APPLICABLE;
- binding_kind: PROVISIONING_REQUEST, FIXTURE_MANIFEST; other operations disabled;
- artifact_type: PROVISIONING_REQUEST, FIXTURE_MANIFEST, PROVENANCE_EVIDENCE,
  RELEASE_EVIDENCE, RECOVERY_EVIDENCE, AUTHORIZATION; approvals bind exactly one type;
- lease_status: LEASED, RELEASED, EXPIRED, QUARANTINED;
- execution_state: NOT_STARTED, STARTED, STOPPED_KNOWN, UNKNOWN;
- quarantine reasons: CLOCK_UNCERTAIN, STORAGE_UNCERTAIN, AUTHORITY_UNCERTAIN,
  ACK_UNCERTAIN, PHASE_UNCERTAIN, EXECUTION_UNCERTAIN, EXPIRED_UNRECONCILED,
  EVIDENCE_MISMATCH, INTEGRITY_FAILURE;
- command: ACQUIRE, ADVANCE, RECORD_EXECUTION, QUARANTINE, RELEASE, RECOVER;
- event: REQUESTED, REJECTED, RESERVED, ACKNOWLEDGED, PHASE_ADVANCE_REQUESTED,
  PHASE_ADVANCED, EXECUTION_RECORDED, EXPIRED, QUARANTINED, RELEASE_REQUESTED,
  RELEASED, RECOVERY_APPROVED, RECOVERED.

No expired/non-released reservation is available just because its lease_status changed.
Availability is absence of blocking claims AND absence of unresolved global recovery.
Historical terminal records and their former key sets remain reconstructible in events.

## 4. M1: exact transactions, outcomes and acknowledgement

Acquisition: verify external authority permit (section 6); BEGIN IMMEDIATE; recheck
mode/revision/clock and authority permit validity; authenticate principal; validate
independent approval and exact artifact/type/phase; derive complete keys; reconcile
command_id/payload; check all existing claims and global recovery. Append REQUESTED,
create reservation, insert ALL claims, append RESERVED/ACKNOWLEDGED, persist successful
COMMANDS outcome and exact ack bytes; update metadata head/state; COMMIT. Publish
protected checkpoint; only then return acknowledgement. Service never performs fixture
or external-auth actions as part of this transaction.

Any conflicting insertion rolls back the ENTIRE transaction. No partial claims/events
or reservation survive. After confirmed rollback only, a separate bounded issuer
transaction may record REQUESTED/REJECTED and the finite rejected command outcome;
it cannot reserve keys. Invalid input rejected before transaction need not have
REQUESTED in SQLite; closed diagnostic rejection suffices. No audit-write failure
is converted to acquisition success. Authority outage permits no audit write.

Finite outcomes: SUCCESS, CONFLICT_REJECTED, BUSY_REJECTED, MALFORMED_REJECTED,
APPROVAL_REJECTED, AUTHORITY_REJECTED, CLOCK_REJECTED, PHASE_REJECTED,
REVISION_REJECTED, REPLAY_MISMATCH, CLOSURE_REJECTED, STORAGE_UNKNOWN.
Only SUCCESS carries operational ack; all other outcomes prohibit operation.

Same command_id + same principal/canonical payload hash returns stored outcome,
with current activation/checkpoint/mode and active/unexpired state checked separately.
Same ID with different principal/payload rejects REPLAY_MISMATCH. Different ID with
overlap conflicts. A replay never returns stale bytes as current execution permission.
Lost delivery is not failed COMMIT: resolve original command_id through authenticated
read-only lookup. No automatic resubmission, new reservation or external action.
An ack identifies register/generation/activation, reservation, revision, owner,
operation/phase, binding kind/hash, exact key-set digest, authority/approval refs,
issued/start/expiry/deadline and durable event sequence/digest. Delivery is outside
the transaction; signed/authenticated response integrity uses approved operator trust.

Advancement: authority gate; BEGIN IMMEDIATE; reconcile command; load exact reservation
and expected revision; require same owner, FIXTURE_PROVISIONING, PRE_AUTH, LEASED,
unexpired; verify predecessor hash, new independent approval and exact bytes;
compare ALL immutable DB identities/values/relationships plus actor-generation scope.
Retain ALL claims; derive/add actual issuer/subject claims; conflict -> entire ROLLBACK.
Otherwise update SAME reservation binding/phase, revision +1; append
PHASE_ADVANCE_REQUESTED/PHASE_ADVANCED/ACKNOWLEDGED; persist outcome/ack, metadata;
COMMIT and checkpoint. No release/reacquire, expiry extension or ownership change.
PRE_AUTH remains blocking unchanged on rejected advancement.

Quarantine: authority gate; BEGIN IMMEDIATE; append QUARANTINED and reason/evidence,
retain every claim, revision +1, durable outcome/ack; COMMIT/checkpoint. A service
unable to persist quarantine closes operational intake immediately; recovery-only
mode remains enforced externally until persistence/reconciliation succeeds.

Release: require exact independent approval of stop/cleanup/outcome and required
unchanged-state evidence, bound to reservation/revision/key set. BEGIN IMMEDIATE;
validate evidence and current state; append RELEASE_REQUESTED; delete ALL claims
for this reservation; mark RELEASED, revision +1, append RELEASED/ACKNOWLEDGED,
persist outcome and metadata; COMMIT/checkpoint. Any failure rolls back all deletions.
No release based on owner assertion, expiry, disposal flag alone or lost response.

Recovery: independently approved diagnosis must prove stopped/fenced execution,
known DB/auth outcome, required fixture/security evidence and no conflicting work.
In a separately authorized recovery ceremony, BEGIN IMMEDIATE; verify exact quarantined
revision/evidence; append RECOVERY_APPROVED; atomically record RECOVERED/RELEASED,
free ALL claims, update revision/history/outcome and persist ACKNOWLEDGED/durable
result in this transaction; COMMIT/checkpoint. This acknowledges only recovery,
never resuming an operation, creating a successor or repair permission. Recovery-only issuer requires
new valid activation before this claim-freeing transaction can be served.

## 5. M2: external authority identity, fencing and activation

register_id identifies the permanent register; issuer_generation is a strictly
increasing integer; activation_id uniquely identifies one approved activation.
Neither a database-stored generation nor a copied register proves authority.

Require ONE protected external activation authority, outside SQLite, Git and Jous
production DB. Its vendor-neutral capability interface must provide authenticated,
linearizable compare-and-set, append-only generation history, non-exportable approved
host/service identity verification, deny-on-unavailable reads, and command permits.
It is a trust dependency requiring separate implementation/qualification, not a
second fixture reservation register or an assumed existing service.

Immutable activation record schema jous.fixture-lease-activation.v1 includes register_id,
issuer_generation, activation_id, approved_host_identity, register checkpoint reference/
digest, predecessor_generation, activation_approval_ref/hash, activated_at and status
ACTIVE or SUPERSEDED. Supersession appends a record; never rewrites historical approval.
External current pointer selects at most one ACTIVE record. Host identity must be
verified through protected host-bound identity, not hostname text supplied by a client.

Before EVERY state-changing command, obtain a fresh single-command permit bound to
activation/generation/host, command_id/payload hash and predecessor checkpoint. Permit
has a bounded validity interval evaluated by the trusted clock. No cached activation
or offline permit reuse. Activation authority allows at most one in-flight permit;
supersession cannot complete while its outcome remains unresolved. Commit/checkpoint
completion closes permit with exact resulting checkpoint. Lost/expired permit outcome
blocks further permits pending reconciliation. This prevents a read-then-supersede
race; a merely readable activation file is insufficient.

Startup: prove local register_id/generation/activation matches current record, approved
host-bound identity, valid checkpoint ancestry/current head and no recovery condition.
Fail any proof -> RECOVERY_ONLY. No acquisition, advancement, claim-freeing release,
operational acknowledgement or valid-lease assertion. Permitted diagnostics: authenticated
read-only identity/integrity/history/command-outcome reports explicitly labeled
NON_OPERATIONAL; no customer data, secrets or raw exceptions.

Replacement ceremony: stop intake; reconcile any in-flight permit/commit; independently
prove prior service/host fenced (service execution disabled and host access revoked,
old operator/service credential revoked where applicable, old activation superseded).
An unreachable host is not fencing evidence. Remove ability to run old issuer or
serve accepted acknowledgements; clients pin current activation and reject old ones.
Review checkpoint/history and external operation outcomes; independent recovery approval;
allocate new generation/activation; CAS current pointer; start new active issuer.
No automatic takeover. Old host must fail fresh permit checks after supersession.
The activation authority cannot fence rogue Jous database writers: operational proof
that prior external/DB work stopped is additionally mandatory before claims are freed.

Every restored/copied DB is NON_AUTHORITATIVE/RECOVERY_ONLY regardless of embedded
ACTIVE metadata. Restore -> integrity -> protected history/checkpoint reconciliation
-> establish latest durable state -> fence prior issuer -> independent recovery approval
-> new generation/activation -> protected record publication -> validated startup.
Stale snapshots never resurrect AVAILABLE: missing events/claims must be recovered
from trusted history or conservatively blocked; inability to reconstruct means STOP.

### 5.1. Generation-one genesis ceremony

A separately authorized local initialization creates an empty SQLite register in
NON_AUTHORITATIVE / RECOVERY_ONLY service mode. It is not normal startup and grants
no command permit or fixture-operation authority. Immutable genesis inputs bind
register_id, schema/version, issuer_generation = 1, proposed activation_id,
genesis_marker = GENESIS_V1, creation-evidence reference and all authority pins.
Reservations, claims, commands and events are empty; last_event_sequence = 0 and
last_event_digest = SHA256(ASCII JOUS-FIXTURE-LEASE-GENESIS-V1). The empty-state
checkpoint uses the existing canonical state serialization. Normal startup still
opens only an existing approved register; it never initializes one implicitly.

The exact generation-one predecessor representation is predecessor_generation = 0,
where zero means GENESIS only; ordinary generations are positive integers. A genesis
checkpoint has checkpoint revision 0, event sequence 0, the genesis event digest,
and predecessor_checkpoint_digest = 32 zero bytes. These sentinels are valid only
in the independently approved generation-one genesis package; never for replacement.
Creation evidence uses exact immutable references under the existing framing rules.

The independently approved genesis package binds register_id, schema/version,
generation 1, proposed activation_id, approved host-bound identity, exact genesis
checkpoint bytes/hash, empty state digest, event sequence/digest, predecessor 0,
activation purpose, creation evidence and approval identity/reference. The local
initializer/issuer cannot approve its own package. No host or trust identity is
chosen here. The initial protected checkpoint additionally binds the approved host
identity and genesis approval reference in its approval evidence. Its publication
alone never activates the issuer.

The external activation authority distinguishes authenticated authoritative ABSENT
from UNAVAILABLE/UNKNOWN. Generation-one publication requires linearizable
create-if-absent/CAS with expected ABSENT and the exact approved genesis package,
initial checkpoint and stable genesis_activation_command_id/payload hash. Exactly
one activation can win for register_id. Existing activation rejects; unknown absence
blocks. A removed local file, empty database or missing cached record is not ABSENT.
External generation history/tombstones must prevent a formerly activated register
from appearing eligible for a fresh generation-one ceremony.

Required order:
1. Initialize local register NON_AUTHORITATIVE / RECOVERY_ONLY under separate authority.
2. Validate exact schema, immutable genesis inputs and empty state.
3. Produce canonical genesis checkpoint candidate and its exact hash.
4. Obtain independent approval of the exact genesis package and checkpoint.
5. Publish the protected initial checkpoint as a non-activating approved genesis anchor.
6. CAS authoritative ABSENT to ACTIVE generation 1 using the stable activation command.
7. Read back the activation record through the authoritative mechanism.
8. Verify local register/checkpoint/package/generation/activation/host/approval equality,
   current authoritative status, fresh qualified time and no unresolved outcome.
9. Only then derive local ACTIVE service mode from verified external authority.

Genesis checkpoint publication is the sole pre-activation checkpoint exception: it
requires independent genesis approval and cannot grant normal command permits.
Initialization creates no reservation or operational acknowledgement. The external
CAS record is the activation outcome authority; generation one has no permanent
bypass of per-command fresh permits, checkpoint gates or independent approvals.

Failure boundaries:
- Local register exists without checkpoint: restart RECOVERY_ONLY, validate/reconcile
  the original genesis inputs; never infer activation.
- Initial checkpoint exists without CAS: still non-authoritative; reconcile the
  original approved genesis package before any authorized continuation.
- CAS known rejected: remain non-authoritative; never overwrite another activation.
- CAS response UNKNOWN: do not retry as new; query the original stable command and
  authoritative activation state. Until resolved, remain RECOVERY_ONLY.
- CAS committed before crash/readback/local ACTIVE: external outcome persists; restart
  RECOVERY_ONLY and verify the exact original package/checkpoint/current host binding
  before deriving ACTIVE. No duplicate CAS mutation is needed.
- Matching authoritative generation-one outcome: treat CAS as committed and continue
  verification only. Different package/host/hash or unavailable lookup: fail closed.
- Local register lost after activation: restore/recovery/new-generation procedure,
  never recreate generation 1. Every copied/restored register remains recovery-only.

Initial checkpoint failure leaves no activation. Lost checkpoint publication response
is reconciled by its exact identity, not by inventing another genesis anchor. Any
ambiguous package, storage or authority outcome requires independent reconciliation.

## 6. M2: protected checkpoint protocol

Checkpoint schema jous.fixture-lease-checkpoint.v1: register_id, generation,
activation_id, contiguous checkpoint revision, latest durable event sequence,
event-chain digest, reservation/claim/command state digest, UTC timestamp,
predecessor checkpoint digest, command/permit reference, approval where applicable.
Canonical state digest covers all mutable projections and blocking keys; history
digest covers immutable records. Exact canonical serialization follows section 8
binary framing with fixed schema field order; sorted records by authoritative key.
State digest excludes its own stored digest and metadata event-head/digest fields to
avoid circular hashing; covers all other metadata, reservations and claims, plus
command outcomes including acknowledgement bytes. Events hash prior digest plus their
fixed fields, never the resulting checkpoint digest. The initial genesis digest and
empty state are independently approved at first activation, not guessed on restart.

The external protection interface retains immutable checkpoints and advances a
linearizable current pointer by predecessor CAS. It must be inaccessible for history
rewrite by requesters/issuer. Issuer may propose its permitted successor checkpoint;
independent audit retains exports/approved anchors. Hash chains alone do not protect
against a privileged administrator rewriting all local history.

Require checkpoint at activation and EVERY committed state-changing command (including
acquisition, advancement, execution recording, quarantine, release/recovery/rejection),
orderly shutdown and backup. Successful COMMIT followed by checkpoint failure is NOT
rolled back. Do not return operational acknowledgement; stop further transitions,
leave command permit unresolved and enter RECOVERY_ONLY. Reconcile actual committed
state with last external checkpoint; publish the exact missing successor only after
independent recovery approval. Never replay the transition or clear claims by restoring
the older checkpoint. Identical checkpoint publication retry is reconciliation only,
not an automatic state-changing command retry.

This two-store protocol deliberately blocks during the commit/checkpoint gap. SQLite
commit is locally authoritative data, but cannot authorize subsequent operations until
externally checkpointed. Activation cannot supersede an unresolved gap. Release commit
may have deleted local claims, yet no acquisition can run until its protected successor
is reconciled. All clones lack host-bound activation/permit authority by default.

## 7. M3: approved clock profile and conservative UTC intervals

Persist UTC microseconds; local OS wall clock is diagnostic/logging time, not the
authorization clock. The former 1-second uncertainty, 30-second sample freshness and
2-second discrepancy values are not controlling-source guarantees and are removed
as universal constants. A separately independently APPROVED CLOCK PROFILE must bind
exact profile bytes/hash, authenticated source identity, sampling/transport model,
MAX_COMMAND_TIME_UNCERTAINTY, MAX_SAMPLE_AGE, elapsed-clock qualification range,
nonnegative conservative error-budget function E(elapsed), anomaly bounds and exact
qualification evidence. Parameters must be finite, validated and justified for the
actual source/host; the profile cannot waive published deadlines or claim-release
rules. No production profile/source or current clock readiness is established here.

Each validated sample records sample_id, source identity, authentication/evidence,
trusted UTC interval [T_sample_lower,T_sample_upper] at local monotonic capture m0,
profile identity and creation evidence. The interval must include source error,
transport/sampling latency and capture uncertainty according to that approved profile.
Malformed, unauthenticated, reversed or unsupported intervals reject. No uncertainty
component may be omitted or counted twice; the profile assigns each component either
to the sample interval or to explicitly bounded subsequent propagation error.

For a command decision in the SAME process/monotonic domain, capture m1 and require
elapsed = m1 - m0 >= 0 within qualification range. Derive:

now_lower = T_sample_lower + elapsed - E(elapsed)
now_upper = T_sample_upper + elapsed + E(elapsed)
command_uncertainty = now_upper - now_lower

E(elapsed) bounds elapsed-clock drift, resolution and propagation error not already
included in the sample interval. Any additional subsequent uncertainty must be
included in E or widen these bounds explicitly under the approved profile. Use exact
bounded arithmetic and conservative outward rounding to persisted microseconds;
overflow or unsupported precision rejects. Sample age is conservatively bounded by
elapsed + E(elapsed), not an untrusted wall-clock subtraction. If age exceeds the
approved maximum, interval width exceeds the approved maximum, error budget cannot
be proved, or monotonic relation/range is anomalous: TIME_UNCERTAIN, stop state-changing
service and enter RECOVERY_ONLY. Never use the midpoint or stale sample upper endpoint.

Evaluate approval valid_from conservatively with now_lower >= valid_from. For an
inclusive authorization deadline, permission requires now_upper <= deadline;
now_lower > deadline is definitely expired, and now_lower <= deadline < now_upper
is overlap uncertainty and fails closed. Published strictly-before deadlines remain
strict: lease/continuation/freshness require now_upper < their deadlines, so equality
also denies continuation. Apply every applicable bound without converting a strict
bound into an inclusive one. Lease expiry remains strictly later than freshness
expiry and planned completion; freshness starts at earliest material observation.

EXPIRY NEVER FREES CLAIMS. Definitely expired and deadline-overlap uncertainty both
retain every claim and deny continuation. Append EXPIRED for definite expiration
then QUARANTINED for unresolved execution; uncertain timing records CLOCK_UNCERTAIN
quarantine when storage/authority permits. If persistence is unavailable, issuer
intake remains stopped. Sweeps are reporting aids, never exclusivity mechanisms.

Persist last_valid_utc conservatively as the validated decision's lower bound, not
raw OS time or a guessed upper bound. On restart no persisted monotonic anchor may
be reused. Require a newly authenticated sample/profile, reconcile its interval
against durable time/history and all outstanding deadlines/permits, and obtain any
required recovery approval before ACTIVE state-changing service. A sample whose
upper bound is earlier than durable last_valid_utc contradicts history; overlap
insufficient to establish required ordering remains uncertain until reconciled.
Downtime never extends deadlines, resumes execution or frees claims.

Refresh before sample-age, error-budget or uncertainty limits are exceeded. Validate
a new interval and process-local anchor independently. Compare the old conservatively
propagated interval at the new capture with the new interval using approved consistency
bounds. Contradiction beyond those bounds means TIME_UNCERTAIN/reconciliation. Do not
intersect, splice or narrow intervals without independently justified evidence; the
new sample has its own complete uncertainty budget. No automatic return from an
already recorded clock anomaly merely because the next reading looks plausible.

Monotonic decrease/reset, unrelatable anchor, exceeded qualification range or violated
drift bounds prohibits extrapolation; require new trusted evidence and reconciliation.
OS wall-clock jumps cannot directly change permissions. If diagnostics contradict
trusted evidence beyond approved anomaly bounds, fail closed. Within-profile NTP
correction is diagnostic only and cannot reset deadlines. Exit from RECOVERY_ONLY
requires independent approval binding the anomaly, qualified interval, outstanding
permits/deadlines, stopped execution/cleanup and reconciled history.

The unchanged canary has no automatic lease/time integration; accountable operators
must verify current acknowledgement/deadlines and invoke authorized cleanup on denial.
The issuer does not fence application SQL. Clock qualification and operator execution
monitoring remain separate operational gates; defining this interface approves neither.

## 8. M4: exact canonical encoding and key derivation

Canonical frame: ASCII prefix JOUS-FIXTURE-LEASE followed by byte version 1, one-byte
domain tag, unsigned big-endian 32-bit field count; each field is unsigned big-endian
32-bit byte length followed by exact bytes. Reject unknown tags, duplicate fields,
trailing bytes, empty required fields, lengths above 65535, invalid UTF-8 or unpaired
surrogates. Schema fixes field order/count; no delimiter concatenation.
UTF-8 validation applies to textual fields only; binary UUID/hash/integer fields use
their exact typed widths and are not interpreted as text.
SHA256 hashes full framed bytes; store FULL canonical key as uniqueness authority,
digest only as index/evidence aid. Hash collisions with unequal bytes reject/stop.

Key domain tags and ordered fields:

| Tag/type | Exact fields |
| --- | --- |
| 1 FIXTURE_SET | approved database-target-scope, authoritative logical fixture_set_id |
| 2 DB_UUID | approved database-target-scope, canonical UUID 16 bytes (no table field) |
| 3 LOGICAL_ACTOR_ALLOCATION | approved global provider-allocation-scope, stable logical actor allocation identifier |
| 4 ISSUER_SUBJECT | exact approved issuer representation, exact subject UTF-8 bytes |

Target scope is an immutable approved logical database identity, not a caller URL.
Provider scope is authoritative across requests/operators; new request IDs/set display
names cannot change it. Unknown issuer requires fixed approved provider allocation
scope; underspecified actors reject. Issuer/provider/subject strings use exact approved
UTF-8 with no runtime trimming, folding, URI normalization or Unicode normalization.
Any required normalization occurs before independent approval and becomes exact bytes.
UUID parser rejects noncanonical textual form in approved requests; key is 16 bytes.
All eight UUIDs must be distinct; UUID key conflicts across table types within target.
Issuer-subject keys deliberately do not include database target, preventing reuse of
the same auth identity across fixture operations in different databases.

Payload domain tag 5: fixed ordered fields for command_kind, authenticated principal,
register/generation/activation, command_id, reservation_id or explicit empty on acquire,
expected_revision, operation, phase, binding_kind/hash, approval/authorization hashes,
evidence hashes and exact operation parameters. Integers use unsigned big-endian 64-bit;
optional absence uses zero-length only where schema permits. Command payload schema
rejects unknown fields; immutable request bytes retain their independent exact-byte hash.
For collections use a field containing uint32 item count and recursively framed
items; evidence/parameter maps have sorted UTF-8 field names and reject duplicates.
Additional framing tags: 6 EVENT (section 3 EVENTS fields in listed order, omitting
event_digest); 7 CHECKPOINT (section 6 fields in listed order); 8 STATE (metadata,
reservations, claims, commands in that order with section 6 exclusions); 9 APPROVAL
(role, principal, artifact_type/hash, operation, phase, target, reservation/revision,
requester, package/hash, allowed_transition, valid_from, valid_until, revocation_ref).
UTC integer fields use signed big-endian 64-bit; IDs/enums are exact UTF-8. Optional
fields use an explicit one-byte presence flag then framed value, except the explicitly
empty acquire reservation field. Binary schema/version/domain are fixed before signing.

PRE_AUTH issuer derives set + eight UUID + stable actor allocation claims from approved
request and authority history. Never accept caller key lists as authority. AUTH_BOUND
retains the complete prior set and adds actual issuer/subject claims. Exact duplicate
canonical keys deduplicate deterministically; contradictory symbolic identities or
distinct bytes claimed as same identity reject. Sort bytewise for state/ack digests.

CANARY: hash exact approved final jous.runtime-canary-fixtures.v1 manifest. Resolve it
through existing independently approved provenance and retained completed provisioning
history, not a new normative companion schema. Verify approval pins manifest bytes to
exact fixture set, both actor/user/org/project mappings, both membership IDs/roles,
complete eight-record identity projection and retained logical actor/issuer-subject keys.
Require confirmed provisioning outcome, independent verification/provenance approval,
final manifest approval and approved release with no quarantine. Missing/ambiguous/
inconsistent closure -> CLOSURE_REJECTED. No inferred membership IDs or supplied missing
keys. No new companion artifact is introduced; approval references existing evidence.
Later independently approved maintenance history must preserve exact closure; until
its authority exists, maintenance acquisition remains disabled.

## 9. M4: approval, access and replay enforcement

Roles: REQUESTER, INDEPENDENT_APPROVER, RECOVERY_APPROVER, ISSUER_SERVICE, AUDITOR.
Authenticated principal comes from protected operator authentication, never payload text.
Only issuer service writes SQLite; requester cannot read raw files/edit approval store.
Approvals are immutable signed/authenticated records verified against independently
approved trust identities and revocation state. No actual credentials/trust keys here.
Approval binds exact artifact/hash/operation/phase, target, reservation/revision where
applicable, requester/package, allowed transition and finite validity. Self-approval
is prohibited; requester cannot satisfy independent or recovery approval. Reviewer
identity must be distinct from execution owner; issuer cannot manufacture approvals.

| Transition | Required evidence |
| --- | --- |
| Acquire PRE_AUTH | independent exact request/generation package approval and requester authorization |
| Acquire AUTH_BOUND directly | independent actual actor/request approval under amendment exception |
| Advance | independent resulting bindings/new request/predecessor approval and requester authorization |
| Acquire CANARY | independent manifest/provenance closure approval plus canary package authorization |
| Record execution | authorized owner and exact operation authorization; no expansion of mutation authority |
| Quarantine | issuer-detected condition or authenticated owner report; no approval needed to block |
| Release | independent exact stop/cleanup/result/required verification approval |
| Recover/free claims | RECOVERY_APPROVER independent reconciliation approval and new valid activation |
| Activate/replace/restore | independent activation/recovery approval plus prior-host fencing proof |

Issuer validates evidence linkage/signatures, never decides live DB/auth fixture facts.
Database INSERT still requires AUTH_BOUND acknowledgement AND separate exact managed
mutation authorization. Lease service does not execute it. CANARY manifest binding is
never satisfied by provisioning hash. No PRE_AUTH CANARY/provisional manifest/operation
conversion. Expired/revoked approvals cannot authorize new transitions; outcomes retain
historical approval identity. Authorization availability uncertainty blocks operations.

CLI output is closed finite result schema: mode, finite outcome, reservation/revision,
typed binding hashes, acknowledgement/checkpoint references and finite reasons only.
No credentials, raw exceptions, DB URLs, arbitrary provider strings or customer data.
Necessary synthetic identity bytes reside only in restricted artifacts/claims, not
default stdout/audit text. All audit payloads whitelist bounded reviewed fields.

## 10. Complete state/authority transition table

| Current state/mode | Condition | Next | Atomic / approval |
| --- | --- | --- | --- |
| ACTIVE issuer + no blocking keys | eligible approved acquisition | PRE_AUTH_RESERVED / AUTH_IDENTITIES_BOUND_RESERVED / CANARY_RESERVED | acquisition transaction + checkpoint, independent approval |
| ACTIVE + eligible maintenance/retirement | separate binding authority absent | REJECTED; no reservation | no shortcut; future separate authority required |
| PRE_AUTH_RESERVED | approved unchanged identities + actual bindings | AUTH_IDENTITIES_BOUND_RESERVED same ID | advancement transaction + checkpoint |
| Any reserved state | execution evidence | same reserved state/revision +1 | record transaction + checkpoint; separate execution authorization |
| Any unreleased reservation | deadline crossed | EXPIRED event + QUARANTINED | retain claims, quarantine transaction/checkpoint |
| Any reserved state | uncertainty | QUARANTINED | retain claims; storage outage blocks whole issuer |
| Reserved state | independently approved complete release gates | RELEASED historical; claims absent | release transaction + checkpoint |
| QUARANTINED | approved reconciliation + valid activation | RECOVERED event + RELEASED | recovery transaction + checkpoint |
| ACTIVE issuer | authority/clock/storage/checkpoint failure | RECOVERY_ONLY | stop intake immediately, externally retain unresolved permit |
| New genesis register | separately authorized initialization | NON_AUTHORITATIVE / RECOVERY_ONLY | section 5.1 package/checkpoint/ABSENT CAS required |
| Restored/copied/unverified issuer | any startup | RECOVERY_ONLY | default, never ACTIVE from DB flag |
| RECOVERY_ONLY issuer | fencing + reconciliation + new activation approval | ACTIVE new generation | external activation ceremony, SQLite metadata/history reconciled |

MAINTENANCE_RESERVED and RETIREMENT_RESERVED are defined future reservation states
with all shared conflict/expiry/release rules, but unreachable until their exact
binding authority is separately adopted. Lease status maps reserved states to LEASED;
phase is independent. AVAILABLE is derived, not a historical reservation transition.
Recovery-only diagnostics never grant continuation. Prohibited shortcuts include
downgrade, owner replacement, phase relabeling, TTL release, stale restore availability,
automatic renewal/failover, cached authority and executing on submitted/unconfirmed ack.

## 11. Deterministic failure matrix

| Failure | Required outcome |
| --- | --- |
| simultaneous eligible overlapping acquire | exactly one SUCCESS, others CONFLICT/BUSY_REJECTED; no silent delayed acquisition |
| any claim insertion conflict | whole transaction rollback; no partial claim set |
| disk full before commit | no ack; rollback/close; suspend and reconcile |
| disk full/I/O during commit | STORAGE_UNKNOWN; no ack; determine durable outcome, never assume rollback |
| commit succeeds, response lost | original command lookup; no new reservation/replay mutation |
| checkpoint fails after commit | no operational ack; unresolved permit, RECOVERY_ONLY; committed data retained |
| process dies before commit | SQLite recovery; independently validate no partial state before activation |
| dies after commit | retained outcome; missing checkpoint reconciliation before serving |
| dies during advancement | old or new whole state; same ID, old keys never released |
| dies during release | all claims retained or approved deletion committed; no service until checkpoint reconciled |
| corruption | RECOVERY_ONLY; no repair or inferred availability |
| copied register | non-authoritative, fails host/activation/permit proof |
| stale restore | reconcile protected head; missing state blocks, never resurrect availability |
| old host returns | superseded generation/host cannot obtain permit; old ack rejected |
| activation record unavailable | deny every state-changing command; diagnostics non-operational only |
| trusted-time contradiction/qualified anomaly/source outage | RECOVERY_ONLY; claims retained, deadlines never extended |
| expiry while offline | reconcile UTC bounds; expired blocks and quarantine; no TTL removal |
| malformed key/omitted identity | MALFORMED_REJECTED; no acquisition |
| missing CANARY provenance closure | CLOSURE_REJECTED; no inferred fields |
| approval mismatch/self-approval | APPROVAL_REJECTED; no transition |
| same command replay | same exact durable result, current authority separate; changed payload/principal rejects |
| network partition | no new permits/acknowledgements; client stops, never local fallback |
| genesis register created before checkpoint | RECOVERY_ONLY/NON_AUTHORITATIVE; original initialization reconciliation only |
| genesis checkpoint published before activation | no authority/permits; checkpoint alone grants nothing |
| genesis CAS conflict | reject without replacing existing activation |
| genesis CAS unknown outcome | original command/state lookup; no new CAS or ACTIVE until reconciled |
| crash after genesis CAS | restart recovery-only; verify exact committed activation/package/checkpoint |
| copied/restored register attempts genesis | reject; protected generation history requires restore/new-generation ceremony |
| trusted sample unavailable/unauthenticated | TIME_UNCERTAIN/RECOVERY_ONLY; retain claims |
| sample age too large | deny decisions until approved refresh/reconciliation |
| command uncertainty too wide/error budget unknown | TIME_UNCERTAIN; no deadline eligibility |
| deadline inside trusted interval | overlap uncertainty denies continuation; claims retained |
| monotonic anomaly or restart without fresh sample | no old-anchor extrapolation; fresh validated interval/reconciliation required |
| contradictory refreshed sample | stop; independent reconciliation, no interval-splicing shortcut |

## 12. Directly testable normative invariants

- INV-001: At most one non-released reservation owns any canonical blocking key.
- INV-002: Expiry/time correction alone never deletes claims or proves AVAILABLE.
- INV-003: PRE_AUTH advancement never changes reservation_id, owner, UUIDs or DB values.
- INV-004: Every successful transition has exactly one atomic durable command outcome/ack.
- INV-005: Copies/restores cannot ACTIVE-start without new approved activation generation.
- INV-006: Complete acquisition/advancement/release is all-or-nothing on every fault point.
- INV-007: Prior advancement claims remain; new pair claims are additive and atomic.
- INV-008: Provisioning and manifest binding kinds cannot substitute or relabel operations.
- INV-009: No PostgreSQL fixture mutation permission exists in PRE_AUTH acknowledgement.
- INV-010: DB-phase permission requires AUTH_BOUND ack plus separate mutation authorization.
- INV-011: Caller keys cannot replace artifact/history-derived complete conflict sets.
- INV-012: CANARY missing any eight-record/provenance/history closure rejects.
- INV-013: Self-approval or mismatched operation/phase/revision/artifact rejects.
- INV-014: Same command/payload yields one outcome; differing payload/principal rejects.
- INV-015: Operational ack requires confirmed SQLite commit and protected checkpoint.
- INV-016: Checkpoint failure never undoes commit; it blocks all further transitions.
- INV-017: Fresh host-bound permit is required for every transition; supersession fences old generation.
- INV-018: Unknown commit/permit/clock/storage state never permits successor acquisition.
- INV-019: Only independently approved release/recovery atomically frees ALL owned claims.
- INV-020: Event history is append-only, contiguous and protected-checkpoint anchored.
- INV-021: Eight UUID keys ignore table type and preserve approved target scope.
- INV-022: Actor key scope cannot be changed by request ID/display-name substitution.
- INV-023: Canonical framing is injective over accepted fields; ambiguous encodings reject.
- INV-024: No automatic failover, retry, renewal, takeover, fallback store or TTL cleanup.
- INV-025: Recovery-only diagnostics never assert active operational permission.
- INV-026: Maintenance/retirement acquisition rejects until separate binding authority exists.
- INV-027: Five-minute freshness remains independent of provisioning and lease start.
- INV-028: Startup rejects changed SQLite profile/version/schema or failed integrity checks.
- INV-029: Safe output contains no secrets, raw exceptions or arbitrary server text.
- INV-030: Lease authority never performs DB/auth provisioning, canary or runtime activation.

- GEN-001: Local initialization is never authority without externally verified genesis activation.
- GEN-002: Generation one publishes only through authoritative ABSENT-state CAS with predecessor 0.
- GEN-003: Unknown genesis CAS outcome never permits blind retry or ACTIVE service.
- GEN-004: Protected initial checkpoint alone never activates an issuer.
- GEN-005: Copies/restores never recreate genesis authority or erase activation history.
- TIME-001: Every deadline-sensitive state-changing decision uses a conservative trusted UTC interval.
- TIME-002: Inclusive deadline permission requires now_upper <= deadline; strict deadlines require now_upper < deadline.
- TIME-003: Deadline-overlap uncertainty fails closed without extending authority.
- TIME-004: Clock uncertainty never frees blocking claims.
- TIME-005: Persisted monotonic anchors are never reused across process restart.
- TIME-006: No independently approved/qualified clock profile means no operational state-changing service.

## 13. Future implementation map and qualification

All modules proposed under services/api/infrastructure; no files are implemented now.
- fixture_lease_contract.py: closed artifact/command/approval schemas, binary canonicalization,
  hash/type validation, conflict derivation, CANARY closure and state-machine predicates.
- fixture_lease_store.py: STRICT schema/constraints, exact profile checks, transactions,
  event/state digests, atomic command/ack persistence, integrity and consistent backup.
- fixture_lease_service.py: authenticated roles/approvals, dispatcher, activation/permit
  interface, clock evidence, checkpoints, mode transitions and recovery ceremony.
- fixture_lease_cli.py: authenticated bounded transport/command IDs and sanitized output;
  no direct SQLite access, credential fallback or automatic transition retry.

Future tests: contract/canonicalization/state-machine unit tests; storage constraint and
fault-injection tests; multi-process conflict/phase/release races; lost-ack/replay tests;
kill-before/after-commit tests; copy/stale-restore/old-host/permit partition tests;
clock intervals/jumps/restart/expiry tests; approval/self-approval/closure negatives;
output adversarial tests. Assert every INV and matrix row, not mirrored constants.
Offline unit tests use symbolic fake identities. Local SQLite crash tests require later
explicit temporary-storage authorization. Operational activation qualification must test
the actual host/filesystem/power-loss guarantees, activation authority linearizability,
host fencing, protected history restore and authenticated time source. None requires
Jous managed access; no such tests or infrastructure are performed here.

## 14. Self-review and non-operation boundary

M1 is frozen by sections 2-4; M2 by 5-6 including the explicit section 5.1 genesis
ceremony; M3 by section 7 interval/profile rules; M4 by 8-9. Sections 10-12 make
the interaction directly testable. Prior M2 maps to section 5.1 non-authoritative
genesis state, predecessor 0, independent package/checkpoint, ABSENT CAS, ordering,
crash matrix and original-command reconciliation. Prior M3 maps to section 7 sample
interval, conservative propagation/error budget, width/age rejection, deadline
upper-bound decisions, fresh restart anchors and independently qualified profiles.
These are design requirements for independent review, not demonstrated operational
closure. Sections 2-4 and 8-9 remain unchanged; no M1/M4 security semantics are reopened. No published authority is weakened. External
activation/checkpoint capability is explicitly required; a readable file or SQLite
generation alone is not an implementation. Actual host/provider/trust selection,
qualification and sensitive operations need separate independent review/authorization.
No fixture UUIDs or real issuer/subjects are supplied. No credentials, managed reads,
SQLite database, activation record, lease, fixture, deployment or canary is created.
This candidate grants no implementation, staging, publication or runtime permission.
