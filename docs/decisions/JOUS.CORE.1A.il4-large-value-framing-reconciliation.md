# JOUS.CORE.1A IL.4 large-value / retained-state framing reconciliation

Status: narrow documentation authority candidate. Unapproved; independent review and explicit adoption are required. This document defines a proposed representation transition only, not implementation or execution authority.

## 1. Controlling authority and demonstrated contradiction

Primary authority is `docs/decisions/JOUS.CORE.1A.fixture-lease-implementation-design.md`, published blob `706b6bf782701a602012bd1fed75099f519a53ee`:

- Section 8, canonical-frame paragraph: ASCII JOUS-FIXTURE-LEASE, version byte 1, domain byte, uint32 big-endian field count and uint32 big-endian byte length per field; reject field lengths above 65,535. The length prefix is 32-bit, NOT 16-bit; the 65,535 bound is an additional validity rule.
- Section 8, collection paragraph: a collection is a field containing uint32 item count and recursively framed items. STATE tag 8 has metadata, reservations, claims and commands, in that order.
- Section 6, canonical-state paragraph: STATE covers all other metadata, reservations and claims, plus command outcomes including exact acknowledgement bytes; only its own stored digest and metadata event-head/digest fields are excluded. History is retained, not truncated.
- Section 3, COMMANDS/EVENTS table: completed outcomes and audit history are append-only. Section 4 requires authoritative RELEASE/RECOVERY transactions and durable outcomes; serialization cannot strand claims by exhaustion of an invented history budget.

Published IL.3 `services/api/infrastructure/fixture_lease_store.py`, blob `a0d9ff39207ad8bc39016e688d59bc17ee290be2`, defines MAX_BYTES = 1,048,576 and permits that width for BLOB domains, including ReservationRow.immutable_db_projection, CommandRow.canonical_payload_bytes and durable_ack_bytes. `_column` and `_validate` implement those limits; `_validate_row` verifies projection/payload hashes without a smaller framing capacity.

A single 1,048,576-byte projection cannot be one v1 field bounded at 65,535. A command-history field holding 4,097 required 32-byte payload hashes needs 131,104 bytes for those hashes alone, excluding row fields, counts and framing. Even streaming unchanged v1 bytes cannot satisfy that field bound. Independently, uint32 collection count cannot express indefinitely retained history without eventual exhaustion. These are representability contradictions, not memory-allocation problems.

## 2. Compatible segmentation analysis and classification

A segmentation construction could use bounded v1 fields as primitives, but it changes the bytes of the enclosing logical value/collection: segment metadata replaces a single length-and-value field, and changes field count or the fixed collection layout. Neither a segmentation domain tag, segment layout, continuation convention nor aggregate exception is currently authorized.

Classification:

| Object | Published aggregate rule | Classification and consequence |
| --- | --- | --- |
| IL.1 conflict key | exact v1 fixed fields and full bytes | B: cannot segment or reinterpret; remains unchanged |
| COMMAND and EVENT frames | v1 primitive framing fixed in design section 8 | B: no compatible global v1 redefinition; this candidate leaves them v1 |
| STATE top-level collection fields | tag 8, four fixed fields, count plus framed members | B: segmentation changes the fixed aggregate envelope, even though detailed row closure remains pending |
| Scalar BLOB field inside STATE projection | fixed v1 length/value primitive applies | B: splitting it changes that field's bytes |
| Detailed STATE row field lists | additional IL.4 closure pending, constrained by published storage and design | A for still-open field-level details only; this does not erase B at the enclosing framing layer |

Therefore compatible v1 segmentation does NOT solve the contradiction. No segmentation is adopted. No segment size, ordinal, count, reconstruction or segment hash is defined. The fallback below is an explicit STATE-only version transition; it does not disguise a byte change as a clarification of v1.

## 3. Minimum explicit transition: STATE representation 2 only

Only the STATE digest projection and its internal projected-record framing change to representation version 2. COMMAND, EVENT, CHECKPOINT, APPROVAL, artifact bytes/hashes, ACK authority and IL.1 conflict keys do not change under this document. No full COMMAND/EVENT/ACK schema is introduced here; their remaining protocol findings stay separate.

New STATE uses the same ASCII prefix and tag 8, but version byte 2 declares a deliberately different streaming aggregate grammar. It is NOT the rejected protocol candidate's generic v2 framing. This is not a global meaning of v1 or v2 for other object tags. Unknown version/tag combinations reject.

An authoritative generation selects exactly one STATE representation through the existing immutable generation protocol binding. The controlling transition authority is the published `JOUS.CORE.1A.replacement-generation-cutover-amendment.md`, commit `247b376c6fc2fe1879d2b962a4dc5f1b1168af73`, blob `6068c9c92504d7f8651da4286a7ee3f9c4440ef9`, especially sections 4-9. This section specializes that authority for STATE selection; it neither duplicates nor changes the replacement ceremony.

### 3.1 Closed generation binding

The exact permitted `state_representation_id` values under this proposed authority are `JOUS_CORE1A_STATE_REPRESENTATION_1` and `JOUS_CORE1A_STATE_REPRESENTATION_2`. They select the existing published STATE-1 grammar and section 4's STATE-2 grammar respectively. No aliases, normalization, numeric substitutes or unknown values are accepted. These external semantic identifiers do not replace any wire version byte or enter the STATE-2 grammar as an additional field.

For a successor using this authority, the mandatory `new_generation_protocol_binding` contains the exact representation identifier and `state_representation_authority_ref/hash` pinning the independently adopted representation authority, including this document's adopted identity for representation 2. The exact field-level projection authority is also pinned by the approved replacement package. The published binding key is (register_id, new_generation, new_activation_id); another activation cannot change the binding within that generation. Package integrity, independent approval, activation linkage and protected checkpoint evidence establish authority; merely constructing a binding does not.

Historical generation selection resolves through original approved evidence and the original published v1 rule, as permitted by cutover section 4. A historical package need not be rewritten to add these new labels. A generation whose approved binding selects representation 1 continues using v1. A newly qualified generation adopting representation 2 uses it for every state, small or large. Configuration, environment, negotiation, size, parser success, byte sniffing and fallback cannot select a representation. Missing or conflicting binding evidence requires RECOVERY_ONLY and rejection of mutation.

### 3.2 Exact replacement specialization

A representation change requires a new approved generation under the published replacement ceremony, never an in-generation switch. Required evidence is the exact current old generation/activation, final validated C_old/state/event/ancestry identity, fencing and reconciliation of outstanding permits/outcomes, immutable successor generation and activation, immutable successor protocol binding, exact successor STATE bytes/digest, exact C_new, exact independently approved replacement package, and protected non-current C_new. The existing activation-current CAS, checkpoint-current completion and startup validation are the only path to mutation eligibility. No alternate transition is authorized.

Final v1 state must verify under its own authority before replacement; unknown or unreconciled state cannot be repaired by encoding it as STATE-2. Derive the new projection from those reconciled authoritative source rows. APPROVED_ARTIFACTS, RESERVATIONS, BLOCKING_CLAIMS, COMMANDS and EVENTS carry forward unchanged, including exact payloads/ACKs, event history, revisions and keys. Generation and activation metadata change only as approved by the ceremony; last_valid_utc and recovery_required follow its explicitly approved projection. Register identity, schema and authority pins remain immutable. Metadata event-head/digest and stored state_digest exclusions remain unchanged. Thus identical business rows do not imply identical metadata, canonical STATE bytes or digest. No fake business command/event is required.

C_new binds the exact first STATE-2 digest and approved new metadata, with the existing checkpoint ancestry/revision rules and predecessor C_old, not a genesis sentinel. The replacement package integrity-binds the complete generation protocol binding and C_new; substitution of representation, source projection or digest after approval invalidates the transition. Exact package encoding/bytes must be independently pinned before ceremony implementation can execute. This document does not invent package wire encoding, checkpoint cryptography or dedicated capability implementation.

### 3.3 Cutover and two-pointer completion

The successful linearizable activation-current-pointer CAS is the generation cutover. Before it succeeds, the old generation remains authoritative subject to fencing. After it succeeds, the exact approved successor is authoritative and its immutable binding alone selects STATE interpretation. Activation cutover is NOT permission to mutate.

If activation points to the new generation while the checkpoint pointer still names C_old and C_new is protected but non-current, the new generation and its representation binding are authoritative; service remains RECOVERY_ONLY. There is no ordinary mutation, old-generation fallback, v1 fallback or alternate successor. Only exact reconciliation/completion under cutover sections 7-9, matching checkpoint-current proof and full startup validation can establish ACTIVE eligibility. Ordinary authorization gates remain independently necessary.

### 3.4 Restart and outcome authority

The following are evidence classifications, not additional lifecycle or issuer modes. Every case uses the published authoritative external current/history evidence, exact immutable approval/package/binding, checkpoint ancestry, and reconciled local register. Process memory and prior ACK receipt are never authority.

| Evidence on restart/reconciliation | Generation / representation | Mode and required behavior |
| --- | --- | --- |
| No replacement started | exact externally proven current generation and its original binding | ordinary startup gates; no inference from local absence |
| Prepared; publication not attempted | exact old generation/binding if externally proven | RECOVERY_ONLY; retain evidence; separately approved continuation or cancellation/resumption |
| Activation publication proven failed; old pointers exact | old generation and old representation | RECOVERY_ONLY; reconcile and obtain independent resumption approval/startup proofs; candidate STATE-2 is not current |
| Activation outcome unknown | neither generation nor representation may be guessed | RECOVERY_ONLY; authoritative reads/reconciliation; no new allocation or retry |
| Exact successor activation proven, ACK lost | original approved successor and exact successor binding | recognize original success; no republish, re-encoding or additional generation; complete checkpoint/startup proofs |
| Successor activation proven, checkpoint completion unknown or old | successor and exact successor representation | RECOVERY_ONLY; validate/reconcile exact C_new completion; no v1 fallback |
| Both pointers exact intended successor/C_new | successor and exact successor binding | RECOVERY_ONLY until full startup proofs; only then ACTIVE eligibility |
| Local says successor, external still exact old | old evidence controls; local successor claim rejected | RECOVERY_ONLY; resolve submission outcome and evidence; no local override |
| Unexpected third authority, CAS conflict, malformed package or ancestry/binding mismatch | no qualified local mutation authority | RECOVERY_ONLY; independent reconciliation; no adoption, repair or fallback |

CAS conflict is not success. Lost acknowledgement is resolved by exact authoritative identity recognition, not another publication. Failed/prepared candidates and approvals remain immutable retained audit evidence as required by published authority; this document authorizes no cleanup. Recovery/restore must prove current generation, immutable binding, checkpoint ancestry and corresponding STATE digest before mutation. Missing/inconsistent evidence fences mutation.

Historical verification uses the historical generation's original representation evidence, never the current successor algorithm. No historical STATE digest/checkpoint, COMMAND/EVENT/ACK bytes or artifact identity is rewritten. Completed ACK bytes project verbatim into STATE-2; representation transition does not change command replay identity or re-execute replay.

### 3.5 R-01 sufficiency and counterexamples

Two conforming implementations must resolve generation from the same protected activation evidence, representation from its exact approved immutable binding, digest from its matching checkpoint/projection, and mutation eligibility from checkpoint completion plus startup/ordinary gates. Unknown outcomes require RECOVERY_ONLY in both. This rejects: two representations for one generation; size-based selection; mutation during the two-pointer gap; successor allocation after lost ACK; memory-dependent restart; representation substitution after approval; predecessor fallback after cutover; historical v1 reinterpretation; history ceilings beyond 4,096 rows; and loss of a permitted 1 MiB value to enclosing overhead. The last two follow the unchanged sections 4-6, not a selection heuristic.

This R-01 specialization does not authorize execution, STATE-2 activation, IL.4 implementation or dedicated ceremony capabilities. It does not resolve the separate protocol candidate's F-03 EXPIRED ordering or F-04 evidence selection.


## 4. Exact STATE-2 streaming grammar

Byte notation: P = ASCII JOUS-FIXTURE-LEASE (18 bytes). U32(n) is exactly four unsigned big-endian bytes. No locale/native serialization. All existing numeric/text/UUID/enum value encodings and exact-byte identity rules remain controlling; this document changes enclosing STATE framing only.

The complete canonical STATE-2 stream is:

P || 02 || 08 || U32(4)
|| 02 || R12(metadata)
|| 03 || C13(reservations)
|| 03 || C14(claims)
|| 03 || C15(completed-command outcomes)

02 denotes a single required record. 03 denotes a collection. These bytes are aggregate structural discriminators, not lifecycle/operation values. There is no top-level collection byte-length field or uint32 retained-row count.

A projected record Rtag(values) is:

P || 02 || tag || U32(exact schema field count)
|| for each schema-ordered value: U32(encoded-value byte length) || encoded-value bytes.

Record tags are 12 metadata, 13 reservation, 14 blocking claim, 15 completed command; valid ONLY inside STATE-2. Their exact field lists, types, optional status and inclusion/exclusion remain the published IL.3 row projections constrained by design section 6. Metadata excludes state_digest, last_event_sequence and last_event_digest and includes every other MetadataRow field. Every ReservationRow and ClaimRow field participates. Every completed CommandRow field participates, including raw exact retained payload and ACK bytes, never replacement digests. Later bounded protocol closure must enumerate those field lists without changing this framing.

Ctag(rows) is the concatenation, for each canonically ordered row, of:

01 || Rtag(row)

followed by exactly one 00 end-of-collection byte. An empty collection is exactly 00. 01 is a row-start marker; 00 is a collection terminator. There is no alternate count-based collection, padding, optional terminator or aggregate total-length encoding. Row framing is self-delimiting through its fixed field count and value lengths. Marker bytes inside length-delimited values have no structural meaning.

Records sort by the published authoritative key: reservation ID exact UTF-8 bytes, full canonical conflict-key bytes, command ID exact UTF-8 bytes. Metadata is the single required singleton. Reject duplicate/non-increasing keys, wrong tag, schema field count or malformed value. SQL row order and locale are irrelevant. No row-count maximum exists in this grammar.

Primitive projected values retain existing domains. Nullable fields retain the controlling explicit one-byte presence marker plus their framed field representation: absent encoded value is 00; present encoded value is 01 followed by the existing exact value bytes, inside the enclosing U32 length. Required scalar bytes have no optional wrapper. An IL.3 BLOB of 1,048,576 bytes remains exactly those bytes; an optional present BLOB encodes as 1,048,577 bytes including its presence marker. That marker is framing overhead, not expanded stored-value authority.

Required BLOB capacity remains 1 through 1,048,576 bytes where IL.3 requires nonempty data. Empty logical aggregates are allowed only where the projection permits an empty collection; this candidate does not legalize empty required BLOBs. Text retains its existing bounded exact UTF-8 capacity; digests are 32 bytes; keys retain full v1 bytes. The record U32 length can encode all these values plus optional overhead. Boolean-like IL.3 INTEGER values remain encoded by the published unsigned 64-bit integer primitive, restricted to 0 or 1; they are not narrowed to a one-byte value. Unknown enums, invalid integers/bool coercion, invalid optional markers or malformed keys reject.

## 5. Capacity arithmetic; no segment-size fiction

No encoded segment is placed in a v1 field: this explicit version transition removes that aggregate requirement for STATE-2 only. The v1 65,535 per-field rule still applies everywhere v1 remains selected. A v1 eligible field of length 65,535 accepts; 65,536 rejects. Complete v1 frames are not capped at 65,535 by substituting a whole-object limit.

STATE-2 scalar encoded lengths use U32 with representable maximum 4,294,967,295. They do NOT grant new data capacity: the largest stored BLOB remains 1,048,576, optional encoding 1,048,577. The largest required raw value therefore has field wire length 4 + 1,048,576 = 1,048,580; an optional present value has 4 + 1 + 1,048,576 = 1,048,581. Enclosing record/header bytes are additional stream bytes, not deducted from scalar capacity.

For a record with k fields and encoded lengths Li:

record length = 24 + 4k + sum(Li).

The 24-byte header is 18-byte prefix + version + tag + four-byte field count. A collection row adds one marker byte. No enclosing record-length or collection-length maximum causes overhead to invalidate a permitted scalar. CommandRow's two large BLOBs can both retain their existing independent capacities; the aggregate record may exceed 1 MiB without being stored in a 1 MiB column.

IL.3's maximum 1 MiB canonical_payload_bytes and durable_ack_bytes still applies to those stored complete objects. This amendment makes their existing bytes representable IN STATE; it does not enlarge COMMAND/ACK storage or permit a newly constructed object to exceed its existing column limit. Event/checkpoint construction and ACK semantics are untouched.

## 6. Streaming, completeness and retained history proof

state_digest_2 = SHA256(the complete canonical STATE-2 stream). The version/domain prefix occurs exactly once at the root plus the specified nested record headers. No other prefix, aggregate hash substitution or processing-chunk metadata is hashed. Implementation reads or SHA256 update chunk sizes never appear in canonical bytes.

Use a consistent authoritative transaction snapshot. Emit sorted rows one at a time, incremental field bytes as needed, then the prescribed terminators. Memory need not scale with retained history: one bounded record/value window and incremental SHA-256 context suffice. Collection length/count is not accumulated or encoded. Any implementation-local row counter is diagnostic and must not overflow into a protocol rejection of otherwise valid history.

The stream is accepted only if all four components and all collection terminators are complete, no trailing bytes exist, all durable snapshot rows were included, and the resulting digest equals the exact independently protected checkpoint/state expectation. A forged early terminator with omitted rows must fail comparison against authoritative snapshot cardinality/completeness evidence and protected digest; syntax alone cannot prove a full history. Never treat syntactic termination as external authority.

No finite retained-row count or aggregate byte cap exists. For every finite valid history H, appending one finite valid completed command record remains representable as the same ordered collection grammar with one extra 01/R15 item before its terminator. RELEASE/RECOVERY can append their result and updated projections regardless of whether H has 4,096, 4,097 or more commands. Claims cannot become stranded due solely to protocol history capacity. This is a representation guarantee, not a claim of infinite disk, unlimited runtime resources or immunity to storage outage. Resource exhaustion remains fail closed and subject to published reconciliation, never history deletion or automatic availability.

## 7. Identity and migration consequences

STATE-2 bytes/digests intentionally differ from STATE-1 even for small states. This is an explicit authority transition, not byte-compatible clarification. Prior digest identities stay historical and must never be overwritten or relabeled. The transition package links the old exact checkpoint/state digest to the new representation and exact new digest under independently approved activation/CAS authority.

IL.1 conflict-key bytes/hashes, artifact identities, genesis event anchor SHA256(ASCII("JOUS-FIXTURE-LEASE-GENESIS-V1")), M-04 acquisition semantics and existing command/event/ACK bytes remain unchanged. Full existing COMMAND bytes remain replay authority; never normalize them across versions. This candidate does not introduce a command protocol version transition, so there is no cross-version command replay equivalence.

Historical STATE verification uses its pinned version; current verification uses exactly the generation-selected version. Supplying v1 as current when v2 is selected rejects as downgrade. Supplying unapproved v2 under v1 rejects. Historical v1 material is verified unchanged only for historical evidence, never as current authority. If old state could never be represented validly, transition cannot manufacture a valid old digest; reconciliation and explicit independent authority are required.

No schema migration or new column is required for representation logic: IL.3 stores only a 32-byte state digest; STATE records/collections are computed streams, not aggregate stored BLOBs. Existing scalar rows retain their values and widths. No existing valid row becomes invalid solely due to STATE wrapping. Published IL.1/IL.2/IL.3 implementations and tests require no edits in this task. Future canonicalization and separately reviewed generation-transition orchestration are necessary; this is not a claim that those implementations exist.

## 8. Boundary table and future tests

| Boundary | Deterministic result |
| --- | --- |
| Empty allowed collection | STATE-2 C = 00; no absent/omitted alternative |
| Required raw BLOB length 0 | reject under existing nonempty stored-value domain |
| Raw BLOB length 1 | STATE-2 field = U32(1) plus exact byte |
| Raw BLOB length 65,535 | v1 primitive accepts if its domain permits; STATE-2 accepts |
| Raw BLOB length 65,536 | v1 primitive rejects; STATE-2 accepts if IL.3 domain permits |
| Raw BLOB length 1,048,576 | STATE-2 accepts with all overhead outside raw capacity |
| Raw BLOB length 1,048,577 | reject as stored value; do not confuse with legal optional framing length |
| 4,096 completed commands | full ordered history remains representable |
| 4,097 completed commands | remains representable; no count-width or total-field-length cap |
| Later RELEASE/RECOVERY | additional outcome remains representable; no history-cap rejection |

There is no first size requiring a different STATE version: all sizes use STATE-2 in a selected generation. 65,536 is the first raw value exceeding v1 primitive capacity, not a version-selection threshold. Supplementary large values do not change conflict/artifact identity. Future tests must compare hashing the exact complete stream against incremental updates of 1, 7, 65,535 and larger processing windows; digests must match. No protocol chunk/segment identity exists.

## 9. Security rejection rules

This design uses no protocol segments. Missing/duplicate/reordered rows, inconsistent schema counts, truncated field bytes, wrong U32 lengths, malformed/oversized scalar values, unknown versions/tags, alternate optional forms, missing terminators, trailing bytes, duplicate keys or incomplete authoritative snapshot coverage reject. A purported segment envelope/ordinal/count is unknown protocol material and rejects, rather than being repaired or reassembled.

There is no declared aggregate total length or retained-row count to overflow. Fixed U32 scalar lengths/field counts must be validated exactly before allocation; arithmetic overflow in a parser rejects, never wraps/clamps. Streaming must consume every declared byte and expected row; implementation buffer boundaries are not protocol boundaries. No automatic repair, omission, truncation, alternate encoding or fallback to v1 is permitted.

## 10. Existing candidate/vector impact and containment

The existing `JOUS.CORE.1A.il4-command-event-state-protocol-amendment.md` remains unchanged at 36,650 bytes, SHA256 `c09b5e52eeb48ac12cd5d7182b5d421171b8d81d9b9c771453fad3a7f0affb65`, 349 LF / 0 CR. It remains rejected; this amendment does not approve it.

Its seven vectors are classified individually:

- Vector 1 COMMAND: invalid as normative published-v1 protocol because it uses the rejected generic v2 frame. Requires later recomputation under separately remediated COMMAND authority; this STATE-only amendment does not fix it.
- Vector 2 first EVENT, vector 3 subsequent EVENT and vector 3a ACKNOWLEDGED EVENT: likewise invalid generic-v2 event representations; require later v1 recomputation and chain-dependent digest recomputation.
- Vector 4 ACK: requires later recomputation because command/event references change, independent of STATE transition; ACK semantics are not redesigned here.
- Vector 5 minimal STATE and vector 6 completed-command STATE: invalid under this STATE-2 grammar, require recomputation under the selected STATE representation and later remediated exact row/ACK authority.

None of those seven becomes an approved byte-identical vector through this amendment. All remain untouched as reviewed evidence. This does not rewrite any published vector/hash; those vectors are from an untracked rejected candidate.

F-03 EXPIRED ordering and F-04 evidence selection remain open and out of scope. M-04 remains exactly acquisition expected_revision integer 0, transactional absence, initial revision 0; existing mutation matches durable revision and first later accepted mutation 0 -> 1; no UPSERT/adoption/sentinel.

This document does not authorize implementation, staging, publication, SQLite access/initialization, genesis, activation, external CAS execution, fixture provisioning, credentials/network/PostgreSQL/Supabase, checkpoint publication, production clock qualification, canary, STRIX or deployment. It establishes no operational current-state facts.

## 11. Fixed framing vectors

The scalar examples below are exact STATE-2 field fragments, not standalone reservation schemas or new independently authoritative hashed artifacts. Their SHA256 values are conformance diagnostics over exactly the displayed/generated bytes. Full STATE vectors use the required root grammar. No live IDs or operational state are supplied.

### Empty collection

Input: No members; exactly one terminator.

Canonical byte length: 1. SHA256: `6e340b9cffb37a989ca544e6bb780a2c78901d3fb33738768511a30617afa01d`.

```text
00
```

### One-byte scalar fragment

Input: Raw value byte 61 hex; U32 length followed by value.

Canonical byte length: 5. SHA256: `72ff6b02949dad95006c343e3db3150090d3afb49f6bbdb92fdc17607997a85c`.

```text
0000000161
```

### First v1-ineligible scalar

Input: Raw value = byte 61 repeated 65,536 times; fragment = U32(65,536) || raw.

Canonical byte length: 65540. SHA256: `5300d4722030294c3cc7e050d8874fbd1bef4afa26d44c5b2d8594d86076d629`.

The input generator and field formula above specify every byte; no protocol segmentation is present.

### Exact v1 boundary scalar

Input: Raw value = byte 61 repeated 65,535 times; fragment = U32(65,535) || raw.

Canonical byte length: 65539. SHA256: `6ffa531328fe1730a0dfcefea140a468818de99af4cb17c9d364fd89ef05e44c`.

The input generator and field formula above specify every byte; no protocol segmentation is present.

### Large scalar / 1 MiB

Input: Raw value = byte 61 repeated 1,048,576 times; fragment = U32(1,048,576) || raw.

Canonical byte length: 1048580. SHA256: `1d00d0dd34dc6c1092aab777156943700554924f6ef4d696c2b2fa300d14d93d`.

The input generator and field formula above specify every byte; no protocol segmentation is present.

### Minimal complete STATE

Input: Metadata singleton/schema 1; register synthetic-register; generation 1; activation synthetic-activation; authority pins 11,22,33,44 each repeated 32 times; last-valid UTC 0; recovery_required false; three empty collections.

Canonical byte length: 305. SHA256: `4e82e4bb28df386a7596b455aeeb9868349ba628cfd50911b44d513b162990a4`.

```text
4a4f55532d464958545552452d4c45415345020800000004024a4f55532d464958545552452d4c45415345020c0000000b0000000800000000000000010000000800000000000000010000001273796e7468657469632d72656769737465720000000800000000000000010000001473796e7468657469632d61637469766174696f6e000000201111111111111111111111111111111111111111111111111111111111111111000000202222222222222222222222222222222222222222222222222222222222222222000000203333333333333333333333333333333333333333333333333333333333333333000000204444444444444444444444444444444444444444444444444444444444444444000000080000000000000000000000080000000000000000030003000300
```

### Large logical collection, 4096 members

Generator: for i = 0 through 4095 in ascending order, derive a v1 FIXTURE_SET key with fields ASCII synthetic-target and ASCII synthetic-set- followed by the decimal i padded to exactly five digits; construct R14 fields [that full key, ASCII synthetic-reservation, U64(0), ASCII synthetic-artifact]; emit 01 || R14 for each, then 00. These are claim-collection framing fixtures, not assertions of an acquired fixture lifecycle.

Canonical byte length: 634881. SHA256: `8ee85f6ce4f41d27c91e42a4d14ed48fa9835b9ea64fadd051b049473aea3aca`. This crosses the old 65,535 aggregate bound without a segment boundary or count cap. The same collection construction applies to completed-command records; later field-level protocol tests must append a valid RELEASE/RECOVERY result after 4,097 commands.

### Large logical collection, 4097 members

Generator: for i = 0 through 4096 in ascending order, derive a v1 FIXTURE_SET key with fields ASCII synthetic-target and ASCII synthetic-set- followed by the decimal i padded to exactly five digits; construct R14 fields [that full key, ASCII synthetic-reservation, U64(0), ASCII synthetic-artifact]; emit 01 || R14 for each, then 00. These are claim-collection framing fixtures, not assertions of an acquired fixture lifecycle.

Canonical byte length: 635036. SHA256: `cf62ea6e2e8d783baf4ebe72fe15567c2602129522c8a7a5fc8a2185c212a1c4`. This crosses the old 65,535 aggregate bound without a segment boundary or count cap. The same collection construction applies to completed-command records; later field-level protocol tests must append a valid RELEASE/RECOVERY result after 4,097 commands.

### Large logical collection, 4098 members

Generator: for i = 0 through 4097 in ascending order, derive a v1 FIXTURE_SET key with fields ASCII synthetic-target and ASCII synthetic-set- followed by the decimal i padded to exactly five digits; construct R14 fields [that full key, ASCII synthetic-reservation, U64(0), ASCII synthetic-artifact]; emit 01 || R14 for each, then 00. These are claim-collection framing fixtures, not assertions of an acquired fixture lifecycle.

Canonical byte length: 635191. SHA256: `c5978683e5d54dbc357099e5e548288bf95a739051e3d3890165116ef594c8c3`. This crosses the old 65,535 aggregate bound without a segment boundary or count cap. The same collection construction applies to completed-command records; later field-level protocol tests must append a valid RELEASE/RECOVERY result after 4,097 commands.

### Completed-command history beyond 4,096: projection framing fixture

For each i starting at 0, CommandRow record R15 has these exact encoded values: ID ASCII synthetic-command- followed by i in five-digit zero-padded decimal; principal ASCII synthetic-principal; command kind ASCII RELEASE; canonical_payload_bytes ASCII synthetic-payload; canonical_payload_hash SHA256(ASCII synthetic-payload); expected_revision U64(0); reservation_id present marker 01 followed by ASCII synthetic-reservation; outcome ASCII SUCCESS; durable_ack_bytes present marker 01 followed by ASCII synthetic-ack; transition_event_sequence present marker 01 followed by U64(i+1). Emit rows in ascending i order as 01 || R15 then terminate with 00.

These test exact retained-column framing only; opaque payload/ACK placeholders do not prove a valid completed command under the later protocol authority. Full completion validation remains mandatory in operational use. The byte generator is exhaustive and every field encoding is fixed.

4096 rows: length 913409 bytes; SHA256 `c3a35a590491c56ecd2994bb51e03a91306998ceff6295b6514330213bcc0948`.

4097 rows: length 913632 bytes; SHA256 `0f5c7374fe8f0bc4a64fafba8a96f4c02fac01ac16a285441239668154836040`.

4098 rows: length 913855 bytes; SHA256 `a31f417e62d7fdb3b825d007d101cb1bfcdf30c5e8e7ca24b69fdbc0d368dc04`.

For valid completed-command records, appending a RELEASE/RECOVERY record uses precisely the same collection operation. The opaque fixture does not waive event/ACK integrity or approval validation. No serialization bound changes between the 4,096th, 4,097th and 4,098th record.

## 12. Self-review and review gate

Compatible segmentation is rejected honestly as classification B for frozen aggregate envelopes. The candidate instead selects one explicit STATE-only representation per approved generation. No size switch, protocol segment or lifetime history cap exists. Existing v1 primitive fields and non-STATE object authority remain unchanged; permitted IL.3 scalar capacities are preserved without migration. SHA256 covers exact streaming bytes independent of buffer size.

Independent review must assess this exact version-transition proposal and vectors before adoption. The existing rejected protocol candidate requires a separate remediation task afterwards; F-03/F-04 are not closed here. No authority transition or operational work has been executed.
