# JOUS.CORE.1A provider realization receipt codec and upload bound

Status: **OFFLINE NORMATIVE CANDIDATE — NOT APPROVED FOR IMPLEMENTATION — NOT OPERATIONALLY ADOPTED**

## 1. Purpose and authority

This candidate exists to close PIR-01 (closed receipt-role schemas and codec/reference mapping) and PIR-02 (the selected single-upload bound) ONLY. It does not authorize implementation or amend frozen authority.

Derivation baseline: `5d55a63ad6ea340a90d206fa4d4cce4ca27e36df`.

| Controlling frozen authority | Git blob | SHA256 |
|---|---|---|
| [Realization implementation contract](JOUS.CORE.1A.operational-provider-realization-implementation-contract.md) | `1e005efbec51898c327fbabdbcdea99e82e4b855` | `75fe1a06f33ebaa3509eeaaa816d072c326ef4acf586827aab8fc948e752a3ba` |
| [Non-RFC3161 authentication profile](JOUS.CORE.1A.non-rfc3161-receipt-authentication-profile.md) | `8067a55d4434e04faf85948191eda9404ef33b81` | `f6995622f93093762854702fc6266efbc7d13495561205fd1ab643b4e523931c` |
| Provider integration contract | `3efb8fef034181d8f4a1ae6d3caf2952ee99095c` | Upstream authority |
| Frozen provider implementation | `f5dcfbfe8d4884fc660a292433c200ce276f69e0` | Frozen seams and view obligations |

Authority chain: frozen realization contract -> frozen non-RFC3161 selection profile -> this reviewed role-schema/codec/upload-bound closure -> separate future bounded implementation authorization. Historical UNRESOLVED language is not rewritten. Conflicts require STOP and independent review.

FROZEN_PROVIDER_REALIZATION_CONTRACT_AMENDMENT_REQUIRED = NO

## 2. Scope and classification

The schemas here define NEW_RECEIPT_BODY detached bindings over unchanged subject evidence. They do not serialize C, Q, governance subjects or frozen in-memory views into new canonical objects. C/Q and other original external subjects remain OPAQUE_EXTERNAL_EVIDENCE. E, P and activation payload remain CANONICAL_JOUS_OBJECT under the frozen serializer; S0/C0 keep frozen binary framing. Stable references remain REFERENCE_ONLY. Hash equality alone authenticates none of these.

The role inventory below is derived from six qualification seams, two role-specific admissions, two entries, two internal dispatch claims, publication/CAS results, authoritative readback, custody phases, independent result verification, verifier provenance, nested proof traversal, governance and key lifecycle authority. The earlier analytical “23 families” is not a frozen enum.

All 24 binding roles use JOUS_NON_RFC3161_RECEIPT_BINDING_V1. Original RFC3161 DER/CMS time tokens do not require a KMS wrapper to become time authority. Clock qualification/validation/error attestations are covered separately as proof subjects. Broker signatures do not issue Q, independent verification, governance adoption or key lifecycle authority.

## 3. Closed types and universal rules

Every field listed in this document is REQUIRED, non-null and present exactly once unless explicitly declared nullable. There are no optional/default fields or extension bags. Every nested object is closed. Reject unknown members, duplicate decoded names (including escape-equivalent names), wrong types and invalid domains. No coercion, floating-point authority values, NaN or infinity is allowed in new bodies/envelopes. Opaque subjects are not reparsed under a new schema merely because a binding signs their digest.

| Type | Exact domain |
|---|---|
| ID | JSON string, valid Unicode; strict UTF-8 length 1..255 bytes, not all whitespace; frozen identifier validation applies |
| U63 | JSON integer lexical token in 0..9223372036854775807; no Boolean, decimal point or exponent |
| UTC | JSON integer token in -9223372036854775808..9223372036854775807 UTC microseconds |
| H | Lowercase hexadecimal JSON string matching `[0-9a-f]{64}` |
| B64 | Strict unpadded base64url string; A-Z/a-z/0-9/-/_ only; no whitespace/padding/nonzero unused bits; decode/re-encode must equal input |
| Ref | Closed object `{identity:ID,sha256:H}`; compare both identity and SHA256 of COMPLETE original bytes |
| MaybeRef | Ref or explicit null only under its stated rule |
| Refs | Array of 0..256 distinct Ref; repeated identity with different digest rejects; field-specific mandatory dependencies cannot be omitted |
| ARN | Full string `arn:<partition>:kms:<region>:<12 decimal account digits>:key/<key-id>`; nonempty components; no alias; exact match to independent approved binding |
| Text | Valid Unicode string, UTF-8 length 1..1024 bytes; additional field constraints below apply |
| Role | Exactly one of the 24 case-sensitive identifiers in §4 |
| Path | Array of 1..64 frozen field-name strings or integer indices 0..4095; only actual reference/opaque leaves under the permitted frozen root are legal |

All values additionally satisfy frozen field predicates. Native device/inode IDs retain their upstream arbitrary-precision nonnegative integer domain in their original opaque evidence; they are not narrowed to U63. A signature does not make a diagnostic value authoritative. Reference transport converts frozen service digest bytes to/from lowercase hex only; it changes no frozen identity rule.

## 4. Complete receipt-role inventory and finite reference mapping

For every row: subject classification = unchanged OPAQUE_EXTERNAL_EVIDENCE; signed representation = NEW_RECEIPT_BODY; KMS binding = REQUIRED; consuming verifier = qualified EvidenceVerifier; independent verification = REQUIRED. Independent approval/result/governance producers additionally require the frozen actor incompatibility. Time = separately qualified RFC3161/monotonic evidence for applicability, never the KMS signature. Custody = complete subject and binding-envelope retention under §9, with finite control-evidence exceptions explicitly described there. `Stage` is enforced transitively.

| Role | Producing authority | Operation/frozen role | Subject interpretation | Stage | Detail code | Exact downstream position/comparison |
|---|---|---|---|---|---|---|
| QUAL_PACKAGE | Qualification authority | package | QualifiedPackageBindings | UPSTREAM_ONLY | QF | QualificationProvider.package; complete snapshot/PackageClaims and all opaque E/P roles |
| QUAL_PREPARATION | Qualification authority | preparation | QualifiedPreparation | CURRENT | QF | QualificationProvider.preparation; actual request/authorization/storage/actors/current absence |
| QUAL_CREATION | Qualification authority over actual creation | creation | QualifiedCreation | UPSTREAM_ONLY | QF | QualificationProvider.creation; preserve actual opaque C reference/raw bytes |
| QUAL_EXECUTION | Qualification authority | execution | QualifiedExecution | CURRENT | QF | QualificationProvider.execution; complete request/fresh qualification at every boundary |
| QUAL_APPROVAL | Independent approval authority | approval | ApprovalView | Q | QF | QualificationProvider.approval; preserve opaque Q; exact P/C0/K/J/independence/validity |
| QUAL_OPENING | Qualification authority | opening | QualifiedOpen | CURRENT | QF | QualificationProvider.opening; existing-only open, fresh history/time/result verification |
| ADMISSION_PUBLICATION | Qualification authority | publication-admission | EffectAdmission | CURRENT | QF | ProtectedAuthorityProvider._admit(publication); exact package/Q/authorization/original absence |
| ADMISSION_CAS | Qualification authority | cas-admission | EffectAdmission | CURRENT | QF | ProtectedAuthorityProvider._admit(cas); exact payload/confirmed publication/original absence |
| ENTRY_PUBLICATION | Protected broker | publication-entry | EnteredOperation | CURRENT | EN | _enter; exact admission/operation/DURABLY_ENTERED_ORIGINAL |
| ENTRY_CAS | Protected broker | cas-entry | EnteredOperation | CURRENT | EN | _enter; separate CAS admission/operation |
| CLAIM_PUBLICATION | Protected broker | DISPATCH_CLAIM for publication | Claim facts | CURRENT | CL | Internal claim_commit_evidence_ref; only originating acknowledged live continuation may dispatch |
| CLAIM_CAS | Protected broker | DISPATCH_CLAIM for CAS | Claim facts | CURRENT | CL | Internal claim_commit_evidence_ref; never frozen success or transferable permission |
| RESULT_PUBLICATION | Protected broker | publication-result | CheckpointResult | CURRENT | PB | publication_receipt_ref and CheckpointResult.evidence; non-activating C0 anchor |
| RESULT_CAS | Protected broker | cas-result | ActivationResult | CURRENT | AC | activation_receipt_ref and ActivationResult.evidence; exact original transition |
| READBACK | Protected authoritative observation source | readback | ReadbackView | CURRENT | RB | Distinct raw readback result.evidence; exact original plus writer-primary ordering |
| CUSTODY_RESERVE | Custody authority | EVIDENCE_CUSTODY_BINDING.RESERVE | Reserve facts | CURRENT | CR | Reservation decision/acknowledgement; no confirmed retain result |
| CUSTODY_VERSION | Custody authority | Single-upload exact-version observation | Version facts | CURRENT | CV | CustodyVersion.custody_authentication_ref before BIND |
| CUSTODY_BIND | Custody authority | EVIDENCE_CUSTODY_BINDING.BIND | Binding facts | CURRENT | CB | Immutable locator/binding_decision_ref; retain returns SAME original subject reference |
| INDEPENDENT_RESULT | Independent result verifier | INDEPENDENT_RESULT_VERIFICATION | Result verification facts | INDEPENDENT_RESULT_VERIFICATION | IV | OpenRequest.independent_result_verification; every frozen result obligation |
| VERIFIER_ATTESTATION | Independently qualified evidence verifier | verify | Actual verification result | Inherit subject stage | VA | AuthenticatedView.provenance; not its own authority proof |
| PROOF_BINDING | Independently authorized original subject issuer/attestor | Exact nested proof leaf | Unchanged leaf subject | Inherit parent stage | PF | Exact frozen _proofs/opaque role/reference position; preserve raw reference |
| GOVERNANCE | Independent governance/adoption authority | Selection/qualification/adoption record | Existing governance decision | CURRENT | GV | ProviderBinding.selection/.qualification/.adoption and exact authority roots |
| KEY_BINDING | Independent key-authority approver | Key-authority binding | Existing independent approval | CURRENT | KB | Key binding/adoption root for permitted issuer/roles/scope |
| KEY_STATUS | Independent lifecycle/status authority | Lifecycle/status observation | Actual key lifecycle evidence | CURRENT | KS | Envelope key_status_ref; no inferred trusted signing time |

### 4.1 Nested proofs, excluded operations and authority separation

PROOF_BINDING legal roots are exactly the frozen returned interpretations for the six QUAL, two ADMISSION, two ENTRY, RESULT_PUBLICATION, RESULT_CAS and READBACK roles, plus frozen E/P reference traversal. Legal leaves are Reference, EvidenceReference or OpaqueEvidence fields, including actual tuple elements. The actual field/type/path and leaf reference MUST match the frozen object. `request`/`snapshot` are bound context, not traversed to manufacture authority. Opaque roles retain exact OpaqueEvidence.role; other paths retain exact frozen `view.<field>.<index>...` spelling; E/P paths retain frozen `_references` order. No arbitrary getter, SQL or caller-selected expression is accepted.

Purpose is exactly CREATION, STORAGE, HOST, SCOPE, ACTOR, AUTHORIZATION, AUTHORITY, REPRESENTATION, SOFTWARE, GENERATION, HISTORY, PROTECTED_STATE, REQUIREMENTS, CLOCK_PROFILE, CLOCK_SAMPLE_VALIDATION, CLOCK_PROPAGATION, INDEPENDENCE, VALIDITY_STATUS or PROVENANCE, determined by that leaf's frozen semantic field and required obligations. A mismatch rejects. Dedicated governance/key roles cannot be bypassed through this role. No role grants new approval/adoption rights. Actual IAM principals/credentials remain future selections.

READ_ONLY_RESOLUTION creates NO new receipt or state: it only returns the already-established five frozen categories within approved scope. Its references resolve to prior role receipts/locators/readback facts. No resolution-signing role or fresh effect success is introduced. Definite negative operation decisions can be bound under the applicable operation role; a duplicate/rejection never becomes new protected success. No historical F/G or completion operation becomes eligible.

## 5. Exact signed-body schema

Every body is exactly these fields plus the selected closed details variant. Each is required. Classification: A = authority claim requiring independent proof, E = evidence of actual observation, R = reference-only. No diagnostic extension fields are admitted.

| Field | Exact type/domain | Source, applicability and comparison | Class |
|---|---|---|---|
| profile_id | Literal JOUS_NON_RFC3161_RECEIPT_BINDING_V1 | All roles; selected frozen profile | A |
| schema_version | Integer literal 1 | All roles; this codec | A |
| receipt_role | Role | Exact inventory row and independently permitted key/issuer role | A |
| receipt_id | ID | Allocated once before signing, independently of future complete-byte hash; no regeneration on uncertainty | R |
| issuer_id | ID | Actual binding issuer, not relabeled original subject issuer | A |
| provider_id | ID | Independently selected provider | A |
| authority_id | ID | Actual adopted logical authority | A |
| account_id | String of exactly 12 decimal digits | KMS key owner; compare ARN/adoption, not automatically subject tenant | A |
| region | ID | Key Region; exact ARN/adoption comparison | A |
| namespace | ID | Exact operation/provider authority scope | A |
| incarnation_id | ID | External qualified authority incarnation, not copied DB flag | A |
| configuration_ref | Ref | Approved secret-free configuration, codec and upload bound | R |
| adoption_ref | Ref | Actual independent authority adoption and current scope/validity | R |
| key_binding_ref | Ref | Existing independent key/authority/roles approval | R |
| key_status_ref | Ref | Applicable independent lifecycle/status evidence | R |
| key_arn | ARN | Actual key; compare Sign response, key binding and public material | A |
| spki_sha256 | H | SHA256(exact retained DER SPKI); approved RSA_3072/SIGN_VERIFY | A |
| signature_algorithm | Literal RSASSA_PSS_SHA_256 | No negotiation | A |
| stage | Literal UPSTREAM_ONLY, Q, CURRENT or INDEPENDENT_RESULT_VERIFICATION | Inventory stage; PF/VA inherit exact subject stage | A |
| subject_ref | Ref | Complete unchanged subject bytes/digest/native identity | R |
| subject_issuer_id | ID | Authenticated original issuer; attestor cannot impersonate | A |
| subject_kind | Literal OPAQUE_EXTERNAL_EVIDENCE | Every role; canonical inputs remain subject dependencies | A |
| request_id | ID | Actual source operation/observation/governance issuance request | R |
| request_ref | Ref | Retained immutable request provenance binding exact request/context, no secrets | R |
| context | Context from §6 | Exact complete authenticated role context | A |
| predecessor_refs | Refs | All and only existing causal predecessors under rule below | R |
| qualification_ref | Ref | Actual independent issuer/interpretation/rights/configuration qualification | R |
| time_ref | Ref | Independently qualified current time evidence, valid source/profile/error/continuity | R |
| valid_from_us | UTC | Actual role authorization start | A |
| valid_until_us | UTC | Actual end; from <= until; full current interval must fit | A |
| outcome | Literal ESTABLISHED or REJECTED | Actual observed/durable decision; not global ACTIVE permission | E |
| rejection_reason | Literal NONE or frozen realization §5.4 reason | NONE iff ESTABLISHED; actual negative subject otherwise | E |
| details | Exact §7 object for role | Closed factual fields, not arbitrary claims bag | A/E/R |

The frozen rejection reasons are DUPLICATE, INPUT_CONFLICT, LIFECYCLE_CONFLICT, WRONG_PREDECESSOR, ALREADY_ACTIVE, WRONG_INCARNATION, UNQUALIFIED, INVALID_INPUT, STALE_CONTINUATION, CUSTODY_CONFLICT and SIZE_UNSUPPORTED. Rejected receipt bodies prove only actual negative facts; they do not create qualified positive views or erase UNKNOWN.

predecessor_refs order: existing Context Ref dependencies in table order, then detail Ref fields in table order, then required frozen typed-subject reference leaves in frozen field/tuple order; distinct identity/hash at first occurrence only. Exclude subject_ref itself and separately named trust/time roots; prohibit future/downstream dependencies. Empty lists cannot waive required dependencies. No self hash, future receipt reference or future custody version appears in a signed body.

Native request provenance may be an approved separate secret-free immutable facts record, rather than secret-bearing original API bytes. It must bind actual request/content/native identity, and MUST NOT be misrepresented as the unchanged original secret-bearing request. This never permits secret leakage or projected-success fabrication.

## 6. Closed Context

Every listed member is required. Null is accepted ONLY under the stated rule. No handles, locks, connections, NativeStorage, GenesisAttempt or exception objects are serialized. Actual in-memory request/ownership comparisons remain frozen requirements.

| Field | Type | Source/domain/null rule; all facts A, references R |
|---|---|---|
| kind | Literal PACKAGE, PREPARATION, CREATION, EXECUTION, APPROVAL, OPENING, PUBLICATION, CAS, READBACK, CUSTODY, GOVERNANCE or KEY | Corresponding role/stage |
| register_id | ID or null | Required PACKAGE through READBACK and inherited register-scoped proofs; null only genuinely non-register custody/governance/key context |
| generation | Integer literal 1 or null | Paired with register_id |
| activation_id | ID or null | Paired with register_id |
| K | ID or null | Exact original activation command; paired with register_id |
| J | ID or null | Exact pending approval identity, paired with register_id; never future Q digest |
| host_ref | MaybeRef | Required register-scoped context; otherwise null |
| scope_ref | Ref | Explicit independent authorized scope for every role |
| operation_id | ID or null | Required protected admission/entry/claim/result/readback; otherwise null unless actual existing operation subject is being bound |
| operation_role | Literal CHECKPOINT_PUBLICATION, ACTIVATION_CAS or null | Required paired protected operation role; otherwise null |
| authorization_ref | Ref | Actual independently authorized action/observation/governance/custody/key scope |
| input_binding_ref | MaybeRef | Required admitted protected operation; otherwise null |
| E_ref | MaybeRef | Required PACKAGE/EXECUTION/APPROVAL/PUBLICATION/CAS/READBACK/OPENING; PREPARATION/CREATION prohibit |
| S0_ref | MaybeRef | Same stages as E_ref; creation uses actual state in opaque subject, not future package |
| C0_ref | MaybeRef | Same as E_ref |
| P_ref | MaybeRef | Same as E_ref |
| Q_ref | MaybeRef | Required EXECUTION/APPROVAL/PUBLICATION/CAS/READBACK/OPENING; PACKAGE/PREPARATION/CREATION prohibit |
| payload_ref | MaybeRef | Required CAS/READBACK/OPENING; PACKAGE/PREPARATION/CREATION/EXECUTION/APPROVAL/PUBLICATION prohibit |
| publication_ref | MaybeRef | Required CAS/READBACK/OPENING; other kinds prohibit |
| activation_ref | MaybeRef | Required READBACK/OPENING; other kinds prohibit; no future result in CAS |
| request_facts_ref | Ref | Existing authenticated complete native/request facts; compare actual context fieldwise, never deserialize live ownership |

Six QUAL roles map to corresponding first six Context kinds. Publication ADMISSION/ENTRY/CLAIM/RESULT map to PUBLICATION; CAS variants to CAS; READBACK and INDEPENDENT_RESULT to READBACK; CUSTODY roles to CUSTODY; GOVERNANCE to GOVERNANCE; KEY roles to KEY. PF/VA inherit actual subject context. Unlisted inapplicable reference fields are null, never invented. A request_facts_ref or dependency cannot smuggle downstream evidence into an upstream context.

## 7. Closed detail expansions

Each variant below has exactly the fields shown. All required/non-null except explicit MaybeRef. IDs/literals/scopes are A; counters/state/decision observations E; Ref fields R. Types, upstream sources, stage and comparison rules apply to EVERY field, not an implementer-selected subset.

| Code / roles | Exact fields and types/domains | Source and comparison |
|---|---|---|
| QF / six QUAL plus two ADMISSION | view_type:ID; view_subject_ref:Ref; view_provenance_ref:Ref; obligations:Obligations | Exact inventory type; subject equals top-level subject_ref; actual preexisting provenance. Complete native subject must prove every Appendix A field, frozen role predicate and requested obligation; no copying expected success. |
| EN / two ENTRY | admission_ref:Ref; operation_id:ID; state:literal DURABLY_ENTERED_ORIGINAL; decision_ref:Ref; state_version:U63; fence_value:U63 | Actual completed ORIGINAL_ATTEMPT_ADMISSION, exact original input/lifecycle; receipt replay creates no live continuation. |
| CL / two CLAIM | admission_id:ID; admission_ref:Ref; operation_id:ID; operation_role:literal CHECKPOINT_PUBLICATION or ACTIVATION_CAS; input_binding_ref:Ref; broker_principal_id:ID; dispatch_claim_id:ID; claim_decision:literal CLAIMED; claim_decision_ref:Ref; claim_commit_evidence_ref:Ref; claim_fence_value:U63 | Exact durable claim and definite completed qualified acknowledgement; variant role and actual broker identity match. No transaction/backend/session ID as authority. |
| PB / RESULT_PUBLICATION | operation:ID; checkpoint:Ref; package:Ref; approval:Ref; host_identity:ID; status:literal CONFIRMED or REJECTED; decision_ref:Ref; state_version:U63; claim_ref:Ref | Actual atomic non-activating publication. Compare CheckpointResult except own evidence supplied after receipt retention. CONFIRMED only with full frozen confirmation/custody. |
| AC / RESULT_CAS | command_id:ID; payload_sha256:H; package:Ref; checkpoint:Ref; approval:Ref; register_id:ID; generation:integer literal 1; activation_id:ID; host_identity:ID; status:literal CONFIRMED or REJECTED; decision_ref:Ref; state_version:U63; claim_ref:Ref | Exact actual atomic activation decision/payload. Generation is target binding, not inference of execution if rejected. Own evidence supplied after retention. |
| RB / READBACK | original_ref:Ref; activation_decision_ref:Ref; ordering_ref:Ref; state:literal LINEARIZABLE_CURRENT_AFTER_ORIGINAL; state_version:U63; fence_value:U63; result_ref:Ref; observation_time_ref:Ref | Actual new writer-primary facts; original result exact; result_ref is existing fact subject, not future readback receipt. Compare complete ReadbackView with frozen sole evidence-reference substitution. |
| CR / CUSTODY_RESERVE | custody_attempt_id:ID; evidence_ref:Ref; raw_size:U63; bucket_resource_ref:Ref; object_key:Text; custody_role:ID; retention_mode:literal COMPLIANCE; required_retention_until:UTC; retention_requirement_ref:Ref; reservation_decision_ref:Ref; state:literal RESERVED | Actual reserve acknowledgement and exact deterministic key/plan; size check BEFORE reserve. No replayed upload continuation. |
| CV / CUSTODY_VERSION | custody_attempt_id:ID; evidence_ref:Ref; raw_size:U63; bucket_resource_ref:Ref; object_key:Text; version_id:Text; retention_mode:literal COMPLIANCE; observed_retention_until:UTC; retention_requirement_ref:Ref; upload_response_ref:Ref; exact_version_readback_ref:Ref; retention_evidence_ref:Ref | Definite one-upload success; exact non-null/non-literal-null version, complete raw digest/size and retention verification. No future BIND dependency. |
| CB / CUSTODY_BIND | custody_attempt_id:ID; evidence_ref:Ref; raw_size:U63; bucket_resource_ref:Ref; object_key:Text; version_id:Text; custody_role:ID; retention_mode:literal COMPLIANCE; observed_retention_until:UTC; retention_evidence_ref:Ref; version_observation_ref:Ref; binding_decision_ref:Ref; state:literal BOUND | Actual immutable completed BIND; reserved identity/digest/key/version/retention all match; no own future custody. |
| IV / INDEPENDENT_RESULT | activation_ref:Ref; publication_ref:Ref; readback_ref:Ref; requirements_ref:Ref; verification_result_ref:Ref; independence_ref:Ref; obligations:Obligations; verdict:literal ALL_REQUIRED_OBLIGATIONS_PROVED or REJECTED | Actual independent decision over original acceptance/readback/all frozen result requirements; not broker self-approval. |
| VA / VERIFIER_ATTESTATION | verified_subject_ref:Ref; authenticated_binding_ref:Ref; expectation_ref:Ref; interpretation_role:Role; interpretation_type:ID; obligations:Obligations; verification_result_ref:Ref; verdict:literal VERIFIED or REJECTED | Actual independent qualified verifier result; exact full expectation/context. No own future provenance as prerequisite/subject. |
| PF / PROOF_BINDING | parent_role:Role; parent_subject_ref:Ref; field_path:Path; frozen_role:ID; purpose:literal from §4.1; leaf_ref:Ref; interpretation_ref:Ref; obligations:Obligations | Actual leaf/path/type/stage; leaf_ref equals subject_ref. Interpretation is independently qualified, not arbitrary executable selection. |
| GV / GOVERNANCE | record_kind:literal SELECTION or QUALIFICATION or ADOPTION; governed_provider_id:ID; governed_authority_id:ID; governed_incarnation_id:ID; governed_configuration_ref:Ref; governed_scope_ref:Ref; governance_decision_ref:Ref; independence_ref:Ref | Actual independently authorized existing governance subject; receipt itself does not create adoption. |
| KB / KEY_BINDING | authorized_key_arn:ARN; authorized_spki_sha256:H; authorized_algorithm:literal RSASSA_PSS_SHA_256; authorized_issuer_id:ID; authorized_provider_id:ID; authorized_authority_id:ID; authorized_namespace:ID; authorized_incarnation_id:ID; authorized_configuration_ref:Ref; permitted_receipt_roles:array of 1..24 distinct Role; authority_valid_from_us:UTC; authority_valid_until_us:UTC; supersedes_ref:MaybeRef; lifecycle_authority_ref:Ref; independent_approval_ref:Ref | Actual independent key authority; scope/role/validity exact. Supersedes null only initial key; replacement names old binding. Signing approver key is not automatically the key being authorized. |
| KS / KEY_STATUS | observed_key_arn:ARN; observed_spki_sha256:H; key_binding_ref:Ref; lifecycle_state:literal ENABLED, DISABLED, PENDING_DELETION, DELETED, REVOKED or COMPROMISED; status_valid_from_us:UTC; status_valid_until_us:UTC; status_source_ref:Ref; supersession_ref:MaybeRef; status_authority_ref:Ref | Actual independent lifecycle observation; supersession null iff none established. Missing/ambiguous status never means ENABLED. |

All validity pairs require from <= until and complete authenticated current interval applicability. Object keys obey exact frozen deterministic key derivation/service bound; version IDs are exact nonempty service strings, never null or literal null. PB/AC status CONFIRMED iff outcome ESTABLISHED; negative outcome never returns successful frozen result. IV/VA verdict matches outcome. Other rejected bindings establish only actual negative facts, never a qualified positive view.

Obligations is the exact requested duplicate-free frozen obligation tuple in frozen order: the six _COMMON literals, corresponding _OBLIGATIONS role literals, and EXACT_ROLE_CONTEXT_ISSUER/TRANSITIVE_STAGE_RESTRICTIONS for nested proofs. No arbitrary new string or subset is allowed. IV additionally authenticates complete existing frozen result requirements through requirements_ref, not a new obligation enum. QUAL_PACKAGE/CREATION forbid Q/payload/results transitively; QUAL_APPROVAL permits actual Q but forbids downstream payload/results. Signature validity does not prove an obligation merely because its name appears.


## 8. Exact body encoding and signature assembly

JCS_REQUIRED = NO

JCS_SELECTED = NO

The signed body is the complete original immutable UTF-8 JSON byte sequence. Accept one object without BOM; reject invalid UTF-8/Unicode, unpaired surrogates, duplicate decoded names, unknown/missing members, wrong types/domains and trailing non-whitespace. JSON leading/trailing whitespace is only bytes 20/09/0A/0D and remains part of the signed bytes. The frozen profile did not forbid grammar whitespace, so acceptance does not silently strip it or newly prohibit it.

No verification-time normalization, Unicode normalization, key reordering, whitespace normalization, re-encoding or parsing-and-reserialization is permitted. Parse for schema/claim checks while preserving original bytes for hashing. Semantically equivalent alternative JSON encodings remain different authority-bearing objects.

Deterministic NEW receipt producers use schema-table field order, UTF-8 without BOM, compact comma/colon separators, no extra leading/trailing whitespace or final LF, minimal decimal integers, unescaped ordinary Unicode scalars, standard JSON quote/backslash escapes, and lowercase hex control escapes. These are producer rules, not JCS or verifier canonicalization, and do not modify frozen E/P/payload serialization. Refs use identity then sha256 field order; arrays preserve their prescribed order.

Assembly is exactly:

receipt_body_bytes -> SHA256(exact complete bytes) -> 32-byte digest -> AWS KMS Sign(MessageType=DIGEST, RSA_3072/SIGN_VERIFY, RSASSA_PSS_SHA_256) -> MGF1-SHA256 / 32-byte salt -> original 384-octet signature.

External verification uses prehashed SHA-256 and exact PSS parameters. Double hashing, salt-length auto-detection, alternate algorithms and fallback signers are forbidden. Retain exact original body bytes/signature octets, full ARN, exact DER SPKI/fingerprint, algorithm/profile and independently resolvable adoption/lifecycle/status/time evidence. Check complete subject bytes, schema, actual key/issuer authority and role claims; mathematical validity alone never qualifies a receipt. No new key, endpoint or resource is selected.

## 9. Exact detached envelope and finite evidence DAG

The complete external raw receipt is one closed UTF-8 JSON envelope with exactly these required members, in producer order. The same JSON acceptance and producer conventions apply. The envelope is NOT the signed body and is not substituted for body hashing.

| Field | Type/domain | Required association/comparison |
|---|---|---|
| envelope_version | Integer literal 1 | This codec |
| profile_id | Literal JOUS_NON_RFC3161_RECEIPT_BINDING_V1 | Equals body |
| body | B64 | Exact original receipt_body_bytes |
| body_sha256 | H | SHA256(decoded complete body), no normalization |
| signature | B64 | Decodes to exactly 384 original signature octets |
| key_arn | ARN | Equals body, Sign response and independent key binding |
| spki_sha256 | H | Equals body and approved exact DER SPKI hash |
| signature_algorithm | Literal RSASSA_PSS_SHA_256 | Equals signed profile |
| key_binding_ref | Ref | Equals signed body; existing independent authority |
| key_status_ref | Ref | Equals signed body; independently applicable status |
| authority_adoption_ref | Ref | Equals body adoption_ref |
| trusted_time_ref | Ref | Equals body time_ref; independent qualified time |
| subject_custody_ref | MaybeRef | Existing exact subject BOUND custody evidence; null ONLY for original bootstrap/control evidence independently retained under qualified finite control-evidence arrangements |

subject_custody_ref authenticates the original SUBJECT, not this envelope's own future custody. It must resolve to exact identity/digest/resource/key/version/retention/issuer/context; it cannot authorize itself. Null never waives actual required raw retention or lets an ordinary returned subject claim custody without evidence.

The final frozen EvidenceReference is `(body.receipt_id, SHA256(complete original envelope bytes))`. This is the existing opaque external complete-byte identity rule, not a new IL6 canonical hash domain. The receipt ID is allocated independently of complete receipt hash. No own final hash/reference, signature or future S3 version is in the body being signed. Changed envelope bytes imply a changed hash even if parsed claims match. The underlying opaque subject retains its original reference/raw identity; a later binding does not retroactively make its signer the original issuer.

EvidenceClient.retain(record) always returns record.reference unchanged. A binding is an independently retained association, not a replacement for the subject bytes/reference. Receipt envelopes themselves require complete retention before confirmed returned success. Their own exact-version locators are external associations established AFTER complete envelope bytes exist and MUST NOT be inserted into their bodies/envelopes.

Finite sequence: independently approved external bootstrap roots/public material and independently retained raw control/time provenance -> actual subjects and existing predecessors -> signed body -> detached envelope/final reference -> separate custody associations -> independent verifier provenance -> frozen typed view/reference consumer. No upstream subject may depend on its own future binding receipt, future verifier result or future locator. A verifier attestation may verify a prior receipt; that prior receipt must not require that future attestation to exist before it is signed.

A custody receipt authenticates its subject's exact object/version and actual decision. Its own later receipt-retention acknowledgement is a raw control observation retained under independently qualified finite bookkeeping, not another recursively mandatory signed custody receipt. A definite internal acknowledgement is not independently qualified frozen success. Required raw retention and provenance cannot be replaced by a cache, invented locator or an infinite chain of uploads of acknowledgements.

KEY_BINDING, KEY_STATUS and GOVERNANCE must terminate in independently retained external trust/bootstrap approval. No key may self-authorize, and no cycle of keys adopting each other is accepted. A qualified verification capability validates its roots without requiring a newly issued verifier receipt for every verifier receipt. Missing operational root material yields fail-closed, not a synthesized bootstrap. Exact operational roots remain future selections/qualification, not a codec choice left open.

## 10. Reference-to-view mapping and complete claims

For each inventory row the mapping is finite and explicit: named producer -> unchanged subject -> named authentication receipt -> required separate time -> subject/envelope custody -> independent qualified verification result/provenance -> exact downstream reference position in ?4. Every step compares full identity/hash, role/issuer, namespace/incarnation/configuration/adoption, exact context, validity/status, causal predecessors and actual frozen obligations.

Appendix A is complete returned-view field coverage. It is NOT a new wire schema for C/Q. The binding schema authenticates unchanged raw subject bytes plus the exact frozen interpretation/context; actual native subject interpretation remains the independently qualified evidence-verifier responsibility already required by frozen authority. A mere signed typed_view label, reference, projected request or parser success does not prove the corresponding claims. All native interpretation/provenance and every frozen field must authenticate before the view is returned. No opaque subject is silently converted into a newly serialized Jous object.

Closed self-reference mappings:

- RESULT_PUBLICATION -> CheckpointResult.evidence is the final retained envelope reference; no body field contains its own evidence hash.
- RESULT_CAS -> ActivationResult.evidence is the final retained envelope reference.
- READBACK -> observed.result.evidence is its distinct final readback receipt reference; original result evidence stays exact. Compare all other result fields exactly and prove actual primary ordering.
- QUAL_CREATION and QUAL_APPROVAL preserve the ORIGINAL opaque C/Q reference/raw/qualification. Their authentication bindings do not replace C/Q identities.
- PROOF_BINDING returns the exact original reference at its leaf; OpaqueEvidence.raw is independently resolved unchanged. It never replaces that leaf with the binding-envelope reference.
- AuthenticatedView.reference names the actual verified record; expectation equals the complete original EvidenceExpectation (provider and retention bindings, role, full context, stage, obligations). provenance is distinct retained verification evidence, not self-authentication. value is the exact frozen type and values. clock and validity are authenticated current facts, never copied caller request.clock.
- Custody returned reference remains the supplied record.reference; locator/binding evidence is separately associated. READ_ONLY_RESOLUTION returns only prior facts/references, never fresh effect authority.

Transitive order stays: preparation -> actual C/S0 -> E/G/C0/P -> independent Q -> payload -> separately authorized publication -> CAS -> authoritative readback -> independent result verification -> full frozen ACTIVE checks. Package/creation exclude downstream Q/payload/results. Q excludes payload/results. Admissions require exact already-complete package/Q; CAS requires confirmed publication. Opening never creates original-operation eligibility.

## 11. Failure and UNKNOWN table

| Stage/condition | Exact handling |
|---|---|
| Malformed signature/base64/envelope or unsupported algorithm/length | Definite evidence rejection; retain original bytes/error provenance |
| Wrong known key/ARN/SPKI or bad mathematical signature | Reject; no fallback signer/algorithm |
| Unknown/unapproved key or missing adoption | Fail closed; no qualified receipt |
| Authority expired/not yet valid | Reject current applicability using full independently qualified UTC interval |
| Revoked/compromised key | Reject operational reliance; quarantine/adjudicate affected scope; historical math validity is separate |
| Disabled/deleted/pending-deletion key | No new use requiring enabled status; historical external mathematical verification does not restore authority |
| Status unavailable/stale/contradictory or lifecycle ambiguous | No qualified result; retain strongest existing UNKNOWN/recovery boundary |
| Complete body/subject hash mismatch | Reject, preserve evidence, STOP applicable progression |
| JSON parse/schema/type/domain/path mismatch | Definite evidence rejection; no normalization repair |
| Ambiguous external verification | Unconfirmed/no qualified result; retain strongest existing uncertainty |
| Required raw subject/proof/custody/time unavailable | No qualified result; no substitute cached success |
| Ambiguous KMS signing entry/result | Authentication unconfirmed; no signing resubmission, new signer or new receipt identity |
| Known DB decision followed by signing/custody failure | Preserve known decision/evidence gap; no CONFIRMED return and no protected-effect replay |
| Admission/claim/effect/upload/binding ambiguity | Frozen UNKNOWN or UNKNOWN_CUSTODY; signature cannot clear it |
| Read-only resolution finds historical evidence | Observation only; never recreated dispatch permission or automatic recovery |

REPLAY_ON_AUTHENTICATION_UNCERTAINTY = FORBIDDEN

No SDK/HTTP/middleware/job/application replay, alternate signer, algorithm negotiation, re-signing to overcome uncertainty, identity regeneration or automatic recovery is permitted. A later definite evidence rejection cannot erase an earlier uncertain effect boundary. Evidence rejection is not proof that an already-entered effect did not occur.

## 12. Trusted time

KMS_SIGNATURE_IS_TRUSTED_TIME = NO

SIGNED_TIMESTAMP_IS_TRUSTED_TIME = NO_UNLESS_SEPARATELY_QUALIFIED

Every current role applicability uses independently qualified time_ref and full-interval validity. Original RFC3161 request/response DER, nonce/imprint/policy/signer/status/accuracy and selected DigiCert Europe profile remain controlling. The qualified same-process/domain monotonic bridge, uncertainty/freshness/error rules, outward rounding and restart invalidation remain exact. No TSA access or actual signer/endpoint is selected.

Clock profile/sample validation/propagation qualification is authenticated through PROOF_BINDING CLOCK_* subjects; raw tokens remain RFC3161 time evidence, not KMS receipts. Creation time stays fixed. Preparation authorization uses authenticated current qualification time. Execution/admission/claim/effect/opening and Q applicability use fresh authenticated current time at their frozen boundaries. No request-clock-only authority, OS-wall-clock fallback, midpoint/half-RTT inference or persisted-anchor restart re-use is introduced. Key status/adoption validity and pre-compromise reliance require independently qualified time/provenance; a signed timestamp claim is insufficient.

## 13. PIR-02: exact pinned upload bound

max_single_upload_bytes = 8388608

MAX_SINGLE_UPLOAD_BYTES = 8388608

MAX_SINGLE_UPLOAD_HUMAN_EQUIVALENT = 8 MiB (8,388,608 bytes)

This exact positive integer is approved configuration authority, part of the secret-free configuration fingerprint. There is no default, automatic enlargement, per-call override or provider-maximum mode. It applies to EACH complete raw object, including the detached envelope AFTER base64/JSON overhead. Checking only the decoded body/subject is insufficient. Independently existing dependency objects may be retained separately under their own immutable identities; this does not permit splitting one authoritative object.

Derived frozen constraints: realization ?14.1 requires fixed complete bytes/hash/size BEFORE RESERVE or upload, support by the selected low-level API, exactly one non-replayed conditional create, fixed identity/key/attempt/resource/retention, no multipart/transfer manager/resume/rewind and no partial hashing. Complete size must fit BOTH this selected bound and the independently verified actual path/service limit.

The frozen authority contains no numerical provider maximum. External factual premise requiring later verification: the exact selected S3 low-level PutObject API/library/configuration supports at least 8,388,608 bytes in one request. The conservative 8 MiB selection is intended to be far below the commonly documented multi-gigabyte single-request ceiling; that ceiling is not asserted here as qualified or frozen fact. Before implementation authorization relying on a concrete API/build, independently check its documented limit; managed qualification must establish the actual supported path/configuration. If the premise fails, STOP for review; never silently change the bound. No AWS access/probe or remote research was used for this offline selection.

Expected subjects are metadata-scale ceremony/package/approval/qualification/decision/time/control evidence and detached receipts, not register dumps, database backups or software archives. Eight MiB supplies conservative headroom, including envelope overhead. This is an intended supported workload, NOT a claim that every possible opaque subject fits. Future conformance fixtures must measure expected complete objects; an oversized required object needs a separate reviewed bound decision, not silent enlargement or bypass.

If object_bytes > 8388608, or the actual path cannot support its size, reject BEFORE custody RESERVE, upload latch consumption or upload dispatch: existing `disposition=REJECTED`, `reason=SIZE_UNSUPPORTED`, prior_decision_ref null unless an actual prior decision exists. At frozen client seams this is ActivationRejected/ProviderBoundaryFailure preserving the reached boundary, never a new success type. Check all already-known required object sizes before entering protected work. If an unexpected oversized receipt arises AFTER a known DB decision, preserve that decision/evidence gap; do not assert no DB effect or replay it. If prior entry was uncertain, preserve UNKNOWN.

Do NOT split, multipart-upload, truncate, compress/re-encode merely to bypass the bound, switch provider/mechanism, regenerate a key/attempt, weaken custody or retry. Size validation cannot edit an immutable receipt into acceptance. Frozen deterministic key derivation, If-None-Match: *, versioning, COMPLIANCE retention, exact non-null version, full readback/digest, immutable BIND and authenticated custody remain mandatory. Ambiguous upload remains UNKNOWN_CUSTODY, with no second upload.

MULTIPART_UPLOAD_ALLOWED = NO

OVERSIZE_OBJECT_DISPOSITION = REJECTED/SIZE_UNSUPPORTED_BEFORE_RESERVE_OR_UPLOAD; PRESERVE_ANY_PRIOR_KNOWN_DECISION_OR_UNKNOWN

## 14. Exact ten-file future implementation mapping

| Future file | Documentary rule consumer; none created now |
|---|---|
| services/api/infrastructure/fixture_lease_authority_provider_clients.py | Role/context/reference mappings; exact frozen view/expectation matching; explicit bound configuration |
| services/api/infrastructure/fixture_lease_authority_transaction_broker.py | Entry/claim/publication/CAS/readback facts, actual decision correspondence and one-dispatch/no-replay boundary |
| services/api/infrastructure/fixture_lease_authority_evidence.py | Strict body/envelope parsing, KMS/external crypto, exact hashes/bytes, graph/locator/custody and oversize checks |
| services/api/infrastructure/fixture_lease_authority_time.py | Existing RFC3161 and qualified monotonic/time applicability; no KMS-time substitution |
| services/api/infrastructure/fixture_lease_authority_schema.sql | Existing frozen admission/claim/decision/receipt-material/locator immutability and references; no caller SQL or new authority |
| services/api/infrastructure/fixture_lease_authority_realization_dependencies.txt | Separately reviewed exact commodity JSON/crypto/transport dependency builds; no installation now |
| tests/test_fixture_lease_authority_provider_clients.py | Future role/schema/context/stage/frozen-reference conformance |
| tests/test_fixture_lease_authority_transaction_broker.py | Future decision/claim/fencing/UNKNOWN correspondence |
| tests/test_fixture_lease_authority_evidence.py | Future strict byte codec/signature/envelope/root/status/custody/size fixtures |
| tests/test_fixture_lease_authority_time.py | Future time separation/validity/provenance/restart tests |

IMPLEMENTATION_BOUNDARY_PATH_COUNT = 10

TEN_FILE_IMPLEMENTATION_BOUNDARY_PRESERVED = YES

EXISTING_FILES_NO_CHANGE = YES

No eleventh path, Jous service, deployment hook, migration runner or resource bootstrapper is selected. No implementation/test file is created by this document.

## 15. Authorization and operational boundary

Only after this artifact is independently reviewed, approved, staged, committed, published and independently frozen may a SEPARATE gate determine whether the ten-file implementation is authorized. This document does not self-approve or establish operational qualification/adoption. Actual accounts/Regions/keys/principals/credential carriers/root material, dependency builds and managed qualification remain downstream selections/evidence, not invented resource values.

This artifact does NOT authorize AWS account access, RDS/S3 access or creation, Object Lock configuration, KMS key creation, IAM changes, TSA access, credentials, managed-resource creation, provider adoption, register creation/preparation, genesis, checkpoint publication, activation CAS, fixture provisioning, CANARY, runtime activation or public traffic. No remote contact, staging, commit, production/test implementation or test execution belongs to this drafting gate.

## Appendix A. Complete frozen returned-view field coverage

The following tables define required coverage of each native opaque interpretation. They do NOT redefine opaque subjects as JSON objects. All listed fields are required, with exact frozen declared types, literal/numeric predicates and validators. Ref fields are reference-only, raw bytes evidentiary, identity/authorization/state claims authoritative only after actual independent proof. Exact native interpretation remains qualified external verification, not expected-value copying. request/snapshot bind the actual immutable calling context and frozen bytes; live ownership resources are never serialized.

| Frozen type | Complete field list and declared types | Source/comparison |
|---|---|---|
| PackageSnapshot | `ceremony: bytes`; `package: bytes`; `state: bytes`; `checkpoint: bytes` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| OpaqueEvidence | `role: str`; `reference: Reference`; `raw: bytes`; `qualification: service.EvidenceReference` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| CreationClaims | `reference: Reference`; `purpose: str`; `register_id: str`; `schema: SchemaBinding`; `generation: int`; `activation_id: str`; `host: HostBinding`; `storage: StorageBinding`; `scope: ScopeBinding`; `preparation_operator: str`; `authorization: service.EvidenceReference`; `fixed_utc: int`; `clock: ClockBinding`; `metadata: protocol.MetadataRow`; `native_identity: tuple[int, int]`; `state: str`; `dependency_stage: str` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| StorageClaims | `binding: StorageBinding`; `location: 'StorageLocation'`; `native_identity: tuple[int, int]`; `account: str`; `effective_access: service.EvidenceReference`; `issuer: str`; `process: str`; `host: str`; `continuity: service.EvidenceReference`; `locking_atomicity_flush_vfs: service.EvidenceReference`; `durability: service.EvidenceReference`; `filesystem: str`; `state: str` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| AuthorityClaims | `role: str`; `reference: Reference`; `version: str`; `adoption: service.EvidenceReference`; `scope: ScopeBinding` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| PackageClaims | `creation: CreationClaims`; `schema: SchemaBinding`; `host: HostBinding`; `host_authentication: service.EvidenceReference`; `storage: StorageClaims`; `scope: ScopeBinding`; `governance_target: service.EvidenceReference`; `scope_justification: service.EvidenceReference`; `actors: ActorBinding`; `actor_role_action_validity: service.EvidenceReference`; `clock: ClockBinding`; `authorities: tuple[AuthorityClaims, ...]`; `representation: RepresentationBinding`; `generation_selection: service.EvidenceReference`; `software: SoftwareBinding`; `host_vfs_compatibility: service.EvidenceReference`; `protected_authorities: ProtectedAuthorities`; `protected_trust_scope: service.EvidenceReference`; `absence: str`; `linearizable_cas: service.EvidenceReference`; `history_tombstones: service.EvidenceReference`; `original_command_outcomes: service.EvidenceReference`; `requirements: Requirements`; `requirement_applicability: service.EvidenceReference`; `authorization: Authorization`; `authorization_register_id: str`; `authorization_activation_id: str`; `authorization_command_id: str`; `authorization_host: str`; `authorization_operator: str`; `authorization_action: str`; `upstream_dependency_stage: str` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| QualifiedPackageBindings | `snapshot: PackageSnapshot`; `opaque: tuple[OpaqueEvidence, ...]`; `schema_bytes: bytes`; `profile: service.QualifiedClockProfile`; `creation_sample: service.QualifiedSample`; `provenance: service.EvidenceReference`; `claims: PackageClaims` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| QualifiedCreation | `evidence: OpaqueEvidence`; `claims: CreationClaims`; `provenance: service.EvidenceReference` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| QualifiedPreparation | `request: PreparationRequest`; `absence_history: service.EvidenceReference`; `storage: service.EvidenceReference`; `actor: service.EvidenceReference`; `authorization: service.EvidenceReference`; `valid_from_us: int`; `valid_until_us: int`; `provenance: service.EvidenceReference`; `operator: str`; `process: str`; `issuer: str`; `action: str`; `presence: str`; `original_history: str` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| ApprovalView | `evidence: OpaqueEvidence`; `package: Reference`; `checkpoint: Reference`; `register_id: str`; `generation: int`; `activation_id: str`; `host_identity: str`; `activation_command_id: str`; `approver: str`; `requester: str`; `issuer: str`; `independence: service.EvidenceReference`; `authority: service.EvidenceReference`; `authorization: service.EvidenceReference`; `not_revoked: service.EvidenceReference`; `validity_observation: service.EvidenceReference`; `valid_from_us: int`; `valid_until_us: int`; `status: str` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| QualifiedExecution | `request: ExecutionRequest`; `absence_history: service.EvidenceReference`; `storage: service.EvidenceReference`; `actor: service.EvidenceReference`; `authorization: service.EvidenceReference`; `valid_from_us: int`; `valid_until_us: int`; `provenance: service.EvidenceReference`; `clock: TimeBinding`; `operator: str`; `process: str`; `issuer: str`; `action: str`; `presence: str`; `original_history: str` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| CheckpointResult | `operation: str`; `checkpoint: Reference`; `package: Reference`; `approval: Reference`; `host_identity: str`; `status: str`; `evidence: service.EvidenceReference` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| ActivationResult | `command_id: str`; `payload_sha256: bytes`; `package: Reference`; `checkpoint: Reference`; `approval: Reference`; `register_id: str`; `generation: int`; `activation_id: str`; `host_identity: str`; `status: str`; `evidence: service.EvidenceReference` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| QualifiedOpen | `request: OpenRequest`; `activation: ActivationResult`; `checkpoint_state_sha256: bytes`; `event_sequence: int`; `event_digest: bytes`; `current_checkpoint: service.EvidenceReference`; `history: service.EvidenceReference`; `storage: service.EvidenceReference`; `actor: service.EvidenceReference`; `result_verification: service.EvidenceReference`; `clock: service.EvidenceReference`; `provenance: service.EvidenceReference`; `fresh_time: TimeBinding`; `opener: str`; `issuer: str`; `process: str`; `state: str` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| TimeBinding | `profile: service.QualifiedClockProfile`; `sample: service.QualifiedSample`; `current: service.MonotonicPoint`; `error: service.QualifiedPropagationError` | Actual authenticated fixture_lease_activation.py subject, complete frozen validators/context, not copied expected success |
| EffectAdmission | `snapshot: a.PackageSnapshot`; `approval: a.ApprovalView`; `authorization: s.EvidenceReference`; `absence_history: s.EvidenceReference`; `clock: a.TimeBinding`; `operation: str`; `presence: str`; `predecessor_generation: int`; `original_history: str` | Actual authenticated fixture_lease_authority_providers.py subject, complete frozen validators/context, not copied expected success |
| EnteredOperation | `admission: s.EvidenceReference`; `operation: str`; `state: str` | Actual authenticated fixture_lease_authority_providers.py subject, complete frozen validators/context, not copied expected success |
| ReadbackView | `result: a.ActivationResult`; `original: a.ActivationResult`; `ordering: s.EvidenceReference`; `state: str` | Actual authenticated fixture_lease_authority_providers.py subject, complete frozen validators/context, not copied expected success |
| EvidenceReference | `identity: str`; `sha256: bytes` | Actual authenticated fixture_lease_service.py subject, complete frozen validators/context, not copied expected success |
| UtcInterval | `lower_us: int`; `upper_us: int` | Actual authenticated fixture_lease_service.py subject, complete frozen validators/context, not copied expected success |
| MonotonicPoint | `process_id: str`; `domain_id: str`; `ticks_ns: int` | Actual authenticated fixture_lease_service.py subject, complete frozen validators/context, not copied expected success |
| QualifiedClockProfile | `profile: EvidenceReference`; `source: str`; `qualification: EvidenceReference`; `max_elapsed_ns: int`; `max_sample_age_us: int`; `max_command_uncertainty_us: int`; `refresh_consistency_us: int` | Actual authenticated fixture_lease_service.py subject, complete frozen validators/context, not copied expected success |
| QualifiedSample | `sample: EvidenceReference`; `source: str`; `profile: EvidenceReference`; `validation: EvidenceReference`; `utc: UtcInterval`; `anchor: MonotonicPoint` | Actual authenticated fixture_lease_service.py subject, complete frozen validators/context, not copied expected success |
| QualifiedPropagationError | `sample: EvidenceReference`; `profile: EvidenceReference`; `elapsed_ns: int`; `error_ns: int`; `qualification: EvidenceReference` | Actual authenticated fixture_lease_service.py subject, complete frozen validators/context, not copied expected success |

Nested canonical types Reference, SchemaBinding, HostBinding, StorageBinding, ScopeBinding, ActorBinding, RepresentationBinding, ClockBinding, SoftwareBinding, ProtectedAuthorities, Requirements, Authorization, AuthorityBindings, CeremonyEvidence, ActivationPackage and ActivationPayload incorporate EXACT frozen `_record` field definitions and predicates in the activation implementation, under serialization profile `63dbed6ae575797da27d6a4ee3be03bb184256c3`. Incorporation names immutable authority, not an implementer-selected schema. Existing canonical bytes/hash identities remain unchanged. Metadata/StateContext retain frozen protocol/store fields and domains. Native device/inode identity stays an exact nonnegative integer pair. Request/PreparedReceipt ownership is compared in memory and independently qualified; it is not reconstructed from an external receipt.

### A.1 Exact obligation vocabulary and selection

The complete accepted obligation vocabulary, taken from the frozen provider, is listed below. For QF/PF/VA the list must equal the actual requested expectation tuple, not merely contain accepted spellings. IV also proves every requirement identified by its already-established result requirements reference; no novel result obligation can be inferred from a flag.

COMMON: `AUTHENTICATED_PEER_ISSUER_ACTOR_RIGHTS`, `QUALIFIED_SELECTION_ADOPTION`, `CURRENT_CREDENTIAL_CONTINUITY_NOT_REVOKED`, `IMMUTABLE_RAW_RETENTION`, `CURRENT_APPLICABILITY_NOT_SUPERSEDED`, `QUALIFIED_CLOCK`.

`package`: `COMPLETE_FROZEN_PACKAGE_CLAIMS`, `TRANSITIVE_UPSTREAM_ONLY`.

`preparation`: `AUTHORIZED_PREPARATION_STORAGE_ACTOR`, `CURRENT_ABSENCE_HISTORY`.

`creation`: `ACTUAL_AUTHORIZED_CREATION_FACTS`, `TRANSITIVE_UPSTREAM_ONLY`.

`execution`: `COMPLETE_EXECUTION_REQUEST`, `FRESH_ABSENCE_EXCLUSION_ORIGINAL_K`.

`approval`: `INDEPENDENT_Q_CURRENT_VALIDITY`, `Q_EXCLUDES_DOWNSTREAM_PAYLOAD`.

`opening`: `CURRENT_PROTECTED_STATE_HISTORY`, `INDEPENDENT_RESULT_ALL_OBLIGATIONS`, `FRESH_OPEN_AND_Q_VALIDITY`, `RESTART_DOES_NOT_ESTABLISH_ELIGIBILITY`.

`publication-admission`: `EXACT_C0_P_Q_K_HOST_AUTHORIZATION`, `FRESH_ABSENCE_EXCLUSION_ORIGINAL_K`.

`cas-admission`: `EXACT_PAYLOAD_CONFIRMED_PUBLICATION`, `FRESH_ABSENCE_EXCLUSION_ORIGINAL_K`.

`publication-entry`: `DURABLE_ORIGINAL_ADMISSION`, `NO_REPLAY_ACROSS_RESTART`.

`cas-entry`: `DURABLE_ORIGINAL_ADMISSION`, `NO_REPLAY_ACROSS_RESTART`.

`publication-result`: `EXACT_ORIGINAL_AUTHENTICATED_ACCEPTANCE`, `PROTECTED_C0_NON_ACTIVATING`, `DURABLE_HISTORY_AND_RAW_ACCEPTANCE`.

`cas-result`: `EXACT_ORIGINAL_AUTHENTICATED_ACCEPTANCE`, `LINEARIZABLE_ABSENT_ZERO_TO_ONE`, `DURABLE_HISTORY_AND_RAW_ACCEPTANCE`.

`readback`: `INDEPENDENT_AUTHORITATIVE_SOURCE`, `LINEARIZABLE_AFTER_ORIGINAL_EFFECT`, `CURRENT_PROTECTED_STATE_EXACT_ORIGINAL`, `RAW_OBSERVATION_TIME_ORDERING`.

Nested proofs additionally request exactly EXACT_ROLE_CONTEXT_ISSUER and TRANSITIVE_STAGE_RESTRICTIONS with the actual _COMMON tuple. Every actual independent claim must satisfy the frozen role/context/transitive-stage obligation, not just a signature over these names.

## 16. Candidate self-review and declarations

PIR_01_CLOSED_BY_CANDIDATE = YES_SUBJECT_TO_INDEPENDENT_REVIEW

RECEIPT_ROLE_COUNT = 24

CLOSED_SCHEMA_COUNT = 24_ROLE_EXPANSIONS_PLUS_SHARED_CONTEXT_AND_ENVELOPE

ALL_APPLICABLE_ROLES_HAVE_CLOSED_SCHEMA = YES

CODEC_EXACT = YES

JCS_SELECTED = NO

EXACT_ORIGINAL_BYTES_PRESERVED = YES

DETACHED_ENVELOPE_ACYCLIC = YES

REFERENCE_MAPPING_COMPLETE = YES

ROLE_SEPARATION_PRESERVED = YES

UNKNOWN_NO_REPLAY_PRESERVED = YES

KMS_SIGNATURE_IS_TRUSTED_TIME = NO

TRUSTED_TIME_MAPPING_COMPLETE = YES

PIR_02_CLOSED_BY_CANDIDATE = YES_SUBJECT_TO_INDEPENDENT_REVIEW

MAX_SINGLE_UPLOAD_BYTES = 8388608

MAX_SINGLE_UPLOAD_HUMAN_EQUIVALENT = 8 MiB

MULTIPART_UPLOAD_ALLOWED = NO

FROZEN_PROVIDER_REALIZATION_CONTRACT_AMENDMENT_REQUIRED = NO

IMPLEMENTATION_AUTHORIZED_BY_THIS_ARTIFACT = NO

OPERATIONAL_ADOPTION_AUTHORIZED = NO

NEW_DOCUMENT_COUNT = 1

EXISTING_TRACKED_MODIFIED_PATH_COUNT = 0

STAGED_PATH_COUNT = 0

COMMIT_COUNT = 0

REMOTE_CONTACT = NO

TESTS_EXECUTED = 0

IMPLEMENTATION_FILE_CHANGE_COUNT = 0

AWS_ACCOUNT_ACCESS = NO

KMS_KEYS_CREATED = 0

IAM_CHANGES = 0

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
