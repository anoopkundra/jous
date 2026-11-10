# JOUS.CORE.1A non-RFC3161 receipt authentication profile

Status: **OFFLINE NORMATIVE SELECTION RECORD ? NOT APPROVED FOR IMPLEMENTATION ? NOT OPERATIONALLY ADOPTED**

## 1. Authority, scope and precedence

Derivation baseline: `e633137d760bfbbdf1545ac41c991e2307039eab`.

Controlling frozen contract: [Operational provider realization implementation contract](JOUS.CORE.1A.operational-provider-realization-implementation-contract.md).

CONTRACT_SHA256 = 75fe1a06f33ebaa3509eeaaa816d072c326ef4acf586827aab8fc948e752a3ba

CONTRACT_GIT_BLOB = 1e005efbec51898c327fbabdbcdea99e82e4b855

Independent owner-decision review token: `CORE1A_NON_RFC3161_RECEIPT_AUTHENTICATION_PROFILE_INDEPENDENTLY_APPROVED_FOR_OWNER_DECISION`.

Owner decision: APPROVED ? create the normative selection/profile record for refined Candidate B. That decision authorizes this offline candidate artifact only. This document closes technology/profile selection only after its independent review and repository publication. It does not self-approve or authorize implementation or operational adoption. Until those gates complete, the frozen contract's unresolved-receipt-role implementation restriction remains in force. Publication of this record would close the technology-selection item, not waive downstream schema, trust, qualification or authorization requirements.

Frozen IL6 semantics, provider seams, opaque evidence identities, R1?R8, original-attempt exclusion, dispatch claims, UNKNOWN terminality, custody, time and incarnation boundaries remain controlling. Conflicts require STOP and independent authority review; no frozen file change is authorized.

## 2. Selected cryptographic profile

| Property | Selection |
|---|---|
| PROFILE_ID | JOUS_NON_RFC3161_RECEIPT_BINDING_V1 |
| TECHNOLOGY | ROLE_SEPARATED_AWS_KMS_ASYMMETRIC_SIGNATURES |
| SIGNATURE_ALGORITHM | RSASSA_PSS_SHA_256 |
| HASH_ALGORITHM | SHA256 |
| KEY_TYPE | AWS KMS customer-managed RSA_3072 |
| KEY_ORIGIN | AWS-generated key material |
| KEY_USAGE | SIGN_VERIFY |
| KMS_MESSAGE_TYPE | DIGEST |
| PSS_PARAMETERS | SHA-256 / MGF1-SHA256 / 32-byte salt |
| SIGNATURE_LENGTH | 384 octets |
| EXTERNAL_SIGNATURE_ENCODING | Strict unpadded base64url where transport encoding is required |
| KEY_IDENTITY | Full KMS key ARN + SHA256(exact DER SubjectPublicKeyInfo) |

The verifier MUST require these exact algorithm, modulus-size, digest, mask-generation and salt-length parameters. Algorithm negotiation, alternate padding, automatic salt-length acceptance and key aliases as authority identifiers are prohibited. The external signature is the original 384 signature octets; any transport encoding MUST decode strictly to those octets. Padding, non-base64url alphabet, malformed encodings and noncanonical base64url representations reject. AWS API transport encoding is distinct from this external receipt encoding.

No actual AWS account, Region, key ARN, public key, credential or resource is selected by this record.

## 3. Exact signed bytes; no JCS

JCS_REQUIRED = NO

JCS_SELECTED = NO

The signed body is the complete immutable UTF-8 byte sequence of one closed-schema JSON object. The producer and verifier MUST reject BOM, invalid Unicode, duplicate members, unknown members, wrong types and invalid domains. Invalid Unicode includes malformed UTF-8 and unpaired surrogate values in JSON strings. Integer parsing MUST be exact and enforce the frozen numeric bounds. Floating-point or Boolean coercion MUST NOT satisfy integer fields. No arbitrary extension bag or inferred authority-bearing default is permitted.

Compute SHA256 over the exact original body bytes and pass that 32-byte digest to KMS with `MessageType=DIGEST` and `SigningAlgorithm=RSASSA_PSS_SHA_256`. External verification MUST use prehashed SHA-256 and the exact PSS parameters in ?2; hashing the supplied digest again is prohibited.

Verification MUST NOT normalize, reorder, re-encode or canonicalize the body. Parsing validates schema and claims without replacing the retained byte sequence being authenticated. Retain the exact body bytes and original signature octets, together with the complete original external receipt representation and its authenticated dependencies.

Semantically equivalent alternative JSON encodings are different authority-bearing byte objects. A deterministic producer may reuse compatible compact JSON conventions, but verification remains over exact retained bytes. The frozen E/P/activation-payload canonical serializer MUST NOT be modified or broadened.

## 4. Detached binding statement and role schemas

The receipt is a detached signed binding statement over unchanged subject evidence. It authenticates the binding issuer's statement, not a rewritten version of its subject.

Each receipt role MUST have a reviewed closed schema, complete field expansion, types, domains, upstream sources and required comparisons before implementation authorization for that role. Role-schema/codec mapping remains downstream; this profile does not invent a universal executable receipt schema. Optionality MUST be explicitly defined per role, never inferred by the implementer.

The role-specific schema MUST bind the following information whenever it exists at that role's stage and is required by its frozen obligations:

| Binding group | Required information |
|---|---|
| Profile | Profile/version, receipt role/purpose, algorithm/profile identity |
| Issuer and provider | Issuer identity, provider identity, logical authority identity, account/Region when part of that authority's scope |
| Authority scope | Namespace, authority incarnation, configuration/adoption references |
| Original request | Original operation identity, request identity/reference/digest |
| Subject | Subject evidence identity and complete raw subject SHA256 |
| Decision | Decision/result identity/reference/digest when already established |
| Causality | Required existing causal predecessor references |
| Qualification and time | Applicable existing qualification/time references |
| Verification key | Full KMS key ARN and SHA256(exact DER SPKI) |

No future/downstream field may be required in upstream evidence. Role definitions MUST distinguish absent upstream facts from contradictory or missing required facts. A matching label or copied request cannot prove that a decision occurred. Producer authorization and decision-to-receipt correspondence require independent qualification.

## 5. Acyclic identity and retained subjects

The signed body MUST NOT contain its own final receipt hash, its own final evidence identity if that identity depends on complete receipt bytes, a future S3 object version, or any downstream result not yet existing. The final external receipt identity/reference is calculated only after complete receipt bytes exist under the applicable frozen evidence-reference rules.

Body and detached signature assembly, transport framing and final evidence-reference mapping require the downstream reviewed codec; this record changes no frozen identity/hash domain. Custody locators remain separate exact-version bindings and MUST NOT introduce a self-dependent receipt.

Existing opaque C, Q and other external evidence remain exact-byte preserved. A later signed binding does not retroactively make its signer the original issuer. Evidence traversal MUST terminate at explicit independently approved trust/bootstrap roots, without self-authentication or circular adoption.

## 6. Cryptographic validity and authority

A mathematically valid KMS signature is insufficient by itself. Operational acceptance requires independently retained authority evidence binding at least provider, account/tenant boundary, Region, full key ARN, DER SPKI fingerprint, algorithm, issuer, permitted receipt roles, namespace/incarnation/configuration scope, adoption/validity interval, replacement/supersession relationship, lifecycle/status authority and independent approval.

The verifier MUST authenticate that binding through approved trust roots and compare it with the actual receipt and required role/context. The public key supplied alongside a receipt cannot authorize itself. Aliases are not authority identifiers. A copied adoption record cannot authorize another authority incarnation. Cryptographic success cannot clear a pre-existing UNKNOWN, approve recovery or create effect eligibility.

MATHEMATICALLY_VALID_SIGNATURE and AUTHORIZED_APPLICABLE_RECEIPT are distinct results. Only the latter, with every frozen evidence obligation satisfied, may contribute to qualified acceptance.

## 7. Role separation and signing rights

The common cryptographic profile does not imply a common key. Incompatible authorities MUST retain separate keys and scoped signing rights. At minimum distinguish, as applicable to their independently approved duties:

- Protected broker.
- Custody authority.
- Qualification authority.
- Independent approval authority.
- Independent result-verification authority.
- Governance/adoption authority.

Further separation is required whenever role incompatibility, issuer scope or incarnation requires it. A broker signing key cannot issue Q, governance adoption or independent result verification. A common AWS provider or account does not itself demonstrate independence; administrative/signing access and effective incompatibility require qualification.

Verifiers require public verification material, not signing permission. Future signing rights MUST be restricted to approved principals, exact keys and receipt roles. Public-material access does not confer issuer authority. No IAM policy, key policy, grant or credential is established here.

## 8. Key replacement, lifecycle and compromise

Asymmetric KMS key replacement uses a new key and new authority binding. An alias MUST NOT be treated as a historical key version. Preserve historical public material, adoption history, lifecycle/status history, supersession relationships and applicable time/custody provenance.

Disabling or deleting a KMS key does not invalidate mathematical verification using previously retained public material. This is an offline cryptographic property, not continuing operational authorization. A disabled key permits no new use requiring enabled status. Historical operational reliance still requires the separately approved lifecycle/status and applicability rules.

Known compromise requires fail-closed operational reliance and independent adjudication of the affected scope. A claimed signed timestamp alone cannot establish that evidence predates compromise. Unknown revocation, missing status, ambiguous replacement or unverifiable continuity yields no qualified receipt. Retained history MUST NOT be rewritten to make replacement material appear to be the original signer.

## 9. Trusted time

KMS_SIGNATURE_IS_TRUSTED_TIME = NO

SIGNED_TIMESTAMP_IS_TRUSTED_TIME = NO_UNLESS_SEPARATELY_QUALIFIED

KMS signatures authenticate bytes/digests. They do not establish UTC accuracy or trusted issuance time. An issuer-supplied timestamp is a claim, not a time authority. Existing RFC3161 and qualified monotonic/time evidence remain controlling wherever trusted time is required. This record changes neither the trusted-time architecture nor fixed creation timestamps, conservative intervals, freshness, monotonic propagation or restart invalidation.

## 10. KMS and Jous trust boundary

AWS KMS does not determine whether a Jous operation was authorized, whether claims are truthful, whether an incarnation is valid, whether independent approval exists, whether a receipt role is permitted, whether an operation may be retried, or whether a protected effect may be replayed.

KMS performs the authorized cryptographic operation on supplied bytes/digest. Approved producer code, scoped signing rights, frozen authority rules and independent authority evidence remain required. A KMS response is not an independent qualification, approval, adoption, database decision or trusted-time receipt. Signing cannot manufacture or retroactively authorize an effect.

## 11. Failure and UNKNOWN semantics

| Condition | Required disposition |
|---|---|
| Invalid signature, unsupported algorithm or malformed envelope | Definite evidence rejection |
| Unknown/unapproved key or missing adoption | Fail closed; no qualified receipt |
| Digest mismatch | Reject, preserve evidence and STOP applicable progression |
| Incarnation mismatch | Reject; replacement resource gains no authority |
| Known compromise/revocation | Reject current operational reliance; quarantine/adjudicate affected scope |
| Disabled key | No new use requiring enabled status; historical mathematical verification remains separate |
| Verification/status unavailable or lifecycle ambiguous | No qualified result; preserve strongest existing UNKNOWN/recovery boundary |
| Ambiguous KMS signing result | Authentication unconfirmed; preserve evidence; no automatic signing resubmission |
| Custody failure after known database decision | Preserve known decision/evidence gap; no confirmed success and no protected-effect replay |

REPLAY_ON_AUTHENTICATION_UNCERTAINTY = FORBIDDEN

SDK, transport, middleware, credential-refresh, job-runner or application behavior MUST NOT automatically resubmit an ambiguously entered signing request. A different signature, key, receipt identity or request identity is not an authorized workaround. Read-only observation within separately permitted scope cannot reconstruct lost dispatch permission, clear UNKNOWN or authorize a second protected effect. Stronger already-reached uncertainty survives a later definite evidence rejection.

## 12. Rejected and non-selected alternatives

| Alternative | Disposition |
|---|---|
| KMS_SIGNATURE_ONLY | INSUFFICIENT_WITHOUT_INDEPENDENT_AUTHORITY_BINDING |
| DEDICATED_SOFTWARE_SIGNING_KEY | VIABLE_NOT_SELECTED |
| AWS_NATIVE_EVIDENCE_ONLY | SUPPORTING_NOT_COMPLETE_COMMON_PROFILE |
| HMAC | TECHNICALLY_SEPARABLE_ONLINE_NOT_SELECTED_FOR_COMMON_DURABLE_PROFILE |
| TLS_ONLY | INSUFFICIENT |
| CMS_NON_RFC3161 | UNNECESSARY_NOT_SELECTED |
| RFC8785_JCS | NOT_REQUIRED_NOT_SELECTED |

CMS processing required by RFC3161 remains unchanged. Provider-native records may support provenance but do not replace this selected detached-binding profile or independent authority evidence.

## 13. Implementation impact and future resource boundary

FROZEN_IMPLEMENTATION_CONTRACT_CHANGE_REQUIRED = NO

NEW_PRODUCTION_FILE_REQUIRED = NO

NEW_TEST_FILE_REQUIRED = NO

NEW_JOUS_SERVICE_REQUIRED = NO

NEW_MANAGED_RESOURCE_CLASS_REQUIRED = YES

The new managed-resource class is AWS KMS asymmetric customer-managed signing keys. This selection does not authorize their creation. The profile MUST fit the already-frozen future implementation and test boundary; no new production/test path, Jous service, frozen seam change or serializer change is selected.

## 14. Remaining downstream work

The following remain separately reviewed/authorized downstream work, not effects or implementation permission granted by this artifact:

- Implementation details and complete role-schema/codec mapping.
- Dependency/build pinning and positive/negative conformance fixtures.
- AWS account/Region/key selection and IAM/signing-right definitions.
- Explicit secure credential carriers and key creation.
- Resource qualification and public-key/adoption evidence.
- Lifecycle/status and compromise-handling qualification.
- Decision-to-receipt correspondence and custody qualification.
- Operational adoption and runtime receipt creation.

The frozen implementation authority DAG remains intact. Selection-record review/publication does not skip bounded implementation authorization, offline certification, independent implementation review, resource establishment, managed qualification, independent adoption or operational gates. No actual account/key identity or trust bootstrap is inferred from this candidate.

## 15. Source and rationale notes

Public AWS documentation was consulted without account or resource access. These notes support technology properties; Jous authority and no-replay requirements above are normative constraints rather than claims that AWS enforces Jous semantics.

- [AWS KMS key-spec reference](https://docs.aws.amazon.com/kms/latest/developerguide/symm-asymm-choose-key-spec.html) documents RSA_3072 signing support and SHA-256 PSS with MGF1-SHA256 and a 256-bit salt. A 3072-bit RSA signature occupies 384 octets.
- [Sign API](https://docs.aws.amazon.com/kms/latest/APIReference/API_Sign.html) documents SIGN_VERIFY keys, DIGEST input, external public-key verification and absence of an intrinsic signature timestamp. Jous supplies exactly the SHA256 body digest and does not treat signature generation as trusted time.
- [GetPublicKey API](https://docs.aws.amazon.com/kms/latest/APIReference/API_GetPublicKey.html) documents DER SubjectPublicKeyInfo, key ARN, usage and supported algorithms. Retain the exact DER bytes and authenticated metadata; fingerprint DER rather than a PEM/base64 rendering.
- [Key rotation](https://docs.aws.amazon.com/kms/latest/developerguide/rotate-keys.html) distinguishes asymmetric replacement/manual rotation from automatic/on-demand material rotation. This profile requires a new key and authority binding for replacement.
- [Downloading public keys](https://docs.aws.amazon.com/kms/latest/developerguide/download-public-key.html) and [deleting keys](https://docs.aws.amazon.com/kms/latest/developerguide/deleting-keys.html) explain external public-key use and deletion of KMS material/metadata. Continued offline mathematical verification with already-retained public material follows from external verification; it does not prove enabled status, historical authorization or acceptable post-compromise reliance.

## 16. Authority and no-effect boundary

This document is an offline normative selection candidate. It closes technology/profile selection only after independent review and repository publication. It does not authorize implementation, dependency installation, AWS access, KMS key creation, IAM changes, credentials, managed-resource creation, managed qualification, provider operational adoption, register creation, preparation, genesis, checkpoint publication, activation CAS, fixture provisioning, CANARY, runtime activation or public traffic.

No existing tracked file is modified. No staging, commit, push, test execution, resource/account access or credential acquisition is authorized by this drafting gate. Normal public documentation research is not AWS account/resource access.

## 17. Candidate declarations

ARTIFACT_STATUS = OFFLINE NORMATIVE SELECTION RECORD ? NOT APPROVED FOR IMPLEMENTATION ? NOT OPERATIONALLY ADOPTED

PROFILE_ID = JOUS_NON_RFC3161_RECEIPT_BINDING_V1

TECHNOLOGY_SELECTION_CANDIDATE = REFINED_CANDIDATE_B

INDEPENDENT_REVIEW_REQUIRED = YES

REPOSITORY_PUBLICATION_REQUIRED_TO_CLOSE_SELECTION = YES

IMPLEMENTATION_AUTHORIZED = NO

OPERATIONALLY_ADOPTED = NO

JCS_REQUIRED = NO

JCS_SELECTED = NO

KMS_SIGNATURE_IS_TRUSTED_TIME = NO

SIGNED_TIMESTAMP_IS_TRUSTED_TIME = NO_UNLESS_SEPARATELY_QUALIFIED

REPLAY_ON_AUTHENTICATION_UNCERTAINTY = FORBIDDEN

FROZEN_IMPLEMENTATION_CONTRACT_CHANGE_REQUIRED = NO

NEW_PRODUCTION_FILE_REQUIRED = NO

NEW_TEST_FILE_REQUIRED = NO

NEW_JOUS_SERVICE_REQUIRED = NO

NEW_MANAGED_RESOURCE_CLASS_REQUIRED = YES

TESTS_EXECUTED = 0

AWS_ACCESS = NO

KMS_KEYS_CREATED = 0

IAM_CHANGES = 0

DIGICERT_ACCESS = NO

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
