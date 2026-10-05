# JOUS.CORE.1A — Foundation & Domain Architecture Gate

**Status:** APPROVED — READY FOR IMPLEMENTATION  
**Project:** Jous  
**Gate:** JOUS.CORE.1A  
**Date:** 2026-10-04  
**Repository:** anoopkundra/jous  
**Implementation Owner:** Jous  
**Primary Engineering Agent:** Codex  

**Depends on:**
- JOUS.SUPPLY.1
- JOUS.ECON.1
- JOUS.CONTEXT.1
- JOUS.MVP.0 v2

---

## 1. Purpose

JOUS.CORE.1A establishes the smallest trustworthy technical foundation on which the Jous MVP can be implemented.

This gate is structural.

It does not implement the Jous economic system itself.

It establishes:

- repository and package boundaries,
- frontend and backend application foundations,
- configuration and environment handling,
- PostgreSQL connectivity and migrations,
- foundational identity and project domain objects,
- organization isolation,
- context-ready Project boundaries,
- execution-policy-ready architecture,
- supplier-neutral model and supply abstractions,
- health and operational foundations,
- test infrastructure,
- CI foundations,
- and implementation guardrails required by later Jous gates.

CORE.1A must make later implementation possible without prematurely implementing those later systems.

---

## 2. Governing Principle

The objective is:

> Build the smallest foundation that preserves the approved Jous architecture without prematurely building the product systems that depend on it.

CORE.1A must not become a disguised implementation of:

- the ledger,
- wallet,
- rewards,
- payments,
- inference execution,
- economic routing,
- Project Memory,
- context retrieval,
- or Jous Auto.

---

## 3. Authority

Implementation authority for this gate is:

1. `docs/decisions/JOUS.SUPPLY.1.md`
2. `docs/decisions/JOUS.ECON.1.md`
3. `docs/decisions/JOUS.CONTEXT.1.md`
4. `docs/JOUS.MVP.0.md`
5. this `JOUS.CORE.1A.md`
6. code and tests

If implementation reveals a material contradiction with an approved architecture decision, Codex must stop and report the contradiction.

It must not silently redesign the architecture.

---

## 4. Repository Foundation

Preserve the canonical repository direction:

```text
jous/
├── apps/
│   └── web/
├── services/
│   └── api/
├── packages/
│   ├── ledger/
│   ├── rewards/
│   ├── spend/
│   └── provider-adapters/
├── docs/
│   └── decisions/
└── tests/
```

CORE.1A may create missing directories, package metadata, configuration and test scaffolding required for this structure.

Empty future-domain packages may remain intentionally minimal.

Do not implement their future business logic merely to populate the directories.

---

## 5. Frontend Foundation

Establish `apps/web` as the Jous application frontend.

Canonical direction:

- Next.js
- React
- TypeScript
- Vercel AI SDK only where appropriate in later gates

CORE.1A should provide a minimal application shell sufficient to prove:

- the application builds,
- configuration loads correctly,
- the frontend can communicate with the Jous API,
- health/system state can be represented,
- and future product surfaces have a stable application boundary.

Do not build the full Jous Workspace.

Do not build production chat or model execution.

Do not reproduce Webflow marketing functionality inside the application.

---

## 6. Backend Foundation

Establish `services/api` as the Jous control-plane backend.

Canonical direction:

- Python
- FastAPI
- Pydantic
- PostgreSQL

The backend must have clear boundaries between:

- API transport,
- domain logic,
- persistence,
- configuration,
- supplier abstractions,
- and future economic modules.

Business rules must not become embedded directly inside route handlers.

---

## 7. Configuration & Environment

Implement typed configuration for at least:

- environment,
- database connection,
- frontend/API origins,
- logging level,
- application identity/version,
- and future supplier configuration namespaces.

Secrets must not be committed.

Provide an example environment file containing names/placeholders only.

Configuration must fail clearly when mandatory production configuration is missing.

Test configuration must be isolated from production configuration.

---

## 8. Database Foundation

Use PostgreSQL.

Jous must use its own database/project and must not share TradeBuddy or another application's operational database.

CORE.1A must establish:

- database connectivity,
- ORM/data-access foundation,
- migration framework,
- reproducible migrations,
- development/test database workflow,
- created/updated timestamps where appropriate,
- stable identifiers,
- and transaction-safe persistence foundations.

Migration history becomes authoritative once committed.

Do not rely on application startup to silently mutate production schema.

---

## 9. Foundational Domain Objects

CORE.1A implements only the foundational domain objects required by the approved MVP.

### User

Represents a Jous identity.

Minimum architectural responsibilities:

- stable identifier,
- authentication identity linkage,
- status,
- created/updated timestamps.

Authentication-provider implementation may remain minimal at this gate.

The User object must not contain an authoritative financial balance.

### Organization

Represents the tenant/economic ownership boundary.

Minimum:

- stable identifier,
- name,
- status,
- created/updated timestamps.

### OrganizationMembership

Represents the relationship between User and Organization.

Minimum:

- organization,
- user,
- role,
- status,
- created/updated timestamps.

Authorization must be capable of evolving around membership rather than assuming every user can access every organization.

### Project

Project is a first-class Jous object.

Minimum:

- stable identifier,
- organization ownership,
- name,
- optional description,
- status,
- created/updated timestamps.

Project is simultaneously intended to become:

- an economic attribution boundary,
- a builder-work boundary,
- and the primary context-continuity boundary.

CORE.1A must preserve all three roles without implementing their later engines.

---

## 10. Tenant Isolation

Organization ownership must be explicit.

A User must not gain access to another Organization's Project merely by knowing its identifier.

Repository/service patterns should make tenant-scoped access the normal implementation path.

Tests must demonstrate basic organization/project isolation.

Do not postpone tenant isolation until the enterprise phase.

---

## 11. Project Context Architecture Seam

JOUS.CONTEXT.1 establishes Jous-owned Project Context semantics.

CORE.1A must therefore make Project compatible with future:

- Conversation,
- ConversationMessage,
- ProjectSource,
- SourceDocument,
- SourceReference,
- ProjectMemory,
- MemorySource,
- MemoryVersion,
- ProjectState,
- ProjectDecision,
- ContextRequest,
- ContextCandidate,
- ContextPackage,
- ContextUsage,
- ContextEvaluation.

CORE.1A does **not** need to implement this complete object set.

It must instead ensure that foundational Project semantics do not prevent these objects from being added cleanly.

The canonical Project must never be owned by a memory vendor.

Do not create Mem0-, Letta-, Graphiti-, LangMem-, vector-database-, or supplier-specific fields in the Project domain.

---

## 12. Source Truth vs Derived Memory

The foundation must preserve the future distinction between:

**Source Truth**
- uploaded/source documents,
- user-provided material,
- authoritative project artifacts,
- explicit decisions.

and:

**Derived Memory**
- extracted facts,
- summaries,
- inferred state,
- retrieval artifacts,
- model-generated memory.

CORE.1A does not implement the memory engine.

It must avoid a schema design that forces source truth and derived memory into one indistinguishable record type.

---

## 13. Execution Policy Architecture Seam

The foundation must permit the three canonical execution policies defined by JOUS.CONTEXT.1:

### JOUS_AUTO

Jous may select the logical model and eligible supplier route within customer constraints.

### MODEL_STACK

The customer defines an ordered logical-model preference stack.

Jous respects model order while retaining supplier optimization underneath each logical model.

### PINNED_MODEL

The customer pins a logical model.

Jous may optimize eligible supplier selection underneath that model.

Cross-model fallback requires explicit customer permission.

CORE.1A does not implement these routing behaviors.

It must ensure that adding them later does not require redesigning User, Organization or Project.

Canonical principle:

> Customer policy constrains optimization. Jous optimizes within those constraints.

---

## 14. Model Selection vs Supplier Selection

CORE.1A must preserve the architectural distinction between:

**Logical Model Selection**

and:

**Supplier Selection**

A logical Jous model must not be permanently bound to one supplier.

Supplier identifiers must not leak into core Project or customer semantics.

This is required by JOUS.SUPPLY.1.

---

## 15. Supplier-Neutral Abstraction

Establish the package/interface boundary for future AI supply.

The architecture should accommodate a future SupplyAdapter contract conceptually capable of:

- `quote()`
- `execute()`
- `get_usage()`
- `get_balance()`
- `health()`
- `capabilities()`

CORE.1A should define only the minimum contract/types required to prove the boundary.

Do not implement production Hugging Face, Vercel, OpenRouter or BYOK execution.

Do not make Portkey, LiteLLM or any gateway authoritative for Jous domain semantics.

Canonical rule:

> NO AI SUPPLIER DEPENDENCY ABOVE THE ADAPTER BOUNDARY.

---

## 16. Model Registry Seam

Preserve a future Jous-owned Model Registry.

The architecture must be capable of distinguishing:

- Jous logical model identity,
- supplier,
- supplier-specific model identifier,
- capabilities,
- commercial eligibility,
- free eligibility,
- availability.

CORE.1A does not require a production registry or populated model catalog.

Supplier model IDs must not become canonical Jous model IDs.

---

## 17. Financial Architecture Seam

CORE.1A must preserve the future implementation of:

- LedgerAccount,
- Transaction,
- LedgerEntry,
- Wallet,
- Jous Balance,
- Jous Rewards,
- UsageEvent,
- PriceQuote,
- RouteDecision,
- Reward,
- Settlement.

However:

**CORE.1A MUST NOT implement the financial posting engine.**

That belongs to JOUS.CORE.1B.

Do not create:

- mutable authoritative `user.balance`,
- mutable authoritative `organization.balance`,
- mutable authoritative `wallet.balance`,
- or equivalent shortcuts.

No financial value should be treated as authoritative outside the future ledger.

---

## 18. API Foundation

Provide versioned or otherwise stable API organization suitable for later expansion.

Minimum useful endpoints should include:

- liveness/health,
- readiness or dependency health where appropriate,
- basic authenticated identity boundary if authentication foundation is included,
- Organization CRUD required by the gate,
- Membership operations required by the gate,
- Project CRUD required by the gate.

Exact endpoint naming may follow the repository's established conventions.

CRUD must enforce tenant boundaries.

Do not expose placeholder financial or inference APIs merely to simulate completeness.

---

## 19. Health Semantics

Health endpoints must distinguish process health from dependency health.

A process-liveness endpoint must not unnecessarily fail merely because PostgreSQL is temporarily unavailable.

Database/dependency health should be separately observable.

This avoids coupling deployment process health to every downstream dependency.

---

## 20. Logging & Observability Foundation

Implement structured application logging sufficient to diagnose:

- startup,
- configuration failures,
- request failures,
- database failures,
- migration state,
- and authorization failures.

Never log:

- secrets,
- database credentials,
- provider credentials,
- authentication tokens,
- or future customer prompt/source content by default.

Request correlation identifiers should be supported where practical.

Full observability platforms are deferred.

Do not introduce Langfuse merely for CORE.1A.

---

## 21. Security Foundation

CORE.1A must establish:

- environment-based secret handling,
- tenant-aware authorization boundaries,
- least-privilege assumptions,
- input validation,
- safe error handling,
- no secrets in logs,
- and dependency hygiene.

Future provider credentials must be capable of being encrypted and organization-scoped.

Actual provider credential storage may be deferred.

---

## 22. OSS Guardrail

Only commercially permissive dependencies should be introduced by default.

Preferred license families include:

- MIT,
- Apache-2.0,
- BSD-2-Clause,
- BSD-3-Clause,
- PostgreSQL License,
- similarly permissive licenses after review.

Do not introduce restricted enterprise modules or source-available components without explicit approval.

Avoid unnecessary dependencies.

CORE.1A should create or update dependency documentation when a material new OSS component is introduced.

---

## 23. Testing Foundation

CORE.1A requires automated tests covering at minimum:

- application startup,
- configuration validation,
- database connectivity,
- migrations,
- User persistence,
- Organization persistence,
- Membership behavior,
- Project persistence,
- organization/project isolation,
- API health,
- basic CRUD behavior,
- supplier abstraction independence,
- and architectural invariants that can reasonably be tested.

Tests must not require paid AI inference.

Tests must not require real customer funds.

Tests must not depend on production credentials.

---

## 24. CI Foundation

GitHub Actions should run the bounded CORE.1A verification suite.

At minimum:

- backend tests,
- frontend build/type validation,
- migration validation where practical,
- lint/static checks adopted by the repository.

CI must not spend money on AI providers.

CI must not require production secrets for ordinary validation.

---

## 25. Local Development

A developer or coding agent should be able to:

1. clone the repository,
2. configure documented local environment values,
3. install dependencies,
4. start PostgreSQL/Supabase-compatible development connectivity,
5. apply migrations,
6. start the API,
7. start the web application,
8. run tests,
9. verify health.

Setup must be documented sufficiently for another engineer or coding agent to reproduce it.

---

## 26. Explicit Non-Goals

CORE.1A must NOT implement:

- double-entry ledger posting,
- wallet balance computation,
- customer funding,
- Stripe payments,
- ACH,
- refunds/disputes,
- Jous Rewards issuance,
- reward rules engine,
- JEAC calculation engine,
- real AI inference,
- production supplier adapters,
- Portkey production gateway,
- LiteLLM production gateway,
- supplier inventory,
- free inference,
- Jous Auto routing,
- MODEL_STACK routing,
- PINNED_MODEL routing,
- autonomous routing,
- production Project Memory,
- Mem0 integration,
- Letta integration,
- Graphiti integration,
- vector retrieval,
- context ranking,
- context optimization,
- production ContextPackage assembly,
- full Jous Workspace,
- Spend Intelligence,
- Rewards Marketplace,
- or enterprise procurement/governance.

Do not implement later gates early.

---

## 27. Required Architectural Invariants

CORE.1A is not complete unless these remain true:

1. No AI supplier dependency exists above the adapter boundary.
2. Project is supplier-neutral.
3. Project is memory-engine-neutral.
4. Logical model identity is separate from supplier model identity.
5. Model selection is separate from supplier selection.
6. User/Organization/Project schemas do not require redesign to support JOUS_AUTO.
7. They do not require redesign to support MODEL_STACK.
8. They do not require redesign to support PINNED_MODEL.
9. Context continuity can later remain independent of model choice.
10. Context continuity can later remain independent of supplier choice.
11. Source truth can remain distinguishable from derived memory.
12. No mutable balance field becomes authoritative.
13. Tenant boundaries are enforceable.
14. No paid inference is required to pass CORE.1A.
15. No real customer money is required to pass CORE.1A.

---

## 28. Acceptance Gate

JOUS.CORE.1A passes only when:

### Repository

- canonical structure exists,
- setup documentation exists,
- no unintended generated/secrets files are committed.

### Backend

- FastAPI starts cleanly,
- typed configuration works,
- PostgreSQL connectivity works,
- migrations apply reproducibly,
- foundational APIs function.

### Frontend

- Next.js application builds,
- application shell runs,
- API connectivity can be demonstrated.

### Domain

- User works,
- Organization works,
- OrganizationMembership works,
- Project works,
- tenant isolation is demonstrated.

### Architecture

- supplier-neutral boundary exists,
- model/supplier separation is preserved,
- Project Context seam is preserved,
- Execution Policy seam is preserved,
- no memory-vendor leakage exists,
- no supplier leakage exists,
- no financial shortcut violates future ledger authority.

### Quality

- tests pass,
- CI passes,
- no production AI spend occurs,
- no real customer funds are handled.

---

## 29. Codex Implementation Rules

Codex must:

1. inspect the existing repository before modifying it,
2. preserve working code unless change is required by this gate,
3. implement only CORE.1A,
4. avoid speculative abstractions beyond approved seams,
5. avoid unrelated refactoring,
6. add tests with implementation,
7. document material architecture choices,
8. report every dependency added,
9. report every migration created,
10. report every API route added,
11. report any deviation from this specification,
12. stop on material architectural conflict.

Codex must not interpret future architecture seams as permission to implement future gates.

---

## 30. Required Implementation Report

At completion Codex must produce:

### Files Changed

Every created/modified/deleted file.

### Database

Every table, column, constraint, index and migration introduced.

### API

Every route introduced and its purpose.

### Dependencies

Every dependency added and its license where known.

### Tests

Tests added and final results.

### Architecture Verification

Explicit confirmation of:

- supplier neutrality,
- model/supplier separation,
- tenant isolation,
- context neutrality,
- execution-policy readiness,
- no financial source-of-truth shortcut.

### Deferred Work

Anything intentionally left for later gates.

### Risks / Questions

Any unresolved issue requiring founder review.

---

## 31. Stop Conditions

Codex must stop and request architectural review if implementation appears to require:

- changing JOUS.SUPPLY.1,
- changing JOUS.ECON.1,
- changing JOUS.CONTEXT.1,
- changing frozen JOUS.MVP.0 behavior,
- introducing supplier dependence above adapters,
- selecting a production memory engine,
- introducing an authoritative mutable balance,
- implementing real-money handling,
- enabling paid production inference,
- or materially expanding MVP scope.

---

## 32. Next Gate

Successful CORE.1A completion authorizes review for:

**JOUS.CORE.1B — Ledger Gate**

It does not automatically authorize implementation of every later MVP gate.

---

## 33. Founder Decision: Step 6 and Step 7 Security Gates

Status: APPROVED IN PRINCIPLE — implementation remains a separately authorized task.

### Completed Foundation: Steps 1–5

Steps 1–5 established the repository/dependency foundation, typed configuration,
structured logging, correlation and safe errors, process liveness, PostgreSQL
connectivity/session/readiness infrastructure, and Alembic revision
`0001_identity_project` with User, Organization, OrganizationMembership and Project.

Step 5 established the provider-neutral, fail-closed sequence:

VerifiedPrincipal → RequestIdentity → active User → active OrganizationMembership
→ authorized Organization scope → authorized Project scope.

Scopes are immutable and request-local. Persistence queries enforce tenant/project
scoping. Offline and controlled managed PostgreSQL application-layer isolation
validation passed. This does not prove runtime-role/RLS isolation.

Supabase automatic RLS remains enabled; no Jous RLS policies exist. No public CRUD,
production credential verification or Supabase Auth integration exists in Steps 1–5.

### Step Split and Public CRUD Gate

- Step 6: production credential verification and application action authorization.
- Step 7: dedicated runtime PostgreSQL role, transaction-local database identity,
  RLS defense-in-depth and real runtime-role isolation validation.
- Public CRUD is prohibited until both Step 6 and Step 7 pass.

### Authentication and Actual Project Configuration

Supabase Auth is the approved initial authentication provider, implemented as a
replaceable adapter below the Jous authentication boundary. The domain flow remains:

External Credential → Provider-Specific Verification Adapter
→ VerifiedPrincipal(issuer, subject) → active internal Jous User
→ RequestIdentity(user_id).

No Supabase-specific identity object is authoritative in domain services.

The non-secret authentication preflight is complete. Verified Jous project facts:

- Project reference: `aqcixpoorbhjgvdkdjqd`.
- Exact issuer: `https://aqcixpoorbhjgvdkdjqd.supabase.co/auth/v1`.
- Expected audience for normal authenticated end-user access tokens: `authenticated`.
- Current JWT signing key: ECC P-256 / ES256.
- Public JWKS: `https://aqcixpoorbhjgvdkdjqd.supabase.co/auth/v1/.well-known/jwks.json`.
  The endpoint has been verified reachable and exposes the current ES256 verification key.
- Previous signing key: Legacy HS256 Shared Secret, retained by Supabase during the
  token-expiration transition.

CORE.1A Step 6 accepts only ES256 end-user access tokens. Do not import or depend on
the legacy HS256 shared secret. Legacy HS256 Jous authentication fails closed; no
HS256 fallback is authorized. Existing old Supabase sessions may refresh or
reauthenticate to obtain newly issued ES256 tokens.

The supported authenticated end-user token profile requires:

- the exact issuer above and audience `authenticated`;
- role `authenticated`;
- a valid subject representing the Supabase Auth user;
- `is_anonymous` equal to boolean `false`;
- a valid `session_id` for the supported user access-token profile;
- valid `exp` and `iat`, and validation of `nbf` when present;
- an explicit ES256 algorithm allowlist;
- a compatible `kid`/key from the configured trusted JWKS.

Token headers must never expand trusted algorithms or key locations.
Supabase `role=authenticated` is not a Jous Organization role. Jous owner/member
authority comes only from internal Jous persistence and central action authorization.

Verified access-token expiry is 3600 seconds. Current session settings are:

- single-session enforcement OFF;
- session time-box 0 / never;
- inactivity timeout 0 / never.

Current authentication settings observed are:

- Email authentication enabled;
- Email confirmation enabled;
- Anonymous sign-ins disabled;
- Manual account linking disabled;
- New-user signup currently enabled.

Enabled Supabase signup does not authorize a Jous identity. Unknown external
identities still fail closed: controlled provisioning requires an exact
issuer/subject mapping to an active pre-provisioned internal Jous User.
Public/new-user signup should be disabled under a separately authorized Supabase
configuration task before controlled CORE.1A production-like testing. This decision
does not change that setting.

Step 6 is approved to locally verify new ES256 access tokens against the trusted
project JWKS using a maintained JWT library. Verification must fail closed. Use
bounded JWKS retrieval/cache/refresh behavior and never follow token-supplied key URLs.
Do not log or persist bearer tokens, private keys, shared secrets, service-role
credentials or sensitive claims. Keep Supabase behind the replaceable authentication
adapter boundary.

### Roles and Central Action Authorization

Only `owner` and `member` are approved. Do not introduce `admin`. Unknown roles and
unknown actions fail closed. Authorization is centrally action-based, not scattered
direct role comparisons.

| Role | Approved CORE.1A actions |
| --- | --- |
| member | read Organization; list Projects; read Project; create Project; update Project; read own Membership |
| owner | all member actions; update Organization name; archive/deactivate Project |

Defer invitations, adding/removing Membership, changing Membership roles, deleting
Organization, destructive Project deletion, billing administration, and ownership
transfer/recovery.

Administrative Organization ownership is represented by active owner membership.
Do not add `organization.owner_user_id`. This authority does not imply payment
authority, legal ownership, authority to modify financial history, or authority over
future ledger records. Future owner transfer/removal must preserve at least one
active owner and requires a separately reviewed transactional workflow.

### Controlled Provisioning and Schema

Step 6 uses controlled/pre-provisioned Jous accounts. Authenticated but unknown
external identities remain denied. Authentication must not automatically create
User, Organization, Membership or Project. Self-service bootstrap/onboarding is a
later explicit operation. Never merge/link accounts by email. Preserve internal
Jous User UUID across future identity-provider changes.

No four-table schema change is approved for Step 6. No migration `0002`.
The current issuer/subject linkage is sufficient for initial single-provider identity.

### Step 7 Founder Decision: Approved Database Security Architecture

Status: APPROVED - Step 7 architecture; implementation remains separately authorized.

The founder approves the refined Step 7 architecture below. This decision does not
implement Step 7 or authorize database changes in this documentation task.

#### Runtime and Helper Roles

Use a dedicated restricted `jous_runtime` PostgreSQL LOGIN for application traffic,
separate from migration/admin credentials. The runtime role must have no schema or
table ownership, permanent-object DDL, role administration, BYPASSRLS, ability to assume privileged
roles, migration-history writes, or access to unrelated Supabase-managed objects.
Grant only minimum required privileges and verify effective grants and memberships.
Do not use Supabase service-role or migration/admin credentials as runtime credentials.

Use a dedicated minimal `jous_security_reader` NOLOGIN helper-owner role. Runtime
must have no membership in or ability to assume this role. Grant no automatic
future-table privileges. Keep Jous object ownership and migration/admin authority
separate from runtime and helper authority.

#### Founder-Approved PUBLIC TEMP Compatibility

Supabase managed PostgreSQL currently grants database TEMPORARY through PUBLIC.
Accept no effective TEMP, or solely PUBLIC-derived TEMP without grant option,
proved through database ACL evidence. Explicit runtime TEMP grants, memberships,
database ownership and ambiguous provenance fail closed. Database CREATE and
permanent schema CREATE remain prohibited, alongside all existing restricted-role,
object-ownership and data-privilege requirements. Do not alter shared PUBLIC or
Supabase-managed TEMP grants to accommodate Jous.

Jous does not require temporary objects in its normal runtime. PUBLIC-derived TEMP
is an explicitly accepted managed-platform residual capability: resource exhaustion,
name shadowing and pooled-session persistence remain risks. Current and future
privileged helpers must retain hardened search_path and schema-qualified protected
relations against pg_temp shadowing. This compatibility adjustment does not expand
MVP scope or alter tenant/RLS architecture, application permissions or provisioning.

#### Exactly Two Privileged Helpers

Approve exactly two narrowly privileged SECURITY DEFINER helpers:

- `resolve_user(issuer, subject)` returns only the internal User UUID or NULL for an
  exact issuer/subject match to an active existing User. It reads only the required
  `users` columns: `id`, `auth_issuer`, `auth_subject`, and `status`. No email lookup,
  normalization, fuzzy matching, account linking or provisioning is permitted.
- `organization_is_active(organization_id)` returns only whether the exact
  Organization UUID identifies an active Organization. It reads only
  `organizations.id` and `organizations.status` and returns false on missing or
  inactive records.

Neither helper may read Memberships or Projects, mutate data, provision records,
select tenants, or evaluate owner/member authorization. The helper-owner role
receives only the required schema usage and column reads, with explicit
role-specific SELECT policies. It receives no table ownership, writes, DDL,
privileged role memberships or BYPASSRLS.

Use fixed secure search paths, fully qualified objects, validated arguments and no
dynamic SQL. Revoke PUBLIC EXECUTE atomically and grant execution explicitly only
to runtime. Helpers must not be IMMUTABLE; use STABLE and PARALLEL UNSAFE initially.
Unexpected database faults remain failures handled by the safe application boundary.

The User resolver breaks the pre-identity bootstrap cycle. The Organization status
helper breaks the Membership/Organization policy cycle without privileged membership
evaluation. Membership status and recognized owner/member role eligibility remain
under ordinary runtime RLS. Runtime User reads after bootstrap are limited to the
required `id` and `status` columns.

#### Transaction Context and RLS

Use provider-neutral transaction-local `jous.user_id` and `jous.organization_id`.
Project ID remains an application/row scope, not database session context.

Verify the external credential, begin the transaction and initialize empty context,
resolve the active internal User, and establish User context. Normal runtime RLS
permits discovery only of that active User's active, recognized-role Memberships in
active Organizations. Validate the candidate Organization before establishing
Organization context, then revalidate Organization access and central action
permissions. Once Organization context exists, Membership visibility is additionally
restricted to that Organization. Client-selected identifiers alone confer no authority.

ENABLE and FORCE RLS on `users`, `organizations`, `organization_memberships` and
`projects`, with explicit role-specific policies and actual runtime-role validation.
Keep the policy dependency graph acyclic. Use command-specific permissive policies
with restrictive runtime isolation guards so future permissive policies cannot
silently broaden tenant access. Do not weaken or disable existing RLS.

Application authentication and central action authorization remain authoritative for
product permissions. RLS primarily provides tenant/data isolation and defense
against query mistakes; it does not replace owner/member action authorization.

The founder accepts that ordinary PostgreSQL transaction-local GUC context is not a
cryptographic boundary against an attacker possessing the raw runtime database
credential with arbitrary SQL execution. Such an attacker can forge context values;
RLS must not be represented as preventing that credential-compromise scenario.

Prove context initialization every transaction, parameterized values, transaction-local
lifetime, no persistent session identity, missing/malformed context denial,
rollback/exception/cancellation safety, sequential connection reuse safety and
concurrent tenant isolation with no pool leakage.

Keep Project RLS tenant-focused. Do not freeze Project archival/lifecycle semantics
in Step 7 and do not grant runtime Project `status` update capability in this step.
Existing application active-Project access checks remain in force.

#### Controlled Validation and Public CRUD Gate

Controlled real-runtime-login validation may use uniquely identified committed
temporary fixtures created administratively. Document deterministic cleanup, control
runtime mutations, clean up in reverse dependency order, and verify final migration
revision, database state and row counts against the recorded baseline. Validate
through the actual restricted runtime login, not only a privileged connection.

Public CRUD remains prohibited until Step 6 and Step 7 security evidence passes the
separate PUBLIC CRUD SECURITY GATE. Required evidence includes production credential
verification, safe mapping to active internal User, central action permissions,
dedicated runtime-role privileges, RLS policies, transaction context, real runtime-role
cross-tenant PostgreSQL tests, pooled-connection isolation, safe errors/logging and
absence of public impersonation or test routes. Passing the gate does not itself
authorize CRUD implementation.

No public onboarding or provisioning is authorized. This decision creates no roles,
policies or migration; Step 7 implementation and controlled infrastructure execution
remain separately authorized tasks.

### Preserved Invariants

No financial authority or mutable balance authority belongs in authentication/access
tables. Project remains the primary context/economic attribution boundary, neutral
to memory provider, model, supplier, gateway, routing and execution provider.
Authentication remains replaceable and suppliers remain below the adapter boundary.
These decisions authorize no inference, rewards, payments, wallet, context/memory
engine or Jous Auto execution.

---

# FINAL CORE.1A PRINCIPLE

> Build the foundation once, preserve Jous's economic and context architecture, and defer every behavior that does not need to exist yet.

CORE.1A succeeds when the next Jous systems can be added cleanly without undoing the foundation.
