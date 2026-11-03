# JOUS.CORE.1A generation-one genesis checkpoint reference amendment

Status: OFFLINE NORMATIVE AUTHORITY CANDIDATE — NOT APPROVED OR ADOPTED.
Independent review and explicit adoption are required. This candidate proposes
one genesis-only semantic specialization; it grants no implementation or execution
authority. Publication of this document would not execute or approve genesis.

## 1. Exact scope, provenance and source authority

Derivation baseline: HEAD/local origin/main
`86a91423c9eb665756bd5445beaa37f5e390c2fa`.
Independent IL6 review classified the missing genesis reference semantics as
`A3_EXISTING_AUTHORITY_INSUFFICIENT_NEW_NORMATIVE_AMENDMENT_REQUIRED`.
This candidate supplies NEW proposed genesis-specific authority; it does not claim
that these semantics were previously implicit or operationally approved.

Controlling sources inspected at that baseline:

- `JOUS.CORE.1A.fixture-lease-implementation-design.md`, sections 5.1, 6, 8 and 9:
  generation-one initialization, protected checkpoint, authoritative ABSENT CAS,
  existing checkpoint positions, canonical framing and approval retention.
- `JOUS.CORE.1A.il5-normal-checkpoint-orchestration-amendment.md`, sections 1, 3–5
  and 14: normal-only reference bundle, Optional ID approval position and explicit
  exclusion of genesis. No normal profile rule is extended by analogy.
- `JOUS.CORE.1A.replacement-generation-cutover-amendment.md`, sections 4–7:
  replacement-only ceremony reference and acyclic approval linkage. This is
  structural precedent ONLY, not authority for a genesis interpretation.
- `JOUS.CORE.1A.il4-command-event-state-protocol-amendment.md` and
  `JOUS.CORE.1A.il4-large-value-framing-reconciliation.md`: unchanged canonical
  primitives, event anchor, STATE projection and generation-bound representation.

The source paths above are under `docs/decisions/`. Implementation evidence only:
`fixture_lease_service.py` defines the logical `EvidenceReference(identity, sha256)`;
`fixture_lease_protocol.py` defines ID/H/integer primitives and framing;
`fixture_lease_checkpoints.py` and `test_fixture_lease_checkpoints.py` implement/test
the NORMAL_COMMAND profile, not genesis. The normal codec requires positive
revision/event sequence and its tag-18 bundle; it MUST NOT be used with fake normal
inputs to encode genesis. No implementation is added or changed here.

## 2. Five distinct identities

| Concept | Meaning and time of availability | Existing carrier |
| --- | --- | --- |
| Genesis ceremony reference G | Content-addressed identity of fixed pre-checkpoint ceremony evidence E; available after E is fixed | Existing checkpoint command/permit-reference position, genesis-only ID interpretation in section 3 |
| Checkpoint approval identifier J | Stable independent approval identifier allocated before checkpoint construction; not yet an approval | Existing checkpoint approval-reference position, present Optional ID |
| Creation evidence reference C | Identity and SHA256 of separately retained creation/preparation evidence; available before E | Existing exact-byte creation-evidence/approval-package retention path, referenced by E and the package |
| Genesis activation command identity K | Stable unique external activation attempt identity allocated before E; not an IL.4 COMMAND | Existing genesis activation command ID/payload-hash path at the external authority |
| Final independent approval Q | Complete immutable approval record with exact bytes/hash, binding the package/checkpoint | Existing external approval record and activation approval ref/hash |

These concepts MUST NOT be substituted for one another. Allocation of J or K,
construction of G, possession of C, and schema-valid references prove no approval,
activation, permit or authority by themselves. All IDs are non-secret, stable,
within existing 1–255 UTF-8-byte ID bounds and never process-local or recycled.

## 3. Genesis ceremony reference and the existing checkpoint position

Semantic type: GENESIS CEREMONY REFERENCE. Let E be the complete immutable exact
bytes of the pre-checkpoint ceremony evidence described below, and let
`hE = SHA256(E)`. Define its identity exactly as ASCII
`genesis-ceremony:sha256:` followed by the 64 lowercase hexadecimal digits of hE.
No whitespace, alias, case folding, URI normalization or mutable URL is allowed.
The logical reference is the unchanged pair `EvidenceReference(identity, hE)`.
Any identity/digest disagreement rejects, even if a resolver returns some bytes.

For generation-one genesis ONLY, the EXISTING checkpoint command/permit-reference
position contains that exact identity, using the existing ID primitive: its UTF-8
bytes in the existing outer field's length/value framing. No additional inner
frame, tag, digest field, count, COMMAND, permit bundle or protocol object is added.
The digest is recoverable unambiguously from the fixed content-addressed ID and
MUST equal SHA256 of the resolved E. The logical EvidenceReference representation
is reused unchanged; it is NOT a claim that the service dataclass already supplies
a wire codec. In particular tag 18 remains the normal IL.5 N bundle, never a
genesis codec with invented command/permit/admission values.

This explicitly closes the previously unqualified genesis position with the
existing ID encoding. It changes no outer CHECKPOINT field order/count, version,
tag, length framing or primitive. Genesis context is mandatory: generation=1,
checkpoint revision=0, event sequence=0, published genesis event-chain digest,
zero checkpoint predecessor, authenticated ABSENT ceremony purpose and exact
independent genesis approval. A matching ID prefix alone cannot select the profile
or authorize anything. Normal/replacement contexts MUST NOT accept this reference.

E is retained through the existing immutable external evidence/package path, not
a new local table, protocol object or register. Its complete closed semantic
contents are: purpose GENESIS_V1; register_id; schema/version and schema identity;
generation 1; proposed activation_id; host/storage and scope bindings; controlling
authority refs/hashes; selected STATE representation and its authority ref/hash;
creation-evidence reference C; fixed qualified creation/checkpoint UTC and its
clock evidence; exact initial metadata/STATE identity/digest; event sequence 0 and
genesis event digest; zero predecessor; stable activation command ID K; and stable
approval ID J. No optional extension bag or mutable implicit input is permitted.

E MUST NOT contain G/hE, final checkpoint bytes/hash, package hash, approval record
Q/hash, publication outcome, activation payload hash or activation outcome. Those
are downstream. Exact evidence bytes and their unambiguous interpretation MUST be
pinned and retained before deriving G. This is an evidence-preimage requirement,
not a new protocol serialization. A later separately approved package/implementation
design must fix its exact evidence serialization and vectors; no runtime-selected
serialization or reconstruction from mutable state is conforming. Different bytes
mean different evidence; after an attempt could have occurred, changing bytes or
identity is prohibited rather than a means to retry.

G becomes available only after the original C, qualified time, metadata/STATE,
host/scope/representation bindings, K and J are fixed and validated. The genesis
package and independent approval subsequently bind that SAME E/G. Its resolver
MUST retain the exact E and all referenced evidence, reject identity collisions
or differing bytes under one identity/hash, and return no claim of permission.

## 4. Creation evidence is separate

Creation evidence is NOT itself G. C is an independently retained identity/hash
reference to exact preparation/creation evidence. It binds the real approved
preparation, host/storage, proposed register/generation/activation and qualified
clock evidence used for the initial state. It is not a mutable display name, URL,
process handle or proof inferred from an empty file/schema.

E explicitly contains C's identity and digest; therefore hE transitively commits
to that digest. The package also directly binds C and the exact initial-state
projection, so qualification verifies consistency, not just transitive existence.
C and its exact bytes MUST remain independently resolvable after publication or
restart. The relationship is C -> initial metadata/time/STATE -> E -> G, never
G/checkpoint/package -> creation evidence -> G. Pre-checkpoint creation evidence
MUST NOT require a final checkpoint/package approval/outcome to exist in its own
preimage. Later execution receipts are separate downstream evidence, not edits to C.
No physical preparation or creation operation is authorized by this document.

## 5. Approval position: an ID first, digest-bearing evidence later

For genesis, the existing applicable-approval-reference position MUST be PRESENT
and contain J. Under the existing Optional ID primitive its field payload is
`01 || UTF8(J)` in the existing outer length-framed field; `00`/NOT_APPLICABLE,
UNKNOWN, empty J, arbitrary hash bytes and a nested EvidenceReference are forbidden.
No approval field is added or expanded.

J MUST be allocated in the independent approval authority's stable namespace before
E/checkpoint construction, with protected uniqueness/non-reuse. It may identify a
PENDING review slot only. A pending slot grants no approval and contains no claim
that Q or its digest already exists. Exactly one final immutable Q may resolve
from J; collision, reassignment, ambiguous resolution or approval of different
package/checkpoint bytes under J rejects. Issuer/initializer cannot self-approve.

Construct the COMPLETE checkpoint including J, then hash it. Construct the closed
activation package binding that complete hash, G/E, C, initial STATE and K. Only
then may independent review create Q binding the exact package and checkpoint,
genesis purpose, applicable authority, host, register/generation/activation,
approver independence and validity/revocation conditions. Q's existing package/hash
and target/allowed-transition approval evidence MUST establish these bindings;
no new APPROVAL wire field or object is introduced here.

Only after Q exists can a complete digest-bearing approval EvidenceReference
`(J, SHA256(exact Q bytes))` be formed and authenticated. The activation record's
existing approval ref/hash carries this later evidence. J in the checkpoint
resolves through Q to the approved package; the authority MUST verify that exact
chain before protected publication or CAS. The checkpoint MUST NOT contain Q's
digest, the package digest, or a fabricated digest placeholder. Completing Q does
not modify the checkpoint or its original hash.

## 6. Stable activation command and hash rules

K is a separately allocated globally unique stable genesis activation command ID
in the qualified external authority namespace. It is fixed before E, explicitly
distinct from G, C and J, never response-generated. Its meaning is the original
ABSENT-to-generation-one attempt for the exact register/activation/package. It
creates no IL.4 COMMAND row, COMMAND bytes, event, CommandPermit or normal permit
completion obligation. It is distinct from a replacement transition identity.

The exact activation payload is fixed AFTER Q: it binds expected authenticated
ABSENT and predecessor_generation 0, register/generation/activation/host, K, exact
approved package identity/hash, complete checkpoint identity/hash and Q ref/hash
under the existing activation authority. Its payload hash hashes those complete
exact payload bytes. E/package may contain K but MUST NOT depend on this downstream
payload hash. The external command result retains K/payload-hash and exact outcome;
same K with different payload rejects, never a second operation.

Hash/preimage rules are closed:

- hC hashes the complete exact retained creation evidence, not its display location.
- Initial STATE digest uses only the unchanged selected canonical STATE projection.
- hE hashes complete E; the content-addressed G is derived afterward, not in E.
- Checkpoint hash hashes the complete existing CHECKPOINT frame including G's ID
  and J. No approval wrapper stripping, omitted field or alternate preimage.
- Package hash hashes the complete closed exact activation package, including the
  complete checkpoint hash and evidence bindings, excluding its own final digest
  and the not-yet-existing Q/hash or activation payload hash/outcome.
- Q hashes/binds complete package/checkpoint evidence through existing approval
  machinery; its own digest is computed afterward, not included in its preimage.
- Activation CAS binds the complete approved identities/payload described above;
  its outcome and later verification evidence are downstream receipts only.

Every digest is SHA256 of the stated exact bytes. Domain/purpose is bound in the
evidence itself, not by changing CHECKPOINT cryptography. No object requires its
own final digest in its preimage; no post-approval value constructs an already
approved checkpoint. Approval allocation and approval issuance remain distinct.

## 7. Normative dependency graph and progression gates

Each row retains its inputs and exact output through existing external evidence
paths. Arrows denote construction dependencies, not execution permission.

| Node | Fixed inputs -> identity/output | Existing carrier / progression gate |
| --- | --- | --- |
| C | Separately authorized preparation/creation facts -> exact bytes, ID/hC | Existing creation evidence reference; validate provenance and qualified time before use |
| S0 | C plus fixed metadata, authority/representation/time bindings -> exact canonical initial STATE/hS0 | Existing metadata/STATE and genesis package; existing schema/empty-state validation; no fabricated genesis |
| K and J allocation | Independent stable namespaces and fixed intended ceremony -> distinct immutable IDs | Existing activation command and approval reference paths; allocation is not approval |
| E/G | C, S0, K, J and section 3 bindings -> exact E, hE, content-addressed G | Existing external evidence; genesis checkpoint reference position carries G ID; complete validated inputs required |
| C0 | Existing genesis scalar fields, hS0, fixed UTC, G ID and J -> complete CHECKPOINT bytes | Existing CHECKPOINT positions; existing genesis context and reference checks required |
| hC0 | Complete C0 -> SHA256(C0) | Existing checkpoint digest/reference; no stripped preimage |
| P | C/E/G/K/J, initial state, authority/scope and complete C0/hash -> closed exact activation package/hash | Existing genesis package; all inputs fixed; independent review required |
| Q | P/C0 and applicable authority -> exact independent approval record/hash resolving J | Existing approval and activation approval ref/hash; verify independence, applicability, validity and exact binding |
| Protected C0 publication | Exact C0/P/Q -> retained immutable non-activating genesis anchor and qualified original result | Existing sole pre-activation checkpoint exception; separate execution authorization required |
| ABSENT CAS | Qualified protected C0, P/Q, K and fixed payload hash, authenticated ABSENT/history -> exact activation result | Existing linearizable activation CAS; separate authorization and positive absence; never a normal permit |
| Readback | Original K/result, protected checkpoint/activation/current history and local bindings -> authenticated exact outcome evidence | Existing authoritative read mechanisms; no mutation retry; mismatch/unknown fences |
| Independent result verification | Exact execution/readback evidence -> separately retained independent adjudication | Later independent result-verification gate; no operational permission inferred from this candidate |

Compact graph: C -> S0; (C, S0, K, J) -> E/G -> C0 -> hC0 -> P -> Q ->
protected C0 publication -> authenticated ABSENT CAS -> authoritative readback ->
independent result verification. P also directly binds its earlier inputs. No
reverse dependency on final approval or execution outcome enters C, S0, E or C0.

## 8. Scope isolation and representability

This specialization applies ONLY to the existing generation-one genesis ceremony.
It does not authorize it. CHECKPOINT retains its existing eleven outer positions,
version 1/tag 7 and length framing; only the genesis reference-position semantics
are closed here using existing ID/Optional ID primitives. The existing zero
revision/event-sequence and predecessor sentinels remain genesis-only. No new
binary primitive, field, tag, protocol object, event type, COMMAND or fake permit.

Normal IL.5 uses its unchanged N bundle and approval applicability. Replacement
retains its own reference/purpose/predecessor and approval semantics. Neither may
accept a genesis ID to bypass its gates. No IL.4 framing or STATE encoding changes;
no codec implementation or claims that NormalCheckpoint already accepts genesis.
Unknown profile/representation or incompatible reference resolution rejects, not
fallback parsing. Any later proof that these semantics require a field/framing
change MUST stop for separate authority review, never an implicit codec extension.

## 9. Failure, uncertainty and restart

| Condition | Required fail-closed response |
| --- | --- |
| Unresolved/invalid creation evidence | No E/G qualification, checkpoint publication or activation |
| Ceremony ID/digest/preimage or initial-state mismatch | Reject; do not substitute another identity or reconstruct convenient evidence |
| J collision, pending/missing approval, multiple Q records or changed bindings | No protected publication/CAS; retain evidence for independent adjudication |
| Package/checkpoint/approval mismatch | Reject exact operation; do not edit approved bytes or adopt another package |
| Protected checkpoint publication unknown | Retain exact original C0/G/J/P; no duplicate anchor, alternate candidate or automatic resubmission |
| ABSENT proof or CAS outcome unknown | NON_AUTHORITATIVE/RECOVERY_ONLY as applicable; no fresh genesis identity, new CAS or inferred failure/success |
| Restart after uncertain publication/CAS | Preserve original identities and strongest reached evidence; separately authorized original-operation reads/reconciliation only |

Uncertainty never proves absence. Matching original success may be recognized
read-only only from qualified exact protected evidence; it is not another genesis.
No retry, new K/G/activation allocation, automatic recovery, repair, claim release
or local ACTIVE override is authorized. IL.7 retains uncertain-genesis/history
reconciliation and recovery ownership. Service remains fenced until all existing
authority and independent verification gates are satisfied.

## 10. IL6 relationship and non-operation

The current IL6 candidate remains NOT APPROVED. It is preserved unchanged at
`docs/decisions/JOUS.CORE.1A.il6-authoritative-register-activation-contract.md`,
blob `8e22d9182b03e7483a99a731b86d06f155a00653`.
This amendment supplies one proposed missing normative prerequisite identified by
independent IL6 review. Adoption of this amendment alone does NOT approve IL6.
After independent approval/publication of this amendment, IL6 requires separate
narrow remediation/re-review incorporating this genesis-reference authority and
provenance-qualified historical Increment G wording. This task performs neither.

No register is created or opened; no genesis, activation, CAS or checkpoint is
executed; no approval is issued; no code/test/IL.4/IL.5/replacement/IL6 file is
changed. No managed access, credentials, fixture reservation/provisioning, canary,
deployment, runtime activation or IL.7 implementation is authorized. Exact external
evidence/package encoding, vectors and dedicated capability implementation remain
separately designed/reviewed work, not permission to add protocol objects now.
