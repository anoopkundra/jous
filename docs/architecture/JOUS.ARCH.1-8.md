# JOUS.ARCH.1–8 — Jous Platform Architecture Baseline

Status: APPROVED ARCHITECTURE BASELINE

Founder approval: October 2026

This document is Jous's long-term architectural constitution. It constrains
future architecture but does not authorize implementation of every capability
described here. Individual capabilities remain subject to separately approved
architecture, security, economic and implementation gates.

Architecture does not imply scope. JOUS.ARCH.1–8 preserves future
architectural optionality; JOUS.MVP.0 remains the authoritative boundary
for current MVP implementation scope.

No capability described in JOUS.ARCH.1–8 may enter the MVP merely because
it is represented in this architecture. Any MVP scope expansion requires an
explicit amendment to JOUS.MVP.0 and founder approval.

ARCH.1–8 does not supersede JOUS.CORE.1A. It constrains and extends Jous's future
architecture around the CORE.1A foundation. Future capabilities described here
must not be presented as implemented capabilities.

## 0. Architectural North Star

Jous is not merely an AI gateway, model router, wallet, rewards program or memory
system. Its canonical direction is:

> Jous is the economic, context and governance control plane between customers
> and the AI ecosystem.

Customers should eventually be able to build through Jous directly or through
external tools while retaining:

- economic visibility;
- economic optimization;
- Project attribution;
- model choice;
- supplier independence;
- rewards;
- context continuity;
- policy control;
- portable authorized AI context.

The conceptual separation is:

```text
Customer → Work / Context → Economic Decision → AI Execution
```

Jous owns the control plane. Providers, gateways and memory engines remain
replaceable infrastructure beneath the Jous-owned customer relationship.

Future execution surfaces may include Jous Workspace, API, SDK, MCP, IDE
integrations, agents, app-building platforms and enterprise applications. They
must not create separate economic or context control planes.

## ARCH.1 — Jous Economic Control Plane

Jous owns a provider-independent economic control plane around AI consumption.
The canonical hierarchy is:

```text
Jous Platform → Organization / Tenant → Project → Authorized Actor → Request / Execution
```

Organization is the canonical Jous tenant and primary customer security and
data-isolation boundary. Project is the primary work, context-continuity and
economic-attribution boundary.

A solo builder may use a one-person Organization; an enterprise may use an
enterprise Organization. There must not be separate personal and enterprise
tenancy architectures.

The Jous control plane may eventually own or coordinate:

- customer identity, Organizations and Projects;
- usage and Project Economics;
- Jous Balance, ledger and rewards;
- supplier economics and Customer Economic Profile;
- model registry and execution policy;
- context policy and routing decisions;
- reconciliation.

The following economic concepts remain distinct:

```text
Customer Charge != Supplier Cost != JEAC != Routing Savings != Jous Rewards != Funding Bonus
```

No future execution surface may create a parallel economic system.

## ARCH.2 — Routing & Execution Intelligence

Jous owns the economic and routing decision. Gateways may provide routing
mechanics but are not authoritative for Jous economic policy.

The conceptual flow is:

```text
Task Understanding
→ Customer / Project Execution Policy
→ Context Requirement
→ Capability Requirement
→ Logical Model Eligibility / Preference
→ Supplier Eligibility
→ Economic Evaluation
→ Execution
```

Logical Model != Supplier. Provider-specific model IDs must not become Jous
canonical model IDs. Logical model selection and supplier selection remain
separate decisions.

The execution-policy vocabulary remains:

| Mode | Architectural meaning |
| --- | --- |
| JOUS_AUTO | Jous selects an eligible logical model and supplier route within customer constraints. |
| MODEL_STACK | The customer defines ordered logical-model preferences. Jous may optimize eligible supplier selection underneath permitted logical models. |
| PINNED_MODEL | The customer pins a logical model. Jous may optimize eligible supplier selection underneath that model. Cross-model fallback requires explicit customer permission. |

> Customer policy constrains optimization. Jous optimizes within those constraints.

Routing maturity may progress through Observe → Shadow Decide → Decide → Execute.
Autonomous routing authority must not be assumed before sufficient evidence exists.

JEAC remains central. The long-term objective should evolve toward **JEAC per
successful task**, rather than token price alone. This does not redefine JEAC's
approved accounting scope or silently merge it with future task-cost metrics.

> Jous optimizes customer value, not merely Jous margin.

## ARCH.3 — Rewards Economics

> Rewards must be funded by measurable economic capacity, not by a permanently
> fixed percentage of gross AI spend.

Keep these reward categories separate:

- Usage Rewards;
- Funding Bonus;
- Promotional / CAC Rewards;
- Partner-Funded Rewards.

Possible future funding sources include routing economics, supplier discounts,
negotiated economics, funding-method savings, provider-funded promotions,
partner-funded offers and approved Jous CAC/promotions.

Jous Balance and Jous Rewards remain separate. Initial Rewards architecture
remains compatible with rewards being non-cash, non-withdrawable,
non-transferable, restricted where applicable and expiring where applicable.

Do not freeze a universal reward percentage. Reward decisions must be
reproducible from economic evidence, eligibility and applicable rule versions.

## ARCH.4 — Customer Economic Profile

Jous develops customer economic intelligence independently of gateway
infrastructure. Potential facts include:

- AI usage and Project patterns;
- provider and model preferences;
- BYOK relationships and known credits;
- funding method and rewards eligibility;
- economic constraints;
- execution preferences and policy constraints.

Provenance must distinguish customer-entered facts, supplier-reported facts,
Jous-observed facts, Jous-derived/inferred facts and negotiated Jous economics.
Inferred facts must not silently become customer-declared facts. Material facts
used for economic decisions should be reproducible.

The following concepts remain separable:

```text
Actor != Tenant != Project != Payer != Context Owner != Reward Beneficiary != Supplier
```

Do not allow `user_id` to become the universal ownership or economic foreign key
for all future domains.

## ARCH.5 — Provider Economics Network

The long-term flywheel is:

```text
More Builders
→ More AI Spend Through Jous
→ Greater Aggregated Demand
→ Better Provider Economics
→ Better Effective Customer Economics / Rewards
→ More Builders
```

> NO AI SUPPLIER DEPENDENCY ABOVE THE ADAPTER BOUNDARY.

Suppliers and gateways remain replaceable. Models use Jous logical identities.
Commercial eligibility remains distinct from technical availability. Customer
economics and supplier economics remain separate.

Customer deposits must not imply 1:1 purchases of credits from one provider.
Future supplier inventory may be managed as pooled economic capacity.

Jous may eventually become a demand aggregator and economic distribution channel
for AI providers and adjacent builder infrastructure. Negotiated supplier
economics must not become an MVP dependency.

## ARCH.6 — Jous API / SDK / MCP Platform

Jous should eventually expose its control plane to external builders,
applications and platforms. Potential consumers include IDEs, app-building
platforms, AI applications, agents, enterprise systems, developer tools, MCP
clients and MCP hosts.

External surfaces may consume economics, model access, routing, Spend
Intelligence, Project Economics, context continuity and governance.

API / SDK is a machine-speed execution interface. MCP is a standardized
capability and context integration surface. MCP must not be assumed to replace
the high-throughput inference API.

All execution surfaces converge on the same control plane:

```text
Organization
→ Project
→ Authorization
→ Execution Policy
→ Context Policy
→ Logical Model Registry
→ Supplier Abstraction
→ UsageEvent
→ Economics
→ Ledger
→ Rewards / Reconciliation
```

### Future Machine Identity

Current User represents the CORE.1A human/customer identity. Do not create fake
human User records for service principals, applications, agents, MCP clients or
machine identities.

Future architecture may introduce a Principal / Actor abstraction, with possible
actor types User, Service Principal, Application and Agent. This is an extension
seam, not authorization to add those tables now.

## ARCH.7 — Ledger, Trust & Intelligence Moat

Jous's defensibility compounds from trustworthy economic and execution history.
The long-term evidence graph may relate the following, where legally and
appropriately collected:

```text
Customer → Project → Task → Context → Logical Model → Supplier → Usage
→ JEAC → Customer Charge → Savings → Rewards → Outcome Evidence
```

Jous Ledger remains append-only, double-entry and reconstructable. Never use
mutable `user.balance` or equivalent as financial authority. Corrections require
compensating entries.

Distinguish estimates, provisional evidence, supplier-reported evidence,
reconciled evidence and settled financial facts.

The future trust trail should support reconstructing:

- what happened;
- who or what authorized it;
- the applicable policy;
- the permitted context;
- model/supplier execution;
- economic cost and customer charge;
- reward rationale.

The conceptual trust layers are Policy Trail + Decision Trail + Economic Trail.

> The gateway is not the moat.

The moat develops from the customer economic relationship, trustworthy history,
aggregated demand, Project intelligence, context continuity, provider economics,
the rewards network and execution intelligence.

## ARCH.8 — Context Fabric, Enterprise Data Control and Privacy

Context becomes a first-class Jous control-plane capability. It is not merely
chat memory. The long-term concept is **Jous Context Fabric**.

It may carry useful, authorized context across models, suppliers, sessions, Jous
Workspace, agents, IDEs, external applications and enterprise environments.
Project remains the primary context-continuity boundary.

Potential Project context includes conversations, instructions, decisions,
source material, Project State, derived memory, Working Context, preferences,
constraints and execution policies.

A memory engine is never authoritative for Organization identity, Project
identity, authorization or financial state. Memory/context providers remain
replaceable.

### Source Context vs Derived Memory

Source/original context and derived/summarized memory remain distinguishable.
Derived memory must not silently overwrite source truth. Preserve provenance
where material.

### Permission Before Retrieval

Enterprise context flow should conceptually be:

```text
Identity
→ Tenant
→ Project
→ Authorization
→ Purpose
→ Data Classification / Policy
→ Eligible Context Retrieval
→ Context Assembly
→ Execution
```

> Permission precedes retrieval.

Do not design enterprise context as retrieve-everything-first and filter later.

### Customer Data Control Modes

Future architecture should be capable of supporting:

| Mode | Architectural meaning |
| --- | --- |
| JOUS-HOSTED | Jous stores permitted context. |
| CUSTOMER-CONTROLLED | Customer policy governs what Jous may store, retrieve and use. |
| CUSTOMER-HOSTED | Underlying context remains in customer-controlled infrastructure; Jous retrieves permitted material when authorized. |
| METADATA-ONLY | Jous retains appropriate metadata, policy and provenance required for orchestration while underlying content remains outside Jous. |

These are future architecture modes, not authorization to implement them in CORE.1A.

### Enterprise Governance

Future architecture should be extensible for:

- least privilege and segregation of duties;
- access policies and approval boundaries;
- data classification and purpose limitation;
- retention and residency;
- provenance and lineage;
- deletion handling;
- policy versioning;
- administrative audit.

Current owner/member roles remain foundational membership roles. They are not
the complete future enterprise authorization system. Possible future
capabilities may distinguish security administration, billing administration,
context administration, auditing, development, approval, procurement and
operations. Do not add these roles now.

### SOX-Supporting Controls

Jous does not claim SOX compliance or certification. Architecture should be
capable of supporting applicable controls for access segregation, privileged
operations, change management, approval evidence, economic reconciliation,
immutable financial evidence, policy/version evidence and audit trails.

The intended wording is **SOX-supporting control architecture where applicable**.

### Consumer Privacy

Architecture should anticipate applicable privacy obligations and principles
reflected in CCPA/CPRA and other relevant regimes. Future architecture should be
capable of supporting, where applicable, access, correction, deletion,
portability/export, purpose limitation, retention controls, provenance and
derived-data propagation.

Privacy deletion must not be implemented by silently destroying
financial/accounting evidence that Jous is legitimately required to retain.
Future architecture should permit separation between personal identity / PII
linkage and immutable financial evidence. Do not place unnecessary PII in the
ledger. Architectural capability alone does not establish legal compliance.

### Residency

Future policy may express:

```text
Organization → Data Policy → permitted storage / execution / residency constraints
```

Project-level scoping may apply where appropriate. CORE.1A does not need
multi-region infrastructure, but domain architecture must not unnecessarily
assume every tenant's data must permanently live in one physical database or
location.

### Context Portability

Portable context does not mean indiscriminately exporting customer secrets.
Future architecture should distinguish potentially portable instructions,
decisions, preferences, approved references, Project State, selected history and
derived memory from restricted/nonportable credentials, secrets, restricted
enterprise data and policy-prohibited content.

Customer policy should increasingly control portability.

### Context Economics

Context creates economic cost through token consumption, latency, model
requirements and inference cost. Future Jous intelligence may optimize:

> What is the smallest authorized context package that preserves enough
> information to successfully complete the task?

This may eventually connect Context Quality + Token Economics + Model Capability
+ JEAC + Task Success. It is potential differentiated Jous IP. Do not implement
it in CORE.1A.

## Cross-ARCH Constitutional Invariants

1. Organization is the canonical tenant/security boundary.
2. Project is the primary work, context-continuity and economic-attribution boundary.
3. User is currently a human identity, not the permanent universal actor abstraction.
4. Actor, Tenant, Project, Payer, Context Owner, Reward Beneficiary and Supplier remain separable concepts.
5. No AI supplier dependency exists above the adapter boundary.
6. Logical model and supplier are separate identities.
7. Customer execution policy constrains optimization.
8. Workspace/API/SDK/MCP/IDE integrations use one Jous control plane.
9. No execution surface creates a parallel economic system.
10. Ledger remains append-only, double-entry and reconstructable.
11. Jous Balance and Jous Rewards remain distinct.
12. Customer economics and supplier economics remain distinct.
13. Context/memory providers never become authoritative for Organization, Project, authorization or financial state.
14. Permission precedes enterprise context retrieval.
15. Source truth and derived memory remain distinguishable.
16. Context provenance is preserved where material.
17. Enterprise authorization remains extensible beyond foundational owner/member membership roles.
18. Privacy lifecycle and immutable financial evidence remain architecturally separable.
19. Residency, retention, purpose, classification and governance belong in policy layers rather than being scattered arbitrarily through core domain tables.
20. Commodity infrastructure remains replaceable.

The overarching invariant is:

> Jous owns the customer economic, context and governance relationship;
> providers, gateways and memory engines are replaceable infrastructure
> underneath that relationship.

## Non-Authorization / Deferred Implementation

Approval of ARCH.1–8 does not authorize immediate implementation of:

- enterprise IAM;
- service principals;
- Principal/Actor tables;
- context-store tables;
- generalized policy tables;
- residency infrastructure;
- multi-region databases;
- privacy request engines;
- SOX workflows;
- MCP infrastructure;
- customer-hosted memory;
- context marketplaces;
- autonomous routing;
- generalized rewards marketplace.

These require separately approved gates. Do not create speculative scaffolding
merely because these capabilities exist in the long-term architecture.

## Relationship to Existing Architecture

The conceptual hierarchy is:

```text
JOUS.ARCH.1–8 — Long-term architectural constitution
↓
JOUS.MVP.0 — Product and implementation boundary
↓
JOUS.CONTEXT.1 / JOUS.SUPPLY.1 / JOUS.ECON.1 — Domain architecture decisions
↓
JOUS.CORE.1A — Current foundation implementation gate
↓
Migrations / Code
```

ARCH.1–8 does not supersede approved domain decisions automatically. This
hierarchy does not silently resolve conflicts or rewrite existing authority
orders. Any discovered conflict must go through ARCH.GAP.1 or a later explicit
architecture decision. ARCH.1–8 does not supersede JOUS.CORE.1A.

## ARCH.GAP.1 — Required Reconciliation Gate

Before the first managed CORE.1A Step 7 database mutation, Jous will perform
**ARCH.GAP.1**.

Its purpose is to reconcile this canonical ARCH.1–8 baseline against:

- JOUS.MVP.0;
- JOUS.CONTEXT.1;
- JOUS.SUPPLY.1;
- JOUS.ECON.1;
- JOUS.CORE.1A;
- migration 0001;
- migration 0002;
- current implementation.

ARCH.GAP.1 findings use these classifications:

| Classification | Meaning |
| --- | --- |
| PASS | Consistent with the approved baseline; no gap identified. |
| DOCUMENTATION | Documentation reconciliation is required. |
| CODE-BEFORE-DB | A code/security gap must be resolved before managed Step 7 mutation. |
| FUTURE-MIGRATION | A schema change belongs to a separately reviewed future migration. |

Any CODE-BEFORE-DB finding blocks managed Step 7 mutation until resolved.
ARCH.GAP.1 is a review gate, not authorization to implement deferred capabilities
or execute managed changes.
