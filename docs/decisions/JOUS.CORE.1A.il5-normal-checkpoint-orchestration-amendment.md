# JOUS.CORE.1A IL.5 normal checkpoint / orchestration amendment

Status: DRAFT authority candidate; independent review and publication required. This document authorizes no implementation or operation. Drafting baseline: `4ff80b2b710aacfc69df761b547845e5a8dae459`.

## 1. Narrow authority and precedence

This NEW specialization closes IL5-01's normal-command checkpoint construction/retention ambiguity and specifies the authority constraints for future IL5-02 admission and IL5-03 typed capabilities. It is not a claim that these exact rules or interfaces previously existed. Implementation remains separately gated.

Controlling references:

- `JOUS.CORE.1A.fixture-lease-implementation-design.md`, sections 3-6, 8-10 and 12: local transactions, host-bound activation, single-command permits, checkpoint schema/CAS, encoding, approval applicability and failure rules; blob `706b6bf782701a602012bd1fed75099f519a53ee`.
- `JOUS.CORE.1A.il4-command-event-state-protocol-amendment.md`, sections 2-9: canonical COMMAND/EVENT/ACK, completed outcomes and STATE; blob `9549831ac43bb9a723a28f082ee97781b6321468`.
- `JOUS.CORE.1A.il4-acquisition-revision-amendment.md`, sections 3-6: creation, mutation and historical replay; blob `8980f5f016dd59465fa5d4465902f026d6040cb0`.
- `JOUS.CORE.1A.il4-large-value-framing-reconciliation.md`: immutable generation protocol binding and STATE-2; blob `28fe3e268589459c89ce80a0c59790b5ed46086e`.
- `JOUS.CORE.1A.replacement-generation-cutover-amendment.md`: separate replacement authority; blob `6068c9c92504d7f8651da4286a7ee3f9c4440ef9`.
- `JOUS.CORE.1A.il4-durable-structural-adaptation-amendment.md`: shared structural rule and writer-scoped admission; blob `0f0cd42e9688e13af5c3113f1ba44e525e4f7113`.
- Published `fixture_lease_service.py`: EvidenceReference, CommandPermit, ActivationIdentity, qualified trusted-time values and deny-by-default capabilities; published IL.4B command core and contract: canonical replay, shared structural rule and local completion.

Only normal successful state-changing command successor checkpoints are specialized here. Shutdown/backup, rejection-audit checkpoints, genesis, replacement and restore are NOT APPLICABLE to this schema profile. This amendment SHALL NOT reinterpret their reference positions or authorize those operations. Earlier ambiguous normal-command construction assumptions yield to this specialization upon adoption; unrelated authority remains controlling.

## 2. Required sequence and isolation

IL.5 SHALL preserve this order:

1. Recognize historical command_id and exact retained completion as applicable; do not execute a replay as a new command.
2. Establish qualified activation/host, exact current predecessor checkpoint, applicable independent approval, requester/authorization and trusted-time evidence through their existing gates.
3. Obtain a fresh single-command permit and confirmed retention of its immutable admission envelope under section 5.
4. Enter the existing BEGIN IMMEDIATE writer transaction.
5. Reread durable admission facts and synchronously revalidate admission under section 12; historical recognition still precedes new-transition admission.
6. Atomically persist the local command transition, reservation/claims, ordered EVENTS, exact retained ACK, complete SUCCESS COMMAND, event head and STATE digest through IL.4B.
7. Confirm local COMMIT.
8. Construct and publish the one exact successor protected checkpoint under predecessor CAS.
9. Resolve/complete the exact original permit/service operation.
10. Permit delivery of the exact retained operational ACK only after all delivery gates resolve.

LOCAL COMMIT SHALL PRECEDE EXTERNAL CHECKPOINT PUBLICATION. No external/network I/O SHALL occur while the SQLite writer transaction is active. There SHALL be NO second required local finalization transaction after checkpoint publication. External confirmation/completion evidence is retained externally, not patched into a local pending column. At most one in-flight permit and one unresolved command/checkpoint gap exist per activation under existing authority; no next transition is admitted across that gap.

## 3. Normal checkpoint object and exact outer order

The type is `jous.fixture-lease-checkpoint.v1`, NORMAL_COMMAND profile. Its REQUIRED type/version identity is represented by the existing binary prefix, version 1 and CHECKPOINT tag 7, not an extra string field. The outer object SHALL be F(1,7,fields) with exactly ELEVEN fields in this published order. No extensions or omitted fields are permitted.

| Position | Field | Type / applicability | Normative source |
| --- | --- | --- | --- |
| 1 | register_id | ID, REQUIRED | Exact admitted command, activation, predecessor and durable metadata register. |
| 2 | generation | U, REQUIRED; positive | Exact mutation-eligible current generation; unchanged from predecessor. |
| 3 | activation_id | ID, REQUIRED | Exact qualified activation and command binding; unchanged from predecessor. |
| 4 | checkpoint_revision | U, REQUIRED | Exact predecessor revision + 1; overflow rejects before new local admission. No reset or skipped revision. |
| 5 | latest_durable_event_sequence | U, REQUIRED; positive | Committed metadata head and retained command ACK final sequence; predecessor head advanced by exactly the transition's validated contiguous event interval. |
| 6 | event_chain_digest | H, REQUIRED | Exact committed final event digest, matching ACK and metadata. |
| 7 | state_digest | H, REQUIRED | Exact committed STATE digest under the generation's immutable representation binding. |
| 8 | checkpoint_utc_us | T, REQUIRED | Fixed admitted command UTC, exactly retained ACK.issued_at, under section 6. |
| 9 | predecessor_checkpoint_digest | H, REQUIRED | SHA256 of exact validated protected predecessor bytes. No zero/ABSENT sentinel or fallback. |
| 10 | command_permit_reference | N, REQUIRED | Exact normal reference bundle in section 4. |
| 11 | applicable_approval_reference | Optional ID, OPTIONAL encoding; applicability CLOSED by section 7 | Present stable independent approval identity when applicable; byte 00 only for proven NOT_APPLICABLE. UNKNOWN cannot be encoded. |

Host/authority identity and STATE representation identity/authority are REQUIRED inside N, not new outer fields. Separate generation-predecessor or replacement-transition fields are NOT APPLICABLE: normal publication preserves register/generation/activation/host and chains the exact checkpoint predecessor. External protected-authority identity is supplied by the qualified current activation's existing authority context; it SHALL resolve to the same retained host and protected checkpoint service and SHALL NOT be inferred from client hostname text.

## 4. Exact command / permit reference bundle

N SHALL be F(1,18,fields) with exactly these ten fields, in order. Tag 18 is this new auxiliary schema closure within the existing framing family; it is not another protocol representation.

| Position | Field | Type / applicability |
| --- | --- | --- |
| 1 | command_id | ID, REQUIRED |
| 2 | canonical_command_sha256 | H, REQUIRED |
| 3 | original_permit_identity | ID, REQUIRED |
| 4 | original_permit_evidence_sha256 | H, REQUIRED |
| 5 | approved_host_identity | ID, REQUIRED |
| 6 | state_representation_id | ID, REQUIRED |
| 7 | state_representation_authority_identity | ID, REQUIRED |
| 8 | state_representation_authority_sha256 | H, REQUIRED |
| 9 | retained_admission_evidence_identity | ID, REQUIRED |
| 10 | retained_admission_evidence_sha256 | H, REQUIRED |

No field of N is optional. Unknown or missing binding rejects. `canonical_command_sha256` SHALL equal SHA256 of the exact admitted, retained IL.4A canonical COMMAND bytes; COMMAND SHALL NOT be serialized a second way. Those bytes include authenticated principal, command_id, expected_revision and exact evidence references. Therefore a principal or payload change changes the reference identity, and command_id alone is insufficient. Hash equality SHALL NOT replace exact-byte replay comparison. A historical replay points to its original command/permit/checkpoint; it creates no new N or successor.

The permit reference SHALL be EXACTLY the existing `CommandPermit.evidence` pair `(identity, sha256)`. Its identity SHALL be a globally unique, stable, non-secret identifier within the qualified activation authority, never recycled or selected by response receipt. No request ID, nonce, alternate permit ID or process-local substitute is conforming. Its digest SHALL bind the immutable exact qualified permit evidence, including context, activation/host, predecessor and validity interval.

The original operation keys SHALL be the semantic tuples `(original_permit_identity, CHECKPOINT_PUBLICATION)` and `(original_permit_identity, PERMIT_COMPLETION)` in that same protected authority namespace. These closed operation-kind literals assign the two distinct external steps; they are not extra checkpoint fields or provider-generated retry IDs. Queries SHALL resolve these exact original keys, not create operations. One permit identity SHALL bind exactly one admitted command and one successor candidate. Provider-native request IDs SHALL NOT replace this authority identity. Construction/transport mapping of qualified evidence remains provider implementation work; its exact immutable bytes/hash and resolvable identity are mandatory, not configurable choices.

STATE representation fields SHALL equal the immutable approved generation protocol binding and its exact authority reference/hash. For published STATE-2 the identifier is exactly `JOUS_CORE1A_STATE_REPRESENTATION_2`. No configuration, size, parser or predecessor fallback is allowed. Unsupported historical profiles fail closed; no STATE-1 codec is defined here.

## 5. Retention before local COMMIT and candidate resolution

Before BEGIN, the protected original permit system SHALL confirm durable retention of an immutable admission envelope identified by N fields 9-10. It SHALL bind: exact COMMAND bytes/hash and principal; original permit reference; qualified activation/register/generation/host; exact predecessor bytes/digest/revision/event head; immutable STATE protocol binding; approval applicability and exact applicable retained approval evidence; fixed command UTC and the qualified time evidence fixing it; and qualified permit validity evidence. Credentials/secrets SHALL NOT be retained in this envelope. The envelope SHALL not contain a future checkpoint digest or claim local COMMIT success, avoiding a recursive dependency.

The original permit record SHALL durably index this envelope by exact register/generation/activation, command_id, canonical COMMAND digest and principal before local admission. A read-only lookup SHALL recover the one existing permit/envelope for those identities after restart without obtain/acquisition. Different or multiple matches, unavailable retention, or uncertain retention confirmation SHALL prohibit local admission. No permit can be considered usable merely because it was sent. At most one original operation is retained for an unresolved command; no second permit is allocated to repair missing evidence.

After confirmed local COMMIT, IL.5 SHALL validate retained COMMAND/ACK/events and the committed metadata STATE/head, combine them with that immutable envelope, and derive the candidate in section 3. Before attempting its CAS publication, the protected operation record SHALL bind and retain the exact candidate bytes/digest under `(permit identity, CHECKPOINT_PUBLICATION)`. Candidate association is immutable; different candidate bytes for that key reject. Retention without current-pointer advancement is NOT publication confirmation. Failure/uncertainty at this step fences intake and hands resolution to IL.7.

A crash between local COMMIT and external candidate retention SHALL be recoverable from the original permit/envelope and existing six-table durable outcome, not a new pending table. During the unresolved gap no later command changes that committed STATE/head. Reconstruction SHALL reproduce the same candidate exactly, including UTC and predecessor. After later commands have been admitted, historical resolution SHALL use externally retained exact checkpoint bytes; current mutable metadata SHALL NOT reconstruct an older successor. Missing/inconsistent required evidence yields UNKNOWN/RECOVERY_ONLY, never invented bytes or authoritative absence.

The permit/operation service SHALL retain envelopes, exact candidates, immutable predecessor evidence, approvals and structured results for the same retained command/checkpoint history lifetime. It SHALL NOT expire unresolved evidence at permit expiry or discard it upon lost ACK. No in-memory-only or response-only retention is conforming. This is an external evidence-retention requirement, not a second local distributed-transaction journal.

## 6. Fixed UTC and deterministic reconstruction

Before BEGIN, qualified trusted-time evidence SHALL fix one signed UTC-microsecond value: the qualified admission interval's `now_lower`. IL.5 SHALL supply that exact value as the command's UTC projection; all its EVENTS and retained ACK.issued_at SHALL equal it. This specializes selection of the already-published command UTC input, without changing any COMMAND/EVENT/ACK bytes or type. It does not assert the command occurred at an exact physical instant: the qualified interval retains uncertainty.

The envelope SHALL retain the exact fixing interval, qualification reference and bound evidence. At in-transaction admission, permit/time validity SHALL be rechecked using a conservatively qualified interval covering that actual admission point from already-acquired evidence under the existing IL.2 measurement/bound model. An earlier timestamp is not proof of current validity. If no such qualified interval is available without external I/O, reject before mutation. This document chooses no production clock/profile and grants no new measurement qualification authority.

Preserve inclusive authorization deadline `now_upper <= deadline`, strict continuation/freshness `now_upper < deadline`, and valid_from `now_lower >= valid_from`. Single-command permit consumption requires `now_lower >= permit.valid_from_us` and strict `now_upper < permit.valid_until_us`; an expired/overlapping interval rejects. No manufactured certainty is permitted. Evidence must remain sufficient for existing transaction-completion timing requirements; inability to prove them fences, not permission to use a stale pre-BEGIN sample.

Checkpoint UTC SHALL be derived after confirmed COMMIT from the retained ACK's fixed issued_at, checked against the envelope, NOT a new post-COMMIT sample. It SHALL NOT change on publication, query, restart, retransmission or reconciliation. Confirmed local completion plus the exact retained envelope SHALL yield one byte-identical candidate and SHA256. Random fields, fresh wall-clock substitution, process-local identifiers, environment encoding and provider serialization SHALL NOT affect it.

## 7. Closed ordinary approval applicability

Independent transition approval applicability SHALL follow the controlling design section 9:

| Command | Normal checkpoint approval field |
| --- | --- |
| ACQUIRE | REQUIRED present independent exact request/manifest/package approval reference, under the existing operation-specific authority. |
| ADVANCE | REQUIRED present independent resulting binding/predecessor approval reference. |
| RELEASE | REQUIRED present independent complete release-gates approval reference. |
| RECOVER | REQUIRED present independent reconciliation/recovery approval reference; IL.5 does not establish recovery eligibility or execute an IL.7 recovery workflow. |
| RECORD_EXECUTION | NOT_APPLICABLE to an additional independent transition approval; existing exact operation authorization, artifact approval integrity and COMMAND approval hash remain required. |
| QUARANTINE | NOT_APPLICABLE to independent approval for blocking; existing authenticated/qualified condition and command evidence remain required. |

This field references the applicable existing transition approval, not a new approval issuance over the future checkpoint hash. Present SHALL be byte 01 followed by the exact stable approval identity; absent SHALL be byte 00 alone, meaning ONLY proven NOT_APPLICABLE for the two listed kinds. Approval unavailable, expired, revoked, inconsistent or uncertain SHALL fail closed before new local admission; it SHALL NOT be encoded as absent. Unexpected present approval for NOT_APPLICABLE SHALL reject this profile. Existing required artifact/authorization checks SHALL NOT be waived by NOT_APPLICABLE.

A present identity SHALL resolve to exact retained independently qualified approval evidence in the envelope, consistent with the canonical COMMAND approval_record_hash and approved transition/package bindings. The checkpoint contains the stable identity, not a self-referential approval digest. No new approval of the checkpoint itself is invented; replacement checkpoint approval/package rules remain separate and unchanged.

## 8. Canonical bytes and digest

F is the published framing primitive: ASCII `JOUS-FIXTURE-LEASE`, one version byte, one domain-tag byte, U32 field count, then U32 length and exact payload for each ordered field. Outer tag 7/count 11 and N tag 18/count 10 are fixed. All use version 1. Unknown tags/profiles, counts, types, fields, trailing bytes, malformed UTF-8 or noncanonical optional markers reject. No JSON, maps, signing wrapper or provider body belongs to the preimage.

U is exact eight-byte unsigned big-endian, values 0 through 2^63-1; no bool/float coercion. T is exact eight-byte signed two's-complement big-endian UTC microseconds, -2^63 through 2^63-1. ID is exact strict UTF-8, 1-255 bytes and not entirely whitespace, without trimming, normalization or folding. H is exactly 32 raw bytes. Optional ID is byte 00 alone or 01 followed by ID; the containing field frames it exactly once. Each v1 field, including complete nested N, SHALL fit 65,535 bytes. No whole-object 65,535 cap substitutes for the per-field rule. No collections occur in this checkpoint profile; any separately referenced canonical COMMAND collections remain U32 count plus recursively framed items under published F-05.

`checkpoint_digest = SHA256(exact_complete_canonical_checkpoint_bytes)`, with no extra prefix, omission, alternate approval wrapper or embedded self-digest. Candidate bytes are authoritative retained material; the digest is derived integrity evidence and SHALL NOT grant permission to reconstruct different bytes. Provider authentication/signatures protect the retained evidence outside this canonical preimage; no algorithm agility is introduced.

## 9. Exact predecessor and publication confirmation

Read/resolve the authoritative protected current checkpoint before obtaining the permit. Retain and validate exact bytes, digest, register/generation/activation/host, representation binding, revision, STATE/head and ancestry. Local admission SHALL require exact predecessor alignment with the writer snapshot. Normal successor is conditional on that exact protected pointer identity/revision/digest; no blind overwrite, fallback predecessor, fork or implicit advancement is permitted. Compare-and-swap remains linearizable under the published protected checkpoint model.

Before the initial normal publication submission, outside the completed local transaction, IL.5 SHALL prove the original permit and current activation/host/fencing authority still authorize that exact publication, using the existing qualified validity/time rules. New qualification SHALL NOT change the fixed candidate UTC or bytes. Expired/unavailable publication authority after local COMMIT SHALL fence and defer to IL.7, not obtain a replacement permit or silently publish under stale authority. Read-only original-operation queries remain permitted for resolution without treating expired permits as new mutation permission. Completion of an already confirmed publication remains the original-operation closure described in section 10.

CONFIRMED SHALL require qualified authenticated/bound evidence that the exact candidate was immutably retained and the protected pointer CAS selected it under the exact expected predecessor. The structured confirmation SHALL bind exact candidate bytes/digest, register, generation, activation, host, checkpoint revision, predecessor reference/digest and the original publication operation key. A request sent, local hash, timeout or unbound provider success SHALL NOT confirm publication. A read showing matching bytes without original-operation and predecessor binding is insufficient; typed resolution SHALL prove all those facts.

DEFINITELY_REJECTED SHALL require authoritative bound evidence that the original operation did not and cannot advance the pointer to this candidate, including a closed original operation result. A generic error or an unexpected current pointer alone SHALL NOT prove no effect. CAS conflict fences and rejects further normal attempts; if original-effect nonoccurrence is not proven, classify UNKNOWN. Unexpected external authority SHALL NOT be adopted as success.

UNKNOWN includes sent-but-unresolved, timeout, lost response, unavailable status and ambiguous rejection. UNKNOWN SHALL never become absence or definite failure by inference. Query original operation read-only; do not resubmit. After local COMMIT, both definite rejection and UNKNOWN SHALL withhold ACK, fence intake, retain all evidence and enter RECOVERY_ONLY. Do not roll back committed local data, restore the older checkpoint or automatically compensate. Identical missing-successor publication is IL.7 reconciliation only after its existing independent recovery approval, never an IL.5 blind retry.

## 10. Original permit completion and delivery

Only after checkpoint publication CONFIRMED SHALL IL.5 invoke completion of `(permit identity, PERMIT_COMPLETION)`. Its exact request and result SHALL bind the original permit evidence reference, exact command_id/canonical bytes digest/principal, exact confirmed checkpoint reference/bytes/digest, register/generation/activation/host and original publication confirmation. The external service SHALL retain an immutable one-completion association. Repeated queries SHALL read that original association, not create another permit or completion identity.

Completion uses the same closed CONFIRMED / DEFINITELY_REJECTED / UNKNOWN outcome classes and bound original-operation proof. CONFIRMED SHALL prove the exact original permit is closed with that checkpoint and no unresolved operation remains. Expiration of the original permit does not erase/query-reset its operation; completion is closure of an already admitted operation, not stale permit reuse for a new mutation. Definite rejection or UNKNOWN fences/RECOVERY_ONLY and hands resolution to IL.7. No new command, permit acquisition, checkpoint publication or ACK regeneration follows lost completion response.

The retained ACK exists after local COMMIT but is NOT deliverable then. Operational delivery SHALL require confirmed local COMMIT, confirmed exact checkpoint publication, confirmed exact original permit completion and current qualified operational fencing/activation/time rules allowing delivery. Current evidence unavailable or superseded forbids delivery, even for historical replay. Historical ACK event bytes SHALL not change. Lost delivery after all gates resolved SHALL use only exact retained ACK bytes when those current delivery gates still hold; never regenerate from later state or execute another transition. No second local finalization transaction is required.

## 11. Failure matrix

YES for a new command means only that the stated failure creates no additional gate; all existing admission gates still apply. NO means intake fenced or unresolved authority bars it. Automatic retry refers to state-changing effects, not read-only original-operation queries.

| Condition | Local state | External state | ACK? | New command? | Automatic retry? | Required next owner/action |
| --- | --- | --- | --- | --- | --- | --- |
| Permit invalid | No transition | Invalid/unqualified; unresolved acquisition, if any, retained | NO | NO | NO | IL.5 reject/fence; IL.7 if external outcome unresolved. |
| Permit expired | No transition | Original permit cannot authorize consumption | NO | NO | NO | Fence; original permit closure/reconciliation under existing authority. |
| Trusted-time overlap | No transition | Validity cannot be proven | NO | NO | NO | Clock qualification gate; IL.7 for existing unresolved operation. |
| Stale revision | No transition; confirmed rollback | Acquired permit, if any, not implicitly completed | NO | NO until original permit definitively closed | NO | Reject; original-operation resolution, no revision rebasing. |
| Structural rejection | No transition; healthy handle | Same unresolved-permit rule | NO | NO until original permit definitively closed | NO | Reject; no diagnostic SUCCESS/ACK; resolve original operation. |
| Local transaction rollback confirmed | Exact pre-transition data | No checkpoint publication; permit unresolved unless proved closed | NO | NO until original permit definitively closed | NO | Retain cause; qualified original-operation closure/IL.7. |
| Local COMMIT outcome UNKNOWN | Durable outcome not inferred; handle poisoned | Publication SHALL NOT be initiated by IL.5 | NO | NO | NO | IL.7 reconcile actual local outcome and original permit; no assumed rollback. |
| COMMIT confirmed; checkpoint definitely rejected | Committed SUCCESS/ACK/STATE retained | Original publication proved rejected; permit unresolved | NO | NO | NO | RECOVERY_ONLY; IL.7 independently approved missing-successor resolution. |
| COMMIT confirmed; checkpoint UNKNOWN | Committed data retained | Original publication may have succeeded | NO | NO | NO | RECOVERY_ONLY; read original operation, IL.7 after restart. |
| Checkpoint confirmed; completion definitely rejected | Committed data retained | Checkpoint selected, original permit not successfully closed | NO | NO | NO | RECOVERY_ONLY; IL.7 original completion reconciliation. |
| Checkpoint confirmed; completion UNKNOWN | Committed data retained | Permit may already be closed; do not infer | NO | NO | NO | RECOVERY_ONLY; query original completion. |
| All gates resolved; ACK delivery lost | Exact retained ACK unchanged | Publication/completion confirmed | YES, only current delivery gates | YES, only current admission gates | NO new state-changing retry; exact ACK redelivery only | Historical replay/delivery path; no new permit or checkpoint for replay. |

Pre-local rollback/rejection closure SHALL NOT invoke the successful completion capability with an invented checkpoint. If existing authority offers no qualified definitive closure for an unused permit, remain fenced and defer to IL.7; this amendment does not invent cancellation or automatic permit renewal.

## 12. Future in-transaction admission seam (IL5-02)

A separately authorized implementation SHALL add only a narrow synchronous admission seam after BEGIN IMMEDIATE and required writer-scoped durable rereads, before any mutation. Existing command_id lookup, retained-completion validation and exact replay/mismatch return SHALL precede the seam. A historical replay SHALL NOT invoke new-transition admission or obtain a fresh command permit. Operational replay delivery remains subject to section 10.

The seam SHALL receive already-acquired qualified external evidence/envelope and a fixed typed view of current writer-scoped reservation/revision, metadata STATE/head/generation and required claims/artifacts. It SHALL recheck exact activation/host/checkpoint/permit/command/approval binding, expected revision, qualified permit/time bounds and existing fencing facts. Structural validation remains the existing single shared contract rule; the seam SHALL NOT duplicate it. Evidence constructors alone prove no qualification.

The seam SHALL perform no network/external I/O, credential lookup, permit acquisition, checkpoint action or mutable external call. It SHALL not authenticate operators, regenerate COMMAND or ACK, own COMMIT, run recovery, accept arbitrary SQL or expose a raw connection. Its result SHALL be only typed admission success or finite typed rejection with the bounded already-qualified evidence/facts needed by completion. Exceptions/unavailable implementations reject before writes. This is not an arbitrary transaction mutation callback. Exact interface implementation and tests require separate authorization.

## 13. Future typed capabilities (IL5-03)

Only the following minimum additive typed surface is authorized conceptually, not implemented:

- Resolve/read exact authoritative predecessor checkpoint evidence and original permit/admission envelope by the exact retained identities.
- Associate/resolve the one exact candidate bytes/digest with the original publication operation; submit those exact bytes under exact predecessor CAS and current permit authority.
- Return structured CONFIRMED / DEFINITELY_REJECTED / UNKNOWN publication evidence under section 9; query original publication without resubmitting.
- Complete the original permit/service operation with the exact command and confirmed checkpoint; return/query structured original completion evidence without creating another operation.

Unavailable/default implementations SHALL reject/fail closed before an effect. Once an effect has been sent, inability to obtain qualified evidence SHALL classify UNKNOWN rather than fabricate rejection. Authenticated bound results and retained exact candidate bytes SHALL be checked, not opaque success booleans. No concrete provider, credentials, transport, CLI or provider serialization is selected. These additions SHALL preserve existing IL.2 values/qualification meanings; required implementation interface adaptations remain separately authorized.

## 14. Durable state and increment boundaries

The six existing local tables remain the durable command-state model. No pending-command table, checkpoint-status column, index/trigger/migration or second local distributed-transaction journal is authorized merely for IL.5. External protected systems retain original operation evidence as specified. A later independently reviewed proof of insufficiency is required before broader local storage changes.

IL.7 owns startup and authoritative-history reconciliation, sent-but-unknown resolution after restart, missing-successor recovery, fenced restore, approved resumption and genesis recovery. IL.5 produces/fences unresolved states and supplies exact evidence; it SHALL NOT silently implement IL.7. IL.8 owns operator authentication, login, credential storage, interactive CLI and secret handling.

Normal IL.5 requires a proven mutation-eligible current generation and matching current checkpoint. It SHALL NOT implement generation/STATE/predecessor fallback, replacement activation or two-pointer cutover completion. Genesis ABSENT-to-generation-one activation, bootstrap package/CAS, restore and replacement ceremonies are out of scope. No production clock/provider choice, fixture eligibility/lifecycle policy, recovery authorization or external managed fixture mutation is added.

## 15. Security invariants and non-operation

IL.5 SHALL fail closed: no synthetic authority/checkpoint evidence, success from UNKNOWN, blind retry, duplicate external effect, stale permit/revision acceptance, premature ACK, ACK regeneration, generation/predecessor fallback or external I/O in a writer transaction. Confirmed local commands SHALL NOT be rolled back because external publication failed. UNKNOWN SHALL NOT become absence.

No Python, tests, schema, provider, credential/auth, CLI, clock-selection, IL.7 recovery, genesis or replacement implementation is authorized by this draft. Runtime remains NOT ACTIVATED. No operational SQLite/register or managed DB is accessed; no STRIX is run. Existing IL.4B and all published authority remain unchanged.

## 16. Exact canonical vectors and self-review

The examples below are synthetic encoding/reconstruction fixtures, not approvals, permits or operational success evidence. Their exact hashes test canonical construction. Qualification and real durable STATE/event provenance remain mandatory independently. No published IL.4A vector is changed. Complete hex and derivations follow below.

Self-review SHALL reject any unspecified field, optional state, timestamp source, permit identity, approval applicability, reconstruction source, predecessor, outcome class or delivery gate. All choices are closed in sections 3-13. IL5-01 is resolved only at proposed authority-design level; IL5-02/03 constraints are specified but no interfaces are implemented. Independent review/adoption and separately authorized implementation remain required.

### 16.1 Normal successor and command/permit reference

Use the published protocol COMMAND c, ACK and Completed-command STATE-2 fixtures verbatim. Synthetic retained predecessor inputs are revision 0, event head 0/genesis and digest 33 repeated 32 bytes; these inputs do not create or authorize genesis. Required external inputs are host h, permit EvidenceReference(p,44 repeated bytes), representation authority EvidenceReference(state-authority,55 repeated bytes), admission EvidenceReference(admission,66 repeated bytes), and applicable stable approval ID approval resolving the COMMAND approval hash 33 repeated bytes. Fixed UTC/ACK.issued_at is 0. C_success has revision 1, event sequence 3, the published ACK final digest and published completed STATE digest. Qualification is simulated input only: this example proves exact successor construction, not real permission or operational closure.

N_c reference: 253 bytes; SHA256 `f4792a0f8e77ec375e0467b0bb114300d606442f0130dfd41834f2e2fee2e4f3`.

```text
4a4f55532d464958545552452d4c4541534501120000000a000000016300000020f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc500000001700000002044444444444444444444444444444444444444444444444444444444444444440000000168000000224a4f55535f434f524531415f53544154455f524550524553454e544154494f4e5f320000000f73746174652d617574686f726974790000002055555555555555555555555555555555555555555555555555555555555555550000000961646d697373696f6e000000206666666666666666666666666666666666666666666666666666666666666666
```

C_success: 460 bytes; SHA256 `c976358de765d6337e3f8c8b48e9e62a7f43b7e5df21857ced144a297a06c7a7`.

```text
4a4f55532d464958545552452d4c4541534501070000000b000000016700000008000000000000000100000001780000000800000000000000010000000800000000000000030000002054c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d00000020435d2954bab863c77ee75fd20f72a17be42550057386c62379b9857d3c0652fd000000080000000000000000000000203333333333333333333333333333333333333333333333333333333333333333000000fd4a4f55532d464958545552452d4c4541534501120000000a000000016300000020f58d835a11128e077af416cda614e8e3ba9947da072ef4ce2e33a87751e07fc500000001700000002044444444444444444444444444444444444444444444444444444444444444440000000168000000224a4f55535f434f524531415f53544154455f524550524553454e544154494f4e5f320000000f73746174652d617574686f726974790000002055555555555555555555555555555555555555555555555555555555555555550000000961646d697373696f6e0000002066666666666666666666666666666666666666666666666666666666666666660000000901617070726f76616c
```

### 16.2 Linked NOT_APPLICABLE approval example

COMMAND d is RECORD_EXECUTION, principal p, same g/generation 1/x/r/s/binding a/authorization z, expected revision 0. Root approval hash is 88 repeated bytes; primary/supporting evidence is R(e,PROVENANCE_EVIDENCE,77 repeated bytes), execution_state STARTED; every other optional parameter is absent. The required root artifact approval remains present while additional independent transition approval is NOT_APPLICABLE.

EVENT 4 is EXECUTION_RECORDED; EVENT 5 is ACKNOWLEDGED. Both use d/r/g/1/x, UTC 1, revision 1, binding artifact a and evidence e. Event 4 prior_digest is the published c ACK final digest; event 5 prior_digest is SHA256(EVENT 4). ACK d is the published ACK with only command_id/payload hash, revision 1, approval hash 88 repeated bytes, evidence R(e), issued_at 1, first/final/count 4/5/2 and final digest replaced; key-set digest remains the exact empty-set digest.

Resulting STATE is the published completed-command fixture with metadata.last_valid_utc=1, reservation revision=1/execution_state=STARTED, and appended SUCCESS CommandRow d containing these exact COMMAND/ACK bytes, principal p, expected_revision=0, target r and transition_event_sequence=5. Every other field/row is unchanged. Command ordering is c then d. This is the same synthetic framing projection used by published vectors, not a proof of complete operational blocking claims.

C_not_applicable uses checkpoint revision 2, head 5 and its final event digest, resulting STATE digest, UTC 1, predecessor SHA256(C_success), permit(p2,99 repeated bytes), admission(admission2,aa repeated bytes), unchanged host/STATE authority and approval byte 00. Synthetic qualified inputs do not confer real permission.

COMMAND d: 785 bytes; SHA256 `cb000e52112b845e91abe827de5a716a64d539d6156129becd71802d2e7e2ba5`.

```text
4a4f55532d464958545552452d4c45415345010500000012000000105245434f52445f455845435554494f4e0000000170000000016700000008000000000000000100000001780000000164000000017200000008000000000000000000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f524551554553540000002011111111111111111111111111111111111111111111111111111111111111110000000173000000594a4f55532d464958545552452d4c4541534501110000000300000001610000001450524f564953494f4e494e475f52455155455354000000201111111111111111111111111111111111111111111111111111111111111111000000208888888888888888888888888888888888888888888888888888888888888888000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000005c000000014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e4345000000207777777777777777777777777777777777777777777777777777777777777777000000ff4a4f55532d464958545552452d4c4541534501100000000900000001720000000100000000010000000008015354415254454400000001000000005c000000014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e43450000002077777777777777777777777777777777777777777777777777777777777777770000000100000000010000000059014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e4345000000207777777777777777777777777777777777777777777777777777777777777777
```

EVENT 4: 163 bytes; SHA256 `1a51e72405b19119dedbfbe2ebc2c6b242f87eff66b47aac91823a792be8c47c`.

```text
4a4f55532d464958545552452d4c4541534501060000000c00000008000000000000000400000001640000000201720000000167000000080000000000000001000000017800000012455845435554494f4e5f5245434f524445440000000800000000000000010000002054c6b63a0197ad58ca73c6ea0044c090a7fe3c90c022c7069ad18727538ea47d000000080000000000000001000000020161000000020165
```

EVENT 5: 157 bytes; SHA256 `3438dfeb7c037b8e861853cceae16cedba86c2fae9c6a4d0f049227100acda99`.

```text
4a4f55532d464958545552452d4c4541534501060000000c0000000800000000000000050000000164000000020172000000016700000008000000000000000100000001780000000c41434b4e4f574c4544474544000000080000000000000001000000201a51e72405b19119dedbfbe2ebc2c6b242f87eff66b47aac91823a792be8c47c000000080000000000000001000000020161000000020165
```

ACK d: 616 bytes; SHA256 `4dab1c70efb3feb69042b397708537411a0c2b119426016669c79122c04dfe80`.

```text
4a4f55532d464958545552452d4c45415345010a0000001a000000016400000020cb000e52112b845e91abe827de5a716a64d539d6156129becd71802d2e7e2ba50000000170000000016700000008000000000000000100000001780000000172000000080000000000000001000000017000000014464958545552455f50524f564953494f4e494e470000001d5052455f415554485f50524f564953494f4e494e475f524551554553540000001450524f564953494f4e494e475f5245515545535400000020111111111111111111111111111111111111111111111111111111111111111100000020df3f619804a92fdb4057192dc43dd748ea778adc52bc498ce80524c014b81119000000208888888888888888888888888888888888888888888888888888888888888888000000524a4f55532d464958545552452d4c45415345011100000003000000017a0000000d415554484f52495a4154494f4e0000002022222222222222222222222222222222222222222222222222222222222222220000005c000000014a4f55532d464958545552452d4c4541534501110000000300000001650000001350524f56454e414e43455f45564944454e434500000020777777777777777777777777777777777777777777777777777777777777777700000008000000000000000100000008000000000000000000000008000000000000006400000008000000000000005a000000080000000000000004000000080000000000000005000000080000000000000002000000203438dfeb7c037b8e861853cceae16cedba86c2fae9c6a4d0f049227100acda990000000753554343455353
```

C_not_applicable: 454 bytes; SHA256 `1fea19201a0f738c8b014c2c2d56e5edeec88055c942361fdbdfbdcf6445e7cc`.

```text
4a4f55532d464958545552452d4c4541534501070000000b00000001670000000800000000000000010000000178000000080000000000000002000000080000000000000005000000203438dfeb7c037b8e861853cceae16cedba86c2fae9c6a4d0f049227100acda9900000020eaf7f9378718deb706e74a9910fc3e7520cc0bffa6852eb0efebbc4bb39ef1c300000008000000000000000100000020c976358de765d6337e3f8c8b48e9e62a7f43b7e5df21857ced144a297a06c7a7000000ff4a4f55532d464958545552452d4c4541534501120000000a000000016400000020cb000e52112b845e91abe827de5a716a64d539d6156129becd71802d2e7e2ba50000000270320000002099999999999999999999999999999999999999999999999999999999999999990000000168000000224a4f55535f434f524531415f53544154455f524550524553454e544154494f4e5f320000000f73746174652d617574686f726974790000002055555555555555555555555555555555555555555555555555555555555555550000000a61646d697373696f6e3200000020aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa0000000100
```

Resulting STATE-2: 3415 bytes; SHA256 `eaf7f9378718deb706e74a9910fc3e7520cc0bffa6852eb0efebbc4bb39ef1c3`. Reconstruct using the exact delta above and the published STATE fixture, without changing STATE grammar.

### 16.3 Predecessor and deterministic reconstruction

Discard process-local values after confirmed local COMMIT. Reload the exact original permit/envelope and retained command/ACK/events/STATE inputs above. Sections 3-8 SHALL reproduce C_success and C_not_applicable byte-for-byte with the exact lengths/digests above; new wall-clock values SHALL NOT enter reconstruction. C_not_applicable predecessor SHALL equal SHA256 of the complete C_success bytes, not a command/STATE hash or another observed checkpoint.

Changing predecessor, COMMAND digest, principal through canonical COMMAND, permit pair, host, representation binding, admission pair, UTC or approval state changes the candidate bytes and/or invalidates evidence agreement. Wrong predecessor CAS SHALL NOT confirm success. Approval 00 for ACQUIRE or 01 for RECORD_EXECUTION SHALL reject; UNKNOWN has no candidate encoding. Exact-byte reconstruction is mandatory even when a digest is supplied.
