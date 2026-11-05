# JOUS.CORE.1A Operational Authority-Provider Integration Contract

## 1. Status and authority

OFFLINE NORMATIVE CANDIDATE — NOT OPERATIONALLY ADOPTED.

Independent normative review is required. Creation, approval or publication of this
document grants no implementation authority, operational qualification, credential
authority, managed-access authority, preparation authority, register-creation
authority, genesis authority, activation authority, fixture-provisioning authority,
CANARY authority or runtime/public-traffic authority. MUST and MUST NOT describe
requirements for future separately authorized integration, not permission to act.

## 2. Purpose

Close I-1 (qualification/approval adapter), I-2 (protected publication, ABSENT CAS
and authoritative readback), and I-3 (external raw-evidence retention/resolution).
These are expected dependencies outside frozen IL6, not IL6 defects. The supplied
reconciliation disposition is
CORE1A_POST_IL6_OPERATIONAL_AUTHORITY_READINESS_RECONCILED_NEXT_GATE_IDENTIFIED,
NEXT_GATE_CLASS B. This document consumes that disposition without inventing a
repository artifact establishing it.

## 3. Frozen inputs

Baseline HEAD and local origin/main: 078aef0860214b6649c2da70916cf55d21a21cf1.
Decision filenames below are under docs/decisions/ with prefix JOUS.CORE.1A.

| File suffix | Frozen Git blob |
| --- | --- |
| il6-authoritative-register-activation-contract.md | ede5e09bf4bdb8461ac92d27da5ec9cb5683f21b |
| il6-authority-serialization-profile.md | 63dbed6ae575797da27d6a4ee3be03bb184256c3 |
| il6-authoritative-register-implementation-contract.md | 92f591b26d2e0b37c34448bc724a4ed4988f6fea |
| genesis-checkpoint-reference-amendment.md | d5136bc32ea8f62c04d09e65121edc00c0387d35 |
| runtime-canary-fixture-provisioning-bootstrap-amendment.md | b2af73ae4788e76f4fd591ac267d40230d70026b |
| runtime-canary-fixture-provisioning-contract.md | 1d84df662ab0e7245f59842039789a55c1df25c4 |

Frozen services/api/infrastructure/fixture_lease_activation.py blob:
f221f3242ac71ef147a195619a8f98541a6243f1.
Frozen tests/test_fixture_lease_activation.py blob:
c3c739808cf2295b9350094f781467fa79f8804a.

These authorities control their respective semantics. Conflict requires STOP and
independent adjudication. Preserve STATE/CHECKPOINT bytes and cryptography,
E/P/payload schemas, hash domains, G/J/K meanings, evidence classifications,
activation state machine, sequencing and original-attempt rules. No new protocol
object, field, event, COMMAND or permit is introduced. Provider governance records
below are opaque external evidence under the frozen profile, not new canonical
IL6 objects or a new serialization system.

## 4. Non-goals

No code, test, schema, migration, dependency, configuration, startup/deployment hook
or provider implementation is authorized here. No credential is accessed. No
preparation, register creation, genesis, protected effect, CAS, managed access,
provisioning, CANARY, runtime or traffic is authorized. No IL.7 recovery design.
LeaseStore remains existing-only with no initialization, repair or migration.

## 5. Trust-provider roles

| Logical role | Required responsibility | Trust separation |
| --- | --- | --- |
| Qualification/approval | Authenticate evidence and supply complete frozen typed views | Executor cannot self-approve through constructor/configuration |
| Protected authority | Protect C0, linearize ABSENT CAS, retain original history and authoritative observations | Caller cannot forge confirmations or erase history |
| Retention/resolution | Preserve raw bytes and resolve immutable authenticated references | Caller cannot replace/delete required evidence |
| Independent result verifier | Independently establish all result obligations | Separate decision authority from preparation operator, requester/issuer and effect executor |

Distinguish logical role, concrete realization, operator identity, credential
identity, logical authority identity and evidence issuer identity. Process or OS
access is not protocol authority. Shared infrastructure is permitted only with
independently qualified principal/rights/audit separation preventing self-approval,
forged verification or history rewriting. Collocation defeating independence rejects.

## 6. Authority/evidence sequence

Separately authorized qualified preparation -> actual creation evidence C -> exact
initial STATE S0 -> E and derived G using fixed K/J -> complete genesis C0 -> exact
P -> independent Q -> downstream activation payload -> separately authorized
physical publication -> protected NON-ACTIVATING C0 publication -> authenticated
ABSENT activation CAS -> authoritative readback -> independent result verification
-> all ACTIVE eligibility checks -> separately authorized provisioning lifecycle.

C is opaque; E/P/payload use the frozen serializer; G derives from E. K is stable
activation-command identity; J is pending stable approval identity, not an advance
Q digest. P excludes Q/hash and activation payload/hash. No downstream effect or
receipt may be hidden in upstream evidence. Qualification checks transitive
dependency-stage restrictions. No self-hashing or downstream-to-upstream cycle.

## 7. Qualification and approval

Default is REJECT. Each adapter MUST authenticate immutable context before returning
a qualified view: register/schema/generation/activation, K/J, scope, host/storage,
actors, software/build, representation, authority/adoption hashes and clock profile.
Validate exact scalar types/domains before comparison: bool cannot satisfy integer
generation, time, sequence or native identity. No coercion.

Package qualification consumes exact PackageSnapshot bytes and resolves every
opaque E/P role in frozen order. Return QualifiedPackageBindings with complete
PackageClaims, exact schema bytes, qualified clock/sample, raw OpaqueEvidence and
authenticated provenance. Authenticate actual creation, host/access/storage,
scope/governance, actors/actions, adoption, generation selection, software/VFS,
protected trust scope, linearizable CAS, history/tombstones/original outcomes,
requirements/applicability and upstream authorization. Hash equality is not authority.

Preparation qualification binds exact PreparationRequest, approved operator,
process/issuer, storage, current absence/history, authorization and validity.
Creation qualification binds actual native identity, STATE/database digest, fixed
creation time and authorized preparation. C MUST NOT be manufactured from expected
bytes or before actual authorized preparation.

Execution qualification binds complete ExecutionRequest, fresh qualified clock,
current storage/actor/exclusion, authorization, AUTHORITATIVE_ABSENT and
ORIGINAL_UNATTEMPTED_K. Requalify at each frozen executor boundary; no cached
eligibility across an effect.

Q remains opaque. Authenticate raw Q/reference/hash and supply ApprovalView binding
exact P/C0/register/generation/activation/host/K/J, requester/issuer, approver,
independence, authority/authorization, current non-revocation and validity observation.
Issuance time/provenance is authenticated external evidence, not a new IL6 field.
Verify frozen approver independence, including preparation-operator separation.
Supersession or revocation affecting applicability rejects. Unknown status rejects.

Opening returns QualifiedOpen with current activation/checkpoint/state/event
digests/sequence, history, storage/actor/verifier proofs and fresh_time. Q MUST be
valid at qualified fresh opening time and every read requalification, not only
request time. Current package authorization and metadata time bounds still apply.
Unavailable, stale, malformed, incomplete, unresolved or mismatched evidence MUST
NOT yield a qualified view. Local configuration and constructor success suffice
for neither authentication nor qualification.

## 8. Protected checkpoint publication

Accept exact snapshot, qualified Q and separate execution authorization. Authenticate
provider/actor/rights and exact register/generation/activation/C0/P/Q/K/host and
original operation binding before entry. Context not present in positional arguments
must resolve from already-qualified immutable bindings, never ambient defaults.

Protect exact C0 against alteration/deletion and durably retain original history
and raw authenticated acceptance evidence before CONFIRMED. CheckpointResult binds
operation, checkpoint, package, approval, host and evidence exactly. Publication
MUST NOT activate. A network ACK or local SQLite commit is insufficient.
Explicit failure needs authenticated nonoccurrence/rejection proof. Timeout,
disconnect, partial response or unknown acceptance is UNKNOWN. Requalify fresh
time/absence/exclusion before CAS; no second checkpoint anchor fills a receipt gap.

## 9. Activation CAS

Accept exact downstream payload bytes, confirmed publication, qualified absence
history and authorization. Recheck authenticated actor/provider, current applicability
and P/Q/K/C0/host binding at admission. Expected state is AUTHORITATIVE_ABSENT,
predecessor generation 0; target is exact generation-one register/activation.
Absence covers authoritative history/tombstones/original outcomes. Inaccessible or
missing observation is UNKNOWN, not ABSENT.

The provider MUST linearize expected-state comparison, original-operation admission
and protected transition in the qualified namespace. Durable history prevents
concurrent/later duplicate entry; SQLite locking or local GenesisAttempt is not
the security boundary. Conflict, already-active or unexpected state rejects this
original CAS; matching names do not establish success. Confirmation requires an
authenticated receipt for the exact original operation.

Return ActivationResult only for authenticated CONFIRMED outcomes binding K,
payload SHA256, P/C0/Q, register/generation/activation/host and evidence. Transport
failure/timeout/incomplete proof after possible entry is UNKNOWN. No blind retry,
takeover, new K/activation or second original attempt. CAS success remains result
verification pending and supplies no operational permission.

## 10. Authoritative readback and independent verification

Read from the qualified protected authority for the same namespace, with authenticated
source/issuer and exact operation/register/generation/activation/P/Q/C0/K/payload.
Require linearizable observation after the confirmed effect, or separately
qualified proof of that ordering and current protected state. Cache/eventual-only
observations cannot qualify. Retain raw response, authenticated observation time,
ordering and digest before returning a qualified ActivationResult. Echoing request
values is not readback.

Mismatch/staleness/unavailability fences the lifecycle without rollback inference.
Independent verifier resolves C/S0/E/G/C0/P/Q, execution authorization,
publication/CAS/readback, original history and authentication/durability proofs.
It records an opaque independent decision establishing every frozen obligation;
provider self-confirmation cannot substitute. Opening requires raw
INDEPENDENT_RESULT_VERIFICATION plus current qualification. A
READBACK_CONFIRMED_VERIFICATION_PENDING result is not ACTIVE eligibility.

## 11. UNKNOWN and uncertainty

Physical publication, protected publication, CAS and evidence/history persistence
may be uncertain. Qualification/readback/retention failure may leave prior effects
unresolved. UNKNOWN establishes neither success nor failure. Preserve original
identity, exact inputs and all available dispatch/request/response/error/time
evidence; quarantine the lifecycle. Do not release/reuse authority, delete remnants,
retry, choose a fresh identity or infer rollback from client silence.

Only complete authenticated proof of pre-entry rejection establishes non-dispatch;
that fact does not authorize another attempt. Uncertain history persistence stops
dispatch. Resolution requires separately approved authoritative observation/recovery
under IL.7 ownership, never automatic adapter repair.

Frozen seam translation: only authenticated confirmation returns existing CONFIRMED
typed results. Nonconfirmation raises ActivationRejected or preserves provider
failure as an exception, never a fabricated result/new enum. The executor retains
its strongest Reached/recovery_only boundary. Even later definite rejection does
not reset an entered effect boundary or attempt guard. External opaque evidence
retains finer outcome distinctions without changing frozen protocol objects.

## 12. Original-attempt uniqueness

Bind stable K, register, generation, activation and operation role in the existing
qualified namespace. Publication operation ID maps immutably to that context and
exact bytes; identity reuse with different content rejects. Provider operation
allocation/history is authenticated opaque evidence, not a new IL6 encoded identity.

Durably distinguish unentered, entered, confirmed, proven rejected and unresolved
outcomes. Record entry before or atomically with possible effect; uncertain entry
persistence stops dispatch. This is external provider history, not a second
authoritative register or new local journal. GenesisAttempt is only a local guard.
No automatic idempotent resubmission is authorized. Read-only resolution of an
existing receipt is not a new effect. Restart/death, new process/session/credential
or host never resets eligibility. Concurrent callers share durable fenced admission.

## 13. Evidence retention/resolution

For C/Q, qualification/storage/clock/actor/adoption, publication/result/readback
and verifier evidence, retain frozen ID syntax and SHA256 of COMPLETE raw bytes.
Resolve authenticated immutable ID/digest/role/issuer/context. Check raw hash and
issuer authorization before supplying OpaqueEvidence/typed claims. Never locally
reserialize opaque evidence to invent identity or meaning.

Retain raw bytes, issuer/issuance provenance, qualification, access/audit and
revocation/supersession observations. Same ID/hash must resolve same bytes; collision,
substitution/corruption/issuer mismatch is STOP. URLs are retrieval hints only.
Access control prevents executor replacement/deletion. Durability, redundancy,
crash behavior and retention meet frozen P requirements under independent
qualification. No deletion while required authority/review/unresolved history
depends on evidence. Unavailable required bytes/proofs fail qualification even
with cached claims. Revocation does not erase original bytes.

## 14. Authentication and credentials

Credential TYPES: host/service authentication; scoped protected publication/CAS/
readback; retention/resolution if separate; independent approver/verifier; accountable
operator. No VALUES. Separately approved secure injection/carrier must authenticate
peers/endpoints and protect confidentiality/integrity. Disabled verification rejects.

Least privilege applies per role/action/namespace. Executor cannot mint approvals,
rewrite history or impersonate verifier. No secrets in canonical objects, retained
audit payloads, logs, exceptions or shell history. References identify credentials
without values. Rotation preserves explicitly verified authority/issuer continuity;
changed trust identity requires independent requalification/adoption. Revocation
denies use; uncertain status rejects. Neither rotation nor revocation erases history.

## 15. Clock qualification

Use existing QualifiedClockProfile, QualifiedSample, MonotonicPoint,
QualifiedPropagationError, TimeBinding and evaluate_time semantics. Authenticated
wall-clock evidence supplies UTC intervals; monotonic measurement propagates elapsed
time only within qualified process/domain continuity. No OS clock fallback.

Profile/source/sample identity and uncertainty/skew/propagation/freshness limits
are immutable separately approved qualification inputs; no production limits are
selected here. Full intervals must satisfy applicable validity bounds; overlap is
not validity. Missing/stale sample/profile, backward time, changed process/domain
or unqualified error rejects. Restart requires qualified fresh startup evidence.

## 16. Storage/host qualification

Qualify exact host/build/process, parent/target native identity, canonical locations,
staging/final separation, ownership/access, exclusion and issuer fencing. Qualify
filesystem/VFS no-replace publication, locking, directory/flush barriers, power-loss
durability, readback and crash behavior on the actual platform. Unsupported primitives
reject without fallback. Evidence/journal/staging storage has qualified rights and
durability; no second register is created.

Preparation storage remains NON_AUTHORITATIVE; protected provider state/history
establishes activation authority. Identity continuity holds through use, not just
path precheck. Copies/relocation/host or issuer replacement/partial publication
cannot establish authority. Restart only reopens/validates, never repairs, migrates,
clears recovery or retries.

## 17. Provider selection/adoption

PROVIDER_REQUIREMENTS are this contract and frozen constraints.
PROVIDER_QUALIFICATION_EVIDENCE proves them for an exact realization.
PROVIDER_SELECTION_RECORD identifies proposed role/realization/scope/configuration
and authority bindings. PROVIDER_ADOPTION_RECORD is the independent authorized
acceptance with role/action/scope/validity. These are opaque authenticated governance
records, not new canonical objects, and none is created here.

API shape/vendor claims/tests do not adopt a provider. Concrete transport/signature/
key realization, endpoints, clock, storage and credentials must be explicitly fixed,
qualified and independently reviewed in realization records before operational use.
No dynamic trust fallback. These are operational selections, not implementation
discretion to choose authority semantics. Shared-role independence must be proven.

## 18. Existing adapter seam mapping

All activation names below are in fixture_lease_activation.py. Return exact frozen
dataclasses; constructors and reference strings do not authenticate themselves.

| Seam | Input authority -> output | Allowed effects; failure rule |
| --- | --- | --- |
| QualificationAdapter.package(snapshot) | Exact snapshot -> QualifiedPackageBindings/PackageClaims | Resolve/authenticate roles only; reject missing proof |
| .preparation(request) | Authorized request -> QualifiedPreparation | Current absence/storage/actor/history proof; no file creation |
| .creation(request, native_identity, state, database_sha256) | Actual authorized preparation -> QualifiedCreation/CreationClaims | Retain/authenticate actual C; uncertain retention stops |
| .execution(request) | Exact ExecutionRequest -> QualifiedExecution | Fresh time/absence/exclusion/history; no protected dispatch |
| .approval(accepted, approval, clock) | Exact qualified P/Q/time -> same ApprovalView | Authenticate opaque Q/current validity; no minting/reserialization |
| .opening(request) | OpenRequest -> QualifiedOpen | Current protected state/history/verifier and fresh_time; no CAS/initialization |
| ProtectedGenesis.publish_checkpoint(snapshot, approval, authorization) | Authorized exact C0/P/Q -> CheckpointResult | One original non-activating publication; uncertainty follows section 11 |
| .activate_absent(payload, publication, absence_history, authorization) | Exact downstream payload -> ActivationResult | One authenticated ABSENT CAS; conflict/unknown cannot confirm |
| .readback(result) | Exact original result -> authoritative ActivationResult | Observation only; no retry/new effect |

OpaqueEvidence and service.EvidenceReference carry raw/reference and proof bindings;
authentication/resolution is external. prepare_register, validate_genesis_package,
activation_payload, execute_genesis and open_authoritative_register remain unchanged.
AuthoritativeHandle.read_rows re-enters opening qualification on each read.
NativeStorage supplies local physical machinery, not authentication/durable history.

fixture_lease_service.py supplies existing evidence/time primitives and rejecting
defaults. Its normal CommandPermit, ProtectedCheckpoints and permit-based
OriginalOperation are not genesis authorization. fixture_lease_publication.py and
fixture_lease_publication_qualification.py provide normal publication/disposition
precedent only; do not route genesis through fake permits or reinterpret normal F.

## 19. Certification requirements

Separately authorized independent certification MUST cover:

1. Exact seam/dataclass conformance and default rejection.
2. Frozen serializer/domain and exact E/P/payload vector continuity.
3. Provider/peer/issuer/actor/credential/scope authentication rejection.
4. Incomplete/malformed/wrong-type/stale/expired/revoked/unavailable evidence.
5. Fresh opening/read Q validity, including request=0, expiry=1, fresh=2 rejection.
6. Timeout/disconnect/partial acceptance UNKNOWN at every effect boundary.
7. Durable duplicate/original exclusion under concurrency/crash/restart.
8. C0 publication non-activation and CAS conflict/already-active rejection.
9. Authoritative readback ordering/mismatch/staleness/unavailability.
10. Raw retention/resolution/hash/issuer/collision/corruption rejection.
11. Credential redaction, rotation continuity and revocation.
12. No automatic retry after uncertain entry or session/process reset.
13. Independent verifier separation and every ACTIVE eligibility requirement.
14. Existing-only open, preparation/genesis separation and no implicit effects.
15. Frozen compatibility population continuity under approved execution scope.

Use offline synthetic tests first. Report exact build/config/source identities,
node manifests, executed/unique/duplicate/missing counts, results/exit codes and
failure evidence. Historical focused 183 and compatibility 68/23/41/41/144 are
certified-byte history, not new execution claims. Later frozen fixture-lease
regression/full-suite scope follows the implementation contract's certification
discipline and separate authorization. Tests alone cannot qualify real trust roots,
credentials, hardware durability or linearizability. No operational probes implied.

## 20. Operational qualification package

A realization must supply exact provider/role, software/build/version, secret-free
configuration identity/hash, host/process, authority/evidence issuer, credential
identity/reference/rights/trust roots; storage/VFS/access/fencing qualification;
clock/authentication/retention qualification; durable original-history/uncertainty/
crash proofs; certification evidence/limitations; independent review/independence;
selection/adoption decision, validity/revocation and continuity conditions.
Fix all realization choices, resolution and retention obligations and exact scope.
Missing actual qualification is a gate failure, not new implementation discretion.
This document neither constructs nor approves that package.

## 21. Preparation/genesis boundary

Physical NON_AUTHORITATIVE preparation requires a separate explicitly approved
operation package and qualified host/storage/time/actor/history. No preparation
during authoring, review, implementation, implementation review or provider evaluation
without separate authorization. Implemented/certified/adopted providers do not
authorize genesis. Require concrete operational selections, external evidence,
separately approved actual preparation/C, exact S0/E/G/C0/P, independent Q and
explicit physical/protected publication/activation ceremony authority in frozen
sequence. Exactly one original attempt remains the limit.

## 22. Fixture/CANARY/runtime and historical boundary

Provider integration is only a prerequisite. FIXTURE_PROVISIONING/request hash/
exclusivity, fixture identities/eight records/manifest, CANARY/manifest binding,
RUNTIME_ACTIVATION and PUBLIC_TRAFFIC retain separate later gates. No Supabase access.

Under the externally supplied prior independent historical adjudication premise,
no historical operational F publication exists and no historical original permit
awaits completion. No committed exact adjudication artifact establishing those
negatives has been identified; this contract does not re-prove them from main.
No missing historical F search, retroactive F/G reconstruction or permit reacquisition
to satisfy historical G. No fabricated historical provenance or operational evidence.

## 23. Smallest future implementation boundary

| Path | Classification | Necessity |
| --- | --- | --- |
| services/api/infrastructure/fixture_lease_authority_providers.py | NEW_REQUIRED | One explicit composition module for qualification/protected seams and injected authenticated retention/verifier/provider clients |
| tests/test_fixture_lease_authority_providers.py | NEW_REQUIRED | Offline conformance/adverse/uncertainty/independence tests |
| services/api/infrastructure/fixture_lease_activation.py | NO_CHANGE | Existing typed seams suffice |
| tests/test_fixture_lease_activation.py | NO_CHANGE | Frozen certified tests |
| services/api/infrastructure/fixture_lease_service.py | NO_CHANGE | Reuse evidence/time primitives |
| services/api/infrastructure/fixture_lease_publication.py | NO_CHANGE | Preserve normal publication isolation |
| All other existing production/tests/docs/config/dependencies/migrations | NO_CHANGE | No supported change requirement |

No MODIFY_REQUIRED path is authorized. Private role adapters may share the proposed
module. Provider clients are explicitly injected and denied absent qualification;
they cannot decide new authority meaning. Realization-specific transport work must
be separately scoped against reviewed selection records; no extra SDK/file is
silently authorized. No endpoint/UI/CLI/startup/deployment hook. If required outcomes
cannot be represented by frozen seams, STOP; do not patch frozen IL6.
This candidate does not authorize creation of either proposed implementation file.

## 24. Failure/STOP conditions

STOP on frozen identity conflict, incompatible seam, need for new canonical object/
field/domain/STATE/CHECKPOINT change, ambiguous ordering, missing authentication/
qualification/retention/time/history, independence failure, UNKNOWN effect,
concurrent original claim, unexpected protected state, frozen-file modification,
unapproved operational selection or actual preparation/genesis/access requirement.
No fallback, evidence rewrite, alternate encoding, success synthesis, automatic
retry or recovery. IL.7 retains recovery ownership. Implementation discretion is
only helper decomposition/naming/organization/test helpers; not authority order,
evidence meaning, identity/trust, serialization, UNKNOWN/retry or permission.

## 25. Explicit authority exclusions

This candidate does not adopt providers, issue credentials/Q/authorization, create
preparation/C/STATE/checkpoint/package, publish protected C0, execute CAS, activate
a register, grant reservations/provisioning/CANARY/runtime or public traffic.
Git publication is distinct from operational adoption. No product/economic-routing work.

## 26. Future gate sequence — no step authorized here

Contract candidate -> independent normative review -> separately authorized exact
Git staging/index review/commit/object review/guarded publication/independent freeze
-> separately authorized implementation -> independent implementation certification
-> exact Git review/publication/freeze -> candidate provider realization/selection
-> operational qualification evidence -> independent provider/adoption review
-> operational authority package -> separately authorized NON_AUTHORITATIVE
preparation -> actual C and generation-one S0/E/G/C0/P construction -> independent Q
-> explicit physical/protected publication and activation ceremony authority
-> exactly one original authorized effect sequence -> authoritative readback and
independent result verification -> all ACTIVE eligibility checks -> only then
separately authorized fixture-provisioning lifecycle -> CANARY -> separate
runtime/public-traffic decision.
