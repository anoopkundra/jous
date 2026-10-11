# JOUS.CORE.1A IL.4 COMMAND / EVENT / ACK / STATE protocol amendment

Status: documentation authority candidate, unapproved and uncommitted. Independent review and adoption are required. This document defines protocol authority only and authorizes no execution.

## 1. Authority and scope

This is a narrow additive clarification of the published fixture-lease implementation design at `docs/decisions/JOUS.CORE.1A.fixture-lease-implementation-design.md`, blob `706b6bf782701a602012bd1fed75099f519a53ee`. Existing authority remains controlling except for the enumerated IL.4 protocol ambiguities resolved here. Published baseline: `8a71511bfcb42272f2497c05599b56c58d2312c0`. Published STATE framing authority is `JOUS.CORE.1A.il4-large-value-framing-reconciliation.md`, blob `28fe3e268589459c89ce80a0c59790b5ed46086e`; replacement authority is `JOUS.CORE.1A.replacement-generation-cutover-amendment.md`, blob `6068c9c92504d7f8651da4286a7ee3f9c4440ef9`. Both control this draft.

M-01 is resolved by the nonrecursive EVENT payload and single prior-digest field below. M-02 is resolved by the exhaustive ACK schema and complete event interval. M-03 is resolved by the exhaustive COMMAND schema, parameters, replay identity and STATE projection. M-04 remains governed without reinterpretation by `JOUS.CORE.1A.il4-acquisition-revision-amendment.md`, blob `8980f5f016dd59465fa5d4465902f026d6040cb0`.

No new command, operation, lifecycle or conflict family is introduced. Maintenance/retirement command execution remains disabled until its separately approved authority exists, as required by the controlling design.

## 2. Canonical primitives and limits

F(version, tag, fields) is ASCII `JOUS-FIXTURE-LEASE`, followed by one version byte, one domain-tag byte, uint32 big-endian field count, then for each schema-ordered field a uint32 big-endian byte length followed by those exact bytes. No padding or trailing bytes. Field count must exactly match the schema; no unknown or duplicate named fields, implicit omissions or alternate encodings.

All non-STATE frames below use published version 1, its exact uint32 big-endian framing and 65,535-byte maximum for EACH field, including a field containing a nested frame. An eligible 65,535-byte field accepts; 65,536 rejects. Complete COMMAND size is not substituted for that per-field rule. No truncation or alternate encoding. A nested encoded object placed in a v1 field must itself fit that field; this does not narrow retained artifact BLOB capacity because commands reference exact separately retained evidence.

Version-1 tags used here: 5 COMMAND; 6 EVENT; 10 ACK; 16 parameter record; 17 reference record. The schema closures for these auxiliary tags do not change v1 primitive meanings. Tags 12-15 below identify projected records ONLY under selected STATE-2 authority. Domain separation is INSIDE each canonical frame; SHA256(exact canonical object bytes) is the only hash formula. No extra prefix or duplicate prior digest. ACK SHA256 is diagnostic only.

STATE representation, record framing, collection framing and capacity are controlled exclusively by the published framing authority, sections 3-9. Historical representation 1 remains historical; the exhaustive field projection below specializes the published selected representation without redefining its grammar.

Primitive domains:

- U: exactly 8-byte unsigned big-endian integer, supported values 0 through 2^63-1. No bool, signed sentinel, alternate width or overflow.
- T: exactly 8-byte signed two's-complement big-endian UTC microseconds, -2^63 through 2^63-1.
- B: one byte 00 or 01 for an explicitly boolean field only.
- ID: exact strict UTF-8 identifier, 1-255 bytes, not entirely whitespace. No trimming, folding or Unicode normalization.
- ENUM: exact UTF-8 published closed enum `.value`; unknown values reject.
- H: exactly 32 bytes, SHA-256 digest, never a replacement for retained authoritative bytes.
- BYTES: exact nonempty byte string, at most 1,048,576 bytes.
- KEY: full valid published version-1 canonical conflict frame; no digest substitution.
- Optional X: byte 00 alone for absent; byte 01 followed by exact X bytes for present. No empty-present values except an explicitly permitted empty collection payload. Required fields never use this wrapper.
- Acquisition reservation field: zero-length bytes for ACQUIRE, otherwise required ID, preserving the published acquisition payload convention. This exception is only for that field, never expected_revision.
- L(items) = U32(item_count) || recursively framed item_1 || ... || recursively framed item_N, preserving the specified canonical item order. U32 is exactly four unsigned big-endian bytes, range 0 through 2^32-1. Empty L is exactly 00000000. No prefix, version, tag 11, outer F, aggregate length or additional per-item wrapper belongs to L. The containing object's existing field length frames this payload exactly once. Each reference item is its complete R frame; each KEY item is its full existing conflict frame. Reject count mismatch, malformed items or trailing bytes. A count beyond U32 range rejects in this non-STATE primitive; this is not a STATE history bound.

Schema field types determine interpretation: UUID identities inside KEY retain canonical 16-byte UUID values; no table identity is added. Opaque immutable database projections retain approved exact bytes; this protocol does not reconstruct UUIDs from text or invent missing record identities. Register, command, reservation and artifact IDs are ID, not implicitly UUIDs.

Retained COMMAND/ACK/EVENT objects remain within their existing IL.3 BLOB capacities; every v1 field additionally obeys the original per-field bound. Oversized fields reject before durable successful command creation. No aggregate STATE byte cap, retained-row cap, 4,096 cap or size-triggered representation switch exists. STATE-2 directly represents each IL.3-valid 1 MiB value plus enclosing overhead, and streams arbitrarily many finite retained records. Processing chunk size never affects canonical identity. No whole-COMMAND 65,535 cap is introduced.

Malformed UTF-8, duplicate keys, wrong count/type/width, invalid enum, noncanonical optional marker, overflow and trailing bytes reject. Parsing must bound lengths before allocation. Round-trip re-encoding must equal original bytes.

## 3. Reference and parameter schemas

R = F(1,17,[artifact_id:ID, artifact_type:ENUM(ArtifactType), artifact_sha256:H]). References are resolved against exact retained APPROVED_ARTIFACTS bytes and approval records; hash equality alone is insufficient. Ordered reference collections sort by exact UTF-8 artifact_id bytes, then artifact_type bytes, then digest bytes; duplicate artifact IDs reject. Their optionality is represented by an empty L, not NULL.

P = F(1,16,[target_reservation_id:ID, prior_binding:Optional R, new_binding:Optional R, execution_state:Optional ENUM(ExecutionState), quarantine_reason:Optional ENUM(QuarantineReason), supporting_refs:L(R), proposed_expires_at:Optional T, proposed_completion_deadline:Optional T, primary_evidence_reference:Optional R]).

Every command has exactly these parameter fields, even when absent. proposed_expires_at and proposed_completion_deadline are REQUIRED present only for ACQUIRE and MUST be absent for mutations; they bind the immutable creation deadlines and must satisfy all published timing/approval constraints. No mutation can renew or substitute deadlines. Applicability of the remaining parameters is exhaustive:

| Command | prior_binding | new_binding | execution_state | quarantine_reason | supporting_refs |
| --- | --- | --- | --- | --- | --- |
| ACQUIRE | absent | required, equal root binding reference | absent | absent | required approved identity/provenance evidence where published authority requires it |
| ADVANCE | required predecessor request | required new bound request | absent | absent | required actor reconciliation evidence |
| RECORD_EXECUTION | absent | absent | required | absent | required execution evidence |
| QUARANTINE | absent | absent | absent | required | required diagnosis evidence |
| RELEASE | absent | absent | absent | absent | required RELEASE_EVIDENCE |
| RECOVER | absent | absent | absent | absent | required RECOVERY_EVIDENCE |

Supporting refs must include all exact artifacts required by the independently approved operation package; structural presence does not prove approval. No arbitrary parameter maps or unrecognized extension keys exist. target_reservation_id is required even on ACQUIRE: it specifies the absent identity to create, while the root acquisition reservation field remains empty. For mutation it equals the root reservation_id. This fixes the target before row lookup without reopening M-04.

Primary supporting artifact is selected ONLY by parameters.primary_evidence_reference, an Optional R containing the existing artifact_id/type/hash reference. It is absent on ACQUIRE exactly when no supporting evidence is required; otherwise it is required present, and its exact R bytes must occur exactly once in supporting_refs. The reference must resolve to the exact retained approved artifact and match its ArtifactType and hash. For RELEASE its type MUST be RELEASE_EVIDENCE; for RECOVER it MUST be RECOVERY_EVIDENCE. Other commands' primary reference must match their independently approved evidence package; no type or approval is fabricated by construction.

The primary slot is a unique semantic role, not a collection position. Supplementary references are all other supporting_refs members. Canonical field count is exactly nine; repeated primary fields, two claims to the primary slot, missing required primary, absent membership, type/hash mismatch or duplicate artifact ID reject. Supplementary evidence cannot substitute for required evidence. The explicitly selected primary may sort anywhere. Artifact-ID order controls serialization only, never semantic role. Root evidence_references MUST equal parameters.supporting_refs byte-for-byte. The selected primary reference is part of canonical parameters and therefore replay identity. No new ArtifactType, persisted field/column or artifact identity is introduced: this is closure of still-unimplemented canonical COMMAND parameters retained in existing opaque bytes.

ADVANCE root binding_reference is the new binding; other mutations root binding_reference is the current binding. Every mutation's fixture_set_id and target identity must match the durable reservation.

Event artifact_id is always the root binding_reference.artifact_id, and evidence_artifact_id is the primary supporting artifact ID or absent if none. This rule applies uniformly to every event in a successful command; per-event selection is not discretionary. The event-linked exact COMMAND carries the complete supporting reference set. ACK evidence_references is that same set, and ACK approval_record_hash is the exact command transition approval hash. Approval validation, including completeness and independence, remains a separate external gate.

## 4. M-03 COMMAND schema and replay

C = F(1,5, ordered fields):

1. command_kind ENUM(Command)
2. authenticated_principal ID
3. register_id ID
4. issuer_generation U (>=1)
5. activation_id ID
6. command_id ID
7. reservation_id: acquisition-empty or mutation ID
8. expected_revision U, always required
9. operation ENUM(Operation)
10. phase ENUM(Phase)
11. binding_kind ENUM(ArtifactType), PROVISIONING_REQUEST or FIXTURE_MANIFEST only
12. binding_sha256 H
13. fixture_set_id ID
14. binding_reference R
15. approval_record_hash H
16. authorization_reference R (AUTHORIZATION)
17. evidence_references L(R)
18. parameters P

command_payload_bytes = C; command_payload_sha256 = SHA256(C). Persist the exact C bytes, not a different request encoding. Fields redundant with references must agree exactly; root binding digest/type must equal binding_reference. The approval hash must resolve to the exact retained independent approval bytes for the transition: new binding artifact for ACQUIRE/ADVANCE, otherwise the primary supporting artifact defined in section 3; authorization/evidence cannot be inferred from caller assertions. Operation/phase/binding constraints remain exactly IL.1/IL.3's constraints. No request hash substitutes for CANARY manifest authority.

M-04: ACQUIRE expected_revision = integer 0, target absent inside the write transaction, successful initial revision 0. Existing mutation requires exact current revision and increments once; first later mutation 0 -> 1. No NULL/N/A/sentinel, UPSERT or adoption. Command kind fixes the interpretation before state lookup.

Eligible completed replay requires same command_id, same authenticated principal, exact C byte equality AND recomputed verified SHA256 equality. Principal is inside C and is also compared to the durable principal column and authenticated requester. All parameters and expected_revision participate. Different principal or bytes is REPLAY_MISMATCH, even if digests collide. No new outcome/event/revision is created on replay or mismatch.

Replay returns the exact retained outcome and ACK, not a reconstruction from later state. Current execution permission still requires the published separate activation/checkpoint/time/lifecycle checks. A stored ACK is not current permission by itself.

## 5. M-01 EVENT schema and chain

Logical event fields are exactly the fields below. Canonical current event material, canonical event payload, event preimage and persisted event_bytes all mean the SAME frame E. event_digest is separately stored SHA256(E), never included in E. The event_bytes storage column is not a logical field inside E.

E = F(1,6,[event_sequence:U, command_id:ID, reservation_id:Optional ID, register_id:ID, issuer_generation:U, activation_id:ID, event_type:ENUM(EventType), utc_time:T, prior_digest:H, revision:U, artifact_id:Optional ID, evidence_artifact_id:Optional ID]).

No additional event payload, ACK bytes, event_digest, state digest, checkpoint digest or embedded event_bytes is permitted. Event-specific information is resolved through the immutable command payload and retained artifact/evidence IDs. These IDs must resolve and match the actual transition; no caller-supplied opaque event is accepted.

prior_digest appears EXACTLY ONCE as field 9 in E. event_digest = SHA256(E); do not prepend prior_digest a second time. The first sequence is 1, prior_digest = SHA256(ASCII("JOUS-FIXTURE-LEASE-GENESIS-V1")). Each subsequent sequence is predecessor sequence +1 and uses that predecessor's event_digest. This anchor is distinct from the protected-checkpoint zero-byte predecessor sentinel.

Event revision is required, including diagnostic rejection events: use the current target revision when a target exists, otherwise creation baseline 0; that diagnostic value does not assert row existence. reservation_id is absent when no reservation exists. UTC is the command's supplied, separately validated authoritative UTC projection, identical across that command's events. IL.4 does not acquire or qualify time.

Successful command event order (no optional reordering):

- ACQUIRE: REQUESTED, RESERVED, ACKNOWLEDGED.
- ADVANCE: PHASE_ADVANCE_REQUESTED, PHASE_ADVANCED, ACKNOWLEDGED.
- RECORD_EXECUTION: EXECUTION_RECORDED, ACKNOWLEDGED.
- QUARANTINE with definite expiry established under controlling strict deadline semantics: EXPIRED, QUARANTINED, ACKNOWLEDGED.
- QUARANTINE without definite expiry (including overlap uncertainty): QUARANTINED, ACKNOWLEDGED; uncertainty uses CLOCK_UNCERTAIN as required, never invents definite EXPIRED history.
- RELEASE: RELEASE_REQUESTED, RELEASED, ACKNOWLEDGED.
- RECOVER: RECOVERY_APPROVED, RECOVERED, RELEASED, ACKNOWLEDGED.

F-03 applicability: controlling design section 8 (expiry paragraph, lines 416-420) requires EXPIRED then quarantine for definite expiration/unresolved execution; its lifecycle table (line 564) requires EXPIRED history plus QUARANTINED for an unreleased reservation crossing a deadline. The fixture plan expiry paragraph (lines 278-281) requires atomic quarantine when execution or cleanup is incomplete/unknown. Failed, ambiguous or unproven-safe execution/cleanup falls in that category. The expiry-driven QUARANTINE order above is mandatory, not discretionary.

Definitely never began: a NOT_STARTED value alone does not prove stopped execution, complete cleanup or independent release approval. This draft creates no automatic non-quarantine expiry path; the design's unreleased-deadline table remains controlling. Where separately verified ordinary RELEASE is permitted before an expiry/quarantine obligation applies, its existing RELEASE order remains unchanged. Once quarantined, only RECOVER with RECOVERY_EVIDENCE can release; no owner takeover, reacquisition, expiry-based claim deletion or deadline extension.

The EXPIRED event is historical evidence within the SAME transaction that commits quarantine, retained blocking claims, all three linked events, one outcome, exact ACK, event head and resulting STATE digest. There is no externally committed EXPIRED-only intermediate state. All events use the one resulting quarantine revision. ACK covers all three; final reference points to ACKNOWLEDGED. Replay adds nothing. Failure before commit leaves no durable transition/event. Commit uncertainty is STORAGE_UNKNOWN, fences intake and withholds operational acknowledgement; reconcile exact durable/external evidence, never assume rollback or replay execution.

Each successful command allocates a contiguous range in the same atomic transaction. All its events use the resulting revision and target reservation. Each event links to the immediately preceding event, including within a command. ACKNOWLEDGED describes atomic internal outcome construction, not network delivery or checkpoint completion, and contains no ACK bytes/hash.

Rejected commands are not durably recorded by this bounded protocol. The design permits, but does not require, a separate rejected-command audit transaction; that optional facility is deferred. Finite diagnostic outcomes remain the published OutcomeCode set. No failed transaction leaves durable events. Replay and mismatch append no event. No successful zero-event or deterministic-no-op command is defined. Unknown outcomes/events reject.

transition_event_sequence always means the FINAL event sequence of the successful command, including ACKNOWLEDGED. It never means first sequence or an arbitrary representative event.

## 6. M-02 ACK schema and event coverage

A = F(1,10, ordered required fields):

1. command_id ID
2. command_payload_sha256 H
3. principal ID
4. register_id ID
5. issuer_generation U
6. activation_id ID
7. reservation_id ID
8. resulting_revision U
9. owner ID
10. operation ENUM(Operation)
11. phase ENUM(Phase)
12. binding_kind ENUM(ArtifactType)
13. binding_sha256 H
14. canonical_key_set_digest H
15. approval_record_hash H
16. authorization_reference R
17. evidence_references L(R)
18. issued_at T
19. acquired_at T
20. expires_at T
21. completion_deadline T
22. first_event_sequence U
23. final_event_sequence U
24. event_count U
25. final_event_digest H
26. outcome_code ENUM(OutcomeCode), SUCCESS only

All fields required; none is NULL/N/A. ACK identifies actual resulting transaction facts and resolved approval/authorization references. issued_at is the command UTC projection, acquired_at the immutable reservation acquisition time. canonical_key_set_digest = SHA256(L(sorted full KEY bytes)), sorting lexicographically by unsigned byte values. On terminal release it covers the resulting empty claim set; pre-release key evidence remains in the approved release/recovery artifacts and event-linked command history.

The frame itself carries domain/version. ack_bytes = A, persisted exact; SHA256(A) is optional diagnostics, not authority replacement. ACK does NOT contain resulting state_digest, its own hash or checkpoint digest. STATE includes raw framed A bytes, so adding state_digest to ACK would be forbidden recursion.

Successful command always has >=1 event. final - first + 1 = event_count, actual command events must exactly cover that interval, all command IDs must match, chain verified, final digest equal and COMMANDS.transition_event_sequence equal final. One-event coverage uses first=final/count=1 if a later independently adopted protocol permits a single-event success; this protocol's command orders currently all have >=2. Zero events reject SUCCESS.

ACK can be returned only from its durable complete command record. SQLite commit confirmation is local storage evidence only; operational delivery also requires the published protected checkpoint gate. No ACK regeneration from current mutable state.

## 7. Completed command criteria

For this protocol only SUCCESS records are durable completed replay sources. Every required column is present; reservation_id, durable_ack_bytes and transition_event_sequence are non-NULL. Validate C and A canonically, recompute C hash, compare all duplicated IDs/types/revisions/references, resolve exact artifacts/approvals, and verify full event interval and final reference against durable EVENTS.

The referenced reservation must exist, but a historical ACK's revision need not equal its later mutable reservation revision. The ACK's result must match the immutable transition events and original command result. Validate the current register projection/head separately; do not regenerate history from mutable state.

Any partial, malformed, tampered, inconsistent or unsupported record rejects as an integrity condition, never completed replay. There is no repair or invented outcome. Storage uncertainty is not persisted as a successful result. Rejected diagnostic outcomes are not replay sources in this protocol.

## 8. STATE projection and field-level schemas

S is the generation-selected canonical STATE stream under the published framing authority. For STATE-2 it is P || 02 || 08 || U32(4) || 02 || R12(metadata) || 03 || C13(reservations) || 03 || C14(claims) || 03 || C15(completed commands). Ctag is ordered 01 || Rtag rows followed by exactly one 00 terminator, not L or a length/count envelope. Each Rtag uses the published STATE-2 record frame. Historical STATE-1 continues under its original exact authority. Exactly one metadata singleton is mandatory. Zero metadata is malformed, not empty/available state.

Below are exhaustive field lists, in order. Use the primitive domain declared in the published IL.3 SPECS: ID -> ID; digest -> H; blob -> BYTES; uint -> U; utc -> T; bool -> U restricted to 0 or 1; key -> KEY; enum -> exact ENUM. Fields nullable in SPECS use Optional wrappers, never SQL textual NULL. The primitive value is converted deterministically, not serialized using Python or SQLite representations.

### MetadataRow: F(2,12, fields)

1. singleton : U
2. schema_version : U
3. register_id : ID
4. issuer_generation : U
5. activation_id : ID
6. fixture_plan_sha256 : H
7. bootstrap_amendment_sha256 : H
8. provisioning_contract_sha256 : H
9. design_sha256 : H
10. last_valid_utc : T
11. recovery_required : U restricted to 0 or 1

### ReservationRow: F(2,13, fields)

1. reservation_id : ID
2. register_id : ID
3. fixture_set_id : ID
4. operation_type : ENUM(Operation)
5. phase : ENUM(Phase)
6. binding_kind : ENUM(ArtifactType)
7. binding_artifact_id : ID
8. binding_sha256 : H
9. immutable_db_projection : BYTES
10. immutable_db_projection_hash : H
11. owner : ID
12. authorization_ref : ID
13. requested_at : T
14. acquired_at : T
15. acknowledged_at : T
16. expires_at : T
17. completion_deadline : T
18. revision : U
19. lease_status : ENUM(LeaseStatus)
20. expired_condition : U restricted to 0 or 1
21. execution_state : ENUM(ExecutionState)
22. release_evidence_artifact_id : Optional ID
23. quarantine_reason : Optional ENUM(QuarantineReason)
24. recovery_evidence_artifact_id : Optional ID

### ClaimRow: F(2,14, fields)

1. canonical_key : KEY
2. reservation_id : ID
3. introduced_revision : U
4. originating_artifact_id : ID

### CommandRow: F(2,15, fields)

1. command_id : ID
2. authenticated_principal : ID
3. command_kind : ENUM(Command)
4. canonical_payload_bytes : BYTES
5. canonical_payload_hash : H
6. expected_revision : U
7. reservation_id : Optional ID
8. outcome_code : ENUM(OutcomeCode)
9. durable_ack_bytes : Optional BYTES
10. transition_event_sequence : Optional U

Metadata includes singleton/schema identity, all four authority pins, generation/activation, last_valid_utc and recovery_required. Excluded metadata fields are ONLY state_digest, last_event_sequence and last_event_digest. Metadata record is mandatory, singleton=1. Reservations and claims include every field above, including exact immutable projection bytes and full blocking key bytes. Completed commands include every CommandRow field, including raw exact payload and raw exact ACK bytes (length-framed as fields, not substituted hashes).

APPROVED_ARTIFACTS and EVENTS are not additional STATE record families: artifact retention/approval hashes and event-chain history remain separately verified as required by the design. No caches, rowid, filesystem/connection/process state or derived diagnostic values participate. This does not relax artifact integrity or event history requirements.

Rows sort by authoritative key: reservations by exact UTF-8 reservation_id bytes; claims by full canonical_key bytes; commands by exact UTF-8 command_id bytes. No locale or numeric/text coercion. Duplicate authoritative keys reject. STATE-2 collections have no retained count or aggregate length cap; empty collections are exactly 00. Historical STATE-1 framing remains governed by its published authority. Do not depend on SQLite row order. All referenced row constraints and exact enum/identity validations remain mandatory.

canonical_state_bytes = S; state_digest = SHA256(S), over the exact generation-selected canonical stream, with no additional separator. A minimal STATE-2 has required metadata and three marker-prefixed empty terminators, exactly as published. Its digest depends on that exact authoritative metadata, not an implementation-selected constant. No operational register is initialized by these vectors.

## 9. Acyclic atomic construction order

Dependency DAG:

C -> command_payload_sha256
prior event anchor/head + actual transition + C references -> ordered E frames -> event digest chain
actual resulting reservation/claims + command hash + final event range/digest -> A
resulting metadata projection + reservations + claims + completed COMMAND row containing C/A -> S -> state_digest

E contains neither A nor S nor event_digest itself. A contains neither S nor its own hash. S contains A but excludes stored state_digest and metadata event head. No STATE -> ACK -> STATE cycle exists. The final event reference in command/ACK is fixed before STATE construction.

Conceptual order: validate prior durable state/head and command/replay/revision; prepare mutation; construct event sequence and chain; construct ACK from the actual result; form completed command row; form resulting STATE including that row; compute digest; atomically persist reservation/claim mutation, events, outcome/ACK, event head and state digest; COMMIT; later checkpoint/delivery gate. This is a dependency order, not a prescription of SQLite statement order; frozen deferred FKs remain supported.

Successful completed replay changes no events, revision, claims, metadata or state digest. Replay mismatch changes nothing. Neither is a new accepted transition. Independent validation and permission checks remain required before treating a returned historical outcome as current operational permission.

## 10. Compatibility and non-goals

IL.1: unchanged. Full conflict-key version-1 identity/encoding, enums, structural invariants and M-04 remain preserved. Non-STATE framing remains v1; STATE-2 is the published STATE-only generation-selected representation, not passed to the IL.1 conflict decoder.

IL.2: unchanged. Explicit capability evidence and required nonnegative revision contexts remain structural values, never proof. This protocol consumes separately validated facts and does not acquire time or authority.

IL.3: no schema migration or representation change. C/E/A fit existing BLOB columns and limits; exact fields map to frozen CommandRow/EventRow, and transition_event_sequence retains a scalar final-event FK. Larger state projection is computed, not stored in a BLOB column; only its 32-byte digest is stored. Full ACK event range lives inside durable_ack_bytes. All six-table constraints remain controlling.

Future IL.4 encoding, command completion, digest construction and validation are expected implementation work, not authorized here. This draft must be independently reviewed/adopted; published generation binding governs STATE representation and no backward reinterpretation of conflict keys is permitted.

This document does not claim IL.4 implementation, activation, an operational SQLite register, fixtures, genesis, checkpoint publication, production clock qualification, STRIX execution or canary readiness. It authorizes none of those, and no network/credentials/PostgreSQL/Supabase/CLI work. M-04 remains published and closed; only M-01/M-02/M-03 are proposed for closure at authority-design level.

## 11. Recomputed normative protocol vectors

All hex below is the complete canonical preimage; SHA256 is over exactly those bytes. These vectors replace the 51419-byte F-03/F-04 candidate's diagnostic vectors, not published historical hashes. No helper implementation is protocol authority. Synthetic opaque projection/ACK fixtures prove serialization, not permission.

### COMMAND

Logical input: ACQUIRE c, principal p, register g, generation 1, activation x, absent root reservation, target r, expected revision 0, fixture s; provisioning binding a/hash 11 repeated 32 bytes; authorization z/hash 22; approval 33; no evidence and absent primary; deadlines 100/90.

Length: 609 bytes. SHA256: `f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc5`. Changed from 51419-byte candidate: YES. Root evidence L and parameter supporting L lose the incompatible envelope; expected_revision and explicit primary semantics are unchanged.

```text
4a4f55532d464958545552452d4c45415345010500000012000000074143515549524500000001700000000167000000080000000000000001000000017800000001630000000000000008000000000000000000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f524551554553540000002011111111111111111111111111111111111111111111111111111111111111110000000173000000594a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000203333333333333333333333333333333333333333333333333333333333333333000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000000400000000000000b14a4f55532d464958545552452d4c45415345011000000009000000017200000001000000005a014a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000010000000001000000000400000000000000090100000000000000640000000901000000000000005a0000000100
```

### First EVENT

Logical input: Sequence 1 REQUESTED for c/r, UTC 0, revision 0; binding a, absent evidence; prior published genesis.

Length: 153 bytes. SHA256: `623e6d5a2de819a64b3d6d6f348e69581adcdc2a096b2c666a8a56b631c5ac75`. Changed from 51419-byte candidate: NO. EVENT has no collection or payload-hash field; genesis and all logical fields remain identical.

```text
4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000100000001630000000201720000000167000000080000000000000001000000017800000009524551554553544544000000080000000000000000000000204e6abfbfdec0d3d621faea244e0b3c71b2632b092e6423e4f2f352e65a5d7b610000000800000000000000000000000201610000000100
```

### Subsequent EVENT

Logical input: Sequence 2 RESERVED with identical identities/time/revision; prior SHA256(first EVENT).

Length: 152 bytes. SHA256: `2032dddef8645040803eef9c789a62f722cedb7fd1dd0c1fc2fded959db9d70f`. Changed from 51419-byte candidate: NO. Its prior EVENT digest is unchanged; no collection-dependent field exists.

```text
4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000200000001630000000201720000000167000000080000000000000001000000017800000008524553455256454400000008000000000000000000000020623e6d5a2de819a64b3d6d6f348e69581adcdc2a096b2c666a8a56b631c5ac750000000800000000000000000000000201610000000100
```

### ACKNOWLEDGED EVENT

Logical input: Sequence 3 ACKNOWLEDGED; prior SHA256(subsequent EVENT).

Length: 156 bytes. SHA256: `54c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d`. Changed from 51419-byte candidate: NO. Its predecessor and complete preimage remain unchanged.

```text
4a4f55532d464958545552452d4c4541534501060000000c0000000800000000000000030000000163000000020172000000016700000008000000000000000100000001780000000c41434b4e4f574c4544474544000000080000000000000000000000202032dddef8645040803eef9c789a62f722cedb7fd1dd0c1fc2fded959db9d70f0000000800000000000000000000000201610000000100
```

### ACK

Logical input: r/revision 0, owner p, issued/acquired 0, deadlines 100/90; events 1..3/count 3; final digest from ACKNOWLEDGED; empty resulting keys; command/reference bindings above.

Length: 528 bytes. SHA256: `71bbc6be226e8e85929bd99a327eb454e0e05c2b6cc706e82a997d300155d720`. Changed from 51419-byte candidate: YES. Corrected command hash, evidence collection and empty key-set digest change; event interval/digest remain identical.

```text
4a4f55532d464958545552452d4c45415345010a0000001a000000016300000020f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc50000000170000000016700000008000000000000000100000001780000000172000000080000000000000000000000017000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f5245515545535400000020111111111111111111111111111111111111111111111111111111111111111100000020df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119000000203333333333333333333333333333333333333333333333333333333333333333000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e000000202222222222222222222222222222222222222222222222222222222222222222000000040000000000000008000000000000000000000008000000000000000000000008000000000000006400000008000000000000005a0000000800000000000000010000000800000000000000030000000800000000000000030000002054c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d0000000753554343455353
```

### Minimal STATE-2

Logical input: Singleton/schema 1, register g/generation 1/activation x; pins 44/55/66/77 each repeated 32 bytes; last_valid_utc 0/recovery_required U(0); empty reservations/claims/commands.

Length: 269 bytes. SHA256: `e0abb0fee5648d285ae3b3f3f61c133c5ac8f18d4e6493a0ad88d5dce87b5d8a`. Changed from 51419-byte candidate: NO. Empty STATE-2 uses its own terminators and unchanged metadata, not non-STATE L.

```text
4a4f55532d464958545552452d4c45415345020800000004024a4f55532d464958545552452d4c45415345020c0000000b00000008000000000000000100000008000000000000000100000001670000000800000000000000010000000178000000204444444444444444444444444444444444444444444444444444444444444444000000205555555555555555555555555555555555555555555555555555555555555555000000206666666666666666666666666666666666666666666666666666666666666666000000207777777777777777777777777777777777777777777777777777777777777777000000080000000000000000000000080000000000000000030003000300
```

### Completed-command STATE-2

Logical input: Same metadata; reservation r with projection ASCII d/hash SHA256(d), times 0/0/0/100/90, revision 0, LEASED/U(0)/NOT_STARTED, optional evidence absent; completed c contains exact COMMAND and ACK above; final sequence 3; no claims. Framing fixture only: it does not establish operational closure.

Length: 1876 bytes. SHA256: `435d2954bab863c77ee75fd20f72a17be42550057386c62379b9857d3c0652fd`. Changed from 51419-byte candidate: YES. Exact retained COMMAND, payload hash and ACK change; STATE-2 grammar remains identical.

```text
4a4f55532d464958545552452d4c45415345020800000004024a4f55532d464958545552452d4c45415345020c0000000b0000000800000000000000010000000800000000000000010000000167000000080000000000000001000000017800000020444444444444444444444444444444444444444444444444444444444444444400000020555555555555555555555555555555555555555555555555555555555555555500000020666666666666666666666666666666666666666666666666666666666666666600000020777777777777777777777777777777777777777777777777777777777777777700000008000000000000000000000008000000000000000003014a4f55532d464958545552452d4c45415345020d0000001800000001720000000167000000017300000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f52455155455354000000016100000020111111111111111111111111111111111111111111111111111111111111111100000001640000002018ac3e7343f016890c510e93f935261169d9e3f565436429830faf0934f4f8e40000000170000000017a00000008000000000000000000000008000000000000000000000008000000000000000000000008000000000000006400000008000000000000005a000000080000000000000000000000064c45415345440000000800000000000000000000000b4e4f545f5354415254454400000001000000000100000000010000030003014a4f55532d464958545552452d4c45415345020f0000000a000000016300000001700000000741435155495245000002614a4f55532d464958545552452d4c45415345010500000012000000074143515549524500000001700000000167000000080000000000000001000000017800000001630000000000000008000000000000000000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f524551554553540000002011111111111111111111111111111111111111111111111111111111111111110000000173000000594a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000203333333333333333333333333333333333333333333333333333333333333333000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000000400000000000000b14a4f55532d464958545552452d4c45415345011000000009000000017200000001000000005a014a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000010000000001000000000400000000000000090100000000000000640000000901000000000000005a000000010000000020f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc5000000080000000000000000000000020172000000075355434345535300000211014a4f55532d464958545552452d4c45415345010a0000001a000000016300000020f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc50000000170000000016700000008000000000000000100000001780000000172000000080000000000000000000000017000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f5245515545535400000020111111111111111111111111111111111111111111111111111111111111111100000020df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119000000203333333333333333333333333333333333333333333333333333333333333333000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e000000202222222222222222222222222222222222222222222222222222222222222222000000040000000000000008000000000000000000000008000000000000000000000008000000000000006400000008000000000000005a0000000800000000000000010000000800000000000000030000000800000000000000030000002054c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d00000007535543434553530000000901000000000000000300
```

### F-03 expiry COMMAND and full atomic event interval

F-05 impact: expiry COMMAND changes because root/parameter evidence collections change. EXPIRED, QUARANTINED and ACKNOWLEDGED event preimages/digests remain unchanged: they contain no command hash/collection, and prior head is unchanged. Expiry ACK changes through corrected command hash, evidence collection and key-set digest. Lifecycle semantics/order are unchanged.

Synthetic command c-expiry is QUARANTINE of r at expected revision 0; diagnosis e/PROVENANCE_EVIDENCE/hash 88 repeated 32 bytes, explicit primary e; approval 99 repeated 32 bytes, remaining binding/context from COMMAND above. This framing fixture assumes separately verified definite expiry and unresolved cleanup; it does not establish those facts. Result revision 1, UTC 101. Prior head is sequence 3 above.

COMMAND length 799; SHA256 `e8bf530487e83ea2800d10e4113820e1ac86a13276169cfadd9ae0389ac96351`.

```text
4a4f55532d464958545552452d4c454153450105000000120000000a51554152414e54494e4500000001700000000167000000080000000000000001000000017800000008632d657870697279000000017200000008000000000000000000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f524551554553540000002011111111111111111111111111111111111111111111111111111111111111110000000173000000594a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000209999999999999999999999999999999999999999999999999999999999999999000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000005c000000014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e43450000002088888888888888888888888888888888888888888888888888888888888888880000010c4a4f55532d464958545552452d4c4541534501100000000900000001720000000100000000010000000001000000001501455850495245445f554e5245434f4e43494c45440000005c000000014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e43450000002088888888888888888888888888888888888888888888888888888888888888880000000100000000010000000059014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e4345000000208888888888888888888888888888888888888888888888888888888888888888
```

EXPIRED sequence 4; prior is the preceding vector digest. Length 159; SHA256 `886e5f51e480e7df7c4c98b6ab1b67a7b0c000ee3d2954507c42fd5776c1b30b`.

```text
4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000400000008632d6578706972790000000201720000000167000000080000000000000001000000017800000007455850495245440000000800000000000000650000002054c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d000000080000000000000001000000020161000000020165
```

QUARANTINED sequence 5; prior is the preceding vector digest. Length 163; SHA256 `e0f165fb70e57a28e2ef514f60d61b3175c0defb9131c6e562f8b860260a4206`.

```text
4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000500000008632d657870697279000000020172000000016700000008000000000000000100000001780000000b51554152414e54494e454400000008000000000000006500000020886e5f51e480e7df7c4c98b6ab1b67a7b0c000ee3d2954507c42fd5776c1b30b000000080000000000000001000000020161000000020165
```

ACKNOWLEDGED sequence 6; prior is the preceding vector digest. Length 164; SHA256 `a24949136abe475b02473b59fda2e60e04ac2cd6cbab4ec0cd4e92e161d2fc20`.

```text
4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000600000008632d657870697279000000020172000000016700000008000000000000000100000001780000000c41434b4e4f574c454447454400000008000000000000006500000020e0f165fb70e57a28e2ef514f60d61b3175c0defb9131c6e562f8b860260a4206000000080000000000000001000000020161000000020165
```

F-03 ACK: interval 4..6/count 3, transition_event_sequence 6, final digest above; other result fields as ACK above. Claims are retained: this synthetic fixture starts with an empty key set, not a claim-release assertion. Length 623; SHA256 `32a8ebc5c69a1aabfc46217a52d5024a7e7537922b3b1899ffaafe5b83035f8e`.

```text
4a4f55532d464958545552452d4c45415345010a0000001a00000008632d65787069727900000020e8bf530487e83ea2800d10e4113820e1ac86a13276169cfadd9ae0389ac963510000000170000000016700000008000000000000000100000001780000000172000000080000000000000001000000017000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f5245515545535400000020111111111111111111111111111111111111111111111111111111111111111100000020df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119000000209999999999999999999999999999999999999999999999999999999999999999000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000005c000000014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e434500000020888888888888888888888888888888888888888888888888888888888888888800000008000000000000006500000008000000000000000000000008000000000000006400000008000000000000005a00000008000000000000000400000008000000000000000600000008000000000000000300000020a24949136abe475b02473b59fda2e60e04ac2cd6cbab4ec0cd4e92e161d2fc200000000753554343455353
```

### F-04 semantic-reference vectors

Each reference uses R = F(1,17,[exact ID, published type, 32-byte digest]); supporting collection sorts by ID independently of primary. Required evidence hash = 11 repeated 32 bytes; supplementary PROVENANCE_EVIDENCE hash = 22 repeated 32 bytes. RELEASE primary type is RELEASE_EVIDENCE. The following exact P vectors use target r, absent prior/new/execution/reason/deadlines, the displayed sorted supporting refs and the displayed present primary. These are parameter/selection fixtures, not independently authorized releases.

Required sorts first: select exact a-required solely from the primary slot, ACCEPT structural selection. Length 362; SHA256 `683cda653fad6d7d7f2872739e0b4721e180ca83c173718eb11a8c76b32b086e`. Changed from 51419-byte candidate: YES, only supporting collection framing changes. IDs differ across these two examples; the semantic selection rule remains identical.

```text
4a4f55532d464958545552452d4c4541534501100000000900000001720000000100000000010000000001000000000100000000c8000000024a4f55532d464958545552452d4c454153450111000000030000000a612d72657175697265640000001052454c454153455f45564944454e43450000002011111111111111111111111111111111111111111111111111111111111111114a4f55532d464958545552452d4c454153450111000000030000000f7a2d737570706c656d656e746172790000001350524f56454e414e43455f45564944454e4345000000202222222222222222222222222222222222222222222222222222222222222222000000010000000001000000005f014a4f55532d464958545552452d4c454153450111000000030000000a612d72657175697265640000001052454c454153455f45564944454e4345000000201111111111111111111111111111111111111111111111111111111111111111
```

Supplementary sorts first: select exact z-required solely from the primary slot, ACCEPT structural selection. Length 362; SHA256 `5d7b5d9c0eb54a470fb84ce7c0ba8eb74947b6667c4c58aa0f03a59d4824f1d8`. Changed from 51419-byte candidate: YES, only supporting collection framing changes. IDs differ across these two examples; the semantic selection rule remains identical.

```text
4a4f55532d464958545552452d4c4541534501100000000900000001720000000100000000010000000001000000000100000000c8000000024a4f55532d464958545552452d4c454153450111000000030000000f612d737570706c656d656e746172790000001350524f56454e414e43455f45564944454e43450000002022222222222222222222222222222222222222222222222222222222222222224a4f55532d464958545552452d4c454153450111000000030000000a7a2d72657175697265640000001052454c454153455f45564944454e4345000000201111111111111111111111111111111111111111111111111111111111111111000000010000000001000000005f014a4f55532d464958545552452d4c454153450111000000030000000a7a2d72657175697265640000001052454c454153455f45564944454e4345000000201111111111111111111111111111111111111111111111111111111111111111
```

Missing primary on RELEASE: REJECT. Present primary not in supporting_refs: REJECT. Duplicate primary field (ten-field P), two primary-role assignments or duplicate artifact ID: REJECT. Primary declared RELEASE_EVIDENCE but retained artifact is PROVENANCE_EVIDENCE: REJECT. Explicitly selecting supplementary PROVENANCE_EVIDENCE as RELEASE primary: REJECT. For RECOVER replace the required type with RECOVERY_EVIDENCE, and reject RELEASE_EVIDENCE cross-substitution. These deterministic negative fixtures are mutations of the exact P vectors, never alternate canonical forms.

## 12. Self-review / independent review gate

The draft chooses exactly one preimage per object and one acyclic DAG. Optional fields, primitive domains, bounds, collection ordering, required expected_revision, first/final event references and empty-state framing are explicit. Full payload equality remains required for replay. No event or ACK includes its own digest, and ACK omits state_digest because STATE includes ACK bytes.

Independent review must verify the exact vectors, published-v1 reconciliation, field mappings, uncapped streaming STATE, completed-command integrity and compatibility against the controlling published authority before any implementation or publication authorization. No claim of overall IL.4 readiness is made by creation of this candidate.

## 13. F-03/F-04 adversarial closure and scope

| Counterexample | Normative result |
| --- | --- |
| Required EXPIRED omitted or QUARANTINED precedes it | reject event order; do not classify durable command as complete |
| ACK interval omits an event or scalar final reference points to EXPIRED | reject completion/ACK consistency |
| Supplementary ID sorts first | accept if independently approved; explicit primary remains selected |
| Missing primary, duplicate unique role or supplementary substitution | reject before accepted transition |
| Declared type differs from approved retained artifact | reject exact reference resolution |
| Replay changes only primary role/reference or any supplementary reference | different C bytes => REPLAY_MISMATCH; no mutation |
| STATE grows and encoder switches representation | reject; immutable generation binding controls |
| STATE-2 parser falls back to STATE-1 | reject; no downgrade/fallback |
| Expiry transition fails before commit | no durable partial history; no claim release |
| Commit outcome uncertain | STORAGE_UNKNOWN / fenced reconciliation; no assumed rollback or operational ACK |

R-01 framing selection is published authority, not redefined here. This draft reconciles old incompatible generic framing/caps only as required to conform to that authority. EVENT nonrecursion, single prior digest, genesis anchor, final-event scalar meaning, contiguous chain, 26-field ACK, exact replay, and ACK-to-STATE acyclicity remain intact. F-04 adds one explicit primary Optional R in the unimplemented parameter payload only; existing ArtifactBytes type/identity, typed release/recovery predicate and immutable storage BLOBs require no change. Frozen IL.2 contexts and IL.3 schemas gain no field or column. Construction never proves external approval. Oversized v1 fields and existing stored-object limits still reject; STATE wrapping never narrows stored scalar capacity.

This draft does not authorize staging, commit, push, IL.4 implementation, operational STATE-2, replacement/package/ceremony implementation, runtime activation, SQLite, checkpoint publication, activation CAS or STRIX.

## 14. F-05 published collection closure

Design section 8 requires a field containing uint32 item count and recursively framed items. The old tag-11 frame was incompatible. L is only the count-plus-items payload; parent field framing occurs exactly once. This correction applies to both COMMAND evidence lists, parameter supporting_refs, ACK evidence references and the canonical key-set digest. STATE-2 collections continue using their own published row markers/terminators. No tag-11 collection is normative.

### Empty non-STATE collection

Logical input: no members.

Length: 4 bytes. SHA256: `df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119`.

```text
00000000
```

### One-item non-STATE collection

Logical input: the first F-04 example's canonical reference(s): a-required/RELEASE_EVIDENCE/hash 11 repeated 32 bytes, then z-supplementary/PROVENANCE_EVIDENCE/hash 22 repeated 32 bytes, using only the first for the one-item case.

Length: 98 bytes. SHA256: `007360d0ceeaddda8b91b019b8ec709fd2335ba288373d6120dfaaabdd96cd75`.

```text
000000014a4f55532d464958545552452d4c454153450111000000030000000a612d72657175697265640000001052454c454153455f45564944454e4345000000201111111111111111111111111111111111111111111111111111111111111111
```

### Two-item non-STATE collection

Logical input: the first F-04 example's canonical reference(s): a-required/RELEASE_EVIDENCE/hash 11 repeated 32 bytes, then z-supplementary/PROVENANCE_EVIDENCE/hash 22 repeated 32 bytes, using only the first for the one-item case.

Length: 200 bytes. SHA256: `455c96148ed881664979ab0cb518a82b628cd67bf20249e12a0b3724941f23f4`.

```text
000000024a4f55532d464958545552452d4c454153450111000000030000000a612d72657175697265640000001052454c454153455f45564944454e43450000002011111111111111111111111111111111111111111111111111111111111111114a4f55532d464958545552452d4c454153450111000000030000000f7a2d737570706c656d656e746172790000001350524f56454e414e43455f45564944454e4345000000202222222222222222222222222222222222222222222222222222222222222222
```

| F-05 adversarial encoding/behavior | Result |
| --- | --- |
| Empty collection wrapped as tag 11 | reject/nonconforming; expected exact four zero bytes |
| Extra collection protocol prefix or aggregate F envelope | reject; first four bytes are item count, and exact consumption must match |
| Double-framed containing field | reject field/item schema and round-trip equality |
| Missing item count | reject truncation or impossible item parsing |
| Declared count differs from complete framed items | reject missing items or trailing bytes |
| Items out of canonical key/reference order | reject non-increasing ordering |
| Malformed recursive item frame | reject unknown tag/version/count/length or invalid value |
| Whole-COMMAND 65,535 cap replaces per-field bound | nonconforming rejection of otherwise valid object; original per-field rule controls |
| Non-STATE L applied to STATE-2 collections | reject selected STATE grammar; its streaming terminators remain exact |

No F-03 or F-04 semantic change is authorized by this correction. A replay under different corrected canonical evidence bytes is still REPLAY_MISMATCH, not equivalence by digest. All retained primary selection, event order, complete ACK coverage and uncertainty/reconciliation rules remain controlling.

Cross-vector DAG: corrected L -> COMMAND bytes/hash and key-set preimage/digest -> ACK bytes -> completed command record -> STATE-2 content/digest. EVENT is unaffected here because its explicit fields contain neither those collections nor command payload hash. Its chain is nevertheless independently recomputed from the genesis/head. No stale collection-dependent hash may be carried forward.
