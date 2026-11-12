# JOUS.CORE.1A admission-subject bootstrap qualification

Status: **OFFLINE NORMATIVE CANDIDATE — NOT APPROVED FOR IMPLEMENTATION — NOT OPERATIONALLY ADOPTED**

## 1. Purpose, baseline and limited effect

This additive candidate defines the missing finite admission-subject bootstrap qualification rule only. It supplies proposed authority through E0/V0/P0, before construction of an ADMISSION_PUBLICATION or ADMISSION_CAS receipt body. It does not make the separate APM candidate authoritative, close APM-D01/D02 by itself or resume implementation.

Derivation baseline: `816ebb7f7cd0555f1a026441c5b5074db3a2be83`.

Controlling stop: `CORE1A_ADMISSION_RECEIPT_PROVENANCE_MAPPING_REMEDIATION_BLOCKED_ADDITIONAL_BOOTSTRAP_AUTHORITY_REQUIRED`.

Known finding: APM-N01 — HIGH — finite V0 qualification base case not established.

APM-N01 remains open until this candidate is independently approved and frozen and the APM candidate is subsequently remediated and independently accepted. Candidate creation is not approval. This record creates no operational authority. The ten-file implementation remains suspended throughout the present gate.

## 2. Controlling frozen sources and new decision

| Source | Frozen identity / controlling provisions |
|---|---|
| [Realization implementation contract](JOUS.CORE.1A.operational-provider-realization-implementation-contract.md) | Blob `1e005efbec51898c327fbabdbcdea99e82e4b855`; SHA256 `75fe1a06f33ebaa3509eeaaa816d072c326ef4acf586827aab8fc948e752a3ba`; §§6.2, 20: distinct retained provenance, independently authorized verification, explicit approved bootstrap roots |
| [Non-RFC3161 profile](JOUS.CORE.1A.non-rfc3161-receipt-authentication-profile.md) | Blob `8067a55d4434e04faf85948191eda9404ef33b81`; SHA256 `f6995622f93093762854702fc6266efbc7d13495561205fd1ab643b4e523931c`; §§2–8: exact-byte signatures, authority beyond mathematics, role separation and lifecycle |
| [Receipt codec/upload bound](JOUS.CORE.1A.provider-realization-receipt-codec-and-upload-bound.md) | Blob `c03dc469024709a49a21aced034f45cf8ad9059e`; SHA256 `c92a4dc04bade38c493b3a448dcddcaf422c0eeb947a9befdc1c20b59b7995a4`; §§4, 7, 9: VERIFIER_ATTESTATION/VA, independent roots, finite control custody and full reference checks |
| [Provider integration contract](JOUS.CORE.1A.operational-authority-provider-integration-contract.md) | Blob `3efb8fef034181d8f4a1ae6d3caf2952ee99095c`; SHA256 `6d4d0ab206e67bb33b6ff137b0d15ae6dc915d44d30d8fb37eb34f8a948bbfed`; §§5, 7, 13: separate qualified verification, exact subjects/claims, complete raw retention |
| [IL6 serialization profile](JOUS.CORE.1A.il6-authority-serialization-profile.md) | Blob `63dbed6ae575797da27d6a4ee3be03bb184256c3`; SHA256 `244af712477959ba0d2c4a6d106829ab8a31a3ae82d9247ecd85b620d349a875`; existing canonical objects remain exact |
| Frozen provider implementation | `services/api/infrastructure/fixture_lease_authority_providers.py`, blob `f5dcfbfe8d4884fc660a292433c200ce276f69e0`; EvidenceVerifier.verify, AuthenticatedView, EffectAdmission and RawEvidence authentication remain unchanged |

NEW normative applicability decision: the existing VERIFIER_ATTESTATION role and explicitly approved verification/key/adoption bootstrap roots MAY authenticate a pre-binding verification decision about the original admission subject, under the exact conditions below. That bounded decision is sufficient provenance for the initial subject-specific V0; it does not first require an ADMISSION_PUBLICATION or ADMISSION_CAS QF binding of that subject.

This applicability was NOT already established by the frozen texts. It is the specific additional authority proposed here. It does not generalize all native evidence into trusted evidence, make admission subjects trust roots, waive KMS authentication or broaden the custody-control exception to admission qualification. Existing root termination is reused; its applicability to this specific pre-binding verification path is newly defined.

No existing root-authentication mechanism is replaced. No software/HMAC/TLS-only root or new KMS signing algorithm is selected. All actual bootstrap packages, resources, key/principal identities and independent approvals remain separately established downstream authority; none is supplied or adopted by this candidate.

## 3. Exact objects and authority classes

The names below denote existing evidence classes and processing facts, not new receipt roles, canonical objects, operational methods or SQL operations.

| Name | Exact meaning |
|---|---|
| T | The separately approved, independently retained trust/adoption bootstrap package already required by realization §20 and codec §9. Its explicit roots establish verifier authority, approved public material, scoped key authorization, lifecycle/status authority and qualified evidence-interpretation capability. |
| S | Complete original opaque external admission qualification subject, with its existing immutable identity/raw SHA256; not a QF binding body or future envelope. It carries actual evidence from which EffectAdmission can be established. |
| X | Existing retained exact verification-request/expectation evidence: original source request, S reference, role, context, obligations and provider/retention bindings. It is not a new authority grant. |
| D | The actual independent verifier's immutable native decision/result evidence over S and X, including the actual observations and complete claimed EffectAdmission interpretation. It is raw external verification-result evidence, not an accepted view merely because it exists. |
| E0 | One complete retained detached receipt envelope of existing role VERIFIER_ATTESTATION, detail schema VA, binding the actual D, exact S/X and verifier authority. Its authenticity is directly checked using T-authorized key/issuer/status material. |
| V0 | The qualified AuthenticatedView of original S resulting only after all root, E0, S/X/D, context, claim, lifecycle/time and retention checks below succeed. |
| P0 | The complete original retained E0 envelope bytes, used as V0's subject-specific authenticated verification provenance; Ref(P0) is E0's exact final external reference. P0 is not D alone, an in-memory view or a newly serialized EffectAdmission. |
| B/R/V1 | Future admission QF body, its completed authenticated envelope, and later verification of R. They do not participate in E0/V0/P0 qualification. Their mapping remains subject to later APM remediation. |

E0 is NOT a trust root. It is subject-specific signed verification evidence anchored to T. A structurally valid envelope or issuer name cannot supply missing T approval. A copied trust/adoption package cannot authorize another incarnation or configuration.

## 4. What exists before V0

Before V0 can be returned, T, S, X, the actual verification inputs/observations comprising D, and the completed authenticated/retained E0 must exist. The verification capability and E0 signing authority must already be independently qualified and adopted for VERIFIER_ATTESTATION in the exact namespace/incarnation/configuration/scope. Merely constructing these objects does not confer that authority.

The native checks producing D are part of the existing independent evidence-verification responsibility. They perform no broker admission, dispatch claim, publication, CAS, resource adoption or recovery. D is not independently accepted as a qualified result before E0 and T authenticate it. This candidate does not authorize executing those checks, issuing a receipt, signing or creating resources now; it defines the semantic rule for later separately authorized operation of existing capabilities.

### 4.1 Terminating trust basis T

T is a supplied, separately approved bootstrap input, not a record discovered or self-approved by the admission verifier. It must already designate the independent verification authority and exact key/issuer/role/scope authorization: provider and account/tenant boundary, Region, full key ARN, exact DER SPKI fingerprint, algorithm, permitted receipt role VERIFIER_ATTESTATION, namespace/incarnation/configuration, validity, status authority and independent adoption/approval.

Its approved public material and authority/status roots must be authenticated by the existing separately approved bootstrap process. At this terminal boundary the verifier consumes established root authority; it does not demand that T first obtain admission qualification or a new verifier receipt about itself. This is the existing explicit-root termination rule, not an exemption invented for ordinary admission evidence. If T is not genuinely established under that process, this design has no usable starting authority and fails closed. A purported runtime root made solely from E0, S, B, aliases, copied DB rows or a caller-supplied public key is invalid.

Any non-root adoption/key-binding/status dependencies must already resolve under the existing frozen GOVERNANCE, KEY_BINDING and KEY_STATUS roles or exact approved external root material. Their chains must terminate at T, never at S, E0, B/R/V1 or a mutual key-adoption cycle. The actual package must expose that finite approved dependency graph. Generic permission to verify or a root label is insufficient. Missing root authentication, status applicability or independent approval stops the path; this candidate supplies no substitute root mechanism.

### 4.2 Exact E0 authentication and content

E0 uses the frozen VERIFIER_ATTESTATION signed body and detached envelope without adding, omitting or changing any member. Its schema and meaning are:

- receipt_role = VERIFIER_ATTESTATION; details.interpretation_role = ADMISSION_PUBLICATION or ADMISSION_CAS as bound below; details.interpretation_type = EffectAdmission.
- body.subject_ref identifies D, the actual original verification-result subject. details.verified_subject_ref identifies S. details.verification_result_ref identifies that exact D. D and S are not E0 and do not contain E0's future raw hash or version.
- body.request_id/request_ref and details.expectation_ref bind X and the actual original source request; X establishes the exact frozen expectation, not a projected successful response.
- details.authenticated_binding_ref identifies the actual preexisting independently approved provider/verifier authority binding in T's finite scope, not a future admission binding R.
- details.obligations equals the exact frozen admission expectation's complete requested tuple in frozen order. details.verdict = VERIFIED and body.outcome = ESTABLISHED are allowed only after actual native checks establish every obligation. Labels alone are insufficient.
- Body issuer/provider/authority/key/namespace/incarnation/configuration/adoption, qualification, validity, current time and predecessor fields retain their frozen meanings. Every reference resolves to its actual existing subject and dependency; no B/R/V1 reference or prior same-class admission-QF provenance is permitted in the bootstrap dependency path.
- E0's authority-adoption, key-binding and key-status references must match the exact independently approved T-authorized signer and applicable lifecycle evidence. A normal non-root key/status receipt retains the frozen codec; it cannot sign itself into authority.

The signature covers SHA256 of the exact original body bytes with RSA_3072/SIGN_VERIFY, RSASSA_PSS_SHA_256, MGF1-SHA256, 32-byte salt, MessageType=DIGEST and a 384-octet signature. Retain exact body/signature/envelope bytes and full key ARN plus SHA256(exact DER SPKI). Externally verify using prehashed SHA-256 and the exact PSS parameters, with no normalization or JCS. A mathematically valid signature without actual role/scope/adoption/status and decision correspondence is rejected.

E0 is signed evidence of an actual verification decision; it is not a normal admission QF binding in disguise. The VA schema has no view_provenance_ref member. NEW narrow authorization: for this pre-binding path, root-authenticated E0 plus the independently checked original subject/inputs/facts may establish V0 without first obtaining the normal admission QF receipt B. This authorizes neither an unauthenticated native-subject shortcut nor an alternate signing profile.

Provider-native bytes may participate as S or D and input proof. They receive no authority merely from emission by a provider, TLS success or a local parser. E0 must authenticate the complete exact subjects and independent actual interpretation; the verifier must additionally establish every frozen predicate and applicable authority. No broker/self-attested projection replaces independent verification.

## 5. Exact S/X/D binding and shared role invariant

Publication and CAS use one shared bootstrap invariant with distinct exact role-specific source associations. E0 must bind exactly one original S and X. Compare identity AND complete raw SHA256, not semantic equivalence, names alone or an allegedly equivalent encoding.

| Intended admission role | Required E0 interpretation and context |
|---|---|
| ADMISSION_PUBLICATION | Frozen role publication-admission; CURRENT; exact original `(snapshot, approval, authorization)` and actual complete EffectAdmission; exact namespace/incarnation/configuration, source request/operation, register, target generation 1, activation, K/J, host/scope, E/S0/C0/P/Q, original input binding, current absence/history, rights and qualified time. |
| ADMISSION_CAS | Frozen role cas-admission; CURRENT; exact original `(payload, publication, absence_history, authorization)` and actual complete EffectAdmission; all shared lifecycle/authority bindings plus exact downstream payload, confirmed publication, CAS original identity and fresh absence/history. |

E0's frozen Context uses the corresponding PUBLICATION or CAS kind and all required/prohibited fields. The full immutable expectation, provider and retention binding, source request and original subject association must match X and S. No cross-role, cross-operation, cross-context, cross-incarnation, cross-register or cross-generation substitution is accepted. The two original subjects never become the same merely because they decode to the same dataclass.

D must prove actual snapshot, approval, authorization, absence_history, clock, operation, presence, predecessor_generation and original_history values required by frozen EffectAdmission and its validators. Presence AUTHORITATIVE_ABSENT, predecessor generation 0 and ORIGINAL_UNATTEMPTED_K are factual qualified claims, not consequences of missing data. CAS cannot use publication-only evidence to avoid its additional obligations. All transitive dependencies remain stage-valid.

## 6. V0 qualification rule and resulting view

An original admission subject may use this bootstrap path ONLY when ALL conditions hold:

1. Existing separately approved T establishes the actual independent verification capability, exact permitted E0 signer, authority/scope, status and qualification. Its finite dependency graph is available and authenticated.
2. Complete S, X and D are retained and independently resolvable with authentic raw identity/issuer/context bindings. The exact E0 association described in §§4–5 is established.
3. E0 passes the frozen closed schema, exact-byte signature, authority, key/public material, lifecycle/status, qualified time, stage, subject/context and obligation checks. It does not depend on any admission QF provenance, B/R/V1, later broker entry or effect to authenticate this initial subject.
4. The qualified verifier establishes every original admission claim and requested obligation from actual evidence, not E0.verdict alone, and checks exact equality with the expectation. It may reject E0 even when its signature is valid.
5. E0/P0 and all required raw verification provenance/custody are retained and available before V0 is exposed. Missing, ambiguous or unconfirmed retention cannot yield a qualified view.
6. Exactly one authority-selected E0/S/X/D association satisfies §8; current applicability is fully established.

Only then may existing EvidenceVerifier.verify return V0 as the existing AuthenticatedView: reference = exact S reference; expectation = exact original admission EvidenceExpectation; value = actual exact EffectAdmission; clock and validity = authenticated qualified current evidence; provenance = exact Ref(P0) in the frozen service reference carrier. No dataclass field, method signature or success type changes.

V0 verifies the original S under this explicitly authorized pre-binding path. It does not verify future B/R, and it does not itself reserve an original or create dispatch permission. QualificationClient.qualify and the existing verifier/retention interfaces can compose this rule internally; no new provider method or operation discriminator is introduced. Lack of T or E0 is a rejected/unconfirmed qualification, not a reason to switch to normal QF recursion.

## 7. P0 identity, authentication and retention

P0 is exactly the complete original E0 envelope bytes already retained as verification provenance. The same evidence object is the starting authenticated attestation E0 and the provenance record P0 of the resulting V0; it is not a new post-V0 receipt that verifies V0 itself. The independent issuer's actual event was verification of S using X and the authenticated inputs represented by D, not verification of a future AuthenticatedView serialization.

Ref(P0) is exactly `(E0.body.receipt_id, SHA256(complete original E0 envelope bytes))` under the frozen opaque receipt rule. Extract and preserve both existing identity and complete raw digest; do not hash a parsed/re-encoded body or signature alone. Existing Ref/service digest-byte conversion is unchanged.

The authorized verifier creates/authenticates E0 under existing VERIFIER_ATTESTATION responsibility; existing independent custody authority retains its complete original bytes and required source evidence. Ordinary S/D/E0 subjects require qualified exact-version retention and immutable associations, including the frozen size bound and no-replay rules. A returned qualified V0 cannot rely on a merely planned reservation, partial upload or a fabricated locator.

E0's envelope subject_custody_ref, where required, concerns actual D custody. It cannot be E0's own future locator. E0's own locator is a separately established immutable association after its bytes exist. Control acknowledgements for that retention use ONLY the already-frozen finite custody-bookkeeping treatment; this does not exempt S, D or E0 from authentication/required raw retention and does not make them custody-control roots. No recursive signed receipt about the retention receipt is required as a condition of creating E0. Required actual retention must nevertheless be established before V0 is returned.

P0's signer/adoption/status/time/retention remain checked for current operational reliance. Historical mathematical verification does not override revocation, compromise, supersession, invalid scope or unavailable provenance. P0's immutable subject/request/expectation associations bind V0 and S uniquely; no new receipt for the in-memory V0 is required to establish that association.

## 8. Deterministic pre-E0 designation, final association and lifecycle

### 8.1 Separate designation from final content identity

`E0_designation` means the exact immutable upstream association defined below. It is NOT a digest, a new identifier type, a new evidence object or a new serialized field. `Ref(E0_final)` means the existing external Ref of the complete immutable final envelope: its signed body.receipt_id together with SHA256 of the complete original envelope bytes. These terms MUST NOT be interchanged.

The frozen codec ?5 receipt_id is an ID allocated once before signing independently of the future complete-byte hash; ?9 separately computes the final complete-envelope reference. Therefore a frozen preallocated opaque receipt identifier IS available. It may identify the intended receipt issuance within the actual authorized verifier's request/result association, but is not a guessed digest, content-addressed input, transferable authority token or independently sufficient designation. It does not replace any existing Ref. No new identity type or extra VA member is introduced.

The T-authorized independent verifier designates the actual completed verification event by its existing authenticated original request/result association: exact S, X, the one actual completed D selected by that request's authorized verifier response, intended admission interpretation role, complete expectation/context/obligations, and actual verifier authority/scope. It does not designate a future envelope SHA256. A caller cannot choose another D or invent a verifier result. Missing/nonunique D or authority association fails closed before E0 assembly. This narrows the previously stated source association; it is not a new protected operation, adoption event, persistent selector table or provider method.

### 8.2 Complete immutable upstream set U

U contains ALL complete objects/facts used in the E0 signed body or detached envelope, including:

- T and its actual approval/adoption/qualification roots; exact independently approved verifier/issuer/provider/scope and resource/incarnation/configuration bindings.
- S and its complete raw identity/hash and authentic original facts; the original source request; X and its exact immutable expectation, role, context, obligations and request identities/references.
- Actual completed D, its complete immutable bytes/reference and authoritative association with that exact S/X verification event.
- Exact key ARN, DER SPKI/fingerprint, key-binding/status/lifecycle evidence and applicable independent authority/qualification/time evidence.
- Every existing predecessor, authorization, context fact and subject-custody reference required by the frozen body/envelope; all complete signed input values, validity bounds and actual VERIFIED/ESTABLISHED decision facts.
- The existing receipt_id allocated once before signing for the actual issuance, independently of final E0 bytes/digest. It can remain scoped issuance state; neither X nor D must be modified to insert it. Its eventual authenticated occurrence is the already-frozen body.receipt_id field.

Every Ref/digest target in U must be complete, immutable, authenticated as required and available BEFORE the final E0 envelope is constructed. U is closed over those referenced prerequisites and their required transitive authority dependencies. No member of U, including X, D, their raw bytes, context, status/time proofs, predecessor evidence or any upstream custody association, may contain or depend on final Ref(E0_final), the final E0 SHA256, E0's future exact custody version, V0 or future B/R/V1. A dependency cycle rejects; it is not resolved by iteration, guessed hashes or later mutation.

E0_designation is the ordered comparison tuple `(Ref(S), Ref(X), Ref(D), intended admission interpretation role, complete frozen expectation/context/obligations, actual T-authorized verifier/issuer/provider/namespace/incarnation/configuration/scope)`. Its components use existing exact values and references. This tuple is comparison notation only: no tuple serialization, hash domain, wire member or new authority object is created. The actual completed D and intended interpretation must already be fixed by the authenticated original verifier request/result association. Preallocating another receipt_id cannot create another eligible source event or repair ambiguity.

### 8.3 Exact construction and observation order

1. Establish existing approved T and all required authority/key/status/qualification/time prerequisites.
2. Establish complete original S and source request.
3. Complete and fix X and all expectation/role/context/obligation inputs; no final E0 digest exists or is required.
4. Perform the separately authorized independent verification of S; complete and fix actual D and its authenticated original request/result association. D contains no dependency on final E0 content identity.
5. Determine exactly one E0_designation solely from these immutable upstream facts under the actual T-authorized verifier scope. Fix the ordinary receipt_id and all remaining U values before signing. If required input/status evidence is not already established, do not assemble E0.
6. Assemble the frozen VA body with exact references to U. Preserve the frozen producer/acceptance codec. Neither X nor D is rewritten to designate a future content hash.
7. Hash the exact original body and authenticate/sign it under the unchanged KMS profile. Signing ambiguity does not permit a second Sign or another receipt identity.
8. Assemble and fix the complete detached E0 envelope with the actual original signature octets and existing upstream envelope fields. It is now immutable.
9. Calculate final SHA256 of those complete bytes and form Ref(E0_final) using the existing body.receipt_id and that digest. The digest is calculated only after step 8; it is not an input to steps 1?8.
10. Retain precisely those complete E0 bytes through the frozen exact-version custody sequence. RESERVE/VERSION/BIND, definite acknowledgements, complete readback/hash, COMPLIANCE retention and same-reference return all remain required. An unconfirmed reservation is not accepted retention.
11. Authenticate the completed envelope, resolve its already-established inputs and compare its existing signed fields to E0_designation. Authenticate its exact final reference and BOUND custody association. This is a read/verification of existing signed receipt and custody facts, not issuance of another association receipt.
12. Require the unique completed E0/P0 association and every V0 criterion below. Only then expose V0 with provenance = exact retained Ref(E0_final). P0 is those same E0 bytes, not a newly constructed downstream receipt.

No downstream step mutates an upstream hashed object. A later status observation may support current reliance only as separately permitted evidence; it does not rewrite U or the completed E0. If assembly/signing/retention becomes uncertain, preserve that uncertainty and original identity, without restarting the sequence merely to fill an evidence gap.

### 8.4 Authenticated final association using existing fields and custody

The existing VA signature is the association authority for E0_designation: it authenticates body.subject_ref = Ref(D), details.verification_result_ref = Ref(D), details.verified_subject_ref = Ref(S), body.request_id/request_ref and details.expectation_ref for X, details.interpretation_role/type, details.obligations, body.context and actual issuer/provider/authority/namespace/incarnation/configuration/adoption/key identity. Check those fields against the independently established U and designated verification event, not merely against one another. Authenticate D/X's actual complete expectation and authority-scope bindings. body.receipt_id authenticates the preallocated opaque issuance ID. These are existing fields; no final hash is inserted in the signed body.

After E0 is immutable, final Ref(E0_final) is established by complete-byte hashing and authenticated immutable custody of exactly that reference. The association is therefore a verifiable composition: T-authorized signature binds the unchanged S/X/D/designation to the actual E0 body; the frozen envelope binds that body/signature to its complete original byte object; SHA256 and exact authenticated custody bind that object to final Ref(E0_final). The final digest is an OUTPUT checked against independently retained bytes, not an upstream signed claim. No separate signed association record is required to insert the digest into X, D or E0, and none is authorized here.

PROOF_BINDING is NOT used for this final association. Its frozen legal roots/paths do not generally cover a VERIFIER_ATTESTATION envelope or an arbitrary new designation tuple. Treating this as a PF leaf would broaden that role. Exact linkage is already authenticated by existing VA fields and the frozen evidence-reference/custody machinery.

CUSTODY_BIND is applicable ONLY to the final-reference/exact-version retention component. Its frozen subject identity/raw SHA256/issuer/role/context and immutable BOUND locator must match the actual E0 bytes and existing designated context. It cannot select D, approve E0_designation, issue qualification or make conflicting verifier assertions true. The VA signature and authenticated original request/result association supply designation meaning; custody supplies protected exact retention. These responsibilities are combined by verification, never collapsed or expanded into new custody authority. No new operation, role, field, provider method, persistent relation or implementation path is needed.

### 8.5 Zero, one and multiple completed records

The relevant set is all completed E0 evidence established by the authoritative original request/result association for the exact E0_designation, not merely the first caller-supplied candidate. Required uniqueness/association evidence must be available under the existing authorized request/result/qualification and resolution scope; incomplete or untrusted enumeration establishes no uniqueness and fails closed. This creates no new enumeration method or global catalog and grants no observation rights.

- Zero completed E0 records: fail closed; no qualified V0 or usable P0. An issuance/signing/retention uncertainty cannot be treated as a proven empty set or permission to reissue.
- Exactly one distinct complete E0 Ref: eligible only after all independent signature, subject/context, authority/status/time, raw integrity and custody checks. Copies of the same identity/hash/raw bytes are one record, not competing sources.
- More than one distinct completed E0 Ref for the same designation, or conflicting claims to one receipt_id: fail closed as ambiguous/conflicting. Agreement of parsed views does not select one. No latest timestamp, first returned, provider/filesystem order or lexicographic-hash selection is permitted.

The frozen codec allocates receipt_id once before signing and prohibits its regeneration on uncertainty. Frozen signing/custody no-replay rules prohibit automatic re-signing, reissuance or another attempt to cure an evidence gap. This record does NOT invent a broader global idempotency or exactly-once-attestation guarantee. If distinct attestations exist for the same immutable designation under other authority, their multiplicity remains ambiguous for this bootstrap rule; the rule does not choose a convenient one or merge them. No automatic second E0 is authorized by this remediation.

V0 acceptance requires one valid authenticated upstream designation, one accepted completed retained E0/P0 under that designation, complete exact S/X/D/expectation/context comparisons, valid verifier/key/status/lifecycle/time/qualification, confirmed exact custody, and no competing/unestablished association. Stored receipt matching never authorizes another event or live continuation.

### 8.6 Unchanged current lifecycle requirements

For T, E0, V0 and P0 reliance, independently establish actual issuer/role/scope, key/resource/incarnation/configuration continuity, authority validity, current non-revocation/non-compromise/non-supersession, and raw-evidence/custody applicability. T's existing approval/lifecycle authority is not the broker. V0 is an in-memory output, not a permanent lifecycle authority; its acceptability at use requires those current checks. P0/E0 bytes remain immutable even when reliance is later disallowed.

Use the existing qualified UTC interval/current status model. A signed issuance timestamp alone is neither trusted time nor proof that evidence predates compromise. Missing status is not ENABLED. Alias movement, copied records or key replacement do not preserve authority without independently approved continuity. Unknown continuity/status yields no qualified V0 or usable future APM provenance.

FROZEN_PREALLOCATED_E0_IDENTIFIER_AVAILABLE = YES

UPSTREAM_INPUT_DEPENDS_ON_FINAL_E0_DIGEST = NO

X_DEPENDS_ON_FINAL_E0_HASH = NO

D_DEPENDS_ON_FINAL_E0_HASH = NO

E0_UPSTREAM_PREREQUISITE_DEPENDS_ON_FINAL_E0_HASH = NO

FINAL_E0_HASH_COMPUTED_ONLY_AFTER_E0_IMMUTABLE = YES

FINAL_E0_ASSOCIATION_DOES_NOT_MUTATE_UPSTREAM_OBJECT = YES

RECIPROCAL_HASH_DEPENDENCY = IMPOSSIBLE_BY_CONSTRUCTION

V0_ACCEPTANCE_CRITERIA_COMPLETE = YES

## 9. Finite graph and termination proof

| Edge | Normative basis and finite prerequisite |
|---|---|
| Existing independently approved T -> verifier/key/status/interpretation authority | Frozen realization §20 and codec §9 explicit-root termination; actual approved bootstrap package, not another admission receipt |
| Actual S and X plus authenticated input evidence -> actual decision D | Existing independent verification duty under provider integration §§5/7/13; this record §§4–5 restricts role/context/claims; D alone is not yet accepted authority |
| T-authorized signer + actual D/S/X -> authenticated E0 | Existing VERIFIER_ATTESTATION/VA and selected KMS profile; NEW applicability decision in this record authorizes the pre-binding admission-subject use |
| Immutable complete E0 -> final Ref -> retained P0 -> authenticated final association | Existing receipt_id plus complete-envelope SHA256 calculated after assembly; existing VA fields authenticate designation and immutable BOUND custody authenticates exact retention, without modifying X/D/U or requiring another association receipt |
| T + exact S/X/D/E0 + actual independent checks + retained P0 -> V0 | This record §6 finite qualification rule, existing AuthenticatedView output, provenance = Ref(P0) |
| V0/P0 -> future APM mapping -> B/R -> V1 | Not authorized/closed here; subsequent APM remediation and downstream gates remain required |

The explicit end-to-end order is T/root authority -> S/X/expectation/context -> actual independent verification -> complete immutable D -> pre-E0 designation from U -> VA body assembly -> authentication/signature -> immutable final envelope -> calculated final Ref -> retention/exact custody -> verification of the authenticated final association -> qualified V0 naming already-retained P0 -> future separately remediated APM mapping -> B -> R -> V1. The V0-to-P0 arrow is a provenance reference to the earlier retained E0, not P0 creation after V0. Signed VA fields point only upstream; the final content digest and locator remain downstream outputs. This specifically eliminates X -> final E0 hash -> E0 body -> Ref(X).

EVERY_PRE_B_EDGE_AUTHORIZED = YES

FINITE_GRAPH_TERMINATES = YES

The E0/P0 node is a single immutable object used in two semantic positions. P0 is retained before V0 is exposed, not produced by verification of V0 or B. This prevents the false cycle “V0 must already be qualified to authenticate its own first provenance.” Native checking/decision D is not a qualified success until T-authorized E0 and actual subject obligations establish it.

Termination follows by construction: T is supplied terminal root authority whose existing approval does not depend on this admission; D/S/X are original raw inputs/facts, not accepted admission QF outputs; E0 uses VA, which contains no view_provenance_ref; this record explicitly permits initial S qualification on that root-authenticated VA basis. Authentication of E0 proceeds through already-approved T/key/status roots, not through an earlier admission QF. P0 is E0, not another newly required receipt. No B/R/V1 or later broker evidence is an ancestor of E0/V0/P0. A dependency that violates any of these constraints rejects rather than initiating another same-class qualification.

V0_REQUIRES_PRIOR_APM_PROVENANCE_OF_SAME_CLASS = NO

UNBOUNDED_PROVENANCE_REGRESSION = IMPOSSIBLE_BY_AUTHORITY_CONSTRUCTION

This proof is conditional on genuinely established, finite approved T and actual evidence. When those operational prerequisites are absent, the rule returns no qualified result; it never synthesizes a terminating root. Their later establishment remains separately authorized qualification/adoption work.

## 10. Failures and strongest UNKNOWN

| Condition | Required result |
|---|---|
| Missing T or E0 | Fail closed: no qualified V0, no P0 usable as APM provenance, no admission QF construction based on this path. Do not create a root automatically. |
| Invalid E0 authenticity/integrity/authority/lifecycle/status/subject binding | Reject and STOP applicable qualification; no alternate evidence class, signer, algorithm or reduced checks. |
| Ambiguous designation of T/E0/S/X/D | Fail closed, unconfirmed qualification; no first/latest/provider/filesystem/time-based choice or retry for uniqueness. |
| V0 criteria incomplete, ambiguous or unqualified | No qualified AuthenticatedView and no P0 usable for APM. Partial observations never become success; V1 cannot repair V0 retroactively. |
| P0 authentication, exact identity, raw retention or unique S/X association unavailable | No usable future admission provenance; no synthesized Ref, fallback record or replacement issuance. |
| KMS signing/custody outcome uncertain | Preserve authentication uncertainty/UNKNOWN_CUSTODY and actual known facts; no automatic resubmission. |
| Stronger protected-entry UNKNOWN already reached | Preserve that boundary and permanent fence regardless of a later definite evidence rejection. |

No E0/V0/P0 failure authorizes replay of an effect, reacquisition, repeated admission/publication/CAS, evidence reissuance or retries merely to cure uncertain evidence. No automatic provider/root/signing fallback is selected. Separately permitted read-only resolution remains observation only and cannot create a qualified bootstrap event, clear UNKNOWN or restore eligibility.

## 11. Role separation and future seams

| Existing authority class | Bootstrap responsibility / prohibition |
|---|---|
| Independent governance/adoption authority | Approve T and verifier/key/role/scope applicability; cannot be replaced by broker configuration |
| Independent qualification/evidence-verification authority | Actually check S/X/inputs and issue authorized E0 under VERIFIER_ATTESTATION; no projected-success shortcut |
| Scoped authorized signer | Authenticate actual E0 bytes/claims for approved issuer/role; signature alone does not approve claims |
| Independent lifecycle/status authority | Establish applicable root/key/issuer status; no self-issued ENABLED claim in place of authority |
| Custodian/custody authority | Preserve exact raw evidence/locators; cannot approve subject claims or grant execution eligibility |
| Protected broker/executor | Consume later qualified admission only under later authority; cannot manufacture T/E0/P0, independent Q or result verification |

Required incompatible authorities retain separate identities, rights, keys and effective independence. A verifier's authorized receipt signer may sign on behalf of that issuer only within approved scope; this does not collapse root approval, custody, status or protected effects into one convenience identity. No actual IAM principal/key/credential is selected.

Future `fixture_lease_authority_evidence.py` can authenticate root-anchored E0, exact subject/expectation/context, retain P0 through existing custody interfaces and return the unchanged AuthenticatedView. `fixture_lease_authority_provider_clients.py` can supply/consume the exact original-subject association internally through existing QualificationClient/EvidenceVerifier/EvidenceClient abstractions. The proposed broker preserves no-entry/no-replay on failure. Existing proposed tests can cover finite-root termination, role substitutions, missing/invalid/ambiguous E0, status, P0 retention and same-class cycle rejection after separate authorization. No implementation is written here.

NEW_OPERATION_TYPE_REQUIRED = NO

NEW_RECEIPT_ROLE_REQUIRED = NO

NEW_AUTHORITY_PROVIDER_METHOD_REQUIRED = NO

TEN_FILE_IMPLEMENTATION_CAN_CONSUME_BOOTSTRAP_RULE = YES

EXISTING_FROZEN_IMPLEMENTATION_FILE_CHANGE_REQUIRED = NO

NEW_IMPLEMENTATION_PATH_REQUIRED = NO

## 12. Explicit ASBQ decisions

| Decision | Candidate normative outcome |
|---|---|
| ASBQ-D01 | E0 is an exact existing-role VERIFIER_ATTESTATION/VA envelope over actual independent decision D about original admission S, directly anchored to approved T. |
| ASBQ-D02 | E0 issuer is the already-qualified/adopted independent verification authority using its scoped approved key; T is the existing separately approved bootstrap trust/adoption package, not a new root system. |
| ASBQ-D03 | Exact S/X/D identity/raw hash, original request, full role/context/obligations, scope/incarnation and immutable operation inputs must match; no semantic or cross-role substitution. |
| ASBQ-D04 | Shared invariant, with distinct publication-admission and cas-admission bindings and full role-specific prerequisites. |
| ASBQ-D05 | New narrow applicability permits root-authenticated VA plus actual evidence checks to qualify original S without prior same-class admission QF; unchanged AuthenticatedView V0 is returned only after all §6 checks. |
| ASBQ-D06 | P0 is complete original E0 bytes, authenticated with the frozen profile and retained under existing exact-version custody before V0 exposure; exact final external Ref is V0.provenance. |
| ASBQ-D07 | T/E0/V0/P0 current scope, adoption, validity, lifecycle/status, continuity, time and raw custody must authenticate; revoked/superseded/expired/ambiguous evidence cannot qualify. |
| ASBQ-D08 | T-authorized verifier fixes the immutable S/X/D/role/expectation/context/scope designation before assembly; existing receipt_id is preallocated, final complete-envelope Ref is calculated afterward and authenticated through existing signed VA fields plus exact custody; zero/multiple/unestablished associations fail closed. |
| ASBQ-D09 | Missing/invalid/ambiguous root/evidence, incomplete V0 or unavailable P0 yields no usable qualification/provenance and preserves strongest UNKNOWN; no substitution/replay. |
| ASBQ-D10 | T is terminal approved authority; E0 uses VA without QF provenance; immutable U/designation precedes signing, final E0 Ref follows immutable envelope assembly, and final association never changes U. P0=E0; no future receipt/same-class V0 or reciprocal upstream digest is a prerequisite. |
| ASBQ-D11 | Existing independent governance, verification, scoped signer, custody, status and broker roles remain separated as in §11. |
| ASBQ-D12 | Existing verifier/qualification/retention seams and proposed ten-file boundary consume the rule internally; no existing file/method/type/schema change or new path is required. |

## 13. APM relationship, continuity and suspension

This candidate supplies proposed finite base authority only. It does NOT itself close APM-D01 or APM-D02. The existing APM candidate remains untracked and byte-for-byte unchanged; its later remediation must explicitly consume this authority after independent approval and freeze. This record does not retroactively validate that candidate's earlier closure claims.

APM_CANDIDATE_REMEDIATION_REQUIRED_AFTER_BOOTSTRAP_FREEZE = YES

PIR_01_REOPEN_REQUIRED = NO

PIR_02_REOPEN_REQUIRED = NO

PIR_02_CHANGE = NONE

max_single_upload_bytes = 8388608

MULTIPART_UPLOAD_ALLOWED = NO

CRYPTO_PROFILE_CHANGE = NONE

TRUSTED_TIME_AUTHORITY_CHANGE = NONE

KMS_SIGNATURE_IS_TRUSTED_TIME = NO

R1_R8_CHANGE = NONE

RECEIPT_CODEC_CHANGE = NONE

ROLE_COUNT_CHANGE = NONE

RECEIPT_ROLE_COUNT = 24

NO JCS. No exact-byte/serializer/signature-envelope/custody technology change. Existing DigiCert Europe RFC3161 and qualified monotonic propagation/current-interval/restart rules remain controlling. No provider-native, TLS-only, OS-clock or unsigned root fallback is introduced.

TEN_FILE_PROVIDER_REALIZATION_IMPLEMENTATION_AUTHORIZATION = SUSPENDED_PENDING_BOOTSTRAP_AND_APM_FREEZE_AND_READINESS_RECONCILIATION

Independent normative review, exact artifact/index/commit review, publication, independent remote verification/freeze, subsequent APM remediation and its review/freeze, and fresh readiness reconciliation remain required before any later implementation authorization. Candidate creation, review or local commit alone does not restore readiness. This gate does not execute verification, create/sign/retain E0, establish T or adopt providers.

## 14. Candidate self-review and no-effect declarations

These are Builder candidate claims awaiting independent review, not self-approval or operational evidence.

ASBQ_D01_CLOSED = YES

ASBQ_D02_CLOSED = YES

ASBQ_D03_CLOSED = YES

ASBQ_D04_CLOSED = YES

ASBQ_D05_CLOSED = YES

ASBQ_D06_CLOSED = YES

ASBQ_D07_CLOSED = YES

ASBQ_D08_CLOSED = YES

ASBQ_D09_CLOSED = YES

ASBQ_D10_CLOSED = YES

ASBQ_D11_CLOSED = YES

ASBQ_D12_CLOSED = YES

FINITE_V0_BASE_CASE_DEFINED = YES

APM_CANDIDATE_MODIFIED = NO

EXISTING_TRACKED_FILE_CHANGE_COUNT = 0

PROVIDER_REALIZATION_IMPLEMENTATION_PATHS_CREATED = 0

STAGED_PATH_COUNT = 0

NEW_COMMIT_COUNT = 0

REMOTE_CONTACT = NO

TESTS_EXECUTED = 0

DEPENDENCIES_INSTALLED = NO

WEB_RESEARCH_USED_TO_DEFINE_JOUS_AUTHORITY = NO

AWS_ACCOUNT_ACCESS = NO

RDS_ACCESS = NO

S3_ACCESS = NO

KMS_KEY_CREATION = NO

IAM_CHANGE = NO

TSA_ACCESS = NO

CREDENTIAL_ACCESS = NO

MANAGED_RESOURCES_CREATED = 0

REGISTER_CREATED = NO

PREPARATION_PERFORMED = NO

GENESIS_ATTEMPTS = 0

CHECKPOINT_PUBLICATION_ATTEMPTS = 0

ACTIVATION_ATTEMPTS = 0

FIXTURE_PROVISIONING = NO

CANARY = NO

RUNTIME_OPERATIONS = 0

PUBLIC_TRAFFIC = NO
