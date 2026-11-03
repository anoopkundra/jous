# JOUS.CORE.1A IL6 authority serialization profile — version 1

Status: OFFLINE NORMATIVE AUTHORITY CANDIDATE FOR INDEPENDENT REVIEW —
NOT ADOPTED — NOT APPROVED FOR IMPLEMENTATION — NOT OPERATIONALLY ADOPTED.

## 1. Scope and precedence

This NEW serialization authority candidate addresses only IL6-IMPL-REVIEW-01.
It defines canonical external evidence/package representations, not a new lifecycle,
register, trust provider or authority mechanism. Vectors certify the prose and
schemas below; they are not the sole definition of encoding. No implementation,
register creation, genesis, activation, managed access, provisioning, CANARY,
deployment, runtime activation or public traffic is authorized.

Derivation baseline HEAD/local origin/main:
`174a0871552761dddc2cd0a7f83ac74e4c549712`, divergence 0/0.
Frozen controlling authorities under `docs/decisions/` remain unchanged:

| Document | Git blob |
| --- | --- |
| JOUS.CORE.1A.il6-authoritative-register-activation-contract.md | ede5e09bf4bdb8461ac92d27da5ec9cb5683f21b |
| JOUS.CORE.1A.genesis-checkpoint-reference-amendment.md | d5136bc32ea8f62c04d09e65121edc00c0387d35 |
| JOUS.CORE.1A.runtime-canary-fixture-provisioning-bootstrap-amendment.md | b2af73ae4788e76f4fd591ac267d40230d70026b |
| JOUS.CORE.1A.runtime-canary-fixture-provisioning-contract.md | 1d84df662ab0e7245f59842039789a55c1df25c4 |

Existing IL.4 STATE/framing and genesis CHECKPOINT authority control their binary
objects. IL.5 normal references, replacement references, time, recovery and
provisioning authority are not reinterpreted. This profile adds no binary protocol
tag, field, COMMAND, permit, event type, database table or second authority store.

## 2. Exhaustive object classification

Each instance belongs to exactly one category. A scalar naming an object is not
that object's bytes. Nested value groups have no independent digest or identity.

| Object | Category | Boundary |
| --- | --- | --- |
| Initial STATE S0 | EXISTING_FROZEN_CANONICAL | Existing StateContext/StateProjection and state_bytes/state_digest under approved generation representation |
| Genesis CHECKPOINT C0 | EXISTING_FROZEN_CANONICAL | Existing eleven-field version-1/tag-7 framing and frozen genesis specialization |
| Creation evidence C | OPAQUE_EXTERNAL_EVIDENCE | Raw immutable externally qualified evidence, not G |
| Ceremony evidence E | NEW_CANONICAL_OBJECT | Exact schema and JSON profile below |
| Ceremony reference G | STABLE_SCALAR_REFERENCE | Exact content-addressed E identity |
| Activation package P | NEW_CANONICAL_OBJECT | Exact schema and JSON profile below |
| Independent approval Q | OPAQUE_EXTERNAL_EVIDENCE | One definitive choice; no new canonical APPROVAL representation |
| Approval identifier J | STABLE_SCALAR_REFERENCE | Stable pending approval slot ID, not Q/hash |
| Activation command identifier K | STABLE_SCALAR_REFERENCE | Stable external original attempt ID, not J/G/COMMAND/permit |
| Activation-command payload | NEW_CANONICAL_OBJECT | Exact downstream-of-Q schema below |
| Qualification, protected publication/result, activation/readback and independent result-verification records | OPAQUE_EXTERNAL_EVIDENCE | Closed role-specific authenticated views in section 7 |
| Clock-profile record, storage-location/ownership/exclusion records, operator/process qualification records | OPAQUE_EXTERNAL_EVIDENCE | Exact raw bytes and qualified claims, no local record serializer |
| Authority documents and their adoption records | OPAQUE_EXTERNAL_EVIDENCE | Exact approved raw bytes and qualified adoption; Git alone is not adoption |
| register_id, activation_id, generation/schema integers, command/approval IDs, storage/volume/host IDs, clock-profile/source IDs, operator/issuer/opener/process/domain IDs, environment/project-scope IDs | STABLE_SCALAR_REFERENCE | Existing scalar meanings and external identity qualification |
| Authority-document references/hashes, other reference pairs R and digest scalars | STABLE_SCALAR_REFERENCE | Inline typed ID/H group; never independently hashed as a protocol object |

Every R slot resolves to its named role and category. Unknown roles reject; an
implementation cannot later elect a canonical encoding for an opaque record.

## 3. Exactly one canonical family

E, P and ActivationPayload use ordered compact ASCII JSON, encoded UTF-8 without
BOM. Exactly one top-level object, no surrounding whitespace, indentation,
separator spaces, line endings or trailing LF. Markdown fences/newlines used to
display vectors do NOT enter preimages. Member order, including every nested
group, is exactly table order in section 5. No sort-by-map-iteration choice.

All fields are required, once only. No unknown/duplicate keys, omitted members,
nulls, arrays or arbitrary maps. Named nested groups are fixed objects, not new
independently identified canonical objects. No hidden defaults or extension bags.

| Type | Unique representation and validation |
| --- | --- |
| ID | Existing nonblank Unicode scalar string, 1–255 UTF-8 bytes before JSON escaping; exact approved value, no trimming/folding/normalization/URI aliases |
| H | JSON string of exactly 64 lowercase ASCII hexadecimal digits representing 32 SHA256 bytes; no 0x, separators, spaces or base64 |
| T | JSON decimal integer in [-2^63, 2^63-1], UTC microseconds; no plus, fraction, exponent, leading zeros or negative zero |
| ONE / ZERO | Exact JSON integer 1 / 0; boolean is not integer |
| TRUE / FALSE | Exact JSON true / false, never integer or string |
| literal X | Exact case-sensitive JSON string X |
| R / named group | Exact nested object with fields/types/order below |

String encoding is closed. Surround with ASCII double quotes. Escape quote as
`\"`, backslash as `\\`, and U+0008/0009/000A/000C/000D as `\b/\t/\n/\f/\r`
respectively. All other U+0000..001F and all scalars above U+007E use lowercase
`\u` followed by four lowercase hex digits; above U+FFFF use the unique UTF-16
high/low surrogate pair as two such escapes. Other U+0020..007E appear literally,
including slash. DEL is escaped. Reject invalid UTF-8 and lone surrogates; a
valid escaped surrogate pair represents one Unicode scalar. No literal non-ASCII,
uppercase escape hex, unnecessary ASCII escape or escaped slash is canonical.

No Unicode normalization occurs. Distinct legal scalar sequences remain distinct
identities; a normalized string is not an alternative spelling of approved bytes.
IDs may contain meaningful whitespace under frozen rules; it is never trimmed.
Object-boundary whitespace is forbidden. No byte-string fields exist in new objects:
raw/canonical bytes are resolved through R, never embedded using alternate codecs.

A receiver MUST validate syntax, field order/schema/types and cross-bindings, then
require exact equality with unique re-encoding of the decoded semantic value.
This rejects noncanonical input; it does not normalize and accept a new identity.
NaN/Infinity/coercions reject. No arbitrary size cap is added to frozen STATE or
retained history; resource exhaustion fails closed, never hashes partial input.

## 4. Domains, digests and scalar identities

SHA256 hashes the complete canonical JSON bytes. Domain separation is INSIDE the
preimage via mandatory object_type/profile_version/purpose; no extra invisible
prefix, signature wrapper stripping, newline or alternative preimage.

| Object | object_type | profile_version | purpose | Derived identity |
| --- | --- | --- | --- | --- |
| E | JOUS.CORE.1A.IL6.E | 1 | GENESIS_V1 | genesis-ceremony:sha256:<hE> |
| P | JOUS.CORE.1A.IL6.P | 1 | GENESIS | il6-package:sha256:<hP> |
| ActivationPayload | JOUS.CORE.1A.IL6.ACTIVATION_PAYLOAD | 1 | ABSENT_TO_GENERATION_ONE | il6-activation-payload:sha256:<hA> |

Digest rendering is lowercase 64 hex. P's ID is a content-addressed package
reference, not a second package authority. Payload's ID is diagnostic only, not
a new operation key; K remains the stable external command identity. Derived
identities/hashes never occur in their own preimages.

G accepts ONLY the exact ASCII prefix `genesis-ceremony:sha256:` and exactly 64
lowercase hex digits. No spaces, uppercase, URI aliases, padding, fragments or
suffixes. Its logical unchanged EvidenceReference is (G, hE bytes). Verify suffix
equals SHA256(resolved complete E). The CHECKPOINT position remains UTF8(G) with
existing outer framing; no nested JSON/R/normal N bundle is inserted there.

## 5. Closed ordered field schemas

Every row is REQUIRED. Each ordered field sequence below is exhaustive; types
and literals are section 3's unique representations. Where several fields share
one row, their comma-separated order is normative and every field has the shown
type/requirement/source. Validation is type/constant plus sections 6–7 agreement.
I denotes frozen IL6, G the genesis-reference amendment, F existing storage/time/
STATE authority, S this proposed serialization closure. No optionality is implied.

### Inline groups

| Group | Exact ordered fields and types | REQUIRED | Validation / source |
| --- | --- | --- | --- |
| R | identity:ID, sha256:H | YES, each | Qualified exact role/ref; G/I/S |
| SchemaBinding | version:ONE, reference:R | YES, each | Exact frozen schema identity; I §3/5 |
| HostBinding | identity:ID, qualification:R | YES, each | Protected host-bound identity; I §3/5/8 |
| StorageBinding | identity:ID, location:R, ownership:R, exclusion:R, qualification:R | YES, each | Exact physical/storage/access bindings; I §5/6 |
| ScopeBinding | environment:ID, project_scope:ID, qualification:R | YES, each | Approved logical scope; I §3/5 |
| ActorBinding | genesis_operator:ID, preparation_operator:ID, issuer:ID, opener:ID, process:ID, authorization:R, fencing:R, qualification:R | YES, each | Exact role/ownership facts; I §5/8 |
| RepresentationBinding | identity:ID, authority:R | YES, each | Immutable generation selection; I §3/5/9, F STATE |
| ClockBinding | profile:R, source:ID, qualification:R, sample:R, monotonic_domain:ID | YES, each | Qualified profile/sample/domain; I §5/7, F time |
| StorageProfile | journal_mode:literal DELETE, synchronous:literal EXTRA, foreign_keys:TRUE, busy_timeout:ZERO, locking_mode:literal NORMAL, read_uncommitted:FALSE | YES, each | Frozen constants; I §6, F storage |
| SoftwareBinding | python_build:ID, driver_build:ID, sqlite_version:ID, sqlite_source_id:ID, package:R, qualification:R, storage_profile:StorageProfile | YES, each | Exact builds/source/qualification; I §5/6 |
| ProtectedAuthorities | activation:R, checkpoint:R, absence_requirements:R, history_retention:R, readback_requirements:R, result_verification_requirements:R | YES, each | Qualified protected authority/gates; I §5/10–12 |
| Requirements | durability:R, backup_restore:R, evidence_retention:R, initial_state_verification:R, approval_applicability:R | YES, each | Exact requirements/conformance; I §5/6/10–12 |
| Authorization | reference:R, valid_from_us:T, valid_until_us:T | YES, each | Exact scope; valid_from <= valid_until; I §4/5/10 |
| ExpectedCounts | metadata:ONE, artifacts:ZERO, reservations:ZERO, claims:ZERO, commands:ZERO, events:ZERO | YES, each | Exact initial state; I §9 |

AuthorityBindings is exactly the following R members in order, ALL required:
fixture_plan, bootstrap_amendment, provisioning_contract, implementation_design,
il6_contract, genesis_reference_amendment, serialization_profile, il4_protocol,
state_framing, il5_normal_checkpoint, replacement_generation, design_adoption_evidence.
Each must qualify the exact named authority/adoption role (I §1/5; S domain binding).

### E — complete ceremony evidence schema

| FIELD (order) | TYPE / canonical representation | REQUIRED | Validation / source |
| --- | --- | --- | --- |
| object_type | literal JOUS.CORE.1A.IL6.E | YES | S domain |
| profile_version | ONE | YES | S version |
| purpose | literal GENESIS_V1 | YES | G §3 |
| register_id | ID | YES | G §3, I §3 |
| schema | SchemaBinding | YES | G §3, I §5 |
| issuer_generation | ONE | YES | G genesis-only |
| activation_id | ID | YES | G §3 |
| host | HostBinding | YES | G §3 |
| storage | StorageBinding | YES | G §3 |
| scope | ScopeBinding | YES | G §3 |
| actors | ActorBinding | YES | I §5/8, G bindings |
| authorities | AuthorityBindings | YES | G §3, I §5 |
| representation | RepresentationBinding | YES | G §3, frozen STATE |
| creation_evidence | R | YES | G §4, exact C |
| clock | ClockBinding | YES | G §3, I §7 |
| creation_utc_us | T | YES | G §3, fixed qualified UTC |
| initial_state | R | YES | G §3, exact canonical S0 |
| event_sequence | ZERO | YES | Frozen genesis |
| event_digest | H | YES | Published genesis event anchor |
| predecessor_generation | ZERO | YES | Frozen genesis |
| predecessor_checkpoint_digest | H | YES | Exactly 64 zero hex digits |
| activation_command_id | ID | YES | G §6, stable K |
| approval_id | ID | YES | G §5, stable pending J |

### P — complete activation-package schema

| FIELD (order) | TYPE / canonical representation | REQUIRED | Validation / source |
| --- | --- | --- | --- |
| object_type | literal JOUS.CORE.1A.IL6.P | YES | S domain |
| profile_version | ONE | YES | S version |
| purpose | literal GENESIS | YES | I §5 |
| register_id | ID | YES | Same E register |
| issuer_generation | ONE | YES | Same E generation |
| activation_id | ID | YES | Same E activation |
| ceremony_evidence | R | YES | identity=G, digest=hE; complete E resolved |
| creation_evidence | R | YES | Same E.C |
| initial_state | R | YES | Same E.S0 |
| checkpoint | R | YES | Complete frozen C0/hash |
| activation_command_id | ID | YES | Same E.K, I §5 |
| approval_id | ID | YES | Same E.J, not Q/hash |
| software | SoftwareBinding | YES | I §5/6 |
| protected_authorities | ProtectedAuthorities | YES | I §5/10–12 |
| requirements | Requirements | YES | I §5/6/10–12 |
| authorization | Authorization | YES | Independently approved execution scope, not Q |
| expected_counts | ExpectedCounts | YES | I §9 |
| recovery_required | FALSE | YES | I §9 |

### ActivationPayload — complete downstream command-payload schema

| FIELD (order) | TYPE / canonical representation | REQUIRED | Validation / source |
| --- | --- | --- | --- |
| object_type | literal JOUS.CORE.1A.IL6.ACTIVATION_PAYLOAD | YES | S domain |
| profile_version | ONE | YES | S version |
| purpose | literal ABSENT_TO_GENERATION_ONE | YES | G §6 |
| activation_command_id | ID | YES | Same P/E.K |
| expected_presence | literal AUTHORITATIVE_ABSENT | YES | G §6 |
| predecessor_generation | ZERO | YES | G §6 |
| register_id | ID | YES | Same P/E register |
| issuer_generation | ONE | YES | Same P/E generation |
| activation_id | ID | YES | Same P/E activation |
| host_identity | ID | YES | Same E.host.identity |
| package | R | YES | Content-addressed P ID/hP |
| checkpoint | R | YES | Same P.C0 |
| approval | R | YES | Exact J and externally established hQ |

## 6. Cross-bindings and preimage exclusions

S0 remains the COMPLETE existing canonical STATE, not another JSON projection.
Its R must resolve to exact metadata and empty initial collections. Check its
four metadata authority pins against E.authorities fixture_plan/bootstrap_amendment/
provisioning_contract/implementation_design; schema=1, register/generation/activation
match E, last_valid_utc=creation_utc_us, recovery_required=0. Check all initial table
counts separately as frozen. Metadata is not duplicated under a competing codec.
E.event_digest is SHA256(ASCII JOUS-FIXTURE-LEASE-GENESIS-V1).

Representation selection remains exactly the approved generation-bound identity
and authority; this profile selects no production representation. Scope IDs are
approved logical bindings, not managed URLs. Inapplicability, if permitted by IL6,
requires explicit independent justification bound by scope qualification; all
fields remain present. No magic NOT_APPLICABLE string or null supplies authority.

E binds only upstream qualified evidence and exact initial state. E must exclude
G/hE, checkpoint/hash, P/hash, Q/hash, activation payload/hash and publication/CAS
outcomes. Its source documents include this profile only once independently
adopted: a future E referencing an adopted profile is not a profile self-hash cycle.
No opaque upstream record may hide a downstream dependency; qualification must
establish that preimage separation.

P binds all E fields through mandatory complete qualified resolution of E and
every nested R. Thus storage/host/scope/clock/actors, schema/version, authority pins,
creation/time/STATE are package-bound, not optional external mutable inputs.
P's repeated bindings must agree exactly with E. K, J, C.identity and G remain
distinct. P.checkpoint must resolve to complete C0 with register/generation/activation
and S0 hash matching E; revision/event sequence 0, fixed UTC, published genesis
event anchor, zero predecessor, G in position 10 and present J in position 11.
No normal N bundle, fake COMMAND/permit or new framing. P.initial counts and false
recovery flag do not prove ACTIVE service mode.

P excludes Q/hash, its own final digest/derived ID, activation payload/hash and
outcomes. It contains only pending J and stable K, not proof of approval. All
authority/adoption, software/build, storage/durability/backup/retention and verification
requirements must qualify under their immutable refs. No mutable policy can waive
frozen requirements. P.authorization binds upstream authorization scope/constraints
and validity, not a downstream execution authorization referring to final P/Q.
Its referenced record cannot contain final P/hash or Q/hash. Later actual execution
authorization may bind final P/Q, but is separate from P's preimage. This preserves
the frozen requirement for separate execution authorization without a hash cycle.
Authorization validity uses the existing time semantics;
stricter continuation/freshness/uncertainty rules remain independent gates.

Only AFTER independent qualified Q may ActivationPayload be constructed. Its
package R is (il6-package:sha256:<hP>, hP), approval R is (J, hQ), and all repeated
P/E/C0/K/host bindings agree. Q must approve the exact P/C0/host/identities under
section 7. Payload bytes/hash are downstream attempt evidence, never P inputs or
part of P's hash. These bytes do not establish actual ABSENT, publication or CAS.

## 7. Opaque external evidence — one closed boundary

C and Q are DEFINITIVELY opaque, not choices to be made by an implementation.
All opaque roles share this exact contract:

- IDs use frozen ID syntax and immutable/non-reused external allocation. SHA256
  identifies COMPLETE RAW external bytes, rendered as H. No unspecified parsed
  projection, JSON map, display name or location is hashed to create identity.
- A separately qualified external issuing/verification authority supplies the
  authenticated immutable ID/digest, raw retention/resolution and a typed verified
  view bound to that SAME ref, role and exact context. No provider/signature/
  credential/wire-format choice is made here. Ordinary constructors prove nothing.
- Raw bytes MUST be retained and independently resolvable under existing retention
  rules. IL6 does not parse or reserialize the external record. It checks exact
  typed claims and qualified authentication/binding; if raw bytes are supplied it
  may verify SHA256(raw)==expected digest, never infer approval from hash equality.
- External raw fields not listed in the role's closed view are uninterpreted and
  cannot influence IL6. Locally validate ID/H, role, context, exact expected claims,
  independence/validity/revocation and qualification provenance where applicable.
  A self-reported callback boolean or unqualified projection is insufficient.
- Missing/unavailable/malformed/contradictory/unqualified evidence rejects. No
  reserialization, normalization, guessing, alternative authority, collision adoption,
  refresh-to-accept or missing-proof fallback. Current-state/time claims require
  fresh qualification; immutable historical refs are not automatically current.

The following role-specific verified views are exhaustive in authority-bearing
claims. Every listed claim is mandatory; IDs/H/references/UTC/booleans use existing
types, not an extensible map. Additional raw bytes do not expand the local view.

| Opaque class / R role | Conceptual supplier and exact required verified claims |
| --- | --- |
| C | Qualified preparation/creation authority: C ref; GENESIS_V1; register/schema/generation/activation/host/storage/scope; preparation operator and authorization; fixed UTC/source/sample and initial metadata inputs; known actual preparation facts/evidence; no downstream E/G/C0/P/Q/payload/outcome in preimage. No claim of creation before it happened. |
| Q | Independent approval authority: exact J/hQ; APPROVED GENESIS; P identity/hP and C0 identity/hash; register/generation/activation/host/K; approver and requester/issuer identities and independence proof; applicable authority/allowed transition/authorization; valid_from/valid_until; qualified current NOT_REVOKED status/evidence/time. Reject PENDING, ambiguous J, self-approval, unknown revocation or different bindings. |
| Schema | Approved schema authority: exact schema bytes/hash/version 1 and six-table identity; same schema as S0/storage. |
| Host | Protected host authority: exact approved host ID, host-bound authentication, permitted service/process and storage relation; not hostname text. |
| Storage location | Approved storage authority: exact canonical absolute database/staging/journal/parent paths; host/volume/native instance identity; approved preparation/final-instance relation; no redirection/unapproved relocation. Path qualification uses frozen platform rules, never JSON normalization. |
| Storage ownership/exclusion/qualification | Storage/OS authority: account/effective access boundary, single-writer/process ownership, native identity continuity and supported locking/atomicity/flush/VFS/durability evidence for exact host/location; no SQLite-lock-only authority. |
| Scope | Scope authority: environment/project-scope IDs, exact governance/target relation, explicit approved justification for any inapplicability; no managed-access permission. |
| Actor authorization/fencing/qualification | Qualified identity/authorization authority: exact genesis/preparation operator, issuer/opener/process and host/generation, role/action/validity/exclusive ownership/fencing/access evidence; OS access alone is insufficient. |
| Clock profile/sample/qualification | Time authority: exact profile/source, authenticated sample/profile/qualification refs, process/monotonic domain, complete conservative interval/error/age/anomaly limits and fixed creation-UTC consistency, under frozen qualified-time model. No new clock-profile codec. |
| Authority documents/adoption | Independent design authority: exact raw document/version/hash, named role, applicable adoption scope and bindings for every AuthorityBindings slot; historical hashes preserved, publication not operational adoption. |
| Representation | Existing generation/STATE authority: exact representation/field/framing refs and immutable register/generation/activation selection; no sniffing/size/fallback. |
| Software/runtime | Runtime/storage authority: exact Python/driver/SQLite build/source/package, frozen settings, approved host/VFS compatibility/durability; no unreviewed upgrade. |
| Protected authorities | Qualified activation/checkpoint authority: exact identities/trust scope, authenticated ABSENT vs UNKNOWN, linearizable expected-state CAS, immutable history/tombstones, retained original K/payload outcomes and checkpoint/readback guarantees. Local files cannot substitute. |
| Requirement refs | Independent requirement/qualification authority: exact durability/backup/retention/initial-state/approval/absence/history/readback/result-verification requirements, applicability to this register/host/attempt, and conformance evidence for the corresponding frozen gate; no waiver of a frozen invariant. |
| Package authorization constraints | Independent authorization authority: upstream register/activation/K/host/operator/action scope and validity constraints; no final P/hash, Q/hash or downstream payload/outcome dependency. P naming this ref is not actual execution authorization. |
| Later execution authorization | Separate independent execution authority: exact approved P/Q/attempt/register/host/operator scope, finite permitted steps and validity. Downstream evidence is not a field/hash input of E or P. |
| Protected checkpoint publication/result | Existing protected checkpoint authority: original operation identity, exact C0/P/Q/host, immutable retention/selection facts under genesis authority and qualified known success/rejection/unknown. Timeout is UNKNOWN. |
| Activation outcome/readback | Existing activation authority: original K/payload hash, exact P/Q/C0/register/generation/activation/host and current/history/tombstone/CAS result; UNKNOWN/unexpected authority fences, no new K/CAS. |
| Independent result verification | Separate independent verifier: exact original execution/readback/package/checkpoint/host/storage identities and qualified adjudication; no self-verification or authority from record construction. |

C's raw digest is bound in E/P; it is not itself G. Q's complete digest-bearing
reference exists only AFTER Q and is bound by payload/activation approval evidence.
Pending J is not a reference to nonexistent approval bytes. Upstream R records must
be available/qualified at their construction stage; downstream execution/readback
evidence is never retrofitted into C/E/P.
This stage rule applies transitively to EVERY upstream opaque R dependency: its
bytes/claims cannot require the later containing E/P/C0/hash, Q/hash, payload or
outcome. Requirements describe future obligations rather than falsely certifying
a future result. Later conformance observations use separate qualified evidence.

## 8. Null, rejection and versioning

Every new-object/group field is required; omission/null/empty placeholders are
never alternatives. Exactly one representation per semantic value. Reject malformed
JSON/UTF-8, duplicate/unknown/reordered fields, wrong version/domain/constants/types,
invalid scalar Unicode, noncanonical escape/normalization-as-identity, out-of-range
integers, uppercase/malformed hashes, leading/trailing whitespace/BOM/bytes, negative
zero and every otherwise-equivalent noncanonical representation. No permissive
normalization after receipt. Distinct valid Unicode strings remain distinct IDs.

Profile version is integer 1 only. No automatic upgrade, fallback, negotiation or
normal/replacement-profile adoption. Future encoding/field/type/domain changes
require separately approved normative authority; old bytes are not reinterpreted.

## 9. Synthetic encoding vectors

The following vectors are encoding arithmetic only, not operational evidence or
approval. Each one-line JSON block supplies semantic field values and EXACT ASCII
canonical bytes; exclude its fences and display line endings. Support STATE and
CHECKPOINT bytes are existing binary forms shown in hex, decoded exactly once.
No product module or test is invoked in deriving these vectors.

Ordinary synthetic opaque R digests are SHA256(ASCII synthetic-external: followed
by the exact R.identity). C/Q/S0/C0 use explicit support bytes below. Synthetic
qualifiers supply matching typed claims only for illustration; these records do
not authenticate themselves. The semantic values are exactly the typed JSON values
shown; the byte tables and field schemas agree without omitted/default values.

### Support C (ASCII)

~~~text
synthetic-opaque-creation-C-v1
~~~

BYTES = 30
SHA256 = f4032fbd522138153f61688e05624a9323d215de787c1b18b880df11ffb0085a

### Support S0 (hex)

~~~text
4a4f55532d464958545552452d4c45415345020800000004024a4f55532d464958545552452d4c45415345020c0000000b000000080000000000000001000000080000000000000001000000016700000008000000000000000100000001780000002048542a92246da394e7e4e30a152d320f6bb30507fafa77ae47a69598fb02b618000000204c003f416b43e20828d1215066ba3313b3813e4b977bb9ddfebd798d2c83263d00000020bfc6a1aa0767ebaa00ddb887765564be2dae46e55d8c5c8e517e34e33f23b8a60000002036b3bfdb942db79cbe813b3722eca9967d5955a8f98ea7ddc836b2daca7f2763000000080000000000000000000000080000000000000000030003000300
~~~

BYTES = 269
SHA256 = 947ce86280cf193006381228df327ff7bb68406ef8679d89272824eb0afd8a20

### Support C0 (hex)

~~~text
4a4f55532d464958545552452d4c4541534501070000000b00000001670000000800000000000000010000000178000000080000000000000000000000080000000000000000000000204e6abfbfdec0d3d621faea244e0b3c71b2632b092e6423e4f2f352e65a5d7b6100000020947ce86280cf193006381228df327ff7bb68406ef8679d89272824eb0afd8a200000000800000000000000000000002000000000000000000000000000000000000000000000000000000000000000000000005867656e657369732d636572656d6f6e793a7368613235363a343362306136616563623766333230366131316234356463333462313739616634626335663138353230663838343231663835663235383537623836623331620000000401762d4a
~~~

BYTES = 290
SHA256 = 37bd0a83f97e3cc6405e95d5da7f1235cc923fee1fa3980ba07fc5b2a4f8612f

### Support Q (ASCII)

~~~text
synthetic-opaque-Q-v1|v-J|il6-package:sha256:1e2096c9295e1835934b347093816995ec4583c7c7188712103d67a020589ba1|1e2096c9295e1835934b347093816995ec4583c7c7188712103d67a020589ba1|v-checkpoint|37bd0a83f97e3cc6405e95d5da7f1235cc923fee1fa3980ba07fc5b2a4f8612f
~~~

BYTES = 252
SHA256 = 90a00209de607fb249696799543fab3be3ab87d0ee9776a21a763ecb53810780

S0: register g, generation 1, activation x, metadata singleton/schema 1, four
first authority hashes from E, UTC 0 and recovery 0, three empty STATE-2 collections.
Other initial tables are empty. C0: frozen genesis scalars, that S0 hash, derived G
and present approval ID v-J. C and Q strings are illustrative opaque raw records,
NOT normative external codecs. Q uses J=v-J and a synthetic independent v-approver
view approving exact P/C0/K/host with validity [0,1000000] and current NOT_REVOKED.

### Vector E

~~~json
{"object_type":"JOUS.CORE.1A.IL6.E","profile_version":1,"purpose":"GENESIS_V1","register_id":"g","schema":{"version":1,"reference":{"identity":"v-schema","sha256":"266237955374a43619287755183054041aad84b86ef49cbc3a58b9435e3733b2"}},"issuer_generation":1,"activation_id":"x","host":{"identity":"v-host","qualification":{"identity":"v-host-qualification","sha256":"3d9766b7bad2ca0f5117c7572b5bf50726d68c8e7921ea3afdc3712f4bd27561"}},"storage":{"identity":"v-storage","location":{"identity":"v-storage-location","sha256":"ba0477af47a8c4c3306814de4800fb2f93243a1d55caf49e234f652532c4ebf9"},"ownership":{"identity":"v-storage-ownership","sha256":"be51452798034139f6250251956dd884a3762efff079ca91a3d7010c643c9601"},"exclusion":{"identity":"v-storage-exclusion","sha256":"f8b5c33af86d9660b39b53d88d7a194a4b6650b7c97542e1d5869f8c01b9999d"},"qualification":{"identity":"v-storage-qualification","sha256":"1cc122706e506a43d6e453de131af5ebeb0a4307e3be6ee70e050c2d18c332c4"}},"scope":{"environment":"v-environment","project_scope":"v-project-scope","qualification":{"identity":"v-scope-qualification","sha256":"a1f7001c6b4d91229be010215c494873e613f836afb7353bdc2e1c7b4b68afff"}},"actors":{"genesis_operator":"v-genesis-operator","preparation_operator":"v-preparation-operator","issuer":"v-issuer","opener":"v-opener","process":"v-process","authorization":{"identity":"v-actor-authorization","sha256":"708490a214c04850284a7ccbb3d1222e220000d2a19664c8d6428fc181d3b6d4"},"fencing":{"identity":"v-fencing","sha256":"ce65832b569d6dbfef7d9f8edc49e47cad69480fe05a771dd378d56e28e5e7ad"},"qualification":{"identity":"v-actor-qualification","sha256":"e9774eab48e8bdab0c52efd3e36823b5ee0594849285452bfd197c4bc31636aa"}},"authorities":{"fixture_plan":{"identity":"v-fixture-plan","sha256":"48542a92246da394e7e4e30a152d320f6bb30507fafa77ae47a69598fb02b618"},"bootstrap_amendment":{"identity":"v-bootstrap-amendment","sha256":"4c003f416b43e20828d1215066ba3313b3813e4b977bb9ddfebd798d2c83263d"},"provisioning_contract":{"identity":"v-provisioning-contract","sha256":"bfc6a1aa0767ebaa00ddb887765564be2dae46e55d8c5c8e517e34e33f23b8a6"},"implementation_design":{"identity":"v-implementation-design","sha256":"36b3bfdb942db79cbe813b3722eca9967d5955a8f98ea7ddc836b2daca7f2763"},"il6_contract":{"identity":"v-il6-contract","sha256":"b91a17d4effd38afeb6441110496e4216016c46bab153fb91b90f477a8d9770a"},"genesis_reference_amendment":{"identity":"v-genesis-reference-amendment","sha256":"902dd6d7368bd574277b7fde0fa73dd29ad31e488cee589ee3fac041a8531fdf"},"serialization_profile":{"identity":"v-serialization-profile","sha256":"55e4c4dde7c339559f4b58bde2c274d03d4ca2f1ab8850397c7d4ea4b139c039"},"il4_protocol":{"identity":"v-il4-protocol","sha256":"a8388defd6a8f7a40d5fb28c62286b297f908853301f6598168260dbcbdf827b"},"state_framing":{"identity":"v-state-framing","sha256":"e12518d4f02e676d9b347ccca0b826bfc6b5f2f9d06169509153c4848fb336f8"},"il5_normal_checkpoint":{"identity":"v-il5-normal-checkpoint","sha256":"9cc1534e27055488a5f43bcaed78bb04f4f211333509ec814b0d72e902748c7f"},"replacement_generation":{"identity":"v-replacement-generation","sha256":"d47b8e5464f1772c44c2641fee6cdc1b9b552a8459e2fa228479dd16b6a806e7"},"design_adoption_evidence":{"identity":"v-design-adoption-evidence","sha256":"b4da29a59654f2cc3ad71f5b73db5acf209d95f0ff342abcc2a05068760e12b7"}},"representation":{"identity":"JOUS_CORE1A_STATE_REPRESENTATION_2","authority":{"identity":"v-state-framing","sha256":"e12518d4f02e676d9b347ccca0b826bfc6b5f2f9d06169509153c4848fb336f8"}},"creation_evidence":{"identity":"v-creation","sha256":"f4032fbd522138153f61688e05624a9323d215de787c1b18b880df11ffb0085a"},"clock":{"profile":{"identity":"v-clock-profile","sha256":"2a0bf128d887b29ad458deed3f69553c61de08428ffe70dca639c3f42c0d09e3"},"source":"v-clock-source","qualification":{"identity":"v-clock-qualification","sha256":"1b4c52387ef4f970923b407482457481e3fba1e4fce6fe66a9c76b61b847cdba"},"sample":{"identity":"v-clock-sample","sha256":"afb71f53919522bdc03395f6d2988c4cb19bdabb651d3848e50c6e77db0c80a6"},"monotonic_domain":"v-monotonic-domain"},"creation_utc_us":0,"initial_state":{"identity":"v-state","sha256":"947ce86280cf193006381228df327ff7bb68406ef8679d89272824eb0afd8a20"},"event_sequence":0,"event_digest":"4e6abfbfdec0d3d621faea244e0b3c71b2632b092e6423e4f2f352e65a5d7b61","predecessor_generation":0,"predecessor_checkpoint_digest":"0000000000000000000000000000000000000000000000000000000000000000","activation_command_id":"v-K","approval_id":"v-J"}
~~~

BYTES = 4484
SHA256 = 43b0a6aecb7f3206a11b45dc34b179af4bc5f18520f88421f85f25857b86b31b
RENDERED_ID = genesis-ceremony:sha256:43b0a6aecb7f3206a11b45dc34b179af4bc5f18520f88421f85f25857b86b31b

### Vector P

~~~json
{"object_type":"JOUS.CORE.1A.IL6.P","profile_version":1,"purpose":"GENESIS","register_id":"g","issuer_generation":1,"activation_id":"x","ceremony_evidence":{"identity":"genesis-ceremony:sha256:43b0a6aecb7f3206a11b45dc34b179af4bc5f18520f88421f85f25857b86b31b","sha256":"43b0a6aecb7f3206a11b45dc34b179af4bc5f18520f88421f85f25857b86b31b"},"creation_evidence":{"identity":"v-creation","sha256":"f4032fbd522138153f61688e05624a9323d215de787c1b18b880df11ffb0085a"},"initial_state":{"identity":"v-state","sha256":"947ce86280cf193006381228df327ff7bb68406ef8679d89272824eb0afd8a20"},"checkpoint":{"identity":"v-checkpoint","sha256":"37bd0a83f97e3cc6405e95d5da7f1235cc923fee1fa3980ba07fc5b2a4f8612f"},"activation_command_id":"v-K","approval_id":"v-J","software":{"python_build":"v-python-build","driver_build":"v-driver-build","sqlite_version":"3.45.0","sqlite_source_id":"v-sqlite-source","package":{"identity":"v-software-package","sha256":"8f300a1c090a976afb0fb92c202357a54922b1dd6081fbd12fa1e434f72b2976"},"qualification":{"identity":"v-runtime-qualification","sha256":"ad0c0cbeae5c87c1942c5613b2ec14b8e7a836554cbde3aa764d3e3c5ee7b213"},"storage_profile":{"journal_mode":"DELETE","synchronous":"EXTRA","foreign_keys":true,"busy_timeout":0,"locking_mode":"NORMAL","read_uncommitted":false}},"protected_authorities":{"activation":{"identity":"v-activation-authority","sha256":"b31e19ca7f740f953fe2cf0a5a422fb9ab278a68ff6a9887a2a4fa456e8a0481"},"checkpoint":{"identity":"v-checkpoint-authority","sha256":"f5e270619d40fa8a629f7bed6af59285db2d2e1a47e35c51596810aef1d14414"},"absence_requirements":{"identity":"v-absence-requirements","sha256":"a664186da90bd41c5726db489b4f380906c16d2c8ad8d1ad4b78707403bd5914"},"history_retention":{"identity":"v-history-retention","sha256":"1c59f913d7c8e1f014b774828fe035bfbdc207a769ddb1e35ea3bee51219a348"},"readback_requirements":{"identity":"v-readback-requirements","sha256":"e811d485d9835372905445eb69e41dbff657bbcdce9ed1a713878bbab8c6ab91"},"result_verification_requirements":{"identity":"v-result-verification-requirements","sha256":"e1100522ec55eedaca88c1f788ee1142e7d22a27ff5644e1fff13542aa6e5f64"}},"requirements":{"durability":{"identity":"v-durability","sha256":"cd9e1378613981d34c3fad1ce6d9d219562b7f9cf68b32984b1ec2210a1da01b"},"backup_restore":{"identity":"v-backup-restore","sha256":"1367cdd9992e9d5e87087ce67f43799e0acc9a4eaad5d63c9033457940c857ab"},"evidence_retention":{"identity":"v-evidence-retention","sha256":"1c75cb4cf26a580dca865497583016669f59c92eca83dea71b8a3d8c809e4e6c"},"initial_state_verification":{"identity":"v-initial-state-verification","sha256":"7aabcfb95290d05dd2abe08e79257f7de053c933b7e8fe5a6ef3130738f61ba5"},"approval_applicability":{"identity":"v-approval-applicability","sha256":"259f7c9d00d8083cb54761450944c3c790b3bc04c0bc6cc941de38b346dcda05"}},"authorization":{"reference":{"identity":"v-execution-authorization","sha256":"79e2921941db14aa6d928b5345418f48025e4dba1c6e3e76501019aae95bcbd2"},"valid_from_us":0,"valid_until_us":1000000},"expected_counts":{"metadata":1,"artifacts":0,"reservations":0,"claims":0,"commands":0,"events":0},"recovery_required":false}
~~~

BYTES = 3128
SHA256 = 1e2096c9295e1835934b347093816995ec4583c7c7188712103d67a020589ba1
RENDERED_ID = il6-package:sha256:1e2096c9295e1835934b347093816995ec4583c7c7188712103d67a020589ba1

### Vector ActivationPayload

~~~json
{"object_type":"JOUS.CORE.1A.IL6.ACTIVATION_PAYLOAD","profile_version":1,"purpose":"ABSENT_TO_GENERATION_ONE","activation_command_id":"v-K","expected_presence":"AUTHORITATIVE_ABSENT","predecessor_generation":0,"register_id":"g","issuer_generation":1,"activation_id":"x","host_identity":"v-host","package":{"identity":"il6-package:sha256:1e2096c9295e1835934b347093816995ec4583c7c7188712103d67a020589ba1","sha256":"1e2096c9295e1835934b347093816995ec4583c7c7188712103d67a020589ba1"},"checkpoint":{"identity":"v-checkpoint","sha256":"37bd0a83f97e3cc6405e95d5da7f1235cc923fee1fa3980ba07fc5b2a4f8612f"},"approval":{"identity":"v-J","sha256":"90a00209de607fb249696799543fab3be3ab87d0ee9776a21a763ecb53810780"}}
~~~

BYTES = 703
SHA256 = 42f289d46f332903b99d782e64eae0867365c43cec1fdc44a60d243f7b94cae8
RENDERED_ID = il6-activation-payload:sha256:42f289d46f332903b99d782e64eae0867365c43cec1fdc44a60d243f7b94cae8

E, P and payload bytes were independently re-encoded with an explicit
scalar/object encoder as well as a standard JSON encoder; preimages agreed.
Independent review must reproduce their hashes. No product code or tests ran.

### Rejection vectors

Each row defines exact rejected bytes by the literal ASCII transformation of the
complete E vector. Replace only the first exact occurrence. No normalization.
Digests below identify REJECTED raw input for reproduction, never accepted authority.

| ID | Exact transformation | Bytes | Rejected raw SHA256 | Reason |
| --- | --- | --- | --- | --- |
| R01 | `Append byte 0a` | 4485 | 6770d14abf7c1a63374f5a858fa57d35044948d0df0a3680c0c2e1ed9c99b85f | trailing LF |
| R02 | `Prepend bytes efbbbf` | 4487 | c308a0c4ef6401a07f00ba380cc29e85667572337a63309eda22d0660ec87dcc | BOM |
| R03 | `Replace first "profile_version":1 with "profile_version":1.0` | 4486 | b8edd9394d6d9fa90cf9c2fef9a766c8ebb335cb9ab197d5cbc3f2c243bf991b | float |
| R04 | `Replace first "profile_version":1 with "profile_version":true` | 4487 | 7f281c0172971abd1ef2f1395bb5f655405fbc52812bb5eaa060fc4a6b5f70fb | wrong scalar type |
| R05 | `Replace first "profile_version":1 with "profile_version":2` | 4484 | 2e9da45355f80810d0b9d6b4cec6da0f221eb8aafb7125f3cdebfa8f247b0064 | unknown version |
| R06 | `Replace first "register_id":"g" with "register_id":"\u0067"` | 4489 | ba206e3ab32240887a08486bf692fce9dde0a0d3055c50b1cc710fe08ed932b0 | unnecessary ASCII escape |
| R07 | `Replace first "register_id":"g" with "register_id":null` | 4485 | e19261b939d3b85167d56a64c43b92e9c2bb5e520a3118849a3fc323e7dde220 | null |
| R08 | `Insert "extra":0, immediately after initial {` | 4494 | 3c010337702ab666b393c528bf63af68270db126a16a2b99164565bc1064aeeb | unknown field/order |
| R09 | `Replace first "register_id":"g" with "register_id":"g","register_id":"g"` | 4502 | d3f31bf7840ef63d887acea28e61df513cec66d61e60ca31f1f97dc5a96503e0 | duplicate key |
| R10 | `Replace first "creation_utc_us":0 with "creation_utc_us":-0` | 4485 | 091f5e8789ba57744bfe6d791b2f215a5e6081ae873cbfaa104db423e20e0dbd | negative zero |
| R11 | `Replace first "object_type":"JOUS.CORE.1A.IL6.E","profile_version":1 with "profile_version":1,"object_type":"JOUS.CORE.1A.IL6.E"` | 4484 | dfd03bf494dd9eab43536e005dd6234eacf7829f02551bcb7594b6a27d9cc1be | member order |
| R12 | `Replace first "creation_utc_us":0 with "creation_utc_us":9223372036854775808` | 4502 | 1a8cb364159f1cd6afb88d545867294564abd307027033decc162d3d98e57494 | integer overflow |
| R13 | `Replace first "register_id":"g" with "register_id":"\ud800"` | 4489 | 0e5c89749e59eaadd81fe320fbbcf32c8fb9f6f338551a4d80a46e24aae5f1f3 | lone surrogate |

For G, reject these exact transformations of the rendered E-vector G: uppercase
the 64-digit suffix; append byte 20; replace initial genesis with Genesis; remove
the final digit. P with any Q/payload/hash field inserted rejects unknown field.
A payload with a different P/Q/C0/K fails binding even if syntactically canonical.
Removing any required member rejects. Uppercasing any nonnumeric digest hex digit,
adding separator whitespace, appending another JSON value or bytes ff rejects.

String-primitive vector (part of all three encodings, not a fourth canonical object):
semantic scalars U+0022, U+005C, U+000A, U+007F, U+00E9, U+1F600 in that order.
Exact quoted JSON bytes are represented by this hex, decode once:
225c225c5c5c6e5c75303037665c75303065395c75643833645c756465303022

Primitive BYTES = 32; SHA256 = 4151067b179bc79ace06b60e393941688adf793cd12bed78dac88361198d7eb5

## 10. Acyclic dependency proof and unchanged execution order

Upstream adopted documents/qualification and stable J/K allocation -> creation C
and fixed metadata/time -> frozen canonical S0 -> canonical E -> hE/G -> complete
frozen C0 -> hC0 -> canonical P -> hP -> independent opaque Q -> hQ -> canonical
ActivationPayload -> hA. Each digest follows its complete preimage. Inline R groups
do not require a hash of themselves. All opaque upstream dependencies obey the
transitive stage restriction in section 7.

C has no E/G/C0/P/Q/payload/outcome dependency. E has no C0/P/Q/payload/outcome
dependency. P contains no Q/payload/outcome and no own final digest. Q approves
P/C0 but P contains only stable pending J, never hQ. Payload binds P/Q/C0/K without
feeding back. Initial metadata/STATE excludes its own stored digest under existing
rules. No post-approval value constructs an already-approved earlier checkpoint.

The actual lifecycle remains frozen: independent approved P/Q gates protected C0
publication as a non-activating anchor; qualified protected publication proof and
authenticated authoritative ABSENT/history gate the original K/payload CAS;
authoritative readback and independent result verification follow. Pure payload
construction after Q does not authorize an activation attempt before checkpoint
publication proof. This serialization profile imposes no new effect ordering.

Unknown C, mismatched G, colliding J, incomplete/mismatched package/approval,
uncertain protected publication, uncertain ABSENT/CAS, and restart after uncertainty
retain the existing fail-closed/RECOVERY_ONLY or STOP boundary. No new identity,
duplicate anchor, retry, new CAS, automatic recovery, normal permit or authority
reset. IL.7 retains recovery ownership.

## 11. Relationship to the held implementation contract

The existing implementation-contract candidate remains ON HOLD:
docs/decisions/JOUS.CORE.1A.il6-authoritative-register-implementation-contract.md
blob f24fb4fb77c13a862663cef3d562267fc6b5bd95
SHA256 94b70da31d09f3dda2ec797b9f37d0f578a2ca828b3882510694275db2b52f1a.

This profile does not edit, remediate or approve that candidate. Required sequence:

1. Independent review of this serialization-profile candidate.
2. If approved, separately authorized exact staging/publication/freeze.
3. Only then narrow implementation-contract remediation binding the frozen profile.
4. Independent re-review of that remediated implementation contract.
5. Only after approval may implementation staging/implementation authority be considered.

## 12. No operational authority and authoring self-review

This candidate grants no implementation, register creation, genesis, activation,
protected publication/CAS, managed access, fixture provisioning, CANARY, deployment,
runtime activation or public-traffic authority. No real operational values,
credentials, providers or execution packages are selected. Repository publication
alone is not operational adoption. Existing lifecycle/STATE/CHECKPOINT/provisioning/
CANARY/recovery semantics are unchanged.

The intended reviewable closure is: complete classification; one encoding for
every new canonical object; closed opaque evidence boundaries; internal digest
domain separation; no null/absence ambiguity; exhaustive rejection/version rules;
complete E/P/payload and G-derivation vectors; acyclic dependency graph. None of
these authoring claims substitutes for fresh independent review and adoption.
