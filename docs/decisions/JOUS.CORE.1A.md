# JOUS.CORE.1A — Foundation & Domain Architecture Gate

**Status:** PROPOSED — READY FOR FOUNDER REVIEW  
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

# FINAL CORE.1A PRINCIPLE

> Build the foundation once, preserve Jous's economic and context architecture, and defer every behavior that does not need to exist yet.

CORE.1A succeeds when the next Jous systems can be added cleanly without undoing the foundation.
