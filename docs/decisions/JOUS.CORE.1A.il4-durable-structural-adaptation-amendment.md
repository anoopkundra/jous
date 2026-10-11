# JOUS.CORE.1A IL.4B durable structural adaptation amendment

Status: DRAFT CANDIDATE. Unapproved, untracked, unstaged and uncommitted. Independent authority review and publication are required. This document authorizes no implementation or operation.

## 1. Narrow purpose and controlling references

This amendment proposes a NEW narrow specialization closing ADAPT-01: adaptation between the full IL.1 structural value and the already-published durable reservation representation. The specialization did not previously exist. IL4B-01 remains HIGH and OPEN; this draft does not approve the current IL.4B implementation candidate.

The drafting baseline is commit `b3ed2e73628276467f966e85a9f350a3ac1c47ac`. Controlling references are:

| Source | Controlling subjects |
| --- | --- |
| [JOUS.CORE.1A.fixture-lease-implementation-design.md](JOUS.CORE.1A.fixture-lease-implementation-design.md), blob `706b6bf782701a602012bd1fed75099f519a53ee` | Sections 3-4: durable domains and transactions; section 8: exact identity/key encoding; sections 9-10: replay and transitions; section 12: invariants. |
| [JOUS.CORE.1A.il4-command-event-state-protocol-amendment.md](JOUS.CORE.1A.il4-command-event-state-protocol-amendment.md), blob `9549831ac43bb9a723a28f082ee97781b6321468` | Section 2: opaque projections and canonical primitives; sections 3-4: COMMAND identity and evidence references; sections 6-8: ACK, retained completion and STATE projection. |
| [JOUS.CORE.1A.il4-acquisition-revision-amendment.md](JOUS.CORE.1A.il4-acquisition-revision-amendment.md), blob `8980f5f016dd59465fa5d4465902f026d6040cb0` | Sections 3-6: expected_revision, absent-target creation, existing-target mutation and replay/failure separation. |
| [JOUS.CORE.1A.runtime-canary-fixture-provisioning-bootstrap-amendment.md](JOUS.CORE.1A.runtime-canary-fixture-provisioning-bootstrap-amendment.md) | Sections 2-4: typed bindings, immutable provisioning identities and generated-subject phases; sections 6-7: overlap claims, expiry and recovery. |
| [fixture_lease_contract.py](../../services/api/infrastructure/fixture_lease_contract.py), frozen blob `8eeaecac68dc1ea2997ea340b0c43743da8d834c` | `ArtifactBytes`, `Binding`, `ReservationValue`, `canonical_conflict_set`, `phase_advance_allowed`, `claims_remain_blocking` and `structurally_permitted_transition`. This exact predicate is the structural operation matrix preserved below. |
| [JOUS.CORE.1A.il4-large-value-framing-reconciliation.md](JOUS.CORE.1A.il4-large-value-framing-reconciliation.md), blob `28fe3e268589459c89ce80a0c59790b5ed46086e` | Generation-bound STATE representation and STATE-2 streaming grammar remain unchanged. |
| [JOUS.CORE.1A.replacement-generation-cutover-amendment.md](JOUS.CORE.1A.replacement-generation-cutover-amendment.md), blob `6068c9c92504d7f8651da4286a7ee3f9c4440ef9` | Generation identity, replacement and activation authority remain unchanged. |

The frozen full model carries an ordered tuple of eight explicit database UUIDs. The durable IL.3/IL.4 row retains immutable database projection bytes and SHA256, without a published universal decoder to that tuple. Direct reconstruction of `ReservationValue` would require missing identity material. This amendment defines a durable entry representation without reconstructing it.

## 2. Non-goals and security boundary

Durable structural validation SHALL be NECESSARY but NOT SUFFICIENT for operational authorization. Passing it SHALL NOT establish authentication, approval, permit validity, trusted-time validity, lease eligibility, provenance completeness, external checkpoint success or runtime activation authority. Those facts remain subject to their separately published gates and increments.

This amendment SHALL NOT redefine the eight database identities, remove them from `ReservationValue`, weaken UUID distinctness, authorize synthetic/sentinel UUIDs, define an opaque-projection decoder, infer UUIDs from claims, evidence-reference position, artifact IDs or hashes, or change provisioning authority. It SHALL NOT alter approval/provenance requirements, authentication/authorization, permit or trusted-time authority, lifecycle eligibility or operational ACK delivery.

It SHALL NOT change schema, STATE-2, COMMAND/EVENT/ACK framing, digest algorithms, representation selection or published vectors. It SHALL NOT authorize runtime activation, SQLite register creation/use, checkpoint publication, activation CAS, replacement ceremony, managed database access or STRIX.

## 3. Entry A: full structural value

The existing `ReservationValue` SHALL remain a valid full structural entry. Every existing constructor requirement SHALL remain unchanged: exact typed identifiers, binding and lease status; bounded deadlines with expires_at greater than completion_deadline; bounded revision; exactly eight distinct UUID objects in exact tuple order; bounded nonempty immutable projection bytes; valid canonical conflict keys; and claims present exactly when the status remains blocking.

For an existing-reservation transition, this entry SHALL require exact before/after equality of reservation_id, fixture_set_id, owner, expires_at, completion_deadline, the ordered database_ids tuple AND immutable_database_projection bytes, as the frozen predicate requires. Projection equality SHALL NOT replace UUID tuple equality. The full entry SHALL retain all existing rejection behavior and public structural results.

## 4. Entry B: durable structural projection

The new conceptual durable structural projection SHALL contain the following typed facts available from durable storage. It defines validation inputs, not a new serialized or persisted object.

| Structural fact | Durable source and validation |
| --- | --- |
| reservation_id, fixture_set_id, owner | Exact retained reservation fields; existing identifier validation applies. |
| register_id | Exact reservation/register context; the adapter SHALL enforce the existing register/command binding before invoking the shared rule. |
| binding | Exact operation_type and phase plus a validated typed artifact resolved under section 6. Retained binding_kind, binding_artifact_id and binding_sha256 SHALL also be checked. |
| status | Exact typed lease_status. |
| expires_at, completion_deadline | Exact immutable retained deadlines; existing bounds and expires_at greater than completion_deadline apply. |
| revision | Exact bounded unsigned retained revision. No bool/float coercion is permitted. |
| immutable_database_projection | Exact immutable_db_projection bytes, with existing nonempty stored-value capacity bound. |
| immutable_database_projection_sha256 | Exact immutable_db_projection_hash, independently verified under section 5. |
| claims | Complete owned set of full canonical conflict keys, read and proposed under section 7. |

The entry SHALL validate its types, domains, binding and claims before invoking the shared rule. It SHALL preserve the full model's claims/status shape: non-RELEASED status requires a nonempty blocking set; RELEASED requires an empty set. Claim canonicalization SHALL use existing conflict decoding and canonical full-key identity. Malformed or duplicate durable keys SHALL reject rather than be silently omitted.

No invented database UUID field SHALL exist in this projection. Other existing durable command/reservation constraints, including immutable acquisition facts and execution/evidence field consistency, SHALL remain enforced at their existing protocol/store boundaries; this projection SHALL NOT relax them.

## 5. Exact opaque-projection preservation; no reconstruction

The durable entry SHALL independently verify, for BOTH before and after:

`retained_projection_hash == SHA256(exact_retained_projection_bytes)`.

It SHALL then require exact before/after projection BYTES equality. Hash equality alone SHALL NOT suffice. A changed byte string SHALL reject even when supplied hashes compare equal. A matching byte string with either incorrect retained hash SHALL reject.

This proves only preservation of the exact retained durable identity/value projection. It SHALL NOT assert eight-identity completeness, UUID role mapping, identity provenance, approval, authorization or external eligibility. UUID identities remain necessary at their existing full/external authority boundaries; they are not irrelevant. Raw UUID identities are absent at this durable boundary, so this entry performs no UUID comparison.

The durable adapter SHALL NOT construct a `ReservationValue` merely to invoke validation. It SHALL NOT synthesize UUIDs, use dummy/sentinel UUIDs, decode the opaque projection without separately published encoding authority, derive the tuple from current claims/evidence order/artifact IDs/hashes, or bypass constructor validation.

## 6. Typed binding and evidence resolution

For each before/after binding, the adapter SHALL resolve the retained binding_artifact_id against the exact referenced `APPROVED_ARTIFACTS` record inside the writer transaction. Absence or inconsistent retained material SHALL reject. It SHALL validate exact artifact identity, published artifact type, exact artifact bytes, SHA256(bytes), the retained artifact hash and the reservation's binding hash/type. Existing retained approval-record integrity checks and command reference checks SHALL remain required; their structural use SHALL NOT confer external approval authority.

The adapter SHALL form the existing typed `ArtifactBytes` from the verified exact bytes/type and the existing `Binding` from operation, phase and that artifact. Binding constructor constraints remain controlling. Artifact ID alone SHALL NOT assign binding semantics; missing bytes SHALL NOT be invented.

Full binding equality in the shared rule SHALL mean existing `Binding` equality: operation, phase, artifact type and exact artifact bytes. Durable artifact/reference identity consistency remains an additional adapter/COMMAND requirement and SHALL NOT be replaced by this equality.

RELEASE/RECOVER structural evidence SHALL be the existing typed `ArtifactBytes` resolved from the exact explicit primary evidence reference and its retained record. The adapter SHALL verify identity/type/hash/bytes and required reference membership as published. Evidence ordering SHALL NOT select the semantic primary. Typed evidence shape SHALL NOT establish release/recovery eligibility.

## 7. Authoritative claim set and proposed effects

BEFORE claims SHALL be the complete owned canonical blocking-claim set read from the same active writer transaction as the reservation. A caller-supplied before set SHALL NOT substitute for it. Comparison SHALL use full canonical conflict-key bytes, never partial keys or hash-only identities.

AFTER claims SHALL be the exact proposed result of the checked typed inserts/deletes applied to that before set. Each deletion SHALL identify an existing exact owned row; each insertion SHALL have exact target ownership, valid canonical key and the existing required row facts. Duplicate/conflicting effects, absent deletion targets, inconsistent ownership and replacement of retained claim facts through nominally unchanged keys SHALL reject. Existing full-key uniqueness and storage constraints remain controlling. No effect SHALL be silently ignored.

The adapter SHALL enforce claim effects, not only final set equality: RECORD_EXECUTION and QUARANTINE SHALL have no claim inserts/deletes; ADVANCE SHALL have no deletes and only additions allowed by the shared rule; RELEASE/RECOVER SHALL remove the exact complete owned set and insert none. No delete/reinsert maneuver SHALL evade those constraints.

ACQUIRE SHALL remain a separate absent-target creation path under M-04; it SHALL NOT replace an existing reservation or be admitted by the existing-reservation transition predicate. Existing structural creation shape and claim validity SHALL still apply without asserting external claim completeness.

## 8. Exactly one shared structural operation rule

There SHALL be exactly ONE underlying implementation of structural operation-transition rules. Both the existing full-value entry and the new durable entry SHALL delegate to it after their representation-specific identity/integrity checks. Copied, parallel or divergent state machines SHALL NOT exist.

The shared rule SHALL preserve the frozen predicate's behavior for operation, before/after status, phase, binding, revision, claims and typed release/recovery evidence. Representation-specific checks SHALL remain outside that operation rule: full entry preserves explicit UUID tuple and projection equality; durable entry preserves verified exact projection bytes and durable reference/context consistency. Both SHALL preserve reservation/set/owner/deadline identity and invoke the same matrix below.

For every existing-reservation transition, after.revision SHALL equal before.revision + 1 within the applicable entry's existing bounded integer domain. Overflow SHALL reject. A RELEASED predecessor SHALL reject every new transition. Before/after binding operation SHALL remain equal. For every command except ADVANCE, full typed binding SHALL remain unchanged.

The following matrix reproduces the frozen predicate exactly; it supplies no external eligibility gates. Status names are exact enum values. PRE_AUTH denotes the existing API name whose wire value is `PRE_AUTH_PROVISIONING_REQUEST`.

| Command | Before status | After status | Phase / binding | Claim-set relation | Typed evidence shape |
| --- | --- | --- | --- | --- | --- |
| ADVANCE | LEASED | LEASED | FIXTURE_PROVISIONING only; PRE_AUTH to AUTH_IDENTITIES_BOUND via existing phase_advance_allowed. Both bindings valid; operation preserved. The frozen predicate does not add an artifact-inequality requirement. Existing command prior/new binding checks remain required. | Every old key retained; every added key decodes as ISSUER_SUBJECT. No deletes. | No new structural evidence requirement introduced. |
| RECORD_EXECUTION | LEASED | LEASED | Full binding unchanged. | Exact set unchanged; no effects. | No new structural evidence requirement introduced; published command evidence applicability remains required. |
| QUARANTINE | Any non-RELEASED status: LEASED, EXPIRED or QUARANTINED | QUARANTINED | Full binding unchanged. | Exact set unchanged; no effects. | No new structural evidence requirement introduced; published command evidence applicability remains required. |
| RELEASE | Non-RELEASED and not QUARANTINED: LEASED or EXPIRED | RELEASED | Full binding unchanged. | Empty after set; exact complete owned-set deletion, no insertion. | Existing ArtifactBytes of RELEASE_EVIDENCE type. |
| RECOVER | QUARANTINED | RELEASED | Full binding unchanged. | Empty after set; exact complete owned-set deletion, no insertion. | Existing ArtifactBytes of RECOVERY_EVIDENCE type. |
| ACQUIRE against an existing reservation | Any | Any | Rejected by the shared existing-reservation rule. | Not an existing-reservation replacement path. | Separate creation rules apply only to absence. |

Unlisted commands, invalid enum/type/domain values and any matrix violation SHALL reject. QUARANTINE's structural allowance SHALL NOT establish lifecycle eligibility. EXPIRED status in the full enum SHALL NOT authorize an EXPIRED-only committed state contrary to published protocol F-03. Necessary structural shape and operational eligibility remain distinct.

## 9. Writer snapshot, validation order and rejection

The durable BEFORE reservation, complete owned claims, referenced retained artifacts, register context and all other durable structural inputs SHALL come from the SAME active writer transaction used for completion. The adapter SHALL NOT compose them from unrelated/stale snapshots or accept a caller's BEFORE assertion.

For a new command, target/revision admission SHALL precede structural validation, and successful structural validation SHALL precede all reservation/claim/event/command/metadata transition writes. AFTER SHALL describe the exact proposed reservation and claim result assembled from authoritative BEFORE plus checked supplied typed effects. The effects SHALL agree with canonical COMMAND identity and existing protocol/contract constraints. No fabricated identity material SHALL enter AFTER.

A failed structural check SHALL reject with no reservation or claim mutation, no revision change, no EVENT, no successful or diagnostic COMMAND persistence, no ACK, no metadata/event-head change and no STATE-digest change. Validation SHALL NOT use partial writes followed by rollback as its ordinary admission mechanism. Ordinary structural rejection SHALL NOT poison a healthy handle. Existing rollback-only statement failure, COMMIT/rollback uncertainty, poisoning and no-retry storage rules remain unchanged.

## 10. Revision, creation and historical replay

M-04 remains unchanged: ACQUIRE/CREATE requires expected_revision = 0 and target absence; successful creation establishes revision 0. Existing-target mutation requires exact durable expected_revision and advances exactly once, n to n+1. No UPSERT, adoption or state-dependent command-kind reinterpretation is authorized.

Existing command_id lookup and retained-completion integrity verification SHALL occur before new-transition admission. Exact historical replay SHALL return the retained successful outcome and exact retained ACK bytes without new structural admission against current reservation state. Later valid transitions SHALL NOT invalidate exact replay solely because the current phase/status/revision differs. Replay, mismatch and confirmed rejection SHALL create no transition or revision increment. Diagnostic REPLAY_MISMATCH/STORAGE_UNKNOWN SHALL NOT enter completed STATE history or fabricate ACKs.

## 11. Later acceptance consequences and IL4B-01 gate

The later implementation SHALL reject the independently reproduced cases with every no-write guarantee in section 9:

1. Ordinary RELEASE from QUARANTINED to RELEASED; RECOVER is the required structural path.
2. RECORD_EXECUTION adding a blocking claim; deletion also violates its unchanged-set/no-effect rule.
3. ADVANCE retaining PRE_AUTH_PROVISIONING_REQUEST and the same binding while merely incrementing revision; the required phase advance is absent.

These examples SHALL NOT replace class-level enforcement. Later tests SHALL cover permitted and forbidden adjacent matrix cases, exact full-value UUID tuple preservation, exact durable projection bytes/hash checks, retained artifact inconsistencies, authoritative claim ownership/effects, revision bounds, ordinary rejection handle usability and historical replay after later valid transitions. Shared-rule tests SHALL demonstrate equivalent operation decisions for corresponding valid full/durable structural facts without inventing UUIDs in the durable path.

IL4B-01 SHALL remain OPEN until all five gates complete: independent review of this amendment; publication/freeze of this amendment; separate bounded implementation-remediation authorization; proof that invalid structural transitions reject; and independent implementation re-review. This document does not itself approve or remediate the current candidate.

## 12. Compatibility and separately authorized implementation consequence

No schema migration or change to REGISTER_METADATA, APPROVED_ARTIFACTS, RESERVATIONS, BLOCKING_CLAIMS, COMMANDS or EVENTS is authorized. No table, column, index, trigger, existing durable-row rewrite or operational SQLite migration is authorized.

STATE-2 bytes, COMMAND bytes, EVENT bytes, ACK bytes, all digest algorithms, generation-scoped representation selection and every published vector SHALL remain unchanged. No STATE-1 codec, fallback, size-selected representation, replacement-package encoding or operational generation selection is introduced.

The expected later implementation shape is one shared pure structural-rule implementation; existing ReservationValue entry delegates after full-value checks; new durable entry delegates after durable projection integrity checks; command core invokes durable entry inside its writer transaction and validates claim effects before writes. This requires a SEPARATELY AUTHORIZED modification to the currently frozen contract implementation. That future change SHALL preserve existing public full-value behavior and unchanged regression tests. This draft authorizes no such edit and no widening of the current IL.4B candidate scope.

## 13. Narrow precedence and current-state disclaimer

Upon independent adoption, this amendment SHALL specialize ONLY the adaptation between full ReservationValue validation and the published durable representation. It SHALL control over an earlier assumption that a durable row can be directly reconstructed as ReservationValue. It SHALL NOT override explicit full-value UUID requirements or supersede unrelated provisioning, protocol, lifecycle, recovery, checkpoint or security authority.

No implementation remediation has occurred because of this document. The current IL.4B store, command-core and test candidates remain byte-identical to their pre-draft identities. No schema or published code/authority has changed. No file has been staged or committed; no push or fetch has occurred. No operational SQLite/register has been opened or created, no managed database has been accessed, no fixture lease has been issued, no checkpoint has been published, no activation CAS or replacement ceremony has occurred, and no runtime has been activated. Runtime remains NOT ACTIVATED. STRIX has not been run.
