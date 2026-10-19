# JOUS.CORE.1A IL.5 candidate-association authority amendment

Status: PROPOSED FOR INDEPENDENT REVIEW. This draft authorizes no implementation or operation.

## 1. Scope and incorporated authority

This amendment specializes only eligibility for the first immutable association of a normal-command successor candidate with its original publication operation after valid writer admission and confirmed local COMMIT.

It incorporates:

- `JOUS.CORE.1A.il5-normal-checkpoint-orchestration-amendment.md`, especially §§4–6, the Local Transaction Completion Temporal Specialization, and §§9–15.
- `JOUS.CORE.1A.fixture-lease-implementation-design.md`, especially its activation, fencing, protected-checkpoint and failure requirements.
- The frozen Increment C preparation boundary: independently qualified committed-snapshot association and exact successor candidate preparation.

All other authority remains controlling. Implementation and operational execution SHALL require separate authorization.

## 2. Narrow gap and first-association rule

Candidate association SHALL be durable completion/preservation of evidence for the already-validly-admitted original operation.

It SHALL NOT constitute another permit consumption, permit acquisition or renewal, publication qualification, predecessor-currentness proof, checkpoint publication or original-permit completion.

The first immutable candidate association SHALL be eligible only when independently qualified evidence establishes all of the following:

1. The exact original operation validly crossed writer-owned actual admission T1 under its original permit.
2. Its exact local transaction reached confirmed COMMIT.
3. Its committed snapshot was independently qualified.
4. Its exact successor candidate was validly prepared through frozen Increment C.
5. The pre-association requirements in this amendment are satisfied.

PREPARED values, constructors, matching digests or matching bytes alone SHALL NOT establish these facts.

## 3. Subsequent temporal expiry

Once §2 is established, subsequent passage beyond the original permit’s temporal expiry SHALL NOT, by itself:

- erase valid historical T1 admission;
- erase confirmed local COMMIT;
- invalidate qualified candidate preparation; or
- prohibit the first immutable candidate association for that same original operation.

Association eligibility SHALL NOT require another consumption-time comparison against the original permit’s expiry.

This rule SHALL NOT grant publication authority, extend the permit’s validity interval, revive an invalid operation or authorize another transaction.

Historical fixed UTC and candidate bytes/digest SHALL remain unchanged. Association SHALL NOT refix time.

## 4. Explicit invalidation and applicable fences

An independently authoritative explicit condition that prohibits continued progression of the already-admitted operation SHALL prohibit first association while that condition applies.

Existing generation invalidation, activation/host fencing, supersession and authoritative revocation/invalidation rules SHALL remain controlling according to their established applicability.

A changed or contradictory activation context SHALL NOT be adopted as a replacement context. If its applicability to this original operation cannot be independently resolved, association SHALL fail closed.

Temporal expiry alone SHALL NOT be relabeled an explicit revocation or progression fence.

The ordinary prohibition on admitting a later command during the unresolved checkpoint gap SHALL remain in force. That intake prohibition alone SHALL NOT be interpreted as a prohibition on the evidence-preservation association specialized here.

This amendment SHALL NOT bypass an existing applicable recovery handoff or clear any established fence.

No new revocation, cancellation, supersession, fence or fence-clearance mechanism is created. An alleged operation cancellation SHALL have effect only where independently established under existing applicable authority; this amendment creates no cancellation authority.

## 5. Required pre-association qualification

Immediately before first association dispatch, independently qualified knowledge SHALL establish:

- genuine frozen Increment C PREPARED provenance;
- the exact original operation and protected authority namespace;
- valid historical T1 admission;
- confirmed local COMMIT;
- independently qualified committed-snapshot association;
- the exact prepared candidate and all bindings required by §6;
- sufficient authoritative evidence that no applicable explicit condition prohibits this association;
- no conflicting retained candidate under the original publication key; and
- that normal progression is not an attempted retry of a possibly sent or unresolved association.

Absence of a locally observed warning SHALL NOT prove absence of an applicable authoritative fence. Qualification SHALL establish the scope and applicability of the evidence relied upon. Missing, unavailable, contradictory or insufficient qualification SHALL prohibit dispatch.

Existing qualified evidence MAY supply these facts when its independently established scope is sufficient. Otherwise a trusted, independently qualified retention-eligibility assertion SHALL supply the missing facts, bound to the exact original operation and prepared candidate.

A constructor, callback shape, reference syntax, boolean or validity label SHALL NOT manufacture that qualification.

This assertion SHALL concern association eligibility only. It SHALL NOT assert current predecessor status or import the later publication-currentness gate. It SHALL NOT require a new permit-consumption evaluation.

An applicable prohibition learned before dispatch SHALL cancel dispatch eligibility.

## 6. Exact immutable association

Association SHALL bind and retain:

- the exact original publication operation key `(original_permit_identity, CHECKPOINT_PUBLICATION)` in its existing qualified authority namespace;
- the exact qualified Increment C prepared candidate;
- its exact canonical candidate bytes and derived digest;
- its original retained admission-envelope/permit graph;
- its exact embedded predecessor; and
- its already-admitted committed transition.

The protected operation record SHALL retain the exact candidate bytes/digest under that original key.

Digest equality SHALL NOT replace exact-byte and required binding comparison or establish provenance.

Candidate bytes, predecessor, original permit, envelope and operation identity SHALL NOT be substituted. No replacement candidate or second candidate is authorized.

Retention lifetime and later resolvability SHALL remain governed by existing IL.5 §5. Unresolved evidence SHALL NOT expire merely because the permit expires.

This amendment does not require serialization of the entire Increment C Python provenance graph.

## 7. Effect cardinality and existing association

A normal Increment D evaluation SHALL invoke candidate association at most once.

It SHALL NOT perform a blind retry, fallback-provider association, overwrite, replacement association, duplicate association write, permit reacquisition, renewal or second consumption.

A subsequent normal evaluation SHALL NOT disguise a retry of an attempted or unresolved association as a new first attempt.

An exact already-existing association MAY be independently observed and qualified through authorized read-only resolution. It SHALL NOT be rewritten merely because association is logically idempotent.

A conflicting association SHALL prohibit another write, preserve the conflicting evidence and require existing fencing/reconciliation handling. Different bytes SHALL NOT replace the existing association.

Unknown association history SHALL NOT be inferred to mean no prior effect.

## 8. Failure, uncertainty and IL.7

Proven failure before dispatch SHALL establish no retention success and SHALL preserve the original operation unresolved under existing post-COMMIT failure rules.

Once the association effect may have been sent, inability to obtain independently qualified evidence of its disposition SHALL remain UNKNOWN/unresolved. It SHALL NOT become ordinary rejection, assumed non-retention or authoritative absence.

Timeout, lost response, malformed or unbound confirmation and unavailable disposition evidence after possible dispatch SHALL follow that rule.

Failure or uncertainty SHALL preserve committed data and original-operation/candidate evidence, fence normal progression under existing authority and hand resolution to IL.7.

No retry, publication, permit completion, ACK/delivery or speculative repair SHALL follow unresolved association.

Returning handoff knowledge SHALL NOT itself claim that protected-system fencing or IL.7 recovery has executed.

If evidence reveals that historical T1 admission was invalid or relied-upon evidence was contradictory, corrupted or unqualified, normal association SHALL stop. Confirmed COMMIT SHALL remain confirmed storage; no rollback, compensation or storage-outcome relabeling is authorized merely by that finding.

## 9. Successful retention knowledge and STOP boundary

Successful Increment D knowledge SHALL require independently qualified evidence that:

- the exact candidate durably exists in protected retained history;
- it is immutably associated with the exact original publication operation; and
- its exact bytes/digest and required original bindings satisfy §6 and existing retention-lifetime requirements.

A receipt, returned candidate, matching hash or unqualified provider success alone SHALL NOT establish successful retention.

Such knowledge MAY be supplied to the later publication-qualification boundary.

It SHALL NOT establish:

- current predecessor identity or currentness;
- current permit validity for publication;
- publication readiness by itself;
- successful CAS or checkpoint publication;
- publication disposition;
- original-permit completion;
- delivery or ACK authority; or
- recovery/resumption authority.

The retention increment SHALL stop after returning qualified retention knowledge or the applicable fail-closed/unresolved knowledge.

## 10. Representation and implementation freedom

Existing canonical checkpoint bytes SHALL remain authoritative candidate material. Existing `CHECKPOINT_PUBLICATION` operation identity SHALL remain unchanged.

This amendment SHALL NOT introduce:

- a candidate or provenance codec;
- a new schema, table, column or local index;
- an OperationKind, journal or local recovery record;
- a concrete provider or physical receipt format;
- a mandatory transport topology; or
- publication, delivery or IL.7 recovery implementation.

Provider realization remains abstract. Choice of transport or receipt representation SHALL NOT weaken exact association, independent qualification, retained-history or uncertainty requirements.

## 11. Compatibility and forbidden authority

This amendment SHALL NOT reopen frozen Increments A, B or C.

It SHALL NOT change:

- T1/T2 meanings or temporal cutoffs;
- canonical candidate construction, bytes or digest;
- publication qualification or predecessor CAS;
- original-permit completion;
- delivery/ACK rules; or
- IL.7 recovery ownership.

It grants no runtime activation, operational SQLite access, fixture-operation authority, permit replacement, recovery execution or fence clearance.

It resolves only first candidate-association eligibility after valid admission, confirmed COMMIT and qualified preparation.

## 12. Acceptance matrix

“Eligible” below always requires all other requirements of this amendment. No row authorizes publication from retention knowledge alone.

| Case | Association eligibility | Association write | Resulting knowledge | Publication from this result? | IL.7 handoff |
|---|---|---|---|---|---|
| 1. Permit valid at T1 and association | Eligible if qualified facts hold | At most one first invocation | Qualified retention only after confirmation | No; later gate required | Not solely for this condition |
| 2. Permit expires after COMMIT, before association | Expiry alone does not disqualify | At most one, after qualified C preparation and remaining checks | Qualified retention if confirmed | No | Not solely for expiry |
| 3. Permit expires after C preparation, before association | Expiry alone does not disqualify | At most one if remaining checks hold | Qualified retention if confirmed | No | Not solely for expiry |
| 4. Applicable explicit progression fence appears before association | Prohibited | Zero | Fail closed; preserve evidence | No | Required under existing rules |
| 5. Evidence reveals invalid T1 | Prohibited | Zero | Historical-validity contradiction; confirmed storage preserved | No | Required |
| 6. Exact candidate already durably associated | Qualified read-only recognition permitted | Zero | Exact retained-association knowledge if independently qualified | No | Not solely for exact recognition; prior unresolved/recovery conditions remain controlling |
| 7. Conflicting candidate already associated | Prohibited | Zero | Conflict; no overwrite or inferred non-effect | No | Required |
| 8. Provider unavailable; independently established that association was not dispatched | No dispatch eligibility | Zero | Proven pre-dispatch failure; no retention assertion | No | Required by existing post-COMMIT failure rules |
| 9. Timeout after possible dispatch | No further normal attempt | No second invocation | UNKNOWN/unresolved | No | Required |
| 10. Malformed/unqualified confirmation after possible dispatch | No further normal attempt | No second invocation | UNKNOWN/unresolved | No | Required |
| 11. Exact retention independently confirmed after permit expiry | Confirmation may establish retention | No repeat invocation | Qualified retention; expiry alone does not erase it | No | Not solely for expiry; existing fences remain controlling |
| 12. Permit expires after retention, before publication qualification | Retained association remains unchanged | Zero repeat writes | Retention knowledge preserved | No stale-authority publication; existing publication gate applies | Required if publication authority is expired/unavailable under existing §9 |
