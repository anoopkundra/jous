# JOUS.CORE.1A IL6 authoritative register activation contract

Status: OFFLINE NORMATIVE CANDIDATE FOR INDEPENDENT REVIEW — NOT OPERATIONALLY
ADOPTED. This document specifies proposed authority constraints only. It approves
no implementation, activation package, genesis execution or operational use.
Repository publication is not independent approval, operational adoption, register
authority, reservation authority, managed-access authority, fixture-provisioning
authority, canary authority, deployment authority or runtime activation authority.

## 1. Derivation and controlling boundary

Historical derivation baseline for this candidate: HEAD and local origin/main
`86a91423c9eb665756bd5445beaa37f5e390c2fa`. This is an evidence pin, not a
requirement to rewrite older baselines when main advances.

The following committed sources were inspected. Paths in this table are relative
to `docs/decisions/`; their historical wording is not a new operational approval.

| Source | Blob at derivation baseline | Relevant boundary |
| --- | --- | --- |
| JOUS.CORE.1A.runtime-canary-fixture-provisioning-bootstrap-amendment.md | b2af73ae4788e76f4fd591ac267d40230d70026b | Typed provisioning binding; sole register; not operationally adopted |
| JOUS.CORE.1A.runtime-canary-fixture-provisioning-contract.md | 1d84df662ab0e7245f59842039789a55c1df25c4 | Separate approvals, exact eight-record provisioning and managed-access gates |
| JOUS.CORE.1A.runtime-canary-fixture-plan.md | f0f3f445c1cdf2151d0c1769989eac48197089a7 | One durable register/serialized issuer outside the protected production database |
| JOUS.CORE.1A.runtime-canary-procedure.md | bfa438aa8f4b19edb4cc3aacfd52137ab2f4f8dc | Fixture prerequisite, separate canary and runtime gates |
| JOUS.CORE.1A.fixture-lease-implementation-design.md | 706b6bf782701a602012bd1fed75099f519a53ee | Sections 2, 5, 5.1, 6 and 7: local SQLite, external activation, genesis, checkpoints, trusted time |
| JOUS.CORE.1A.il5-normal-checkpoint-orchestration-amendment.md | 567ad14ca53e1bdd67b6146fd8f304c97805446c | Normal admitted operations; excludes genesis and IL.7 recovery |

Controlling normative authority for generation-one genesis checkpoint-reference
semantics is the published/frozen
`docs/decisions/JOUS.CORE.1A.genesis-checkpoint-reference-amendment.md`,
commit `68cd9fcd7800daf0e23a720cc203a69c8b88d421`, blob
`d5136bc32ea8f62c04d09e65121edc00c0387d35`, SHA256
`2787bb6fed551f29b756a7fa915feea5d1b509f133f380427366f3c10786574f`.
Its independent publication-verification/freeze token is
`CORE1A_GENESIS_CHECKPOINT_REFERENCE_AMENDMENT_PUBLISHED_INDEPENDENTLY_VERIFIED_AND_FROZEN`.
For every discussion in this contract of the genesis ceremony reference, creation
evidence, checkpoint command/permit-reference position, stable approval identifier
versus digest-bearing approval evidence, stable genesis activation command identity,
acyclic dependency ordering and genesis-specific restart/uncertainty, that amendment
controls. This contract defers to it and MUST NOT duplicate, reinterpret or weaken
its definitions. Its adoption resolves prior Blocker A's missing normative
prerequisite; it does not approve IL6 or authorize implementation or genesis.

The IL.4 protocol/framing/adaptation authorities and replacement-generation
cutover amendment continue to govern their existing representations and ceremonies.
IL6 specializes the existing generation-one ceremony; it does not replace it with
a local-file flag or a second authority. Any incompatibility with those sources
MUST stop design/implementation for independent adjudication, not implicit repair.

## 2. Already built versus missing operational binding

The frozen `services/api/infrastructure/fixture_lease_*.py` machinery supplies
structural lease values, canonical COMMAND/EVENT/ACK/STATE, existing-only storage,
command transitions, admission, qualification, retention, predecessor/checkpoint
construction, original-permit acquisition, publication and completion. Specifically:

- `fixture_lease_contract.py` supplies necessary structural predicates, not permission.
- `fixture_lease_protocol.py` supplies canonical representations and the genesis
  event-chain anchor, not activation or lifecycle decisions.
- `fixture_lease_store.py` defines six tables and opens existing files with
  `mode=rw`; it explicitly excludes genesis/operational initialization. Its storage
  commit result is not an operational acknowledgement.
- `fixture_lease_service.py` defines activation, approval, permit and qualified-time
  capability boundaries; default capabilities reject. Constructing evidence values
  does not authenticate the claims in them.
- `fixture_lease_checkpoints.py`, `fixture_lease_permit_acquisition.py`,
  `fixture_lease_publication.py` and `fixture_lease_completion.py` implement bounded
  normal-operation knowledge/effect boundaries, not a genesis service.
- Synthetic storage tests create disposable databases only; the missing-file test
  explicitly requires no file or parent creation. Such tests prove no real authority.

What remains unestablished is the real host/storage instance, protected activation
and checkpoint authorities, qualified clock, issuer/access boundary, approved exact
activation package and separately authorized/verified genesis. No genuine register
or operational authority is inferred from source, schema, tests or certification.
IL.5 A–G semantics, effect cardinality, permissions and failure handling remain
unchanged. IL6 adds no reservation command, operation kind, event type, table,
migration, normal protocol field or alternate STATE codec.

## 3. Immutable register and activation identity

A future operational binding MUST identify exactly one register by `register_id`,
schema version and exact schema identity, generation `1`, unique `activation_id`,
approved host-bound identity, storage-instance identity and approved environment /
project scope. An environment label or pathname supplied by a caller is not proof.
The scope identifies what the register may govern; it grants no managed access.

Its immutable genesis evidence MUST bind the authority-document versions/exact
SHA256 values, implementation/build identity, selected STATE representation and
representation authority, creation-evidence reference, trusted creation timestamp,
initial metadata and exact initial STATE/checkpoint identities. Register/schema/
authority pins are immutable. Generation/activation changes require the existing
separate replacement ceremony, never a normal-open or configuration override.

The operational authority is the externally protected activation record and current
pointer, verified against the exact local register, host and checkpoint. Embedded
metadata, a valid schema, SQLite integrity success, OS ownership or a copied database
MUST NOT confer authority. The external record MUST retain immutable approval and
generation history/tombstones so a previously activated identity cannot become
apparently absent and undergo generation-one genesis again.

## 4. Genesis is a separate privileged operation

Genesis MUST be explicit, one-time, separately authorized and independently
reviewable. Normal startup/open MUST NOT initialize schema, create missing files or
directories, populate metadata, select identities or publish activation/checkpoints.
Schema initialization alone creates NON_AUTHORITATIVE preparation only.

Genesis is not an idempotent create-or-open API. Duplicate genesis is rejected.
Recognition of an already-completed exact genesis may be read-only verification
of its original stable command/package and protected outcome; it MUST NOT execute
another genesis. A timeout, missing local file or unavailable lookup never proves
absence. Unknown outcome forbids a fresh attempt, changed package or new identity.

Genesis authority and normal issuer authority MUST be separately scoped. The
initializer/issuer MUST NOT approve its own activation package. Later execution
authorization MUST name its accountable operator, independent approver, exact
implementation/package, permitted steps and finite stop conditions.

## 5. Exact immutable activation package

Before any genesis effect, an independently approved closed package MUST fix all
inputs in this table. Every referenced artifact MUST resolve to retained exact
bytes and SHA256; mutable URLs/display names alone are insufficient.

| Binding | Required contents |
| --- | --- |
| Identity | Package schema/version; register_id; exact register schema/version/hash; generation 1; activation_id; purpose GENESIS; genesis_marker GENESIS_V1; predecessor_generation 0 |
| Scope | Environment/project authority scope; approved host-bound identity and its verification authority; storage-instance identity and canonical absolute database/journal/directory location |
| Actors | Genesis operator and authorization; independent approval reference; normal issuer/service principal and generation; permitted opener/writer boundary; fencing and access-control evidence |
| Time | Exact approved clock profile bytes/hash, source/qualification authority and monotonic-domain rules; qualified creation sample/evidence and fixed creation UTC in microseconds |
| Authority | Exact relevant plan, bootstrap amendment, provisioning contract, implementation design, adopted IL6, frozen genesis checkpoint reference amendment and controlling IL.4/IL.5/representation authority hashes; approval/adoption evidence for each relied-upon authority |
| Software/storage | Approved exact Python/driver/SQLite builds and source identity; frozen connection profile; host/filesystem/VFS ownership, durability, permission and qualification evidence |
| Initial state | Exact metadata values including the four existing authority pins, last_valid_utc and recovery_required=0; empty reservation/claim/command/artifact/event populations; canonical initial STATE bytes/digest and genesis event anchor |
| Checkpoint | Exact complete genesis checkpoint bytes/hash; checkpoint revision 0; event sequence 0; genesis event digest; predecessor checkpoint digest of 32 zero bytes; genesis ceremony reference and approval identifier governed by the frozen genesis checkpoint reference amendment |
| Protected authorities | Exact activation/checkpoint authority identities and trust bindings; authoritative ABSENT proof requirements; append-only history/tombstones; linearizable create-if-absent/CAS and readback qualification |
| Attempt/evidence | Stable genesis_activation_command_id; creation evidence; independent approval linkage; authorization validity; exact verification/readback obligations and durable evidence retention |

The activation-command payload bytes/hash are downstream attempt evidence constructed only after Q under the frozen genesis checkpoint reference amendment, binding the approved package identity/hash and Q reference/hash; neither the payload nor its hash is a package input or included in this activation package's hash.

All fields are required. Unused scope elements MUST be explicitly inapplicable with
approved justification, never silently omitted. Reject duplicate/unknown fields,
malformed or contradictory identities, substituted dependencies and unbound inputs.
No ambient environment variable, current directory, default clock, implicit account,
random value or runtime configuration may silently alter genesis.

Package identity is SHA256 of its complete exact canonical bytes. A future minimal
design MUST specify and independently test one closed canonical package encoding,
field order/types/bounds and digest vectors before implementation approval. This
document defines required bindings, not a new executable codec or codec alteration
for frozen objects. An exact-byte hash or self-reported digest is not approval.

The exact genesis-reference meanings, distinct creation evidence, approval-ID
allocation versus final approval evidence, stable activation command identity and
acyclic checkpoint/package/approval/activation construction MUST follow sections
2 through 7 of the frozen genesis checkpoint reference amendment. No competing dependency
model or reference interpretation is defined here; the frozen codec remains unchanged.

Creation UTC is fixed from approved qualified evidence during separately authorized
preparation, not invented wall time. Package approval MUST bind that evidence and
the later execution validity bounds. Fresh execution-time qualification may deny
execution but MUST NOT recompute approved initial bytes/timestamp. External activated_at
is a separately evidenced actual activation time; it does not rewrite creation UTC.

## 6. Physical storage authority and durability

Preserve the existing architecture: one authoritative SQLite register on one
approved host, outside Git and outside the protected Jous managed database, with
one serialized issuer. Supabase is not selected as the register or activation
provider. No competing local register, replica writer or automatic failover exists.

The approved absolute canonical path MUST resolve to the approved physical storage
instance without symlink/reparse redirection. Database, rollback journal and parent
directory MUST share the approved durable local filesystem. Preserve the design's
prohibition on network/shared/cloud-synchronized, removable, ephemeral and RAM
storage. Bind volume/storage identity and host-bound verification, not pathname
alone. Path/instance/ownership/permission mismatch means STOP, not relocation.

The service account owns a restricted directory; only the approved service may
write through its serialized boundary. Operators/backups MUST NOT replace, edit or
adopt live files. OS access is necessary but never protocol authority. Unsupported
privileged-writer exposure invalidates the boundary until independently resolved.

Preserve the exact frozen connection profile: DELETE rollback journal, synchronous
EXTRA, foreign_keys ON, busy_timeout 0, locking_mode NORMAL, read_uncommitted OFF,
and BEGIN IMMEDIATE for normal state changes. Exact builds and actual filesystem
locking/flush/barrier/power-loss behavior require independent qualification.
SQLite atomicity does not make local storage plus external activation one transaction.

Backups require the existing paused-transition, protected-checkpoint and consistent
backup procedure with verified content and restricted retention/access. Every copy
is externally marked NON_AUTHORITATIVE. Raw live-file copying, backup substitution,
unapproved relocation and restored-file activation are prohibited. Corruption or
I/O ambiguity suspends service; no repair, vacuum, journal deletion or rebuild is
authorized. Restore/replacement belongs to separately approved IL.7 authority.

## 7. Trusted operational clock

The package MUST select an independently approved exact clock profile and
authenticated source/qualification authority. IL6 selects no production provider.
OS wall time is diagnostic only. Preserve the design's conservative UTC interval
and same-process monotonic propagation with its complete approved error budget,
sample age, uncertainty limits, anomaly bounds and outward rounding rules.

Expiry/validity decisions MUST apply the existing strict/inclusive bounds without
weakening them; uncertainty overlap denies permission. Expiry never releases claims
or proves stopped execution. Persist last_valid_utc as the qualified decision lower
bound under existing rules. No midpoint, stale sample or permissive OS-clock fallback.

Unavailable/unauthenticated time, backward monotonic movement, inconsistent UTC,
unbounded drift or arithmetic uncertainty MUST stop time-dependent authority and
retain RECOVERY_ONLY/STOP as applicable. Clock replacement needs separate approval;
it cannot reset deadlines or erase anomalies. Restart discards monotonic anchors,
requires a fresh qualified sample and comparison with durable time/history, and
does not automatically clear recorded uncertainty or recovery requirements.

## 8. Operator, opener and issuer/process boundary

Only the separately authorized genesis operator may execute the exact approved
ceremony. Only the approved host-bound service identity and qualified opener may
open for authoritative use. Normal reservation issuance/state advancement remains
the sole serialized issuer's role under existing authenticated requester/approval,
single-command permit, checkpoint, time and fencing gates.

The activation authority MUST enforce one current generation and at most one
in-flight command permit under existing rules. A hostname string, administrator
login, file handle, local ACTIVE flag or access to the same schema is insufficient.
No unapproved issuer/process replacement, shared writable clone, direct-SQL operator
path or new credential/authentication workflow is introduced. IL.8 continues to own
operator authentication and credential/interactive tooling implementation.

## 9. Exact initial state and genesis outcome

Preserve design section 5.1: zero reservations, zero blocking claims, zero commands,
zero approved operation artifacts and zero EVENTS rows. No operational permits exist
or are issued by genesis. Metadata singleton=1, schema_version=1, generation=1,
approved register/activation IDs and authority pins, recovery_required=0,
last_event_sequence=0, and last_event_digest equal
SHA256(ASCII `JOUS-FIXTURE-LEASE-GENESIS-V1`). Initial last_valid_utc and state_digest
MUST match the exact approved initial metadata/STATE projection.

The genesis record is the immutable package, creation evidence, protected checkpoint
and external activation outcome/history, not an invented GENESIS event or normal
COMMAND row. The existing sentinel is the initial event-chain anchor. No new event
enum, fake command, ACK or reservation is needed. Initial checkpoint revision and
event sequence are 0; its predecessor digest is 32 zero bytes, only for genesis.
The representation is selected by exact approved generation binding, never sniffing
or fallback. Synthetic vectors are not operational initial-state evidence.

Identity/schema/authority pins and the historical initial-state identity are immutable;
normal mutable head/time/state/recovery projections retain existing transition rules.
Local recovery_required=0 does not make a prepared register authoritative or ACTIVE.
During preparation/verification the service remains NON_AUTHORITATIVE/RECOVERY_ONLY.

## 10. Future ceremony and independent activation verification

These are constraints for later separately authorized execution, not instructions
to execute now. Preserve the existing ceremony order:

1. Under separate preparation authority, initialize the exact local register in
   NON_AUTHORITATIVE/RECOVERY_ONLY mode; validate exact schema and empty state.
2. Fix canonical genesis checkpoint/package and obtain independent exact-byte
   approval. Recheck all package, storage, actor, software and fresh time gates.
3. Retain the independently approved initial protected checkpoint as a non-activating
   genesis anchor. This sole pre-activation exception grants no normal command permit.
4. Submit the one stable genesis activation command to the external linearizable
   ABSENT-to-generation-one CAS with the exact approved package/checkpoint. ABSENT
   MUST be positively authenticated and consistent with protected generation history.
5. Read back the original outcome and current activation/checkpoint through their
   qualified authorities. Verify exact identities/bytes/hashes, host/storage binding,
   approval, generation, local state and absence of unresolved outcomes.
6. Obtain independent genesis-result verification binding the exact execution
   evidence and current authority. Only after this and all startup gates may the
   service derive AUTHORITATIVE REGISTER ACTIVE status.

The external CAS is the authority-establishment point. Its success is necessary,
not sufficient, for service ACTIVE eligibility. A committed CAS with verification
pending is fenced, not permission to operate. Genesis independent verification is
an additional operational gate, not a replacement authority or a second CAS.

## 11. Opening an existing register and restart

Normal open validates authority; it MUST NOT manufacture it. Open only the existing
approved physical instance without create flags or schema initialization. Before
authoritative service, independently validate:

- exact register/schema/version, metadata singleton and authority-document pins;
- original activation/package/approval identities and immutable generation binding;
- current protected activation, host/storage identity, permitted opener/writer,
  exclusive ownership/access boundary and current issuer generation;
- exact approved software/SQLite/connection/storage profile and permissions;
- integrity/foreign-key checks, canonical event chain, command/event consistency,
  complete blocking claims, state digest and protected checkpoint/current ancestry;
- original genesis result verification, recovery state and no unresolved permit,
  activation, local commit, checkpoint or completion outcome;
- fresh qualified time, durable time consistency and existing validity/fencing gates.

Missing, malformed, contradictory, unavailable, stale or unexpected evidence denies
authoritative operation. A storage-only successful open is not a qualified operational
open. Diagnostics, if separately permitted, MUST be labeled NON_OPERATIONAL and
cannot return executable lease authority or secrets/customer data.

Restart only reopens and validates already-established authority. It creates no
register, generation, reservation, permit, eligibility or replacement issuer; it
does not reacquire, extend expiry, free claims, clear recovery or clear uncertainty.
Exact resolved genesis may be recognized without re-execution. Unresolved history
requires IL.7 reconciliation; startup validation is not automatic recovery.

## 12. Failure and recovery boundary

| Condition | Required disposition; no automatic mutation retry |
| --- | --- |
| Register absent at normal open | Reject/STOP; never initialize |
| Invalid/unapproved package or uncertain ABSENT | No genesis effect; remain non-authoritative |
| Local preparation exists without protected checkpoint | NON_AUTHORITATIVE/RECOVERY_ONLY; preserve original evidence |
| Protected checkpoint exists without activation | Still non-authoritative; no command permits |
| Known CAS rejection/existing activation | Do not overwrite, adopt or create another identity |
| Genesis checkpoint or CAS response unknown | Retain stable original identity; fence; separately authorized read-only reconciliation only |
| CAS succeeded but process crashed/readback incomplete | Preserve external outcome; restart fenced; verify original outcome, no duplicate CAS |
| Exact completed original genesis proved | Verification only; no second initialization/publication |
| Local data lost, copied, restored, relocated or corrupted | STOP/RECOVERY_ONLY; separate IL.7 restore/replacement authority |
| Partially committed or contradictory local/external state | Retain strongest evidence; no rollback inference, compensation or fresh genesis |
| Clock/ownership/issuer/checkpoint uncertainty | Deny operations and retain recovery/STOP condition |

Uncertainty MUST NOT become absence, definite failure or success by inference.
Set/retain existing recovery_required only through already-authorized durable
mechanisms when safely possible; otherwise stop intake and preserve external
evidence. A failure to persist a recovery flag is not permission to serve. No new
recovery schema, repair mechanism or authority-clearing shortcut is proposed.
IL.7 owns uncertain-genesis/history reconciliation, restore, missing-successor and
approved resumption. This contract supplies boundaries, not IL.7 implementation.

## 13. Fixture provisioning and Increment G separation

Successful IL6 genesis establishes ONLY the authoritative register. It does not
approve/adopt the bootstrap amendment or provisioning contract, acquire
FIXTURE_PROVISIONING exclusivity, generate fixture identities, write the eight
fixture records, access Supabase, generate a final manifest, authorize CANARY,
deploy or activate runtime. Each requires its later independent gate and exact
operation authorization. An active empty register is not an eligible fixture set.

Under the previously completed independent historical runtime adjudication supplied
to this contract as an external prior adjudication premise, the conclusions were:

- NO_HISTORICAL_OPERATIONAL_F_PUBLICATION_EXISTS
- NO_ORIGINAL_PERMIT_COMPLETION_OPERATION_CURRENTLY_ELIGIBLE
- NO_RUNTIME_EFFECT_REQUIRED_OR_AUTHORIZED

No committed exact adjudication artifact establishing those historical conclusions
has been identified in current repository authority. IL6 does not independently
establish or re-prove those historical negative facts. These are provenance-qualified
external historical premises for this contract, not facts independently derived
from current-main repository evidence. Source/certification/Git publication is not
operational F evidence.
Genesis MUST NOT manufacture, reconstruct or retroactively create it, synthesize
a permit/publication/completion, or call Increment G because a register now exists.
Future genuine normal operations remain subject to unchanged IL.5 A–G gates.

## 14. Authority lifecycle and forbidden shortcuts

The conceptual lifecycle is:

DOCUMENTED -> INDEPENDENTLY APPROVED -> IMPLEMENTED -> CERTIFIED ->
ACTIVATION PACKAGE APPROVED -> GENESIS AUTHORIZED -> GENESIS EXECUTED ->
GENESIS INDEPENDENTLY VERIFIED -> AUTHORITATIVE REGISTER ACTIVE.

Each arrow requires distinct retained evidence and separately scoped authorization
where action is involved. This candidate is DOCUMENTED only. Implementation requires
its own authorization after contract adoption; certification is not execution
approval. Repository commitment/publication advances none of the operational gates
by itself. Later gates cannot retroactively approve an earlier unauthorized effect.

Reject implicit creation, schema-means-authority, arbitrary SQLite authority,
copied-register authority, duplicate genesis, unapproved relocation/issuer/clock
replacement, restart-created authority, automatic recovery, uncertain-genesis retry,
fixture reservation during genesis, managed-database access during genesis and
runtime/canary activation during genesis. No availability-driven fallback exists.

## 15. Future design/review obligations and exclusions

Before minimal implementation can be approved, independently resolve the closed
package encoding/vectors and conformance to the frozen genesis checkpoint reference
amendment, protected activation/checkpoint capability interfaces and their outcome
proofs. Operational execution additionally requires actual host/storage/clock/trust
selection and qualification, authority adoption evidence, exact package, bounded
executor and independent result-verification method. None is selected or approved
by this draft. If these cannot be represented without changing frozen semantics,
STOP for separate authority review; do not silently extend IL.5 or its codec.

Future review MUST test duplicate/concurrent genesis (one winner), missing-file
normal open, copied/relocated files, forged metadata, wrong host/generation/package,
clock uncertainty/restart, checkpoint/CAS loss and crash boundaries. Such a test
plan is not authorization to execute tests or operational fault injection now.

Out of scope: implementation, migrations, SQLite/database creation or opening,
Supabase/managed access, credentials, fixture identities/provisioning, eight fixture
INSERTs, reservation acquisition, final fixture manifest, CANARY, deployment, public
traffic, runtime activation, IL.7 recovery implementation and economic-routing or
product work. No existing authority document, application/infrastructure code or
test is changed by this candidate. No register or operational authority is created.
