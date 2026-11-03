# JOUS.CORE.1A IL6 authoritative register implementation contract

Status: OFFLINE IMPLEMENTATION CONTRACT CANDIDATE FOR INDEPENDENT REVIEW —
NOT APPROVED FOR IMPLEMENTATION — NOT OPERATIONALLY ADOPTED.
Creation or publication of this document does not authorize implementation,
genesis, activation, managed access, provisioning, CANARY, runtime activation or
public traffic. Every future effect described below requires its own later gate.

## 1. Locked sources and precedence

Derivation baseline: HEAD/local origin/main
`174a0871552761dddc2cd0a7f83ac74e4c549712`, divergence 0/0, clean tracked
worktree/index. Historical baselines inside source documents remain historical.

Paths in this table are relative to `docs/decisions/`. SHA256 values identify
COMMITTED BLOB BYTES, not a checkout's possible CRLF conversion. Hash approved
operational artifacts as their exact approved bytes; never normalize after approval.

| Controlling source | Exact Git blob | Committed-byte SHA256 |
| --- | --- | --- |
| JOUS.CORE.1A.il6-authoritative-register-activation-contract.md, frozen commit 174a0871552761dddc2cd0a7f83ac74e4c549712 | ede5e09bf4bdb8461ac92d27da5ec9cb5683f21b | d687f86997b371ceebe3c84b504e1a7582b4a2cade4b657c7625c18844eff429 |
| JOUS.CORE.1A.genesis-checkpoint-reference-amendment.md | d5136bc32ea8f62c04d09e65121edc00c0387d35 | 2787bb6fed551f29b756a7fa915feea5d1b509f133f380427366f3c10786574f |
| JOUS.CORE.1A.runtime-canary-fixture-provisioning-bootstrap-amendment.md | b2af73ae4788e76f4fd591ac267d40230d70026b | eb6fe7d8ae02daa4c409c166b2bbc2d9b0940017f418676bb7ee3836aaec3cf6 |
| JOUS.CORE.1A.runtime-canary-fixture-provisioning-contract.md | 1d84df662ab0e7245f59842039789a55c1df25c4 | a36b527fe2c6d9fa16b4debf9e4fb9fea3c2a725611a457569ec96a5d220dab8 |

Serialization-binding remediation baseline: HEAD/local origin/main
`b1cedc4f0250d40bb4b05f4aff290fa0a662ffb7`, divergence 0/0. The additional
controlling normative authority is
`docs/decisions/JOUS.CORE.1A.il6-authority-serialization-profile.md`, frozen commit
`b1cedc4f0250d40bb4b05f4aff290fa0a662ffb7`, blob
`63dbed6ae575797da27d6a4ee3be03bb184256c3`, SHA256
`244af712477959ba0d2c4a6d106829ab8a31a3ae82d9247ecd85b620d349a875`,
46,184 bytes / 535 LF lines. Its approval/freeze token is
`CORE1A_IL6_AUTHORITY_SERIALIZATION_PROFILE_PUBLISHED_INDEPENDENTLY_VERIFIED_AND_GIT_FROZEN`.
This frozen upstream authority resolves the former IL6-IMPL-REVIEW-01 normative
serialization gap; it does not approve this implementation contract or grant
implementation or operational authority. Fresh full-contract review remains required.

Provisioning design-authority adoption is supplied by
`CORE1A_FIXTURE_PROVISIONING_BOOTSTRAP_AND_CONTRACT_INDEPENDENTLY_APPROVED_FOR_DESIGN_AUTHORITY_ADOPTION`.
Design adoption is not operational adoption or execution authority. The frozen IL6
and genesis-reference authorities control all semantics; this contract maps them
to bounded code and certification work. Existing fixture-lease implementation
design, IL.4 framing/projection, normal IL.5 and replacement authorities remain
controlling in their scopes. Conflict requires STOP, never precedence by convenience.

## 2. Objective and seven separate boundaries

Implement the minimum CODE CAPABILITY for authoritative register identity,
schema/version, generation/activation, authority pins, storage/clock/actor binding,
exclusive issuer ownership, initial digest/recovery state, explicit genesis,
existing-register validation and fail-closed operation. Implementing these checks
does not establish an actual authoritative operational register.

Keep separate: (A) code implementation; (B) offline implementation certification;
(C) concrete activation-package construction; (D) independent package approval and
explicit execution authorization; (E) one actual genesis invocation; (F) independent
result/readback verification; (G) later fixture-provisioning authorization.
Completion of A/B never implies D/E/F/G. Synthetic tests exercise code paths with
fake authorities and disposable storage; they are not operational genesis attempts.

## 3. Inspected existing store and safe reuse

`services/api/infrastructure/fixture_lease_store.py` supplies SCHEMA_SQL, TABLE_SQL,
SPECS, typed rows, exact schema/profile/integrity checks and storage transactions.
LeaseStore resolves an absolute existing path strictly, requires a file, and opens
SQLite with `mode=rw`, isolation_level=None, timeout=0. It neither creates parents
nor initializes schema. It performs no migration or repair and its handle explicitly
does not prove issuer authority. Preserve this implementation byte-for-byte.

Reuse its schema/row definitions and existing-only handle. Dedicated creation may
use the exact frozen SCHEMA_SQL only inside the new explicit capability on an
exclusively created disposable/staging file, never through LeaseStore's constructor.
No caller SQL, mutable schema text, schema inference, INSERT OR REPLACE or UPSERT.
Reuse exact existing validators where callable; do not expose the private connection
or weaken a validator merely to share it. Any necessary storage API modification
requires scope review before work, not an opportunistic refactor.

Reuse `fixture_lease_protocol.py` primitives, StateContext/StateProjection and
canonical STATE hashing; reuse `fixture_lease_service.py` EvidenceReference,
activation/time values and conservative time predicates. Those values are claims,
not authentication. The current STATE implementation supports STATE-2 only: honor
an exactly approved compatible binding, otherwise reject unsupported representation;
never select or operationally adopt it by default. Do not add a STATE codec.

`fixture_lease_checkpoints.py` is NORMAL_COMMAND-only: its positive revision/event
requirements and tag-18 bundle exclude genesis. Do not modify or trick it with
fake COMMAND/permit values. The new module may construct/validate the already
authorized genesis profile using existing frame/ID/U/H/T primitives and the frozen
genesis amendment, without changing normal codecs. Commands, acquisition, admission,
retention, qualification, publication and completion remain unchanged.

`tests/test_fixture_lease_store.py` creates synthetic databases explicitly and
tests missing-file/parent noncreation. Such fixture helpers are not production
initializers and must not be imported as production infrastructure.

## 4. Smallest proposed exact implementation file set

| Production path under services/api/infrastructure/ | Classification | Necessity |
| --- | --- | --- |
| fixture_lease_activation.py | NEW_REQUIRED | One bounded module for typed activation inputs, pure binding validation/genesis profile, dedicated preparation/genesis and qualified existing-open orchestration; deny-by-default dependencies |
| fixture_lease_store.py | NO_CHANGE | Reuse schema and existing-only storage; preserve frozen constructor and transaction behavior |
| fixture_lease_contract.py | NO_CHANGE | Existing operation/binding predicates; no new command/type |
| fixture_lease_protocol.py | NO_CHANGE | Reuse canonical primitives/STATE; no protocol mutation |
| fixture_lease_service.py | NO_CHANGE | Reuse evidence/time values and predicates; dedicated genesis seams live in the new module |
| fixture_lease_checkpoints.py | NO_CHANGE | Normal codec stays isolated |
| All other fixture_lease_*.py and application/runtime files | NO_CHANGE | Frozen behavior is outside IL6 implementation scope |

| Test path | Classification | Necessity |
| --- | --- | --- |
| tests/test_fixture_lease_activation.py | NEW_REQUIRED | Offline typed-input, pure-vector, disposable physical-creation, fault, exact-open and negative-authority certification |
| tests/test_fixture_lease_store.py | NO_CHANGE | Existing-only/profile/storage regression authority |
| tests/test_fixture_lease_service.py | NO_CHANGE | Evidence/clock/default rejection regressions |
| tests/test_fixture_lease_protocol.py | NO_CHANGE | Canonical STATE/protocol regressions |
| tests/test_fixture_lease_checkpoints.py | NO_CHANGE | Normal-profile isolation regressions |
| All other existing tests | NO_CHANGE | Execute required regression population later; no maintenance edits under this contract |

No EXISTING_MODIFY path is proposed. Two new implementation/test files only; no CLI,
web endpoint, public API, UI, startup/deployment hook, new package dependency,
provider service, second authority store or reusable generic integrity framework.
File-set insufficiency is a stop condition, not permission to widen it.

## 5. Minimum callable surface and dependency composition

Names below identify proposed typed responsibilities, not implemented functions:

| Callable | Inputs / result | Effect boundary |
| --- | --- | --- |
| validate_genesis_package | Immutable package/evidence snapshot plus separately qualified bindings -> validated fixed snapshot or finite rejection | Pure; no resolution I/O or physical creation |
| prepare_register | Closed preparation inputs, separately approved preparation authority, qualified ABSENT/storage/clock/exclusion capabilities -> prepared NON_AUTHORITATIVE receipt or structured failure | Explicit local staging initialization only; no protected publication/CAS |
| execute_genesis | Exact prepared receipt, complete approved package plus Q, exact execution authorization and qualified capabilities -> structured reached-state evidence | Publish exact prepared storage and approved checkpoint; one original ABSENT CAS; never returns operational fixture permission |
| open_authoritative_register | Existing binding/package/result-verification evidence plus qualified current authority/clock/storage/owner capabilities -> validated scoped handle or fenced rejection | Existing-only open/read qualification; no genesis, repair, migration, checkpoint publication or CAS |

Genesis is a distinct explicit capability. Import, object/dataclass construction,
LeaseStore construction and normal application startup MUST perform zero genesis
effects. No environment flag, path absence or ordinary open can select genesis.
Capabilities are composed explicitly; omitted/unqualified ones reject before an
effect. Constructors do not authenticate supplied claims. Capture/validate exact
inputs before callbacks; callbacks must not mutate the accepted package/evidence.

The new module defines only narrow genesis-specific storage, approval-resolution,
protected-checkpoint and activation-CAS seams absent from existing normal interfaces.
They return exact bound structured evidence, never generic success booleans. No
concrete production network/trust provider, credentials or external authority
implementation is selected. Existing authority remains external; no SQLite file
or local JSON sidecar becomes its replacement. Default seams reject without I/O.

Results report actual reached milestones and uncertainty, preserving original
causes and strongest safely reached evidence. Exceptions after effects MUST NOT
escape as apparent pre-effect rejection or invite automatic retry. No result may
claim fixture/lease/canary/runtime permission. An evaluator-local one-attempt guard
prevents duplicate dispatch, while durable uniqueness remains the external
authority's existing stable-command/history responsibility, not process memory.

## 6. Exact typed input boundary

Use closed immutable records, explicit field types and exact nested records; no
arbitrary dictionary/options bag. IDs use existing ID bounds; SHA256 is exactly
32 bytes; UTC is existing signed microseconds; generation/schema integers use
existing domains; booleans reject integer/string coercion. Exact bytes are immutable
bytes. All references bind an ID plus hash and resolve to retained exact bytes.

| Record / binding | Required typed contents |
| --- | --- |
| RegisterBinding | register_id; schema_version=1 and exact schema identity/hash; issuer_generation=1; activation_id; purpose GENESIS / marker GENESIS_V1; predecessor_generation=0; approved environment/project scope |
| AuthorityBindings | Exact identities/bytes/hashes and applicable adoption evidence for all IL6 section 5 authorities; four existing metadata pins separately mapped to their existing fields; no new metadata column |
| StorageBinding | Canonical absolute final database, staging and journal/directory locations; physical volume/host/storage identity; account/permissions/exclusion evidence; exact runtime/VFS/durability qualification refs |
| ActorBinding | Genesis/preparation operator and authorization refs; independent approver ID; normal issuer/service identity/generation; qualified opener identity; exclusive writer/process/host binding and fencing evidence |
| ClockBinding | Exact clock profile/source/qualification refs, QualifiedClockProfile, fixed qualified creation sample/UTC and supported process/monotonic domain; fresh execution/open qualification separately supplied |
| InitialProjection | Exact MetadataRow values, selected StateContext/authority, complete initial STATE bytes/hash; all five non-metadata table populations empty; recovery_required=false; genesis event anchor/head |
| CreationBinding C | Separate retained exact creation/preparation evidence bytes/ref and qualification, consistent with actual separately authorized staging preparation; never future Q/hash |
| CeremonyBinding E/G | Exact E bytes/ref, content-addressed G ID/digest and all frozen amendment section 3 bindings; stable K and J; no downstream checkpoint/package/Q/payload hash in E |
| CheckpointBinding C0 | Complete exact genesis CHECKPOINT bytes/hash/ref, fixed UTC, G and present approval ID J; no normal N bundle |
| Package P | Closed exact package bytes/ref/hash and all required bindings above, protected-authority identities/absence/history/readback requirements, software/profile and evidence-retention requirements; stable K, authorization validity and J |
| Approval Q (separate input) | Complete exact independent approval bytes/ref/hash resolving J, verified package/C0/host/identity/validity binding and independence; not a field or hash dependency of P |
| Execution context (separate input) | Exact execution authorization, qualified current ABSENT/history/storage/clock/owner evidence, prepared receipt and one-attempt context; downstream activation payload only after Q |
| Result verification (open only) | Independently verified original genesis/readback evidence and current protected activation/checkpoint/recovery evidence; no self-issued verification |

The record closure MUST cover EVERY frozen IL6 section 5 package requirement,
including software/build/profile, scope, authority adoption, initial state and
retention. Missing/extra/duplicate/malformed/contradictory fields reject, as do
unresolved identities and differing bytes under a matching ID/digest. Explicit
inapplicability needs approved justification under IL6; no silent optional scope.
No operational register IDs, paths, principals, providers or clocks are chosen here.

The records above describe implementation responsibilities and qualified inputs,
not alternative wire schemas. Their exact canonical fields/grouping and opaque
evidence boundaries are controlled by the frozen serialization profile. In
particular C and Q remain OPAQUE_EXTERNAL_EVIDENCE: validate authenticated exact
references/digests and the profile's closed qualified views, never locally
reserialize external records to establish their identities.

## 7. Frozen serialization authority and certification conformance

The former deferred-encoding HOLD was IL6-IMPL-REVIEW-01. It is resolved upstream
by the exact frozen serialization profile pinned in section 1, not by an
implementation-specific serializer or future vector design. This contract MUST
consume that authority and MUST NOT define, reinterpret, extend or replace it.

All construction/validation of NEW_CANONICAL_OBJECTS E, P and the activation-command
payload, and derivation/validation of G, MUST follow that profile exactly. Its
field closure/order/types, encoding, exact-byte preimages/hashes, domain separation,
normalization, null/absence, versioning and rejection rules are controlling. Fail
closed on profile/version/serialization mismatch; do not silently normalize or
accept alternate bytes the profile rejects. OPAQUE_EXTERNAL_EVIDENCE, including
Q, C and every other class identified there, remains opaque under its exact
authenticated reference/digest/qualified-view contract.

The profile's deterministic vectors are CERTIFICATION_ONLY: reproduce them and
prove implementation conformance without treating them as runtime authority or
defining new semantics through additional vectors. Existing STATE encoding remains
under its existing frozen authority; existing genesis CHECKPOINT framing,
serialization and cryptography remain under their existing frozen authority and
genesis specialization. No new encoding decision for these objects is delegated
to the implementation Builder.

Remaining IMPLEMENTATION_DETAIL includes native file/exclusion/flush primitives
that satisfy frozen requirements; ACTIVATION_PACKAGE_DETAIL includes exact concrete
package instances and evidence bindings; OPERATIONAL_SELECTION includes separately
approved actual storage, clock, actors/processes, access/protection mechanisms and
their qualification. None is selected by this remediation or converted into a new
normative constant. Synthetic certification does not qualify those real selections.

Do not add or reinterpret a frozen protocol object, field, enum or framing rule.
An external package serialization is not permission to modify COMMAND, EVENT,
APPROVAL, STATE or CHECKPOINT. Preserve full exact-byte hashes and unknown-field
rejection; never rely on Python repr/pickle, ambient JSON settings or mutable URLs.

## 8. Genesis reference, approval and downstream activation payload

Conform exactly to the frozen genesis-reference amendment, especially sections
2–7. G is `genesis-ceremony:sha256:<64 lowercase hex SHA256(E)>`; its existing
checkpoint position contains the ID using existing outer length framing. Approval
position contains present Optional ID J, not Q's digest or a nested reference.
Creation C, ceremony E/G, checkpoint C0, package P, pending approval ID J, final
approval Q and stable activation command K remain distinct. No fake normal COMMAND,
CommandPermit, admission bundle, tag-18 reuse or normal permit completion.

Implement pure genesis-profile construction/validation using existing primitives:
eleven CHECKPOINT fields, version 1/tag 7, generation 1, revision/event sequence 0,
published genesis event digest, approved initial STATE digest/fixed UTC, zero
checkpoint predecessor, G ID and present J. Hash the COMPLETE checkpoint. Normal
checkpoint codec behavior remains unchanged and must continue rejecting genesis.

P binds K but contains no activation-command payload bytes/hash, Q/hash, outcome
or self-digest. E contains no downstream G/hash, checkpoint/hash, P/hash, Q/hash,
activation payload hash/outcome. Validate exclusions before effect eligibility.
Only AFTER independently qualified Q may code construct the exact activation
payload binding authenticated expected ABSENT, predecessor_generation 0,
register/generation/activation/host, K, approved P identity/hash, complete C0
identity/hash and Q ref/hash. Hash its exact complete bytes. Neither payload nor
payload hash feeds back into P or its hash. Same K/different payload rejects.

Preparation/encoding and final package approval are separate lifecycle phases.
No code may fake Q to prepare E/C0 or claim creation evidence exists before the
separately authorized facts it records. Retained exact preparation evidence is
upstream; later publication/CAS receipts are downstream and never edits to C/E/P.

## 9. Qualified ABSENT and phased physical preparation

Local file absence is NOT authoritative ABSENT. Require positive qualified external
absence/history/tombstone evidence, approved host/storage identity, exclusive
preparation ownership and complete preparation authority before any local preparation.
Existing activation, inaccessible target, unknown storage, unresolved prior K,
in-progress/uncertain genesis or unavailable absence proof rejects. No check/create
race may be treated as a win. No overwrite, repair, takeover, blind retry or new K.

Preserve the frozen ceremony's separate local preparation then exact package review
then protected publication/CAS. `prepare_register` may initialize only a specifically
authorized NON_AUTHORITATIVE staging instance on the approved filesystem; it must
not publish the final operational pathname or grant authority. The receipt binds
that same physical instance, initial bytes/state, C and approved final location.
This is preparation of one register, not a second authority store or operational
register. Preparation itself requires separate explicit authorization; approval of
this implementation contract does not authorize even that physical operation.

`execute_genesis` consumes that exact prepared receipt and complete independently
approved P/Q; it cannot opportunistically create/adopt a different existing file.
The final target MUST be absent and absence/exclusion freshly qualified. A prepared
staging instance is usable only through its original receipt and exact approved
package; arbitrary existing staging/target files reject. Restart does not resume
preparation or publish it automatically. Reconciliation of uncertain prior work is
IL.7-owned, not a second attempt through either callable.

## 10. Physical creation, atomic publication and crash boundary

The dedicated local capability must implement/qualify these bounded steps:

1. Validate absolute final/staging/journal/parent paths, no symlink/reparse or parent
   substitution, approved physical volume/local filesystem, access/ownership and
   required flush/locking profile. Parent directory must already exist and be
   independently approved; never mkdir as a convenience.
2. Acquire exclusive process/storage ownership through qualified native primitives
   and recheck physical identity/absence under that boundary. A pathname-only check
   or SQLite busy lock is insufficient. Unsupported guarantees reject before creation.
3. Exclusively create the approved staging file without following redirection or
   replacing existing data. Bind its native file identity to the receipt and later
   final location. Initialize ONLY frozen schema plus the one exact metadata row;
   commit under the frozen SQLite profile. No operation tables gain rows.
4. Validate schema/profile/integrity/FKs, exact initial rows and canonical STATE;
   close SQLite cleanly, account for its journal, flush file and parent-directory
   metadata under the qualified platform/VFS model, and read back exact identities.
   Fsync/FlushFileBuffers return alone is not a hardware durability proof.
5. After exact P/Q and execution gates, publish the SAME prepared file to the
   approved final location using qualified atomic NO-REPLACE publication on that
   filesystem. Generic rename/replace with overwrite semantics is forbidden. Bind
   native identity across the operation; race/existing target rejects.
6. Flush required directory/rename metadata, read back final identity, ownership,
   schema/rows/STATE and durability evidence. Only then may the separately authorized
   exact protected checkpoint publication and ABSENT CAS proceed in frozen order.

No production platform/path is chosen. The implementation must identify and test
the exact native no-replace/exclusion/flush primitives it supports; platforms lacking
required guarantees reject, with no weaker fallback. Do not hold a SQLite writer
transaction across external checkpoint/CAS I/O. Native ownership must remain valid
through physical publication and use; check-before-use without identity continuity
does not qualify storage.

Incomplete schema, commit/close/flush/readback failure, crash before/after rename,
unknown rename outcome or contradictory identities leaves NON_AUTHORITATIVE /
RECOVERY_ONLY or STOP with strongest evidence retained. Do not delete remnants,
reinitialize, retry rename, create another file, infer rollback, or acquire a fresh
identity to escape uncertainty. No new persistent local attempt journal is added;
existing external exact evidence/original operation history remains authoritative.

## 11. Initial schema mapping

Initialize exactly one REGISTER_METADATA row: singleton=1, schema_version=1,
approved register_id/generation=1/activation_id, the four existing authority pins,
last_event_sequence=0, last_event_digest=SHA256(ASCII
`JOUS-FIXTURE-LEASE-GENESIS-V1`), approved fixed last_valid_utc, recovery_required=0
and state_digest of the exact canonical initial STATE. Derive STATE through existing
projection exclusions, never by inserting its own digest into its preimage.

APPROVED_ARTIFACTS, RESERVATIONS, BLOCKING_CLAIMS, COMMANDS and EVENTS are empty.
No operational permits exist. Genesis evidence is externally retained C/E/P/Q,
protected C0 and activation history; no GENESIS event, fake ACK, normal COMMAND,
lease/provisioning/CANARY history or new metadata field. Immutable identities/pins
stay immutable; future normal head/time/recovery transitions retain existing rules.
Stored recovery_required=0 is necessary initial data, not proof of authority.

## 12. Existing-register authoritative open

The new qualified opener wraps the existing-only LeaseStore; it is not a new
initializer. Before any authoritative handle is returned, validate exact package,
independent genesis-result verification, current external activation/checkpoint,
register/schema/generation/activation/authority pins, host/storage/native identity,
clock profile/fresh qualification, opener/issuer/exclusion and software/profile.
Run existing schema/integrity/FK checks and existing canonical state/event/command/
claim coherence against the qualified current protected head. At genesis require
exact empty projection; after legitimate operations validate current history, not
an impossible requirement that current state stay equal to the initial digest.

Recovery_required, unresolved permit/publication/CAS/completion, copied/restored
storage, stale/contradictory current authority or insufficient history denies
authoritative open. No authority from embedded flags or an integrity-only open.
On rejection close owned resources without clearing evidence or claiming an
uncertain close succeeded. No repair, migration, new checkpoint or CAS on open.

Restart always starts fenced; it validates already-established authority only.
No persisted monotonic anchor reuse, reservation reacquisition, recovery clearing,
new generation or implicit resumption. Exact original success may be recognized
read-only; unresolved history requires separate IL.7 authority. A validated handle
does not bypass per-command normal permits, independent approvals or delivery gates.

## 13. Three exclusion layers and trusted time

OS/process exclusion protects the physical instance and access boundary; register
ownership binds the approved host/service/generation/current external activation;
normal operation exclusivity remains the frozen atomic typed reservation/claim
and single-flight permit protocol. Each layer must be independently established.
SQLite locking alone cannot authenticate a host, stop copied registers, establish
protected ABSENT or fence an unauthorized issuer. No deployment credential is added.

Reuse QualifiedClockProfile, QualifiedSample, UtcInterval, MonotonicPoint and
qualified propagation-error semantics through a narrow injected qualification seam.
No hard-coded production source or OS-wall-clock fallback. Reject wrong profile,
stale sample, backward/unrelated monotonic domain, excessive error, uncertain UTC
ordering or expired authorization under frozen strict/inclusive rules. Fixed
creation/C0 bytes do not change when execution time is requalified. Restart requires
fresh qualified evidence and durable-time comparison; a plausible reading does
not clear anomalies/recovery. Tests use deterministic synthetic profiles/clocks.

## 14. Recovery and provisioning isolation

Valid initial metadata has recovery_required=false, while service mode remains
fenced until protected activation and independent verification gates. Partial or
uncertain preparation/genesis must preserve reached evidence and prevent serving.
Persist an existing recovery condition only where already authorized and safe;
otherwise STOP without inventing a recovery write or falsely claiming safety.
No automatic recovery, uncertain retry, reset, replacement or takeover. IL.7 owns
uncertain-genesis/history reconciliation, restore and approved resumption.

Preserve existing Operation/Phase/ArtifactType distinctions: FIXTURE_PROVISIONING
binds provisioning_request_sha256; CANARY binds fixture_manifest_sha256. No automatic
conversion, manifest fabrication or bypass through an active empty register. No
provisioning/canary executor, real UUID/user/row generation or managed connector.
Preserve frozen IL6's provenance-qualified external historical Increment G premises;
do not claim repository-derived proof or manufacture historical F/permit evidence.

## 15. Offline focused certification contract

Future tests must operate only on symbolic inputs, deterministic fake protected
authorities and explicitly authorized disposable local storage outside the checkout.
No genuine authority registration, production credentials, managed database or
Supabase. Instrument every capability/effect; exact call identity/cardinality and
reached-state evidence matter, not only final booleans. Physical tests exercise the
same creation path with synthetic identities; mocks alone do not prove OS durability.

| ID | Mandatory case / required proof |
| --- | --- |
| A | Valid synthetic preparation/genesis: independent vectors, exact schema/metadata/STATE/C0/P/Q and original K; correct phase order; one attempt; no operation permission |
| B | Existing final/staging target: reject without overwrite/adoption or external publication/CAS |
| C | Uncertain/inaccessible target or absence proof: no initialization/publication/CAS |
| D | Missing/extra/duplicate/incomplete package fields: reject before effect |
| E | Any authority-pin/hash/adoption mismatch: reject; no alternate authority |
| F | G prefix/digest/E or C mismatch: reject before protected publication |
| G | C0/P/J/Q binding, pending/colliding J, self-approval or validity mismatch: reject |
| H | Payload constructed only after Q; binds approved P/Q/C0/K; forbidden payload/Q/self-hash fields in P/E reject; reproduce frozen serialization-profile vectors as certification-only evidence and verify the frozen acyclic preimages |
| I | Schema/version/build/profile mismatch: reject with no migration |
| J | Register_id mismatch: reject |
| K | Generation not exactly approved/initial 1: reject |
| L | Activation_id mismatch: reject |
| M | Wrong/unavailable/stale/uncertain clock profile/domain: fail closed; no fallback |
| N | Storage/parent/native identity mismatch, symlink/reparse or unsupported volume: reject |
| O | Exclusive owner/process/issuer mismatch, simultaneous preparation or CAS race: no dual winner; losing attempt never adopts winner |
| P | recovery_required or unresolved external/local outcome: fenced rejection; no flag clearing |
| Q | Initial EVENTS empty and correct genesis anchor/zero head |
| R | Initial COMMANDS/reservations/claims/artifacts empty; zero normal permit/provisioning/canary history or effects |
| S | Inject faults/crashes at create/schema/commit/close/flush/rename/checkpoint/CAS boundaries; preserve strongest known result, original IDs, fencing and no retry |
| T | Readback identity/content/digest/authority mismatch: no ACTIVE claim; no repair |
| U | Missing-file normal LeaseStore/qualified open creates neither database nor directories |
| V | Import, constructors and existing startup paths invoke zero genesis/create/publication/CAS capabilities |
| W | Restart creates no authority, reservation, eligibility or monotonic continuity; original success recognition needs qualified evidence |
| X | Unknown publication/CAS/creation followed by repeat/restart: no new K/G, duplicate anchor, second CAS, takeover or fallback |
| Y | Existing fixture-lease codecs, store semantics, typed provisioning/CANARY bindings and IL.5 A–G remain unchanged |

Add negative assertions across cases: zero managed network/credential access,
no normal-open initialization, no auto repair/migration, no operational permissions,
fixture-provisioning/CANARY/runtime/public-traffic authority, no registry creation
outside the synthetic harness and no entry through a CLI/web/startup/deployment hook.
Unexpected callback exceptions/interruption after each effect must retain structured
outcome evidence; raw failure must not be misreported as definite nonoccurrence.

## 16. Certification sequence and exact population evidence

After independent implementation review, run focused IL6 tests first, then the
relevant existing frozen fixture-lease regression population. The baseline has
19 fixture-lease test modules: test_fixture_lease_contract, protocol, service,
store, commands, checkpoints, outcomes, publication_gate, predecessor_resolution,
permit_gate, permit_acquisition, admission_envelope, admission_retention,
admission_qualification, candidate_preparation, candidate_retention,
publication_qualification, publication and completion (all under tests/, .py).
Retain each exact module identity and collect a deterministic node manifest before
later execution under certification authority. Do not substitute historical counts
or repeat the earlier G split-run recovery policy automatically.

Existing subsystem discipline includes complete focused and frozen regression
certification, exact identities and independent result review. No inspected source
establishes that those 19 modules equal the full repository suite. The fresh
certification plan MUST explicitly resolve any additional historically mandatory
repository-wide suite from preserved authority; if required, run it only after
focused/frozen checks and explicit scope approval. Missing authority is HOLD, not
an assertion that a full-repository gate passed or may be skipped. Do not run or
discover tests in this authoring task.

Future certification records collected/run/unique/duplicate/missing/extra counts,
per-node starts/results/durations, exact executed-set comparison, failure tracebacks,
exit codes, wall time and peak memory where available. No failure repair/retry is
part of certification. Stop at the authorized gate on failure; preserve evidence.
Exact execution authority and any long-run partition policy require separate review.
Offline tests cannot certify a production clock/provider or hardware flush behavior;
those remain concrete activation-package qualification, never claimed from fakes.

## 17. Artifact/evidence and Builder stop conditions

Report exact changed production/test file set; before/after Git blobs, committed
and worktree SHA256 distinguished, bytes/LF/CR where relevant; exact patch; dependency
and codec conformance; focused/regression manifests/counts/outcomes; no managed
access/runtime effects/operational genesis; synthetic storage paths and disposal
evidence; frozen authority/baseline and unrelated-artifact preservation. Keep durable
certification evidence outside the checkout; do not edit historical evidence.

The Builder MUST STOP for separate authority if work requires changing frozen IL6,
genesis-reference or adopted provisioning semantics, existing schema/codec/IL.5,
the exact file set, creating a second authority store, weakening fail-closed rules,
implicit genesis, retry/takeover after uncertainty, a repair/recovery protocol,
production storage/identity/clock/credentials selection, managed access or actual
genesis. No authority may be inferred from implementation, tests or Git publication.
Serialization/profile/version nonconformance under section 7 blocks implementation
progression; it is not permission to invent replacement encoding authority.

## 18. Out of scope and ordered future gates

Excluded: actual authoritative-register genesis, activation-package approval,
operational storage selection, production operator/clock selection, Supabase or
managed access, credential acquisition, fixture provisioning, real fixture UUIDs,
eight provisioning INSERTs, final manifest generation, CANARY, deployment, runtime
activation, public traffic, economic-routing/product changes and IL.7 recovery
implementation. No such action occurred or is authorized by this candidate.

Required future gates remain distinct and ordered:

1. Implementation-contract independent full review, including conformance to the
   frozen serialization profile, before implementation permission is issued.
2. Exact contract staging/publication, only if separately authorized.
3. Implementation Builder under exact separate scope and synthetic-storage authority.
4. Implementation independent review.
5. Focused certification.
6. Regression certification under independently approved exact scope.
7. Exact implementation staging.
8. Staged-index review.
9. Local commit.
10. Commit-object review.
11. Guarded publication.
12. Independent Git freeze.
13. Concrete activation-package construction, with any physical preparation separately
    authorized and remaining NON_AUTHORITATIVE under the frozen lifecycle.
14. Independent activation-package review.
15. Explicit genesis authorization.
16. Exactly one genesis attempt under the original fixed identities and package.
17. Independent result/readback verification and all frozen ACTIVE eligibility gates.
18. Only then consider a separately authorized fixture-provisioning package.
