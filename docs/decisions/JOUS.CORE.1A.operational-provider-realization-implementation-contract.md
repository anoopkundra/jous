# JOUS.CORE.1A operational provider realization implementation contract

Status: **OFFLINE NORMATIVE CANDIDATE FOR INDEPENDENT REVIEW.**

This document selects no operational resources, issues no credentials or approvals, and authorizes no implementation or operational activity.

## 1\. Scope, baseline and precedence

Derivation baseline:

`f7e434ce8fc48472caab5fb8486b09cc0a86b2e6`

At drafting, local HEAD and local `origin/main` equal that baseline. The index and tracked worktree have no differences.

The owner has selected R1–R8 for implementation-design purposes only. Owner selection does not establish provider qualification, operational adoption, preparation authority or ceremony authority.

The following frozen authorities control this realization:

| Authority | Frozen Git blob |
|---|---|
| Provider-integration contract | `3efb8fef034181d8f4a1ae6d3caf2952ee99095c` |
| IL6 activation contract | `ede5e09bf4bdb8461ac92d27da5ec9cb5683f21b` |
| IL6 serialization profile | `63dbed6ae575797da27d6a4ee3be03bb184256c3` |
| IL6 implementation contract | `92f591b26d2e0b37c34448bc724a4ed4988f6fea` |
| Genesis reference amendment | `d5136bc32ea8f62c04d09e65121edc00c0387d35` |
| Fixture-provisioning bootstrap | `b2af73ae4788e76f4fd591ac267d40230d70026b` |
| Fixture-provisioning contract | `1d84df662ab0e7245f59842039789a55c1df25c4` |
| Frozen activation implementation | `f221f3242ac71ef147a195619a8f98541a6243f1` |
| Frozen provider implementation | `f5dcfbfe8d4884fc660a292433c200ce276f69e0` |

Provider-integration contract SHA256:

`6d4d0ab206e67bb33b6ff137b0d15ae6dc915d44d30d8fb37eb34f8a948bbfed`

This contract specializes transport, storage and authentication realization. It MUST NOT alter E, P, G, J, K, C, Q, STATE, CHECKPOINT, activation payloads, hash domains, validity predicates, original-attempt rules or ACTIVE eligibility.

Conflicts require STOP and independent authority review. Implementation convenience does not override frozen authority.

## 2\. Selected realization

| Role | Selected realization |
|---|---|
| R1 | Isolated RDS PostgreSQL Multi-AZ **DB instance**, one synchronous standby, restricted functions and bounded transaction broker |
| R2 | S3 Object Lock compliance-retained raw evidence, exact-version resolution |
| R3 | Effectively independent qualification and result-verification authority |
| R4 | Incompatible executor, approver, verifier, custodian and recovery roles |
| R5 | DigiCert Europe RFC3161 service under applicable TSP/PS v3.1, plus qualified monotonic propagation |
| R6 | Hosted physical Linux register host, permanent local SSD/NVMe and qualified local filesystem |
| R7 | Separate scoped identities and explicitly supplied secure credential carriers |
| R8 | Independently retained adoption/incarnation binding, restore quarantine and separate recovery authority |

RDS storage belongs to the external protected authority plane. It does not replace or relocate the local SQLite IL6 register.

The R6 register MUST NOT use network-backed block storage, NFS/SMB, cloud synchronization, removable storage, ephemeral storage or RAM storage. Backups remain NON\_AUTHORITATIVE.

## 3\. Exact future implementation boundary

All paths below are proposed future implementation artifacts. None is authorized for creation by this document.

| Path | Classification | Purpose |
|---|---|---|
| `services/api/infrastructure/fixture_lease_authority_provider_clients.py` | NEW\_REQUIRED | Explicit composition, fixed-operation clients, configuration validation, incarnation checks and frozen seam translation |
| `services/api/infrastructure/fixture_lease_authority_transaction_broker.py` | NEW\_REQUIRED | Fixed-operation broker handlers, authenticated admission, transaction/session ownership and uncertainty handling |
| `services/api/infrastructure/fixture_lease_authority_evidence.py` | NEW\_REQUIRED | S3 custody/resolution, provider receipt authentication and external attestation verification |
| `services/api/infrastructure/fixture_lease_authority_time.py` | NEW\_REQUIRED | RFC3161 validation and frozen-time-model bridge |
| `services/api/infrastructure/fixture_lease_authority_schema.sql` | NEW\_REQUIRED | Reviewed authority-side schema, fixed functions and privilege definitions; inert until separately installed |
| `services/api/infrastructure/fixture_lease_authority_realization_dependencies.txt` | NEW\_REQUIRED | Exact future implementation dependency/build lock; no installation or deployment authority |
| `tests/test_fixture_lease_authority_provider_clients.py` | NEW\_REQUIRED | Frozen seam, configuration and authority-binding tests |
| `tests/test_fixture_lease_authority_transaction_broker.py` | NEW\_REQUIRED | SQL invariants, transaction, concurrency, duplicate and UNKNOWN tests |
| `tests/test_fixture_lease_authority_evidence.py` | NEW\_REQUIRED | Exact-version custody, integrity, receipt and authentication tests |
| `tests/test_fixture_lease_authority_time.py` | NEW\_REQUIRED | RFC3161, interval, propagation and restart tests |
| All existing files | NO\_CHANGE | Preserve frozen behavior and application startup |

No frozen modification is required.

The broker is a callable fixed-operation component. This scope includes no public listener, deployment service, application startup hook, CLI, migration runner or resource bootstrapper.

Dependency selection may choose maintained commodity libraries for PostgreSQL, AWS transport, ASN.1/CMS and X.509 processing. Exact versions/build identities MUST be locked and independently reviewed before implementation certification. Handwritten replacements for commodity cryptographic verification are prohibited.

CMS/X.509 dependencies support the required RFC3161 processing. Their availability does not select them for non-RFC3161 receipt authentication.

Changes outside the listed boundary require separate scope review.

## 4\. Frozen seam mapping

The realization MUST implement the existing abstract clients without modifying their signatures.

| Frozen seam | Concrete obligation |
|---|---|
| `EvidenceClient.retain(record)` | Establish durable custody of the exact supplied raw bytes; return the same frozen reference only after exact-version custody is verified |
| `EvidenceClient.resolve(reference)` | Resolve the immutable reference to an exact retained version and verify the complete raw digest |
| `EvidenceVerifier.verify(record, expectation)` | Authenticate actual raw evidence and independently established claims; return the exact frozen `AuthenticatedView` |
| `QualificationClient.qualify(role, context)` | Obtain authenticated role-specific qualification evidence; never manufacture qualification from configuration |
| `ProtectedClient.enter(role, context, admission)` | Commit permanent original admission and return authenticated entry evidence |
| `ProtectedClient.publish_checkpoint(...)` | Use the admitted original’s permanent dispatch claim and acknowledged live broker continuation for at most one exact non-activating C0 publication entry |
| `ProtectedClient.activate_absent(...)` | Use the admitted CAS original’s permanent dispatch claim and acknowledged live broker continuation for at most one exact expected-state effect entry |
| `ProtectedClient.readback(result)` | Obtain ordered authoritative primary observation of the exact original effect |

The existing `RawEvidence`, `QualificationProvider` and `ProtectedAuthorityProvider` remain the composition boundary.

Only authenticated confirmation returns existing success types. All other outcomes preserve failure/UNKNOWN through exceptions and retained evidence. No new frozen enum or successful-looking substitute is permitted.

The operation discriminators, dispatch records and custody states below belong only to the additive external realization. They do not change frozen dataclasses, enums or signatures.

Admission/claim evidence is not a transferable dispatch capability. Broker continuity across the existing seams is internal trusted enforcement state under §9, not a newly serialized frozen object.

## 5\. Closed request and response rules

Every request MUST use a fixed operation discriminator and schema version. No arbitrary operation names, SQL, table names, expressions or executable content are accepted.

### 5\.1 Logical scalar types

| Type | Required domain |
|---|---|
| `ID` | Exact string satisfying frozen identifier syntax and length limits |
| `Counter` | Exact non-Boolean integer in `0..2^63−1`; overflow rejects |
| `UTC` | Exact signed 64-bit UTC microseconds under frozen time semantics |
| `Digest` | Exactly 32 SHA256 bytes |
| `Bytes` | Complete immutable bytes, bounded by the explicitly approved field/configuration limit |
| `Ref` | Existing frozen evidence/reference identity and complete raw SHA256; preserve its frozen representation |
| `Time` | Exact frozen `TimeBinding`, with authenticated sample/profile/error and qualified provenance |
| `Key` | Exact UTF-8 object key satisfying §14 and the selected service’s supported key-size limit |
| `VersionID` | Exact nonempty service version identifier; neither null nor the literal null-version value |
| `Literal` | Exactly one of the case-sensitive values listed for the field |
| `Nullable[T]` | `T` or null only under the explicit conditions stated in this contract |

These are logical schema types. They introduce no new IL6 canonical serialization or hash domain.

Requests and responses reject unknown or duplicate members, missing required members, wrong scalar types, invalid domains and contradictory references. Boolean/float values MUST NOT satisfy integer claims.

Frozen canonical objects travel as their exact frozen bytes. References identify complete retained bytes.

### 5\.2 Complete field groups

A group expands to exactly its listed fields. No additional authority-bearing fields are inferred.

| Group | Fields | Source |
|---|---|---|
| `Envelope` | `schema_version:Counter=1`, `operation:Literal`, `request_id:ID` | Fixed operation schema; request identity allocated before dispatch |
| `Authority` | `namespace:ID`, `incarnation_id:ID`, `configuration_ref:Ref`, `adoption_ref:Ref`, `expected_fence_epoch:Counter` | Explicit reviewed configuration and independently authenticated adoption/continuity evidence |
| `Caller` | `principal_id:ID`, `credential_identity:ID`, `logical_role:Literal`, `authorization_ref:Ref` | Authenticated transport/carrier and independently verified role/scope authorization |
| `Freshness` | `current_time:Time`, `time_evidence_ref:Ref`, `qualification_ref:Ref` | Independently authenticated current qualification evidence |
| `Lifecycle` | `register_id:ID`, `generation:Counter=1`, `activation_id:ID`, `K:ID`, `J:ID`, `host_ref:Ref`, `scope_ref:Ref` | Exact authenticated original lifecycle/package bindings |
| `Original` | `operation_id:ID`, `operation_role:Literal`, `input_binding_ref:Ref` | Fixed provider operation allocation and already-established exact input-binding evidence |
| `Snapshot` | `E_bytes:Bytes`, `S0_bytes:Bytes`, `C0_bytes:Bytes`, `P_bytes:Bytes`, `E_ref:Ref`, `S0_ref:Ref`, `C0_ref:Ref`, `P_ref:Ref` | Exact frozen input bytes and their existing references |
| `Approval` | `Q_bytes:Bytes`, `Q_ref:Ref` | Actual opaque independently approved Q and authenticated reference |
| `Absence` | `absence_history_ref:Ref`, `original_history_ref:Ref`, `expected_state:Literal=AUTHORITATIVE_ABSENT`, `expected_generation:Counter=0`, `expected_state_version:Counter` | Qualified current protected state/history observation |
| `Admission` | `admission_id:ID`, `admission_evidence_ref:Ref` | Exact committed admission and authenticated retained entry evidence |
| `Claim` | `dispatch_claim_id:ID`, `claim_fence_value:Counter`, `claim_commit_evidence_ref:Ref` | Exact committed claim and qualified completed-commit observation |
| `Payload` | `payload_bytes:Bytes`, `payload_sha256:Digest` | Exact downstream frozen payload and complete-byte SHA256 |
| `Publication` | `publication_operation_id:ID`, `publication_decision_ref:Ref`, `publication_receipt_ref:Ref` | Previously confirmed exact non-activating checkpoint publication |
| `ObservationScope` | `observation_authorization_ref:Ref`, `observation_scope_ref:Ref` | Separately approved exact observation target and output permissions |
| `CustodySubject` | `evidence_identity:ID`, `raw_sha256:Digest`, `raw_size:Counter`, `evidence_role:ID`, `issuer_id:ID`, `subject_context_ref:Ref` | Already-existing raw evidence identity, bytes and authenticated role/issuer/context |
| `CustodyPlan` | `custody_attempt_id:ID`, `custody_role:ID`, `bucket_resource_ref:Ref`, `object_key:Key`, `retention_mode:Literal=COMPLIANCE`, `required_retention_until:UTC`, `retention_requirement_ref:Ref` | Fixed authorized attempt, reviewed custody configuration and deterministic §14 key |
| `CustodyVersion` | `version_id:VersionID`, `observed_retention_until:UTC`, `retention_evidence_ref:Ref`, `upload_response_ref:Ref`, `exact_version_readback_ref:Ref`, `custody_authentication_ref:Ref` | Actual definite upload response and authenticated exact-version, digest and retention observations |

For `Original.operation_role`, the only values are `CHECKPOINT_PUBLICATION` and `ACTIVATION_CAS`.

For the seven operations in §7, `Caller.logical_role` is one of:

- `EXECUTOR`;
- `CUSTODY`;
- `OBSERVER`;
- `RESULT_VERIFIER`.

These are operation scopes, not permission to combine the incompatible actors in §11. Each operation specifies its accepted role.

The broker principal is established separately from the caller by its actual approved service/database credential identity. A caller-provided broker name does not establish that principal.

### 5\.3 Exact immutable input bindings

For checkpoint publication, `input_binding_ref` authenticates exactly:

- `Authority`;
- `Lifecycle`;
- `Original.operation_id` and publication role;
- `Snapshot`;
- `Approval`;
- the original execution `authorization_ref`;
- expected protected state `AUTHORITATIVE_ABSENT`;
- expected predecessor generation 0.

For activation CAS, it authenticates exactly the same fields with CAS role, plus `Payload` and `Publication`.

It does not contain its own resulting digest, a future receipt or future custody version.

Fresh requalification evidence and current observed state/fence counters are evaluated at their required boundaries. They cannot rewrite the immutable original inputs. A changed authorization, package, Q, payload, host, scope or lifecycle identity requires rejection, not rebinding.

Bindings absent at an upstream stage MUST NOT be fabricated. Preparation qualification does not require future P/Q/result evidence.

In-memory resources—including open handles, locks, connections and local attempt objects—MUST NOT be serialized or treated as authority. Their relevant host/native-storage facts require separately authenticated evidence.

### 5\.4 Closed responses

Each response echoes exactly:

- schema version;
- operation discriminator;
- request ID;
- namespace and incarnation;
- the exact original input-binding reference, custody subject identity/digest, or resolution target defined by its request.

A successful response additionally contains only the typed fields specified by its operation table.

A rejected response contains:

- `disposition=REJECTED`;
- `reason:Literal`;
- `prior_decision_ref:Nullable[Ref]`.

`reason` is exactly one of:

`DUPLICATE`, `INPUT_CONFLICT`, `LIFECYCLE_CONFLICT`, `WRONG_PREDECESSOR`, `ALREADY_ACTIVE`, `WRONG_INCARNATION`, `UNQUALIFIED`, `INVALID_INPUT`, `STALE_CONTINUATION`, `CUSTODY_CONFLICT`, `SIZE_UNSUPPORTED`.

`prior_decision_ref` is non-null only when an already-established authenticated decision is available.

An unestablished observation uses `disposition=NOT_ESTABLISHED`; it supplies no fabricated state, outcome or receipt.

Ambiguous entry/persistence is an exception or unconfirmed result preserving exact request identity, reached boundary, known facts and available raw evidence. It is not a normal confirmed response.

A response label alone establishes nothing.

## 6\. Provider records and authentication

Provider receipts and verification attestations remain **opaque external evidence**, not new IL6 canonical objects.

The implementation MUST distinguish:

- Original externally issued raw evidence.
- Provider-issued transport/decision receipts.
- Independent verification attestations about original evidence.
- Frozen in-memory views decoded from authenticated evidence.

For non-RFC3161 evidence, the concrete authentication realization MUST establish:

- Authentic issuer identity.
- Integrity of the complete original bytes.
- Issuer authorization for the exact role.
- Exact subject and operation/context binding.
- Authority-incarnation binding.
- Configuration/adoption binding.
- Validity and current applicability.
- Required revocation/status evidence.
- Replay resistance.
- Substitution resistance.
- Effective independent verification where required.
- Retention of original bytes.
- Explicit trust/bootstrap authority.

The authenticated claims MUST cover:

- Format/version and evidence role.
- Issuer, authority and subject identities.
- Namespace, incarnation and configuration/adoption references.
- Issuance and validity bounds.
- Subject raw-evidence identity/digest where attesting another record.
- Exact role-specific claims and dependency references.
- Operation/context bindings.
- Applicable qualification and status evidence.

Unknown fields, unsupported formats, ambiguous content binding and malformed encodings reject.

CMS SignedData processing is mandatory where required by RFC3161 in §15. No universal CMS/X.509 or other non-RFC3161 receipt technology is selected here.

### 6\.1 Unresolved receipt-authentication realization

| Alternative | Required showing |
|---|---|
| A. Authenticated provider-native evidence | The complete retained native evidence, authenticated source and approved interpretation satisfy every frozen issuer, role, context, incarnation, validity/status and independent-verification obligation. TLS or a transport ACK alone is insufficient. |
| B. Separately signed Jous/provider receipt | The complete original receipt and approved signing realization satisfy those same obligations without executor self-approval or substitution for required independent verification. |

Neither alternative is selected by this contract.

If separate signing is later selected, explicit review MUST close:

- Content schema.
- Algorithm/profile.
- Signer identity.
- Key custody.
- Trust bootstrap.
- Rotation.
- Revocation/status.
- Resource boundary.

```
NON_RFC3161_RECEIPT_AUTHENTICATION_DECISION = UNRESOLVED

CLASSIFICATION =
REALIZATION_DECISION_REQUIRED_BEFORE_IMPLEMENTATION_AUTHORIZATION

BLOCKS_CONTRACT_DRAFTING_OR_NORMATIVE_REVIEW = NO

BLOCKS_FUTURE_IMPLEMENTATION_AUTHORIZATION_FOR_UNRESOLVED_RECEIPT_ROLES = YES
```

This unresolved realization decision does not prevent completion or independent normative review of this contract. It does prevent future implementation authorization for affected receipt roles until concretely selected and reviewed.

The implementer MUST NOT select an authentication technology merely because the logical receipt claims are defined.

### 6\.2 Original bytes and evidence graph

An external record’s identity refers to the **complete original received bytes**, hashed without normalization or reserialization.

The receiver MUST NOT serialize C, Q, governance, storage or qualification records to manufacture their identities. Broker receipt issuance may describe only the broker’s actual authenticated decisions and observations. It cannot issue independent Q, adoption, host qualification or independent result approval.

The implementation MAY emit broker-owned external receipts through an approved authentication realization. It MUST NOT implement an approval-issuing service.

Self-reference is prohibited:

- A receipt does not include its own resulting raw digest or S3 version as an upstream authenticated input.
- Frozen result `.evidence` references are supplied from the authenticated retained record reference, rather than requiring the raw record to contain its own hash.
- Verification provenance is a distinct retained record or already established authority reference, never a proof that authenticates itself.

A custody receipt authenticates its subject object/version and binding decision. It does not require its own future custody receipt to establish its creation.

Definite internal transaction acknowledgements are control observations, not independent qualification or returned frozen success. Their raw observations and required provenance MUST be retained under a finite acyclic evidence plan. A bookkeeping acknowledgement MUST NOT require an infinite chain of prior uploads of acknowledgements.

The concrete authentication realization must demonstrate termination at explicit independently approved roots before affected implementation authorization.

Typed claims MUST cover every field required by the corresponding frozen view and every requested `_COMMON` and role obligation. A matching label or projected copy of the request is insufficient.

## 7\. Logical protected operations

All seven operations include `Envelope`, `Authority` and `Caller`.

Effect-capable operations require the exact currently adopted incarnation, approved configuration, authenticated rights, current qualified time and valid fencing. Resolution of a non-authoritative or quarantined resource is possible only under an observation scope expressly authorizing that resource/status. It cannot confer effect permission.

### 7\.1 ORIGINAL\_ATTEMPT\_ADMISSION

| Property | Normative definition |
|---|---|
| Discriminator | `ORIGINAL_ATTEMPT_ADMISSION` |
| Request fields | Common groups; `Freshness`, `Lifecycle`, `Original`, `Snapshot`, `Approval`, `Absence`; `admission_id:ID`. CAS role additionally requires `Payload` and `Publication`. Publication role prohibits those two groups. |
| Field sources | §5 sources; admission/operation identities are fixed before dispatch; actual package/Q and history are independently qualified. |
| Comparisons | Authenticate every reference and complete raw digest; compare frozen package/Q and immutable original input binding; exact namespace/incarnation/configuration, lifecycle, authorization, state version and absence/history. CAS also compares exact payload and confirmed publication. |
| Preconditions | Caller role EXECUTOR; no prior role-specific admission; no competing lifecycle; no unresolved prior/in-flight original; qualified current absence and valid authorization/time. CAS requires confirmed publication and fresh requalification. |
| Database effect | Lock incarnation and register/lifecycle boundary; create the original lifecycle only if unclaimed, otherwise require the identical existing lifecycle; insert one immutable admission and sequence-0 decision history; commit. No dispatch claim, C0 publication or activation. |
| Success response | `disposition=ADMITTED`; `operation_id:ID`, `admission_id:ID`, `input_binding_ref:Ref`, `state_version:Counter`, `fence_value:Counter`, `admission_decision_ref:Ref`, `admission_evidence_ref:Ref`. |
| Terminal disposition | Permanent admission. Only its original definitely acknowledged live broker continuation may proceed. |
| Duplicate | Identical existing admission: REJECTED/DUPLICATE; no new continuation or success. |
| Conflict | Changed original inputs: INPUT\_CONFLICT. Competing original/lifecycle: LIFECYCLE\_CONFLICT. |
| Uncertainty | UNKNOWN; no claim/effect continuation from an unacknowledged admission. |
| Permitted follow-on | Its one fixed DISPATCH\_CLAIM through the existing live continuation; separately permitted observation. |

Checkpoint and CAS admissions are separate role-specific records. Publication admission does not consume or authorize CAS admission.

### 7\.2 DISPATCH\_CLAIM

| Property | Normative definition |
|---|---|
| Discriminator | `DISPATCH_CLAIM` |
| Request fields | Common groups; `Freshness`, `Lifecycle`, `Original`, `Admission`; `dispatch_claim_id:ID`, `broker_principal_id:ID`, `expected_fence_value:Counter`. |
| Field sources | Exact committed admission; actual authenticated broker identity; qualified current slot fence; original live acknowledged admission continuation. |
| Comparisons | Every admission/lifecycle/input/role field must match. Actual broker identity must match the request. Current incarnation fence and slot fence must match. No claim may already exist for the operation or admission. |
| Preconditions | Caller role EXECUTOR; exactly one live originating admission continuation; it has not attempted its claim invocation; no uncertainty, quarantine or prior claim. |
| Database effect | Separate completed transaction: lock authority/slot/admission, increment slot fence with overflow rejection, insert immutable terminal CLAIMED record and sequence-1 history, then COMMIT. This does not hold open an effect transaction. |
| Success response | `disposition=CLAIMED`; operation/admission/claim IDs, `broker_principal_id:ID`, `claim_fence_value:Counter`, `claim_decision_ref:Ref`, `claim_commit_evidence_ref:Ref`. |
| Terminal disposition | Claim permanently non-reusable. Only the same live continuation with definite acknowledgement may dispatch once. |
| Duplicate | Same claim and bindings: REJECTED/DUPLICATE; no dispatch capability returned. |
| Conflict | Different claim/bindings for the operation: INPUT\_CONFLICT. Non-originating or invalidated continuation: STALE\_CONTINUATION. |
| Uncertainty | UNKNOWN; no effect dispatch; original remains fenced. |
| Permitted follow-on | At most one matching protected effect invocation by that same acknowledged live continuation; separately permitted observation. |

The claim binds namespace, incarnation, register, target generation, original operation, role, admission, exact input reference, actual broker principal, claim identity, CLAIMED decision and allocated fence.

Qualified committed-at evidence is a distinct immutable observation associated with that claim. It must conservatively establish completion ordering using qualified observations before and after the definite COMMIT acknowledgement, or equivalent independently qualified proof.

Pre-COMMIT time is not represented as proof that COMMIT completed. Post-COMMIT observation material is appended separately and cannot rewrite the claim.

If recording/authenticating required commit observation fails, the claim remains a fence and dispatch is prohibited.

### 7\.3 CHECKPOINT\_PUBLICATION

| Property | Normative definition |
|---|---|
| Discriminator | `CHECKPOINT_PUBLICATION` |
| Request fields | Common groups; `Freshness`, `Lifecycle`, `Original` with publication role, `Snapshot`, `Approval`, `Absence`, `Admission`, `Claim`. |
| Field sources | Exact admitted original inputs, actual Q, fresh qualification/history, committed claim and its original live continuation. |
| Comparisons | Exact original/admission/claim/input bindings; current incarnation/epoch; actual broker principal; claim fence; expected state version; complete E/S0/C0/P/Q/K/J/host/scope and authorization. |
| Preconditions | Caller role EXECUTOR; live dispatch latch not yet consumed; no prior publication decision; authoritative ABSENT/generation 0; exact current claim fence. |
| Database effect | One transaction locks and validates authority/slot/admission/claim, inserts non-activating checkpoint publication and immutable decision/history, increments state version and advances lifecycle projection. State remains ABSENT/generation 0. A definite precondition rejection records REJECTED without publication. |
| Success response | `disposition=CHECKPOINT_PUBLISHED`; exact operation/admission/claim/lifecycle bindings, C0/P/Q/host references, resulting state version, `publication_decision_ref:Ref`, `publication_receipt_ref:Ref`. |
| Terminal disposition | One recorded publication; full confirmation also requires §9.3 and required custody. |
| Duplicate | Identical recorded publication: REJECTED/DUPLICATE. |
| Conflict | Different inputs: INPUT\_CONFLICT. Active state: ALREADY\_ACTIVE. Wrong predecessor/version: WRONG\_PREDECESSOR. Wrong incarnation: WRONG\_INCARNATION. |
| Uncertainty | UNKNOWN; no CAS progression. |
| Permitted follow-on | After full confirmation only: separately authorized, freshly qualified CAS admission. |

### 7\.4 ACTIVATION\_CAS

| Property | Normative definition |
|---|---|
| Discriminator | `ACTIVATION_CAS` |
| Request fields | Common groups; `Freshness`, `Lifecycle`, `Original` with CAS role, `Snapshot`, `Approval`, `Payload`, `Publication`, `Absence`, `Admission`, `Claim`. |
| Field sources | Exact downstream payload, qualified P/Q, confirmed publication, current absence/history, committed admission/claim and original live continuation. |
| Comparisons | Complete payload digest/frozen bindings; exact P/Q/C0/publication/K/J/register/generation/activation/host/scope; authorization and current validity; expected ABSENT/generation 0/state version; current incarnation and claim fence. |
| Preconditions | Caller role EXECUTOR; no prior activation decision; no active/tombstoned/unresolved history contradicting absence; confirmed publication; live dispatch latch unused. |
| Database effect | One transaction atomically checks expected state/fence, changes slot to exact ACTIVE/generation 1, inserts activation decision and sequence-2 history, increments state version and advances lifecycle projection. A definite failed comparison records REJECTED without activation. |
| Success response | `disposition=ACTIVATED`; exact original/admission/claim/lifecycle, payload digest, P/Q/C0/host references, resulting state version, `activation_decision_ref:Ref`, `activation_receipt_ref:Ref`. |
| Terminal disposition | One recorded transition; independent verification and frozen ACTIVE eligibility remain separate. |
| Duplicate | Same recorded original: REJECTED/DUPLICATE, including matching active content. |
| Conflict | Active without that original decision: ALREADY\_ACTIVE. Wrong predecessor/version: WRONG\_PREDECESSOR. Different inputs: INPUT\_CONFLICT. Wrong incarnation: WRONG\_INCARNATION. |
| Uncertainty | UNKNOWN; no ACTIVE inference or resubmission. |
| Permitted follow-on | Separately permitted authoritative readback and independent verification. |

### 7\.5 AUTHORITATIVE\_READBACK

| Property | Normative definition |
|---|---|
| Discriminator | `AUTHORITATIVE_READBACK` |
| Request fields | Common groups; `Freshness`, `Lifecycle`, `Original` with CAS role, `Payload`, `Publication`, `ObservationScope`; `activation_decision_ref:Ref`, `activation_receipt_ref:Ref`, `minimum_state_version:Counter`. |
| Field sources | Previously confirmed original activation result and retained evidence; separately approved observation scope. |
| Comparisons | Exact original result/resource/incarnation; actual primary state/history; K/payload/P/Q/C0/register/generation/activation/host; state version and ordering after original decision. |
| Preconditions | Caller role OBSERVER or RESULT\_VERIFIER; authorized new primary observation under §10; no replica/cache/stale snapshot; required raw evidence resolves. |
| Database effect | Read-only authority transaction using required locking/ordering. No admission, claim, state progression or effect. Raw-observation retention is a distinct custody workflow. |
| Success response | `disposition=OBSERVED`; actual protected state, generation, state version, fence value, exact original lifecycle/operation/payload/P/Q/C0/host bindings, publication/activation decision references, `observation_time:Time`, `ordering_ref:Ref`, `readback_evidence_ref:Ref`. |
| Terminal disposition | Observation only; no independent result approval or ACTIVE permission. |
| Duplicate | Another observation needs its own authorized scope/freshness; never an effect retry. |
| Conflict | Mismatch is REJECT/STOP. Requested values cannot substitute for observed values. |
| Uncertainty | No qualified readback; preserve previous reached/UNKNOWN condition. |
| Permitted follow-on | Separately authorized independent result verification. |

### 7\.6 READ\_ONLY\_RESOLUTION

| Property | Normative definition |
|---|---|
| Discriminator | `READ_ONLY_RESOLUTION` |
| Request fields | Common groups; `ObservationScope`; `target_kind:Literal`, `permitted_outputs`, a nonempty duplicate-free subset of the five categories below. OPERATION target requires `operation_id:ID` and prohibits evidence identity. EVIDENCE target requires `evidence_identity:ID` and prohibits operation ID. |
| Field sources | Existing immutable target and separately authenticated observation scope. |
| Comparisons | Exact target namespace/incarnation/resource and authorization; requested categories must be a subset of approved categories. |
| Preconditions | Caller role OBSERVER, RESULT\_VERIFIER or CUSTODY, with exact observation rights. Quarantined/non-authoritative resource inspection must be expressly permitted. |
| Database effect | Read-only. No inserts, updates, authority progression, receipt issuance, admission, claim, custody binding or adoption. |
| Success response | `disposition=RESOLVED`; target identity and exactly the requested categories. Each unestablished requested category is null/NOT\_ESTABLISHED, not reconstructed. |
| Terminal disposition | Observation only. |
| Duplicate | Another permitted observation; no new protected success. |
| Conflict | Wrong target/incarnation/scope rejects. |
| Uncertainty | NOT\_ESTABLISHED/observation failure; no fabricated outcome. |
| Permitted follow-on | Separately permitted observation or separate recovery decision—not dispatch. |

The five output categories are closed:

| Category | Exact content |
|---|---|
| `OPERATION_STATE` | Existing admission, claim and stored/derived role-specific state, identities and versions |
| `DECISION` | Existing immutable decision code, sequence and decision reference |
| `RECEIPT_REFERENCE` | Existing authenticated receipt/evidence reference and established subject |
| `CUSTODY_LOCATOR` | Existing BOUND locator’s complete fields; RESERVED is explicitly unconfirmed |
| `AUTHORITATIVE_READBACK_FACTS` | Previously retained readback facts with their original observation time and ordering, not a fresh-state assertion |

Resolution cannot create admission, create a claim, clear UNKNOWN, create eligibility, perform an effect, approve recovery, adopt restored resources or reconstruct lost original permission.

### 7\.7 EVIDENCE\_CUSTODY\_BINDING

This fixed discriminator has two closed phases, `RESERVE` and `BIND`. Reservation is permanent custody bookkeeping. It is not confirmed custody, activation authority or qualification.

| Property | RESERVE | BIND |
|---|---|---|
| Request fields | Common groups; `phase=RESERVE`, `Freshness`, `CustodySubject`, `CustodyPlan`, `raw_bytes:Bytes` | Common groups; `phase=BIND`, `Freshness`, exact `CustodySubject`, `CustodyPlan`, `CustodyVersion` |
| Field sources | Existing evidence identity/raw bytes and authorized reviewed custody plan | Exact reservation and actual definite upload/readback/retention/authentication evidence |
| Comparisons | Complete hash/size and frozen identity; issuer/role/context; adopted resource; deterministic key; retention requirement; supported size | Every reserved field equal; exact version; complete digest/size; retention mode/deadline; actual authenticated custody evidence |
| Preconditions | Caller role CUSTODY; no prior reservation/binding for the identity or key; all pre-upload checks pass | Caller role CUSTODY; exact reservation and original live continuation; definite upload success; no prior binding; all §14 conditions pass |
| Database effect | Completed transaction inserts one RESERVED locator intent and sequence-0 history; no version authority exists | One transaction assigns previously null version/proof fields once, changes RESERVED→BOUND and inserts sequence-1 history |
| Success response | `disposition=CUSTODY_RESERVED`; attempt/subject/resource/key/retention bindings, reservation decision reference | `disposition=CUSTODY_BOUND`; complete exact locator, binding decision reference, authenticated custody evidence reference |
| Terminal disposition | Permanent reservation; one original acknowledged live continuation may upload once | Immutable BOUND locator |
| Duplicate | REJECTED/DUPLICATE; no new upload continuation | REJECTED/DUPLICATE; observe existing facts only through resolution |
| Conflict | CUSTODY\_CONFLICT; no new key or identity | CUSTODY\_CONFLICT; no replacement/rebinding |
| Uncertainty | UNKNOWN\_CUSTODY; no upload without definite acknowledgement | UNKNOWN\_CUSTODY; no repeated upload or binding |
| Permitted follow-on | Exactly one §14 upload by the original live continuation | Exact-version read-only resolution |

Custody functions have only the necessary locator/history/receipt-material rights. They cannot update activation state, admissions, dispatch claims, Q, qualification, adoption or recovery state.

A RESERVED row has no version authority. Only BOUND establishes an exact-version locator.

Externally supplied bootstrap roots remain governed by §20. This operation cannot bootstrap the adoption authorizing itself.

Admission and effect identities are allocated before dispatch, immutable and never regenerated on timeout.

Confirmation requires acknowledged durable COMMIT plus authenticated decision evidence and required custody. Intermediate SQL results do not qualify.

## 8\. Minimum authority-side relational model

The SQL artifact MUST contain an isolated schema with the following logical relations. Physical names may differ only through a documented one-to-one mapping.

### 8\.1 Logical keys and complete incarnation binding

Define:

- `A = (namespace, incarnation_id)`.
- `S = (namespace, incarnation_id, register_id)`.
- `L = (namespace, incarnation_id, register_id, generation)`.
- `O = (namespace, incarnation_id, operation_id)`.
- `D = (namespace, incarnation_id, dispatch_claim_id)`.
- `V = (namespace, incarnation_id, evidence_identity)`.
- `H = (namespace, incarnation_id, subject_kind, subject_id, sequence)`.

All key components use §5 types. Lifecycle generation is exactly 1.

`subject_kind` is OPERATION or CUSTODY. OPERATION subject ID is the operation ID; CUSTODY subject ID is the evidence identity.

| Relation | PRIMARY KEY | Required UNIQUE | Required FKs and content |
|---|---|---|---|
| Authority incarnation | A | Exact adopted resource/configuration association within A | Adopted resource/configuration/selection/adoption references, lifecycle status, logical fence epoch |
| Register authority slot | S | S plus each copied identity combination referenced by child FKs | A→incarnation; original K/J/activation/host/scope bindings, state, generation, state version and fence value |
| Original lifecycle | L | `(namespace, register_id, generation)` and `(namespace, K)`; no cross-incarnation original bypass | S→slot; immutable original lifecycle bindings and lifecycle projection |
| Operation admission | O | `(namespace, operation_id)`, `(A, admission_id)`, `(L, operation_role)` | L→lifecycle; immutable Original/Admission fields and ADMITTED state |
| Dispatch claim | D | O and `(A, admission_id)` | O→admission; complete matching lifecycle/role/admission/input bindings; actual broker principal; CLAIMED; allocated fence; qualified commit-observation association |
| Checkpoint publication | O | L for publication role | O→publication admission; D→matching claim; L→lifecycle; exact C0/P/Q/host, decision and resulting state version |
| Activation decision | O | L for CAS role | O→CAS admission; D→matching claim; publication O→exact checkpoint publication; L→lifecycle; exact expected/target/payload decision |
| Decision history | H | Exact predecessor per subject/sequence | A→incarnation; OPERATION→admission or CUSTODY→locator under disjoint enforced cases; noninitial row→same subject sequence−1 |
| Receipt material | `(A, material_id)` | `(namespace, evidence_identity)` and exact parent/request/receipt-role association | Parent H for decision receipts; exact activation O for readback receipts under disjoint enforced cases; complete original bytes/digest, issuer/authentication and subject bindings |
| Evidence locator | V | `(namespace, evidence_identity)`, `(A, custody_attempt_id)`, `(A, bucket_resource_ref, object_key)` | A→incarnation; immutable custody subject/plan; RESERVED/BOUND state; exact version and verification fields assigned once |

No cross-incarnation FK is permitted.

A child carrying a lifecycle, role, admission, claim or input-binding field MUST reference a parent UNIQUE combination containing those same copied fields. Short-ID equality alone is insufficient.

The disjoint history and receipt-parent cases require explicit SQL checks and FKs. An unchecked polymorphic target string is prohibited.

External `Ref` values require authenticated resolution; they are not falsely treated as local SQL FKs to nonexistent root evidence.

The original-lifecycle uniqueness across incarnation does not authorize migration/import/re-adoption. External incarnation fencing remains mandatory before any new authority is usable.

### 8\.2 Closed decision-history sequences

For each OPERATION subject:

| Sequence | Permitted decision |
|---|---|
| 0 | `ADMITTED` |
| 1 | `CLAIMED` |
| 2, publication role | `CHECKPOINT_PUBLISHED` or `CHECKPOINT_REJECTED` |
| 2, CAS role | `ACTIVATED` or `ACTIVATION_REJECTED` |

For each CUSTODY subject:

| Sequence | Permitted decision |
|---|---|
| 0 | `CUSTODY_RESERVED` |
| 1 | `CUSTODY_BOUND` |

No other sequence or decision code is created by these fixed operations.

Claim/history insertion and claim-row insertion are atomic. Effect decision/history and effect mutation or definite rejection are atomic. Custody state change and its history are atomic.

Post-COMMIT acknowledgement/qualified-time material is append-only receipt material associated with the exact established decision. Recording it does not reacquire a claim or repeat an effect.

Readback/resolution do not append authority decisions or progress these sequences. Their actual observation evidence may be retained through separate custody authority.

### 8\.3 Closed states and transition tables

| State machine | Initial state | Permitted successor | Terminal states/prohibited regressions | UNKNOWN treatment |
|---|---|---|---|---|
| Incarnation | NON\_AUTHORITATIVE | ADOPTED only through separately authorized external adoption; ADOPTED may be fenced QUARANTINED | No in-scope adoption/re-adoption operation; no QUARANTINED→ADOPTED here | No effects while continuity/applicability is uncertain |
| Register slot | Separately established ABSENT, generation 0 | Publication preserves ABSENT; successful CAS changes ABSENT→ACTIVE, generation 1; separately authorized fencing may establish QUARANTINED | No ACTIVE→ABSENT, generation decrement or automatic release; quarantine permits no effects | Missing/uncertain observation never becomes ABSENT |
| Original lifecycle | RESERVED | CHECKPOINT\_RECORDED, then ACTIVATION\_RECORDED; separately authorized fencing may establish QUARANTINED | No backward transition or alternate K/activation; recorded phase does not establish full confirmation | Preserve permanent reservations/claims; do not synthesize missing decisions |
| Operation lifecycle, derived from immutable rows | ADMITTED | CLAIMED when exact claim exists; DECIDED when exact effect decision exists | No derived regression or dispatch permission from a scan | Unresolved caller outcome remains terminal; stored facts do not recreate acknowledgement |
| Operation admission | ADMITTED | None | Immutable and permanent; no expiry/release/reclaim state | No acknowledged live continuation is reconstructed |
| Dispatch claim | CLAIMED on committed insertion | None | Permanent, non-reusable | Observing CLAIMED does not authorize dispatch |
| Checkpoint publication | No row | Insert PUBLISHED or REJECTED once | Both immutable; no REJECTED→PUBLISHED or overwrite | Missing decision does not restore claim |
| Activation decision | No row | Insert ACTIVATED or REJECTED once | Both immutable; no REJECTED→ACTIVATED or overwrite | No ACTIVE inference from uncertainty |
| Custody locator | RESERVED | BOUND through exact BIND operation | BOUND cannot revert/rebind; RESERVED cannot be resumed after lost live continuation | UNKNOWN\_CUSTODY remains fenced; no repeated upload |
| History/receipt material | No row | Append actual immutable material | No rewrite/delete/reset/substitution | Missing evidence stays missing |

Absence of a row is not an eligibility state.

UNKNOWN and UNKNOWN\_CUSTODY are terminal safety dispositions for the current attempt. They MUST NOT be fabricated as committed database facts when persistence is itself unknown.

Resolution reports established rows and evidence gaps; it does not clear the terminal disposition.

CHECKPOINT\_RECORDED, ACTIVATION\_RECORDED and DECIDED describe database facts, not independent approval, complete custody or frozen ACTIVE eligibility.

### 8\.4 Immutable fields

| Relation | Immutable fields |
|---|---|
| Incarnation | A and adopted resource/configuration references; authorized lifecycle/fence changes cannot rewrite prior evidence |
| Slot | S and original identity bindings after first successful admission; state/version changes only through defined transitions |
| Lifecycle | L, K, J, activation, host/scope and original bindings |
| Admission | Entire successful admission identity, role, lifecycle, input binding and entry facts |
| Claim | Entire claim/admission/operation/lifecycle/input/broker binding, CLAIMED decision and allocated fence; later commit-observation material is separate |
| Checkpoint publication | Entire decision, exact original content/context and resulting version |
| Activation decision | Entire decision, exact expected/target/payload/publication bindings |
| Decision history | Entire row, subject, sequence, predecessor and decision facts |
| Receipt material | Complete original bytes, digest, issuer/authentication and parent/request bindings |
| Locator | Subject identity/digest/size/role/issuer/context and custody plan from RESERVE; version/proof fields assigned once by BIND and then immutable |

No DELETE, TRUNCATE, TTL, expiry, cleanup, rollback, restore or reconciliation path may recreate eligibility.

Retention extension does not rewrite the original locator. Separately authorized extension evidence is a distinct observation and cannot shorten or replace required custody.

State versions and fence values are distinct exact counters. Claim allocation increments the fence value; effect commitment increments state version. Both reject overflow. Neither is a PostgreSQL transaction ID or transaction-ID epoch.

### 8\.5 Duplicate/conflict matrix

Incarnation/authentication validation precedes effect eligibility. Among authenticated requests for the same incarnation, existing original identity is checked before treating matching active state as a different outcome.

| Condition | Disposition |
|---|---|
| Same original identity, identical inputs | REJECTED/DUPLICATE; no new admission, claim or protected success |
| Same original identity, different inputs | REJECTED/INPUT\_CONFLICT; STOP |
| Different original competing for same lifecycle/role | REJECTED/LIFECYCLE\_CONFLICT |
| Same dispatch claim and identical bindings | REJECTED/DUPLICATE |
| Different claim ID or changed claim bindings for the same admitted operation | REJECTED/INPUT\_CONFLICT |
| Stale/non-originating broker continuation | REJECTED/STALE\_CONTINUATION before effect invocation |
| Duplicate identical checkpoint publication | REJECTED/DUPLICATE |
| Conflicting checkpoint publication | REJECTED/INPUT\_CONFLICT |
| Duplicate activation original | REJECTED/DUPLICATE, even if active content matches |
| Already active without that matching original decision | REJECTED/ALREADY\_ACTIVE |
| Wrong predecessor/state version | REJECTED/WRONG\_PREDECESSOR |
| Wrong incarnation/configuration/adopted fence epoch | REJECTED/WRONG\_INCARNATION |
| Identical custody reservation or BOUND locator request | REJECTED/DUPLICATE; existing facts are observable only |
| Evidence identity with changed digest/resource/key/version/context | REJECTED/CUSTODY\_CONFLICT |
| Custody key already bound/reserved for another identity | REJECTED/CUSTODY\_CONFLICT |
| Prior entry/persistence uncertain or evidence missing | UNKNOWN/FAIL\_CLOSED; no new eligibility |

A known rejection does not erase a stronger reached boundary or permit retry.

A missing register slot is not independently sufficient ABSENT proof. Qualified history must include namespace coverage, tombstones, previous/in-flight originals and unresolved outcomes.

Required invariants remain:

- Unique original lifecycle for a register/generation.
- Unique role-specific original operation.
- No alternate K, activation ID or operation ID bypass.
- No DELETE, TRUNCATE, TTL, expiry release or delete/recreate eligibility.
- No UPSERT returning a prior operation as a newly successful original attempt.
- Immutable identity/input columns after first admission.
- Append-only decisions; no rewriting prior outcomes.
- No downgrade from generation one to absent.
- Monotonically increasing fencing/version values with overflow rejection.
- FK consistency within the same namespace/incarnation.
- Protected mutation and its durable decision updated atomically.
- Evidence identity maps to exactly one raw digest and exact version.

Protected state begins only from separately established and qualified absence. Schema installation does not adopt an incarnation.

The protected authority model does not mirror SQLite STATE, EVENTS or CHECKPOINT tables and creates no second IL6 register.

## 9\. Transaction and one-dispatch rules

The broker MUST use explicit transactions and approved sessions.

### 9\.1 Admission

Admission checks qualified current authority, locks the relevant lifecycle/slot, rejects prior or conflicting originals, writes permanent entry/history and commits.

No entry receipt is returned before COMMIT acknowledgement and required evidence retention.

Lost admission acknowledgement is UNKNOWN. The caller MUST NOT repeat admission.

Only the originating live broker continuation receiving the definite newly created admission acknowledgement may proceed toward its fixed dispatch claim.

Duplicate admission, history scanning, matching retained evidence or restart cannot create another originating continuation.

The continuation is trusted internal enforcement state, not a serialized token or independent source of original-attempt uniqueness. Permanent database admission/history and uniqueness constraints prevent another original from being admitted.

### 9\.2 Permanent durable dispatch claim

The invariant is:

**ONE ORIGINAL EFFECT ENTRY MAXIMUM.**

Required sequence:

1. The operation already has permanent admission.
2. Its originating live broker continuation requests exactly one fixed DISPATCH\_CLAIM.
3. The claim commits durably in a separate completed authority transaction.
4. Exactly that live continuation receiving definite acknowledgement of that committed claim may proceed.
5. Before effect invocation, it irreversibly consumes its thread/concurrency-safe one-dispatch latch.
6. It invokes the matching protected effect at most once.
7. Protected mutation and durable decision are one atomic database transaction.

The broker is explicitly part of the trusted enforcement boundary. SQL uniqueness establishes permanent claim exclusion; it does not alone prove that trusted broker code invoked the effect function only once after rollback.

The broker MUST prevent duplicate callbacks, concurrent workers, RPC replay, exception handling, transaction helpers and task resumption from resetting or recreating the live continuation or latch.

The bounded live context may cross the unchanged frozen seams. A later matching fixed call may use only that already-existing live context; it cannot reconstruct one from admission/claim evidence.

If dispatch-claim COMMIT acknowledgement is lost or uncertain:

- UNKNOWN.
- No effect dispatch.
- The original remains permanently fenced.
- No new claim identity or replacement continuation.
- No reconnect, scan or recovery process may acquire dispatch permission.

If the broker crashes after definite claim acknowledgement but before effect entry:

- The original remains consumed/fenced.
- No replacement broker may dispatch it.
- Restart permits observation only.

If effect invocation rejects, rolls back, loses its session or becomes uncertain:

- The claim remains consumed.
- No second effect invocation.
- Savepoints/subtransactions cannot restore or repeat effect entry.
- A later definite rejection does not authorize another attempt.

PostgreSQL transaction IDs, backend IDs and session IDs MUST NOT be permanent authority identities. They may appear only as diagnostic or qualification evidence.

There is no control transaction binding an open effect transaction, no transaction-ID epoch authority and no designated-transaction identity dispatch mechanism.

Claim committed-at evidence is associated with the exact completed claim decision. It must establish the qualified completion bracket/order under §7.2, not a guessed server wall-clock time.

Future qualification MUST prove the correspondence between permanent admissions/claims, definite acknowledgements, one live continuation and actual effect entry, including stale/duplicate worker fencing.

### 9\.3 COMMIT

Only the broker issues COMMIT. The effect response is not exposed as confirmed before acknowledgement.

Connection loss, timeout or incomplete response after possible COMMIT entry means UNKNOWN. No reconnect-and-replay is permitted.

An acknowledged database decision followed by failed receipt retention remains a known database decision with incomplete evidence. It MUST NOT become returned confirmation or execution eligibility.

Required ordering is:

1. Complete admission and required evidence.
2. Complete the separate claim and its required acknowledgement/qualified observation.
3. Invoke the effect once.
4. Commit protected mutation and durable decision atomically.
5. Establish definite commit acknowledgement and required authoritative facts.
6. Authenticate actual decision/receipt material under the reviewed realization.
7. Complete required custody and resolution.
8. Return only the existing frozen confirmed type.

PostgreSQL, external receipt authentication and S3 custody are not assumed to form one transaction.

Post-COMMIT receipt-material recording is append-only and associated with the established decision. Failure prevents confirmation; it does not authorize another claim or effect.

## 10\. RDS session and readback profile

Required profile:

- RDS PostgreSQL Multi-AZ DB instance with one synchronous standby.
- One adopted writer resource and endpoint.
- Permanent logged authority/history tables.
- `fsync=on`, `full_page_writes=on`, `synchronous_commit=on`.
- No session/function override weakening durability.
- Explicit bounded transaction timeouts and connection policy.
- Verified TLS peer/hostname and approved trust roots.
- No authority reads from replicas, caches or stale snapshots.
- No automatic protected transaction retry.

Engine/build, parameter groups, extension set, SQL/function hashes and network/TLS configuration MUST be pinned in the realization configuration.

Authority readback MUST use a new primary observation after the committed effect, with applicable locking/ordering sufficient to establish the current protected state. `READ COMMITTED` alone is not a blanket linearizability proof.

Readback checks exact original operation, state, version, register/generation/activation, K, payload, P/Q/C0 and incarnation. Changed or unavailable state fences progression.

Supported failover may preserve an adopted incarnation only within the independently qualified continuity profile. It never authorizes resubmitting an uncertain operation.

## 11\. Privilege architecture

| Principal | Permitted responsibility | Prohibited responsibility |
|---|---|---|
| Administrative custodian | Separately authorized installation/maintenance | Ordinary execution, approval or independent result verification |
| Schema/table owner | Own protected objects; non-login | Broker login or executor identity |
| Function owner | Minimum rights needed by fixed functions; non-login | Administrative roles or unrestricted delegation |
| Broker login | CONNECT, required schema USAGE, exact function EXECUTE | Table/schema ownership, arbitrary DML/DDL, role administration, owner impersonation |
| Executor | Authenticated fixed broker operations | Database login capable of bypassing broker |
| Approver | Independently authorized Q | Protected effects or custodian role |
| Result verifier | Independent observation and verification | Effect mutation or approval impersonation |
| Recovery administrator | Separately authorized fenced recovery scope | Automatic operational recovery or ordinary execution |

SECURITY DEFINER functions MUST:

- Use fixed trusted `search_path`, with temporary schemas unable to shadow trusted objects.
- Qualify protected object names.
- Revoke PUBLIC execution and grant exact signatures selectively.
- Reject caller SQL, caller-selected functions and arbitrary object names.
- Validate authenticated role and namespace/incarnation.
- Reject wrong types and domains before comparisons or effects.
- Avoid role switching and caller-controlled session settings.
- Apply grants atomically with installation.

Broker privileges MUST NOT provide a `SET ROLE` or membership route to owners.

Privileged custodians remain capable of disrupting or altering the system. Their intervention is a trust-boundary event requiring external evidence, fencing and independent continuity/re-adoption.

Custody-only grants cannot reach register-state, admission, dispatch-claim or effect mutation functions. Observation-only grants cannot mutate any authority relation.

The function responsible for custody binding may modify only the defined locator/history/receipt-material records. Neither function ownership nor shared infrastructure establishes actor independence.

## 12\. Broker interface and responsibility

The broker exposes fixed typed handlers only.

It owns:

- Authenticated session establishment.
- Configuration/incarnation validation.
- Exact session profile.
- Admission and transaction boundaries.
- Permanent dispatch-claim sequencing.
- One acknowledged live continuation and irreversible pre-invocation latch.
- Function invocation and COMMIT.
- Receipt issuance sequencing.
- Primary readback sequencing.
- Failure classification and redaction.

It MUST NOT expose generic SQL or become a database administrator, approval authority, independent verifier, recovery engine, scheduler or automatic retry engine.

Transport authentication binds the caller principal and credential identity to the logical role. An untrusted caller cannot supply an identity header that the broker accepts as authenticated.

A broker restart reopens observation capability only. It does not resume entered operations, regenerate operation identities or clear uncertainty.

The custody component similarly retains only the original acknowledged live reservation continuation for one upload. A matching reservation/object or a restart cannot reconstruct upload permission.

## 13\. Retry inventory

| Layer/mechanism | Required treatment |
|---|---|
| Application protected-effect retry | PROHIBITED |
| Broker protected-effect retry | PROHIBITED |
| PostgreSQL automatic statement/transaction replay | PROHIBITED; ambiguous entry becomes UNKNOWN |
| Connection replacement continuing a prior effect | PROHIBITED |
| Proxy | Excluded unless independently proven not to replay and separately included in configuration |
| Transaction-helper protected-operation retry, including serialization/deadlock retry | PROHIBITED |
| AWS SDK mutation retry | PROHIBITED for uploads and other protected persistence |
| HTTP automatic mutation retry | PROHIBITED |
| S3 multipart | PROHIBITED |
| S3 high-level transfer manager | PROHIBITED |
| Automatic multipart conversion | PROHIBITED |
| Asynchronous transfer/upload resume | PROHIBITED |
| Middleware mutation replay | PROHIBITED |
| Stream rewind/resubmission | PROHIBITED |
| Authentication-refresh replay after possible entry | PROHIBITED |
| Redirect mutation replay | PROHIBITED |
| TSA automatic retransmission | PROHIBITED |
| Job-runner protected-workflow retry/resume | PROHIBITED |

Read-only retry MAY occur only for the same explicitly permitted observation, within freshness limits, with every attempt retained where required.

Read-only retry does not change a prior UNKNOWN, admit an operation or authorize recovery. Separately authorized new clock sampling does not reuse a timed-out sample as valid evidence.

Refreshing credentials before a separately authorized future request cannot replay a request that may already have entered.

## 14\. S3 custody and exact-version resolution

The evidence store MUST use:

- Adopted bucket/resource/account/Region identity.
- Versioning and Object Lock compliance retention.
- Exact object key and exact non-null version ID.
- Complete raw-byte SHA256.
- Authority incarnation, issuer, evidence role and original operation bindings.
- Verified retention mode and retention-until information.
- Independently qualified access and durability arrangements.

No bare key, current-version lookup, ETag or “latest” alias establishes evidence identity.

The frozen `retain(record)` receives an already assigned evidence identity. Because an S3 version ID is assigned after upload, the implementation MUST use the immutable evidence-locator relation to bind that existing identity to its exact resulting version.

Custody binding is a separate fixed operation with restricted rights. It cannot mutate protected activation state or manufacture qualification.

The upload’s raw body MUST NOT contain its own future version ID or resulting raw digest as a self-dependent input.

### 14\.1 Single-request preconditions

Each custody attempt permits exactly one low-level non-replayed upload request.

Multipart upload, transfer managers, automatic multipart conversion, asynchronous resume, streaming-body rewind/resubmission, middleware mutation replay, redirect replay and authentication-refresh replay after possible entry are prohibited.

Before reservation or upload:

- Complete raw bytes are fixed and immutable.
- Complete SHA256 and exact byte size are known.
- Existing frozen evidence identity/digest match those bytes.
- The reviewed configuration supplies `max_single_upload_bytes`.
- Complete size is within that bound and the selected low-level single-request API’s supported maximum.
- Request/attempt identity, bucket, key, retention plan and incarnation are fixed.
- Unsupported size rejects before upload.
- No truncation, splitting or partial hashing occurs.

`max_single_upload_bytes` is an exact positive integer, explicitly selected and pinned before affected implementation authorization. There is no default, automatic enlargement or multipart fallback.

### 14\.2 Deterministic key and conditional conflict

The key is exactly the concatenation:

`evidence/v1/`

then, separated by `/`:

1. Lowercase hexadecimal UTF-8 bytes of namespace.
2. Lowercase hexadecimal UTF-8 bytes of incarnation ID.
3. Lowercase hexadecimal UTF-8 bytes of custody role.
4. Lowercase hexadecimal UTF-8 bytes of evidence identity.

This is a storage-locator rule, not a new frozen identity/hash domain.

The derived key must fit the supported service key-size limit. Otherwise reject before upload. No shortening, random suffix or substitute key is permitted.

The request MUST use the selected low-level conditional create with `If-None-Match: *`, versioning enabled and approved COMPLIANCE retention parameters.

Qualified rights/policy must prevent executor deletion, delete-marker creation, versioning suspension and replacement. A delete marker cannot justify writing again to a previously used custody key.

A conditional precondition failure or conditional-write conflict terminates the attempt without another upload. Provider retry recommendations do not override this rule.

Conflict MUST NOT cause:

- Key regeneration.
- A new evidence identity.
- A new custody attempt.
- Unconditional overwrite.
- A second upload “to make sure.”

### 14\.3 Custody sequence

The original live custody continuation:

1. Validates exact immutable bytes and plan.
2. Commits RESERVE.
3. Receives definite reservation acknowledgement.
4. Irreversibly consumes its one-upload latch.
5. Dispatches one low-level conditional upload.
6. Requires a definite successful response and exact non-null version ID.
7. Reads that exact version.
8. Verifies complete raw digest/size.
9. Verifies COMPLIANCE retention and required deadline.
10. Authenticates required custody evidence.
11. Commits BIND.
12. Establishes definite binding acknowledgement and required authenticated evidence.
13. Returns the same frozen reference.

Confirmed custody requires all of:

1. Exactly one dispatched upload.
2. Definite successful upload response.
3. Exact non-null version ID.
4. Exact-version readback.
5. Complete raw digest verification.
6. Compliance-retention verification.
7. Durable immutable EVIDENCE\_CUSTODY\_BINDING.
8. Required authenticated custody evidence.

A reservation is not a resumable upload job. A BOUND locator is not replaceable.

### 14\.4 UNKNOWN\_CUSTODY and resolution

Lost/ambiguous upload response is UNKNOWN\_CUSTODY. No upload repetition.

Unknown version, uncertain locator COMMIT or unavailable retention verification is UNKNOWN/unconfirmed custody.

Read-only resolution may inspect permitted custody evidence to identify the original version. It MUST NOT choose an arbitrary matching or latest object and declare success.

Matching bytes or an absent object do not reconstruct acknowledgement or upload permission. Any later outcome determination requires separately permitted resolution/recovery authority.

Resolution verifies locator authenticity, bucket/resource identity, version, raw digest, issuer/role/context and continuing custody applicability.

Missing, corrupt, substituted, deleted or inaccessible evidence fails closed. Retention extension does not permit shortening, replacing or deleting required evidence.

## 15\. RFC3161 client and evidence validation

No endpoint, subscription identifier, credential value or certificate value is fixed here.

The operational profile MUST bind the selected DigiCert Europe service, applicable TSP/PS, requested policy OID, permitted TSUs/chains, algorithms, status validation and subscriber entitlement.

Each sample request requires:

- Fresh unpredictable nonce.
- Exact message imprint binding the sample context and request identity.
- Requested policy.
- Retained exact DER request.
- Monotonic send and receive observations.

The response validator MUST check:

- Successful supported RFC3161 status.
- Correct complete DER/CMS structure.
- Exact message imprint and nonce.
- Exact requested policy.
- Signature and signer-certificate binding.
- Authorized timestamp-signing usage and chain.
- Certificate validity and applicable revocation/status evidence.
- Authenticated `genTime`.
- Applicable accuracy statement and policy.
- Permitted algorithms and sizes.
- Complete request/response/context provenance.

No TLS success alone establishes timestamp validity.

Certificate/status validation MUST have an explicitly approved bootstrap policy; it cannot silently trust an unqualified OS clock or waive certificate validity to obtain the first sample.

Unknown policy, unavailable status proof, malformed token, bad signature or substituted nonce rejects.

The client retains original DER bytes without reserialization to invent evidence identity.

## 16\. Conservative UTC interval and monotonic bridge

Let:

- `g` be authenticated TSU processing time.
- `a` conservatively cover applicable authenticated accuracy.
- `D` bound request-to-response elapsed time, including qualified measurement uncertainty.

The initial receipt-anchor interval SHALL conservatively contain:

`[g − a, g + a + D]`

Any additional parsing, scheduling, transport or validation uncertainty MUST be accounted for exactly once at the correct anchor. Bounds MUST round outward.

No symmetric-network assumption, half-RTT shortcut, midpoint or narrower inferred accuracy is allowed.

A missing token accuracy field does not imply zero error. The approved policy accuracy remains applicable. Wider applicable bounds prevail.

The bridge returns only existing:

- `QualifiedClockProfile`
- `QualifiedSample`
- `MonotonicPoint`
- `QualifiedPropagationError`
- `TimeBinding`

It MUST use frozen `evaluate_time` behavior.

The bridge requires qualified same-process/domain continuity, explicit elapsed/error binding, freshness and maximum uncertainty. It cannot self-qualify its oscillator or drift limits.

Current decisions use authenticated current intervals. Fixed creation timestamps remain fixed.

Restart invalidates monotonic anchors. New qualified startup evidence and durable-history comparison are required. No persisted sample is silently re-anchored.

Full intervals must satisfy applicable frozen bounds. No OS-wall-clock authority fallback is permitted.

## 17\. Incarnation and restore fencing

Every session and protected operation MUST bind:

- AWS account and Region.
- Immutable RDS DB resource identity.
- Adopted writer endpoint.
- Engine/build.
- Parameter and function/schema identities.
- Secret-free configuration fingerprint.
- Authority incarnation.
- Externally retained selection/adoption evidence.

DNS names, tags, copied rows and database-local adoption flags are insufficient.

Snapshot restore, PITR, replacement, migration, endpoint substitution or continuity outside the qualified profile starts NON\_AUTHORITATIVE.

The implementation MUST check externally established identity/continuity evidence before effect admission and reject mismatches. It cannot trust a copied resource’s internal claim that it is adopted.

An incarnation fence MUST be checked by broker admission and protected functions against the adopted scope. External trust must prevent a restored copy from gaining active broker/signing credentials solely through copied configuration.

Privileged changes suspend authority until independently adjudicated. The implementation supplies detection and rejection; recovery/re-adoption remains outside scope.

## 18\. Failure and UNKNOWN matrix

“Read-only resolution allowed” means only within existing approved observation authority. It is never implicit recovery permission.

| Condition | Required result | Read-only resolution |
|---|---|---|
| Admission connection failure with proven no dispatch | REJECT/FAIL\_CLOSED; no retry permission | Allowed if needed |
| Admission COMMIT uncertain | UNKNOWN; original fenced | Allowed |
| Duplicate/conflicting admission | Reject; no new admission or continuation | Allowed |
| Claim COMMIT acknowledgement uncertain | UNKNOWN; no effect dispatch | Allowed |
| Crash after definite claim/before effect | Permanently consumed/fenced; no replacement dispatch | Allowed |
| Duplicate/conflicting claim | Reject; no new claim/dispatch capability | Allowed |
| Stale/duplicate broker continuation | Reject before invocation; no latch reset | Allowed |
| Effect/savepoint/subtransaction rollback | Claim remains consumed; no repeated effect entry | Allowed |
| Checkpoint publication uncertain | UNKNOWN; no CAS progression | Allowed |
| Activation CAS uncertain | UNKNOWN; no ACTIVE inference | Allowed |
| Readback unavailable | FAIL\_CLOSED; preserve prior reached state | Allowed |
| Readback mismatch | REJECT/STOP; independent recovery required | Allowed |
| Receipt issuance/retention uncertain | No confirmed return; preserve known effect and evidence gap | Allowed |
| Custody reservation uncertain | UNKNOWN\_CUSTODY; no upload permission reconstructed | Allowed |
| S3 upload/version/retention uncertain | UNKNOWN\_CUSTODY; no replacement upload | Allowed |
| S3 conditional conflict | Reject; no new key/upload | Allowed |
| Custody binding COMMIT uncertain | UNKNOWN\_CUSTODY; no upload/binding repetition | Allowed |
| S3 resolution unavailable | FAIL\_CLOSED | Allowed |
| S3 raw digest or locator mismatch | REJECT/STOP | Allowed |
| TSA timeout | No usable sample; preserve request identity | No automatic retransmission |
| TSA invalid signature | REJECT | Observation only |
| TSA policy mismatch | REJECT | Observation only |
| TSA nonce/imprint mismatch | REJECT | Observation only |
| TSA interval too wide/stale | REJECT | Separately permitted fresh sampling only |
| Database failover during effect | UNKNOWN unless complete outcome proof already exists | Allowed |
| Broker restart | No entered-operation or custody continuation eligibility | Allowed |
| Host restart | Invalidate monotonic anchors; no automatic continuation | Allowed |
| Credential rotation | Reject until continuity/current rights are established | Allowed |
| Restore/PITR detection | NON\_AUTHORITATIVE quarantine | Separately approved observation |
| Incarnation/configuration mismatch | REJECT/STOP before effect | Allowed |

A later definite rejection cannot erase a stronger already-reached uncertain boundary.

## 19\. Configuration and credential carriers

Configuration is explicitly supplied. No environment discovery, default endpoint, default AWS credential chain, home-directory credential search or ambient database fallback is permitted.

Required names/types:

| Class | Names and types |
|---|---|
| Resource identity | AWS account, Region, DB resource ID, writer endpoint identity, bucket identity: identifiers |
| Incarnation | Namespace, incarnation ID, fence epoch: identifiers/exact integer |
| Software/configuration | Engine/build, schema/function digest, dependency lock digest, configuration fingerprint: identifiers/digests |
| Adoption | Selection, qualification, adoption and recovery-policy references: frozen evidence references |
| Network/TLS | Endpoint references, peer names, CA/trust references, bounded timeout profile |
| Database | Database/schema identifiers and fixed session-profile identity |
| S3 | Bucket/key policy, retention profile, exact-version locator policy, exact positive single-upload byte limit |
| TSA | Service reference, policy OID, signer/chain/status policy, subscriber-entitlement reference |
| Time | Qualified clock profile, uncertainty/age/error limits and continuity policy |
| Actors | Logical role, principal, authority and issuer identities |
| Secret references | Database, broker, custody, signer, verifier and TSA credential references |
| Credential carriers | Explicit opaque capability objects; no printable secret fields |

The configuration fingerprint covers the exact non-secret configuration and credential **identity/reference**, never credential values.

Credential carriers MUST provide only the required scoped operation. Construction/import does not acquire credentials or contact services.

Secrets MUST NOT enter canonical objects, raw retained request bodies, exception chains, logs, diagnostics or shell history. Audit records identify credential identity without value.

Rotation preserves verified logical continuity; uncertain revocation or changed authority rejects.

A signer reference does not select a non-RFC3161 signing technology. The relevant receipt role must first satisfy §6.1’s realization-decision gate.

## 20\. Qualification and independent-verification inputs

The realization does not replace R3 with broker self-attestation.

R3 must supply independently authorized evidence covering:

- Provider/resource/configuration identity.
- Host, storage and native-filesystem qualification.
- Clock profile and propagation limits.
- Actor rights and effective role incompatibility.
- Custody and resolution qualification.
- Current authority/history and applicable revocation.
- Complete role-specific frozen claims.
- Independent result verification.

A verifier decision MUST name the actual raw subjects and obligations proved. The client cannot turn requested obligations into successful claims.

Root trust/adoption material is supplied through a separately approved bootstrap package. Evidence dependency traversal must terminate at those explicit roots, not at a self-signed success label or an infinite provenance cycle.

Package/creation qualification remains upstream-only. Q qualification excludes downstream payload and execution results.

## 21\. Offline certification before staging

Certification MUST distinguish exact executed-byte evidence from historical context.

Required offline coverage:

1. Frozen serializer and E/P/payload vector continuity.
2. Exact abstract-client and dataclass compatibility.
3. All required role/obligation mappings.
4. Strict scalar types and numeric boundaries.
5. SQL PK/FK/uniqueness/immutability invariants.
6. Concurrent original admission and duplicate rejection.
7. Dispatch-claim concurrency.
8. Duplicate and conflicting claim rejection.
9. Lost claim acknowledgement prevents effect dispatch.
10. Broker crash after definite claim/before effect leaves original consumed.
11. Broker restart cannot reconstruct a continuation.
12. Stale and duplicate worker/RPC continuation rejection.
13. Savepoint/subtransaction cannot restore eligibility.
14. Effect rollback cannot restore eligibility.
15. Complete duplicate/conflict matrix.
16. Closed states and illegal regression rejection.
17. Cross-incarnation FK and copied-binding rejection.
18. Immutable-field enforcement.
19. Driver/pool/HTTP/SDK/job retry suppression.
20. Non-activating C0 publication.
21. ABSENT CAS conflict/already-active rejection.
22. Primary readback ordering and stale-snapshot rejection.
23. Incarnation/configuration mismatch and restore quarantine.
24. Custody reservation/binding duplicate/conflict behavior.
25. Read-only resolution cannot progress state or recreate permission.
26. S3 exact-version custody and immutable locator behavior.
27. Lost upload response and unknown version.
28. Uncertain custody reservation/binding acknowledgement.
29. Multipart prohibited.
30. High-level transfer managers prohibited.
31. Automatic multipart conversion prohibited.
32. Middleware replay prohibited.
33. Stream rewind/resubmission prohibited.
34. Authentication-refresh replay after possible entry prohibited.
35. Redirect mutation replay prohibited.
36. Asynchronous transfer resume prohibited.
37. Single-request size rejection before dispatch.
38. No truncation or partial hashing.
39. Deterministic-key/conditional-conflict behavior without new-key retry.
40. Exact-version digest and compliance-retention verification.
41. Digest, issuer, role and evidence substitution rejection.
42. Non-RFC3161 authentication/status/replay tests against the separately selected reviewed realization.
43. Mandatory RFC3161 CMS, policy, nonce, imprint, signer and accuracy failures.
44. Interval boundaries, propagation errors and restart invalidation.
45. Credential redaction, ambient-credential rejection and role separation.
46. Import/construction zero-I/O behavior.
47. UNKNOWN terminality across process/session/credential changes.
48. No register preparation, genesis or runtime side effects.
49. Existing relevant frozen compatibility suites under separately approved certification scope.

No test requires PostgreSQL transaction IDs, backend IDs or session IDs as durable authority identities.

Use maintained cryptographic libraries and independently generated positive/negative fixtures. Tests must not merely echo the same serializer or mocked success path.

SQL transaction/concurrency behavior MUST be exercised against disposable **local PostgreSQL** matching the selected engine family. A dictionary mock is insufficient. Starting such tests requires separate test-execution authorization.

No managed AWS/DigiCert access is part of offline certification.

Historical census failures remain raw failures. Any expected artifact-population interaction requires explicit reporting and independent disposition, not hiding files or changing frozen tests.

## 22\. Future managed qualification

Separate authorization is required to establish real evidence for:

- Supported RDS failover and acknowledged-commit preservation.
- Actual driver/session behavior and claim acknowledgement.
- Live-continuation, stale-worker and duplicate-worker fencing.
- Rights separation and privileged-custodian fencing.
- Real primary readback ordering.
- Crash, concurrency, lost-response and restart behavior.
- S3 single-request conditional custody, compliance retention and exact-version resolution.
- External receipt authentication/verifier trust and independence.
- DigiCert subscription, endpoint, TSU/status validation and latency.
- Local monotonic uncertainty and physical storage durability.
- Resource/configuration continuity and restore quarantine.

Synthetic compatibility does not qualify these properties.

## 23\. Future resources — none authorized for creation

| Resource | Status |
|---|---|
| Isolated RDS PostgreSQL Multi-AZ DB instance and synchronous standby | NOT AUTHORIZED FOR CREATION |
| Authority database/schema/functions and restricted roles | NOT AUTHORIZED FOR CREATION |
| Broker execution/service boundary and authenticated transport | NOT AUTHORIZED FOR CREATION |
| S3 Object Lock compliance evidence bucket and custody policy | NOT AUTHORIZED FOR CREATION |
| Independent verifier/approver authority arrangements | NOT AUTHORIZED FOR ESTABLISHMENT |
| Hosted physical Linux register host | NOT AUTHORIZED FOR CREATION |
| Permanent SSD/NVMe and qualified local filesystem | NOT AUTHORIZED FOR PREPARATION |
| DigiCert subscriber access | NOT AUTHORIZED FOR ACQUISITION |
| Scoped identities, credential carriers, signing and trust material | NOT AUTHORIZED FOR ACQUISITION |
| Independent adoption/incarnation evidence arrangements | NOT AUTHORIZED FOR OPERATIONAL ADOPTION |

No additional managed platform, KMS service, proxy, queue or orchestration service is selected implicitly.

## 24\. Frozen surfaces

All existing tracked files remain unchanged, including:

- `fixture_lease_activation.py` and its tests.
- `fixture_lease_authority_providers.py` and its tests.
- `fixture_lease_store.py`.
- `fixture_lease_service.py`.
- Existing protocol, checkpoint, publication, publication-qualification, completion and command modules/tests.
- Existing migrations, application startup, dependencies and deployment configuration.
- All authority/design documents.

The additive dependency lock does not modify existing application dependencies or authorize installation.

Frozen STATE/CHECKPOINT framing, E/P/payload encoding, scalar references, opaque-evidence categories, validity predicates and generation semantics remain exact.

Any frozen-surface modification, incompatible seam, new permit, altered authority meaning or extra implementation path is a contract finding requiring owner and independent review.

## 25\. Preparation and later operational boundaries

After qualified independent adoption, a separate NON\_AUTHORITATIVE preparation package must bind:

- Register and activation identities.
- Fixed K and J.
- Approved host, native paths and storage identity.
- Software/build/configuration identities.
- Qualified clock and fixed creation-time semantics.
- Operator/process/issuer identities.
- Qualified provider incarnation.
- Current ABSENT and original-history evidence.
- Evidence custody arrangements.
- Authorization validity and finite preparation steps.

This realization does not create that authorization.

Actual preparation precedes actual C/S0/E/G/C0/P. Independent Q follows exact P. The activation payload remains downstream of Q.

Physical publication, protected non-activating C0 publication, ABSENT CAS, readback and independent result verification remain separately authorized stages.

No historical operational F, permit completion or G artifact is reconstructed. The external historical adjudication premise remains unchanged.

Fixture provisioning, Step-7 CANARY, runtime activation and public traffic retain independent later gates.

## 26\. Future implementation and authority DAG

The required order is:

Owner-approved implementation contract\
→ separately authorized bounded implementation\
→ separately authorized offline certification\
→ independent implementation review\
→ exact staging/index/commit/object/publication/freeze gates\
→ separate resource-establishment authorization\
→ bounded resource establishment/configuration\
→ separate qualification-execution authorization\
→ retained qualification evidence\
→ independent provider adoption\
→ operational preparation package\
→ explicit NON\_AUTHORITATIVE preparation authorization\
→ actual authorized preparation and C/S0\
→ E/G and complete C0\
→ exact P\
→ independent Q\
→ downstream activation payload\
→ explicit physical/protected publication and activation authorization\
→ one original authorized effect sequence\
→ authoritative readback\
→ independent result verification\
→ all frozen ACTIVE eligibility checks\
→ separately authorized fixture provisioning and later CANARY/runtime gates.

No downstream receipt, approval or result authenticates an upstream prerequisite. No receipt includes its own future custody identity as an input.

**AUTHORITY\_DAG = PASS**

**CYCLE\_COUNT = 0**

Concrete non-RFC3161 authentication selection/review must occur before affected implementation authorization. It does not advance operational adoption or any later gate.

## 27\. STOP conditions

Implementation or certification MUST STOP on:

- Frozen identity or semantic conflict.
- Need to modify a frozen surface.
- Unspecified issuer/role meaning or evidence interpretation.
- Unresolved concrete authentication realization for an affected receipt role at implementation authorization.
- Unauthenticated qualification or adoption.
- Missing raw evidence or unresolved integrity/status.
- Inability to enforce permanent admission/claim history and the one live dispatch continuation.
- Any automatic retry after possible protected entry.
- Unqualified time/storage/resource continuity.
- Restore or incarnation ambiguity.
- Authority cycle or self-authentication.
- Unexpected managed access, credential acquisition or operational effect.

No fallback, repair, alternate provider, new original identity or automatic recovery is authorized.

## 28\. Candidate status

This proposed contract is ready for independent normative review. It is not self-approved and grants no implementation, resource, credential, qualification, preparation, genesis or activation authority.

The finding closures below record proposed textual remediation only. Independent normative review must determine their acceptance.

```
PROPOSED_PATH =
docs/decisions/JOUS.CORE.1A.operational-provider-realization-implementation-contract.md

PROPOSED_STATUS =
OFFLINE_NORMATIVE_CANDIDATE_NOT_WRITTEN

PROPOSED_IMPLEMENTATION_FILES =
services/api/infrastructure/fixture_lease_authority_provider_clients.py
services/api/infrastructure/fixture_lease_authority_transaction_broker.py
services/api/infrastructure/fixture_lease_authority_evidence.py
services/api/infrastructure/fixture_lease_authority_time.py
services/api/infrastructure/fixture_lease_authority_schema.sql
services/api/infrastructure/fixture_lease_authority_realization_dependencies.txt

PROPOSED_TEST_FILES =
tests/test_fixture_lease_authority_provider_clients.py
tests/test_fixture_lease_authority_transaction_broker.py
tests/test_fixture_lease_authority_evidence.py
tests/test_fixture_lease_authority_time.py

FROZEN_FILES_REQUIRING_CHANGE = NONE

NEW_RESOURCE_TYPES =
RDS authority instance/database/roles
S3 compliance evidence custody
bounded broker service boundary
independent verification arrangements
physical Linux host/local storage
DigiCert subscriber access
scoped identities/credential and trust material

MANAGED_QUALIFICATION_REQUIRED = YES

SECRET_ROLE_GROUPS =
broker/database
executor
evidence custody/resolution
provider receipt signer — only if separately selected and reviewed
independent approver
independent verifier
TSA subscriber
custodian/recovery

UNRESOLVED_IMPLEMENTATION_CONTRACT_GAPS = 0

RIC_01_STATUS = CLOSED
RIC_02_STATUS = CLOSED
RIC_03_STATUS = CLOSED
RIC_04_STATUS = CLOSED

FINDING_CLOSURE_BASIS =
Proposed remediation, subject to new independent normative review.
No independent approval is asserted.

NON_RFC3161_RECEIPT_AUTHENTICATION_DECISION = UNRESOLVED

CLASSIFICATION =
REALIZATION_DECISION_REQUIRED_BEFORE_IMPLEMENTATION_AUTHORIZATION

BLOCKS_ARTIFACT_CREATION = NO
BLOCKS_INDEPENDENT_NORMATIVE_REVIEW = NO
BLOCKS_FUTURE_IMPLEMENTATION_AUTHORIZATION = YES_FOR_UNRESOLVED_RECEIPT_ROLES

ARTIFACT_CREATION_AUTHORIZED_BY_THIS_GATE = NO

IMPLEMENTATION_CONTRACT_CANDIDATE_COMPLETE = YES
READY_FOR_INDEPENDENT_NORMATIVE_REVIEW = YES

FILES_WRITTEN = NO
CODE_CHANGED = NO
GIT_MUTATED = NO
TESTS_EXECUTED = 0
MANAGED_ACCESS = NO
AWS_ACCOUNT_ACCESS = NO
DIGICERT_ACCOUNT_ACCESS = NO
CREDENTIAL_ACCESS = NO
RESOURCES_CREATED = 0
REGISTER_CREATED = NO
PREPARATION_PERFORMED = NO
GENESIS_ATTEMPTS = 0
ACTIVATION_ATTEMPTS = 0
FIXTURE_PROVISIONING = NO
CANARY = NO
RUNTIME_OPERATIONS = 0
PUBLIC_TRAFFIC = NO
