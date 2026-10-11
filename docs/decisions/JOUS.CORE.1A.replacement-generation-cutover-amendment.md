# JOUS.CORE.1A replacement-generation checkpoint / activation cutover amendment

Status: unapproved documentation authority candidate. Independent review and adoption are required. This amendment defines replacement transition AUTHORITY only; it authorizes no execution.

## 1. Controlling authority and narrow change

This is additive to `JOUS.CORE.1A.fixture-lease-implementation-design.md`, blob `706b6bf782701a602012bd1fed75099f519a53ee`, especially sections 5, 5.1 and 6. Published baseline is `abe0c967e26089855bf528f0812759b6f7ae43ed`.

Section 5 requires a matching protected checkpoint and activation for startup and fresh permits for normal mutations. Section 5 defines fenced replacement but does not define publication of its first checkpoint. Section 5.1 calls genesis publication the sole pre-activation checkpoint exception. Section 6 requires protected checkpoints at activation and permits immutable checkpoint retention with predecessor CAS. Together these leave replacement bootstrap unspecified.

This amendment explicitly adds ONE separate exception: approved, fenced replacement-first-checkpoint publication as defined below. It narrows the old 'sole' wording to sole GENESIS/bootstrap-from-absence exception, while authorizing only this enumerated replacement ceremony from authoritative PRESENT. It does not permit general pre-activation checkpoints. No checkpoint hash formula, CAS comparison rule, ordinary command permit or genesis sentinel is redefined.

## 2. One model: staged protected checkpoint, activation CAS, checkpoint-pointer completion

The first replacement checkpoint is protected as an immutable, non-current candidate under a dedicated independently approved replacement authority. Protecting it does NOT advance the current checkpoint pointer or activate the new issuer. The single generation cutover point is the existing external activation-current-pointer CAS from the exact old activation to the exact new activation referencing that candidate.

After this CAS is authoritatively confirmed, the existing checkpoint-current pointer is advanced by predecessor CAS from the exact final old checkpoint to the exact protected first new checkpoint. Until both external references agree and startup validation succeeds, normal mutation intake remains fenced and service mode RECOVERY_ONLY. These are two physical pointer operations with one generation-authority cutover; they are not presented as an atomic two-store commit.

At every resolved point the activation-current pointer selects exactly one generation. Before cutover the old generation is authoritative but fenced. After cutover the new generation is authoritative but may still be RECOVERY_ONLY pending checkpoint completion. Being authoritative is necessary, not sufficient, for ACTIVE mutation permission. Local preparation never establishes authority.

## 3. Replacement prerequisites and final old evidence

Before preparation require all of the following:

1. Authenticated protected external evidence identifies the exact current register_id, generation n, activation_id, approved host/service identity and activation approval.
2. Normal intake is stopped; old service execution and accepted-acknowledgement capability are independently proven fenced under section 5. Unreachability is not fencing. Old-generation credentials/host access are disabled as required by the approved ceremony.
3. Every in-flight permit, local commit, checkpoint gap and external execution outcome is authoritatively reconciled. No unresolved permit may be superseded. No unknown committed mutation remains.
4. A consistent validated source register exactly matches the final old protected checkpoint, event head, state digest, immutable authority pins and checkpoint ancestry. Restored/copied data alone is never authoritative.
5. Independent replacement/recovery approval binds the exact transition and evidence. Requester/issuer cannot self-approve. The preparation host is approved and local mode RECOVERY_ONLY.
6. Proposed generation n+1 and unique activation identity are fixed before publication. Integer range exhaustion rejects; no wrap/rebase. No higher generation is allocated while an earlier attempt is unresolved. Failed/ambiguous candidate identities remain bound to their exact retained attempt; they cannot be reused for different candidate bytes. Any later retry/allocation requires separately approved reconciliation consistent with protected generation history, never a local counter decision.

Final old checkpoint C_old means the exact immutable checkpoint selected by the authoritative protected current pointer after all old outcomes are resolved. Verify register/generation/activation, checkpoint revision q, event sequence e/digest h, old state digest d_old, predecessor ancestry, UTC/evidence and approval/permit closure. The exact checkpoint bytes/hash and old activation bytes/hash are retained. No transition begins from a stale or unreconciled C_old.

## 4. Replacement authorization evidence and immutable binding hook

Use the existing activation approval/ref/hash and independently approved recovery/authorization package path. Define a narrow logical replacement package within that existing exact-byte approval evidence; it is not a new registry, table, current pointer or mutable config file. The external new activation record's activation_approval_ref/hash resolves to the immutable approval record, whose existing package/hash fields bind the exact independently approved package. The first checkpoint's existing approval reference resolves to the SAME package. Protected authority must resolve and validate those exact retained bytes before acting.

The replacement package has these mandatory semantic fields, no arbitrary extension/config dictionary:

- transition_id: stable unique approved replacement identity;
- register_id;
- old_generation and old_activation_id;
- expected_old_activation_ref/hash;
- final_old_checkpoint_ref/hash, checkpoint_revision, event_sequence/event_digest, old_state_digest and predecessor ancestry reference;
- new_generation = old_generation + 1 and new_activation_id;
- approved_new_host_identity;
- first_new_checkpoint_ref/hash, its revision and first_new_state_digest;
- expected_checkpoint_predecessor_ref/hash = final_old_checkpoint_ref/hash;
- applicable_cutover_authority_ref/hash;
- independent_replacement_approval_ref and fencing/reconciliation evidence refs;
- new_generation_protocol_binding, the immutable hook defined next;
- old_generation_protocol_evidence_ref, sufficient to resolve the old generation's existing binding without changing historical approval.

`new_generation_protocol_binding` is a closed logical object with exactly `state_representation_id` and `state_representation_authority_ref/hash`. It is mandatory for replacement packages adopted under this amendment. state_representation_id is exact, nonempty bounded UTF-8 identity (1-255 bytes), with no aliases, normalization, preferences or inference. Its permitted exact identifiers/encoding and interpretation MUST be explicitly defined by the independently approved referenced representation authority. Unknown or unapproved identifier rejects. This amendment does NOT choose a STATE representation or approve the existing STATE-2 candidate.

The binding key is (register_id, new_generation, new_activation_id). One immutable binding exists for that generation; another activation cannot change it within the same generation. The package hash, activation approval linkage, protected checkpoint approval and append-only activation history protect it. Startup resolves this one evidence chain; local/env settings, size heuristics or 'try both' are not authoritative.

Historical generation bindings resolve through their original approved authority evidence, including the published representation rule where it was already fixed. A new package may cite that rule, never retroactively rewrite historical approval. If it cannot resolve exactly one old representation, STOP.

No package wire encoding is invented here. Exact package bytes/hash must be independently pinned under existing approval/package machinery before authorization. The following dependency is mandatory: allocate a stable independent approval reference ID; encode complete C_new with that ID in its existing approval-reference field; compute hash(C_new); encode the package binding that exact complete checkpoint hash; obtain independent approval whose existing package/hash fields bind the package; encode the new activation record with the resulting approval ref/hash. The approval ID is not an approval until verification succeeds. The checkpoint approval field is the existing stable reference, NOT the package digest or approval-record digest; these resolve through the externally retained immutable approval record. Thus C_new -> package -> approval record -> new activation is acyclic. No approval wrapper is stripped, no different checkpoint preimage is hashed, and the full immutable checkpoint identity includes its fixed approval reference. Unknown or incompatible checkpoint approval-field interpretation rejects; no alternate encoding or recursive hash workaround is permitted.

## 5. First new checkpoint and metadata boundary

Derive first new state only from reconciled authoritative source rows. Carry APPROVED_ARTIFACTS, RESERVATIONS, BLOCKING_CLAIMS, COMMANDS and EVENTS forward unchanged, including exact COMMAND/EVENT/ACK bytes, revisions and keys. No fake command, business mutation or synthetic event is required to obtain this checkpoint.

Register identity, schema and authority pins remain immutable. Generation and activation metadata change only under the approved activation ceremony. last_event_sequence/digest remain the reconciled old event head; no event is appended solely for replacement. last_valid_utc and recovery_required may change only as explicitly approved ceremony projections under existing clock/recovery requirements. The package must pin the exact proposed metadata values used in first_new_state_digest. No byte-identical metadata claim is made when generation/activation changes.

Existing STATE exclusions remain controlling: stored state_digest and metadata event-head/digest fields are excluded. Same logical business rows do not mean same canonical STATE bytes or digest. The selected new representation and changed generation metadata determine the new digest. No representation is selected by this document.

Construct C_new with register_id, new generation/activation, checkpoint revision q+1, unchanged event head e/h, exact approved first_new_state_digest, approved UTC, predecessor_checkpoint_digest = hash(C_old), stable replacement transition reference in the existing command/permit-reference position, and existing approval reference. This extends that reference position semantically to the dedicated ceremony identity, not a normal COMMAND or fake permit. It does not change the field order or checkpoint cryptography. No genesis zero predecessor, ABSENT sentinel or revision reset is permitted.

Once exact transition identities/bytes are approved, C_new is immutable. Do not recompute it from later state or change time, metadata, representation, activation, predecessor or authority after an attempt could have occurred. If changes are required, STOP for separately approved reconciliation; do not substitute a new candidate under the same transition identity.

## 6. Dedicated first-checkpoint publication authority

The protected checkpoint authority may retain exactly C_new as an immutable non-current candidate only on presentation of the exact approved replacement package and verified prerequisites. This REPLACEMENT-FIRST-CHECKPOINT authority is distinct from genesis and from ProtectedCheckpoints.publish for an ordinary current-activation command permit.

It grants no command permit, lease acknowledgement, claim release, availability or issuer activation. It cannot publish unrelated checkpoints or advance the checkpoint-current pointer before activation cutover. It must verify old activation and C_old are still exact expected current evidence; otherwise reject and reconcile. No ordinary G(n+1) permit is required or fabricated, and no G(n) permit is used to mislabel the checkpoint.

This is a future dedicated ceremony operation of the existing protected authority, not an incompatible change to the frozen IL.2 normal-command capability value objects/interfaces. Future implementation needs this additional separately reviewed replacement ceremony path; rejecting defaults stay rejecting. No implementation is created here.

## 7. Exact ordering and CAS boundaries

1. Stop/fence intake; resolve old operations/permits and prove all prerequisites.
2. Resolve and verify C_old and old activation through authoritative external reads.
3. Fix transition_id, n+1, activation, host, protocol-binding evidence and proposed metadata; derive the candidate new state digest and C_new from reconciled source rows.
4. Obtain independent approval of the exact package/candidates/evidence. Verify its integrity, independence and applicable authority.
5. Protect C_new immutably as NON-CURRENT under the dedicated first-checkpoint authority; read back its exact identity and ancestry. Lost response requires read/reconciliation, not a new candidate.
6. CAS the existing activation-current pointer with expected exact old activation identity/hash and its approved C_old predecessor context; successor is the exact approved new activation referencing C_new/package. Supersession appends immutable evidence and permits no unresolved old permit. A mismatch rejects; no automatic adoption/retry.
7. Resolve activation outcome authoritatively by exact transition identity and protected current/history evidence. If unknown, both issuers remain fenced RECOVERY_ONLY.
8. Only on confirmed exact activation success, complete the existing checkpoint-current-pointer predecessor CAS: expected C_old, successor C_new, under that SAME approved replacement ceremony authority. No separate CAS namespace. Read back current activation/checkpoint and immutable history.
9. Reconcile local metadata/register to the exact approved new projection; verify startup identity, host binding, ancestry, state digest, protocol binding, trusted time and no unresolved recovery condition. Only after all proofs may local ACTIVE mode be derived and fresh normal permits requested.

The authority cutover is step 6's linearizable activation CAS, not checkpoint staging, local writes, message delivery or step 9. Step 8 is completion required for mutation eligibility. At no intermediate stage may an old fenced issuer resume automatically or a new issuer mutate without matching current checkpoint proof.

Activation CAS comparison is exact old current authority, not merely generation number. Checkpoint CAS comparison is exact C_old. CAS conflict is a definite failed comparison, not evidence of success; authoritative read may separately discover that the exact original operation previously succeeded. Unexpected third authority always blocks automatic adoption.

No automatic retry is authorized. The published exact checkpoint reconciliation principle may later permit independently approved completion of the SAME missing pointer successor after authoritative reconciliation; this document authorizes only read/reconciliation after lost response. Never allocate another generation or resubmit an activation publication to resolve uncertainty.

## 8. Outcome and restart table

The labels below are evidence classifications, not new reservation/issuer states. Issuer modes remain ACTIVE or RECOVERY_ONLY. Mutation permission always requires all ordinary gates in addition to the listed necessary condition.

| Evidence classification / restart case | Authoritative generation | Mode / mutation | Required action |
| --- | --- | --- | --- |
| A: replacement never started | exact externally current old, if verified | ordinary startup gates; ACTIVE possible | verify existing authority; do not infer from local absence |
| B: PREPARED / PUBLICATION_NOT_ATTEMPTED | exact old if authoritative read proves it | RECOVERY_ONLY; no mutation | retain preparation; independent cancellation/resumption approval or separately authorized continuation |
| C: PUBLICATION_KNOWN_FAILED, current old and checkpoint still C_old | old | RECOVERY_ONLY; no automatic resume | reconcile exact failure, retained candidate/evidence and fencing; independent approval before old service capability restoration/startup |
| D: PUBLICATION_UNKNOWN | unknown to caller | RECOVERY_ONLY; no mutation on either | read exact current/history/operation evidence; no second publication/allocation |
| E: PUBLICATION_CONFIRMED, both pointers exact intended new/C_new | new | RECOVERY_ONLY until startup proofs; ACTIVE possible afterwards | exact local/protected/host/protocol/state verification |
| F: external still exact old, local says new | old; local claim rejected | RECOVERY_ONLY; no mutation | prove submission outcome, candidate non-current status and consistency; no local-authority inference |
| G: exact intended new external activation, ACK lost | new | RECOVERY_ONLY until C_new pointer/startup complete | recognize original success by exact identities; no second publication/generation |
| H: unexpected third authority / CAS conflict | only externally evidenced authority is knowable; not adopted | RECOVERY_ONLY; no mutation | independent reconciliation; never chase changed predecessor |
| I: malformed/incomplete local transition evidence | current external may be observable, but qualification incomplete | RECOVERY_ONLY; no mutation | reconstruct exact approved evidence or STOP; no guessed binding |
| J: ancestry or protocol-binding mismatch | not safely qualified | RECOVERY_ONLY; no mutation | reconcile exact history; no repair/fallback |
| Activation exact new, checkpoint pointer still C_old | new generation current but completion unresolved | RECOVERY_ONLY; no mutation | exact independently approved completion reconciliation; never activate old |
| Checkpoint pointer unexpected after new activation | new generation may be current; integrity unresolved | RECOVERY_ONLY; no mutation | independent reconciliation; do not force pointer or allocate another generation |

Known success requires authenticated protected external current/history evidence of the exact new activation and exact protected C_new; mutation additionally requires checkpoint-current completion and startup validation. A sent request/local write/candidate alone is insufficient. Known failed activation leaves old authority current, not permission to resume.

Unknown includes timeout, crash, lost ACK, connection loss and uncertain CAS. All remain fenced. Exact success recognition is read-only reconciliation of the original operation, never a second competing transition. A failed candidate and approvals remain retained as immutable audit evidence; no silent deletion or history cleanup. Old service resumption requires independent approval and renewed authoritative startup/fencing checks; it is never triggered by a local error.

## 9. Restore, historical verification and replay

Every restore begins NON_AUTHORITATIVE / RECOVERY_ONLY. Resolve current activation, immutable approved package/binding, C_old/C_new ancestry, checkpoint-current pointer and exact corresponding state digest. Missing rows/history, uncertain authority or inconsistent binding blocks mutation. Historical state verification uses the representation established by that historical generation's exact approval evidence; no sniffing, size inference or fallback.

Historical activations/checkpoints/state digests and COMMAND/EVENT/ACK/artifact bytes are never rewritten. New generation authority is prospective. Historical ACKs may be projected verbatim under a later approved representation. STATE representation change does not change command identity, regenerate ACKs or re-execute a completed command. Old returned ACKs still require the published current-permission checks.

## 10. Deterministic semantic fixtures

No new wire encoding or hashes are invented. All fixtures below use the same compact semantic input:

register_id = synthetic-register; old generation = 7, old activation = synthetic-old; C_old identity = synthetic-checkpoint-41, revision 41, event sequence 100, event digest = 11 repeated 32 bytes, old state digest = 22 repeated 32 bytes; new generation = 8, new activation = synthetic-new; transition_id = synthetic-replacement; C_new identity = synthetic-checkpoint-42, revision 42, same event head, first new state digest = 33 repeated 32 bytes, predecessor = exact C_old hash; approved authority identity = synthetic-cutover-authority; representation binding = exact symbolic identifier supplied by independently approved synthetic representation authority (no production representation selected). Both checkpoint identities stand for exact approved bytes/hash references in the test harness; no fabricated real checkpoint hash is asserted.

| Fixture | External observation | Authority / mode / mutation |
| --- | --- | --- |
| 1 Known success | activation synthetic-new/generation 8 and checkpoint current exact C_new; package/ancestry verified | generation 8; ACTIVE only after all startup proofs; then normal independently permitted mutations possible |
| 2 Known failure | exact authoritative rejection of original activation CAS, old activation/C_old remain current | generation 7; RECOVERY_ONLY; no mutation until independent old-service resumption approval/startup |
| 3 Lost ACK | history proves original exact transition committed; current new activation/C_new exact | recognize generation 8; verify startup; no republish/new generation; ACTIVE only after proofs |
| 4 Unknown | operation lookup/current authority unavailable after submission | unknown; RECOVERY_ONLY; no mutation |
| 5 CAS conflict | external current is synthetic-other generation 9 or checkpoint predecessor differs | unexpected authority not adopted; RECOVERY_ONLY; no mutation; independent reconciliation |
| 6 Restart with exact new | local exact package/new projection and external activation/C_new match | generation 8; RECOVERY_ONLY during proofs; ACTIVE only after full validation |
| 7 Malformed local package | external may show exact new, but required binding/approval missing locally | no qualified mutation authority; RECOVERY_ONLY; recover exact evidence or STOP |
| 8 Partial completion | activation exact generation 8, checkpoint current still C_old | generation 8 current; RECOVERY_ONLY; reconcile original checkpoint completion, no old resume |

Every fixture retains the fixed old/new identities and predecessor. Changing any candidate/package/binding after possible submission rejects exact success recognition. These fixtures test semantic authority relationships, not operational readiness.

## 11. Compatibility, non-action and self-review

IL.1 representations and M-04 are unchanged. IL.2 normal-command interfaces/values and trusted-time semantics are unchanged; a future dedicated replacement ceremony implementation is required, not reuse of a forged normal permit. IL.3 six-table schema needs no migration/new column: approval/package references and exact evidence use existing retention/external authority paths. No speculative SQLite table is introduced. Checkpoint cryptography and field layout stay unchanged; first replacement predecessor/revision and ceremony-reference interpretation are explicitly authorized above. Genesis retains authoritative ABSENT, zero predecessor, generation-one purpose and independent approval; replacement requires PRESENT and never uses those sentinels.

This amendment defines transition AUTHORITY only. It does NOT authorize performing a transition, operational SQLite creation/access, production generation change, external checkpoint publication/CAS, activation of any representation including STATE-2, runtime activation, fixture provisioning, canary or STRIX.

No replacement transition has been performed by this task. No new generation exists because of this document. No checkpoint has been published. No activation has changed. No STATE-2 representation is active because of this task. Runtime remains NOT ACTIVATED. No SQLite register has been opened. STRIX has not been run.

Self-review answers:

1. YES: activation-current CAS selects at most one generation; ACTIVE additionally needs matching checkpoint proof.
2. YES: every unknown outcome fences both mutation paths under RECOVERY_ONLY.
3. YES: lost ACK is resolved by authoritative read, not another publication.
4. YES: first checkpoint has the explicitly scoped replacement-first-checkpoint authority.
5. YES: non-current protected candidate before activation CAS breaks the bootstrap cycle; pointer completion gates ACTIVE.
6. YES: genesis remains distinct bootstrap-from-ABSENT authority.
7. YES: CAS conflict is failed comparison; exact prior success requires separate authoritative proof.
8. YES: restart table derives authority from external current/history plus exact approved evidence.
9. YES: generation binding is immutable through activation/checkpoint approval refs and exact package integrity.
10. YES: no operational action is authorized.

Independent review must assess the dedicated ceremony boundary, two-pointer completion gap and package integrity path before adoption. No claim of implementation readiness or approval of either existing untracked IL.4 candidate is made.
