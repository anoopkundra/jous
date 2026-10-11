# JOUS.CORE.1A IL.4 acquisition revision amendment

Status: unapproved documentation authority candidate; independent review and adoption are required before normative use. This document authorizes no execution.

## 1. Authority and narrow scope

This is an additive clarification of `docs/decisions/JOUS.CORE.1A.fixture-lease-implementation-design.md`, published blob `706b6bf782701a602012bd1fed75099f519a53ee`. That design remains controlling except for the acquisition expected-revision convention explicitly resolved here. No other authority is rewritten or superseded.

The inspected baseline is commit `338b5c23dcb988193a248efee0806026f087b1d1`, tree `1c7d6ea402894cf08f001f52146c4dc7d386345d`.

This candidate resolves only IL.4 readiness M-04: the initial acquisition revision convention was absent. An earlier proposed NOT_APPLICABLE acquisition value would contradict the required integer representation. This amendment rejects that proposal and defines integer-zero semantics compatible with published representations.

M-01 EVENT representation/digest-preimage ambiguity, M-02 internal ACK schema/event-reference ambiguity, and M-03 COMMAND/STATE protocol closure remain OPEN. This document does not specify their protocols or resolve them.

## 2. Published constraints preserved

The controlling design sections on storage domains, COMMANDS, acquisition, phase advancement and canonical payloads require nonnegative revisions, required COMMANDS.expected_revision, serialized acquisition, and revision increments for subsequent state changes. Its canonical command payload includes expected_revision and uses unsigned big-endian 64-bit integer framing. Optional absence is permitted only where the schema permits it; this field is not optional.

Published representations inspected:

- IL.1: `services/api/infrastructure/fixture_lease_contract.py`, blob `8eeaecac68dc1ea2997ea340b0c43743da8d834c`. ReservationValue validates a nonnegative integer revision; structurally_permitted_transition requires after.revision = before.revision + 1 and rejects ACQUIRE as replacement of an existing reservation.
- IL.2: `services/api/infrastructure/fixture_lease_service.py`, blob `b32cc1f8338d1f57912b90d788ab3c69407987af`. CommandContext.reservation_revision requires an integer in the nonnegative signed-64-bit range. Construction supplies a structural value, not proof of an existing reservation or external authority.
- IL.3: `services/api/infrastructure/fixture_lease_store.py`, blob `a0d9ff39207ad8bc39016e688d59bc17ee290be2`. CommandRow.expected_revision is an integer; the frozen COMMANDS column is INTEGER NOT NULL with a nonnegative constraint. ReservationRow.revision is also nonnegative. Serialization rejects bool and out-of-range integers.

The corresponding published tests were inspected as representation evidence, not altered. No constraint, wire integer encoding, numeric range or previously published code semantics is relaxed by this candidate. The shared durable range remains bounded by the existing IL.2/IL.3 signed-64-bit storage representations; this amendment does not expand it.

## 3. Required expected_revision

Every durable COMMAND MUST retain required expected_revision as a nonnegative integer.

NULL, omission, NOT_APPLICABLE, an empty optional encoding, a negative sentinel, or any alternate representation MUST NOT be used for expected_revision.

The canonical acquisition COMMAND payload MUST contain expected_revision = integer 0, encoded using the same required integer type as mutation commands. There is no N/A encoding for this field. The later full COMMAND protocol amendment must preserve this uniform representation.

## 4. Creation baseline: ACQUIRE

For a command whose authorized semantics create a new reservation, expected_revision MUST equal 0. The existing ACQUIRE command supplies those creation semantics; CREATE in this document is a descriptive category, not a new command or operation enum.

Creation-baseline zero means: the command expects the target reservation identity to be absent and is authorized, subject to all separately required gates, to establish its initial durable revision. It does not assert that an existing reservation has revision 0.

The target identity is the identity to be inserted according to the later canonical acquisition protocol. This amendment does not change the published acquisition reservation-field convention or decide the still-open complete COMMAND schema.

Within the same authoritative write transaction that inserts the reservation, creation MUST verify that the target reservation identity is absent. Storage uniqueness constraints remain mandatory. Absence alone is insufficient: all conflict, authentication, approval, authority, timing and other published acquisition gates remain required.

If that reservation identity already exists, creation MUST fail closed under the later command/conflict semantics. It MUST NOT mutate, adopt, overwrite or replace the existing reservation, including a released historical record or a record currently at revision 0. Creation is never an UPSERT.

A successful creation establishes initial durable revision = 0. Creation does not establish revision 1.

## 5. Mutation baseline: existing reservation

For every command whose semantics mutate an existing reservation, expected_revision MUST equal the current durable revision of that existing reservation. The reservation MUST exist. Mutation MUST NOT create a missing reservation.

The comparison and accepted mutation occur within the same authoritative write transaction. Each accepted state-changing transition increments revision exactly once. All existing operation, owner, phase, lifecycle, evidence and separate authorization rules remain controlling.

The command kind and operation semantics fix creation versus mutation before database state is examined. A command MUST NOT choose its interpretation merely because a row exists or is absent.

| Semantic category | expected_revision | Required target state | Result of accepted change |
| --- | --- | --- | --- |
| ACQUIRE / creation | 0 | Target identity absent | New reservation revision 0 |
| Existing-reservation mutation | 0 | Target exists at revision 0 | Revision 1 |
| Existing-reservation mutation | r | Target exists at revision r | Revision r + 1 |

For the nth accepted later mutation, expected_revision = n - 1 and resulting revision = n. Creation is not counted as a later mutation.

If the next revision is outside the existing supported durable range, the change MUST reject rather than wrap, clamp, reset or rebase the revision.

## 6. Replay and failure separation

Replay remains separately bound to command identity, authenticated principal and exact payload identity under the later complete command protocol. Revision equality or digest equality alone is not replay proof.

A replay of the same completed creation command returns its established durable result under command replay rules; it does not attempt another creation. The presence of a reservation at revision 0 MUST NOT turn a distinct creation attempt into replay.

Replay makes no revision change. A rejected or failed command makes no revision change. An uncertain outcome requires authoritative command/state reconciliation under the published fail-closed rules; it does not establish failure, availability or permission to retry creation.

No automatic retry, revision rebasing, owner replacement, phase substitution or operation substitution is authorized. This clarification supplies neither command replay implementation nor operational authorization logic.

## 7. Compatibility determination

IL.1 compatibility: YES. Creation is outside the existing-reservation structural transition predicate, while later accepted mutations preserve its +1 rule. No domain enum or predicate changes are required.

IL.2 compatibility: YES. Integer 0 is accepted by CommandContext.reservation_revision. The context does not establish row existence; later command semantics supply the creation-baseline interpretation. No representation change is required.

IL.3 compatibility: YES. Integer 0 satisfies COMMANDS.expected_revision INTEGER NOT NULL and the nonnegative integer validators; initial reservation revision 0 satisfies the existing representation. Transactional absence checks belong to later command orchestration, not a schema alteration.

Schema migration impact: NONE. No published code or test change is required or authorized by this candidate. Compatibility is a design-level finding, not evidence that IL.4 is implemented or qualified.

## 8. Non-goals and adoption gate

This candidate does NOT authorize IL.4 implementation, IL.4 staging or publication, operational issuer startup, runtime activation, operational SQLite creation or access, genesis, external CAS, fixture provisioning, runtime canary execution, CLI implementation or execution, network access, credential access, PostgreSQL/Supabase access, or STRIX.

No actual fixture identity, host, credential, register, lease or operational evidence is selected or asserted here.

Independent review must confirm this narrow acquisition convention against the controlling design and published IL.1-IL.3 representations before adoption. The larger COMMAND/ACK/EVENT/STATE authority clarification remains a separate task after this contradiction is resolved.

## 9. Self-review checklist

- Required nonnegative integer expected_revision is preserved; no NULL/N/A/sentinel is introduced.
- Creation and mutation interpretations are fixed by command semantics before row lookup.
- Creation requires transactional absence and establishes revision 0; it cannot adopt or UPSERT.
- Existing mutation requires matching revision and increments once; it cannot create.
- Replay is separate from row existence, preserves revision, and does not repeat creation.
- Rejection preserves revision; uncertainty remains fail closed without automatic retry.
- IL.2 and IL.3 representations remain compatible; no schema migration or code change is required.
- Only M-04 is addressed; M-01, M-02 and M-03 remain open.
- No operational authorization or current-state readiness claim is made.
