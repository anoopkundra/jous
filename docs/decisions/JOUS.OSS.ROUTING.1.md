# JOUS.OSS.ROUTING.1 — Commodity Routing, Workspace Reuse & Routing R&D Boundary

**Status:** APPROVED ROADMAP / EVALUATION POLICY  
**Date:** 2026-10-23  
**Scope:** Documentation and candidate-evaluation policy only  
**Implementation authorization:** NO

---

## 1. Purpose

JOUS.OSS.ROUTING.1 defines how Jous may reuse commodity Workspace, gateway, routing, evaluation and context infrastructure without outsourcing Jous's differentiated economic authority.

Canonical engineering principle:

> **Don't rebuild commodity infrastructure. Build Jous IP.**

Canonical routing principle:

> **Commodity routing infrastructure executes routes. Routing research generates evidence. Jous owns the economic decision.**

This decision does not approve a package, version, production integration, schema change, runtime behavior, or dependency installation.

---

## 2. Jous-owned authority

Jous must retain authority over:

- Jous Ledger;
- Spend Intelligence;
- Project Economics;
- Provider/Supplier Economics;
- Customer Economic Profile;
- Effective-Cost Engine;
- Economic Routing;
- Jous Auto policy;
- completion/outcome economics;
- Rewards Engine;
- economic policies and explanations;
- savings methodology;
- attribution and reconciliation;
- and cost/economic evidence for credible completed work.

Commodity systems may provide infrastructure or evidence but must not redefine these semantics.

---

## 3. Target execution architecture

**Workspace → Platform API → Capability / Policy / Context Gates → Jous Economic Evaluation → RouteDecision / permitted execution → Commodity Gateway or Supply Adapter → Provider / Model → Usage + Outcome Evidence → Ledger / Project Economics / Learning**

Project/customer policy and Context Requirement are resolved before economic comparison of eligible routes.

A lower token price does not make a route eligible when it cannot preserve the context required for credible work.

---

## 4. Workspace reuse

Jous Workspace is a Jous-owned product surface.

Commodity implementation candidates should be evaluated before custom-building equivalent infrastructure:

| Capability | Candidate | Classification | Initial priority |
| --- | --- | --- | --- |
| UI primitives | shadcn/ui | ADOPT candidate | P0 Workspace |
| Chat/message/composer patterns | shadcn chatbot/template patterns | ADOPT SELECTIVELY | P0 Workspace |
| Streaming / AI interaction plumbing | Vercel AI SDK | ADOPT candidate | P0 Workspace |

Jous retains authority over Projects, Project Context UX, Jous Auto, Model Stack, Pinned Model, Spend Intelligence, Project Economics, economic explanations and customer policy.

Using commodity chat primitives does not make Jous a generic chatbot and does not transfer Workspace product authority.

---

## 5. Gateway and execution infrastructure

| Capability | Candidate | Classification | Boundary |
| --- | --- | --- | --- |
| Multi-provider gateway plumbing | Portkey OSS | EVALUATE / ADOPT candidate | Must remain below Jous economic and policy authority |
| Gateway alternative | LiteLLM Core | EVALUATE / ADOPT candidate | Same boundary; do not run both merely for architectural elegance |
| Supplier access | Hugging Face, Vercel AI Gateway, OpenRouter, BYOK, future direct suppliers | INTEGRATE | Replaceable supply routes |

Gateway-native behavior may perform delegated mechanical retry, failover, load balancing, health exclusion, streaming and provider transport selection.

It must not silently replace, reinterpret or broaden Jous economic/execution-policy authority.

---

## 6. Jous Auto V1

Jous Auto V1 is not dependent on learned routing.

For MVP it should be deterministic, versioned, auditable and explainable.

Conceptual ordering:

**Task → Project/Customer Policy → Context Requirement → Context Package → Capability Requirement → Eligible Logical Models → Eligible Supplier Routes → Jous Economic Evaluation → RouteDecision / permitted execution → Execution**

Approved evidence may include capability, context requirements, commercial eligibility, supplier availability, provider price, gateway/funding overhead, reliability, retries/fallback economics and other approved JEAC inputs.

Jous Auto V1 belongs within JOUS.USE.1 rather than creating a new implementation gate.

---

## 7. Outcome evidence

Jous should accumulate evidence sufficient to compare raw execution cost with effective credible-completion economics.

Evidence may include task/workload class, context requirement, context supplied, model, supplier/provider, inference/context/gateway/funding cost, latency, retries, fallback, escalation, success/failure, validation/acceptance evidence, completion grouping, measurable rework and effective completion cost.

Outcome evidence is accumulated across the approved implementation gates, especially USE.1, SPEND.1 and ROUTE.1.

No universal automated quality score is required by this decision.

---

## 8. Routing R&D

The following are research candidates, not production routing authority:

| Candidate | Classification | Intended use |
| --- | --- | --- |
| UIUC LLMRouter | RESEARCH | Routing experiments / evidence |
| RouteLLM | RESEARCH | Routing experiments / benchmarks |
| vLLM Semantic Router | RESEARCH | Semantic-routing research |
| Future AGI | EVALUATE / RESEARCH | Evaluation/tracing infrastructure where useful |
| LeanCTX | RESEARCH | Post-MVP context-optimization research |

Research promotion path:

**RESEARCH → candidate policy/signal → offline validation → shadow evaluation where approved → explicit production approval**

No research system may self-promote into production or directly override Jous customer/economic authority.

---

## 9. Classification model

For this decision:

- **BUILD** — Jous-owned differentiated product or authoritative control plane.
- **ADOPT** — commercially and operationally approved reusable infrastructure.
- **INTEGRATE** — replaceable external provider/service behind a Jous boundary.
- **RESEARCH** — isolated study/benchmarking; not a production dependency or authority.
- **DEFER** — intentionally excluded from current MVP work.

Candidate, EVALUATE or RESEARCH status is not approval to install or integrate.

---

## 10. Dependency-admission lifecycle

Candidate technologies should progress through:

**DISCOVERED → EVALUATING → APPROVED → ADOPTED**

Before APPROVED, evaluate at minimum:

- license and transitive-license obligations;
- security and maintenance posture;
- architecture fit;
- data/privacy and tenant boundaries;
- vendor/implementation lock-in;
- operational cost;
- Jous IP/authority boundary;
- and explicit need in the current implementation gate.

Only dependencies actually introduced into implementation belong in `docs/DEPENDENCIES.md`.

---

## 11. Production intelligence progression

The intended evolution is:

**Deterministic Jous Auto V1 → Outcome/Economic Evidence → Routing R&D → Offline/Shadow Candidate Intelligence → Explicit Approval → JOUS.INTELLIGENCE.1 Production Intelligence**

This decision does not authorize production learned routing.

JOUS.INTELLIGENCE.1 remains governed by the existing requirement that sufficient economic evidence exist and that production activation receive explicit approval.

---

## 12. Non-authorizations

This decision does not authorize:

- changes to frozen CORE.1A increments;
- schema or migration changes;
- package or lockfile changes;
- new runtime dependencies;
- production gateway adoption;
- production routing behavior;
- a new canonical EconomicDecision domain entity;
- replacement of existing RouteDecision vocabulary;
- provider-specific context authority;
- or edits to `docs/DEPENDENCIES.md` merely for speculative candidates.

---

## 13. Final decision

Jous will reuse commodity infrastructure aggressively where it does not compromise Jous authority.

Jous will build the economic, context-aware and customer-specific intelligence that differentiates the product.

> **Build the Jous Workspace; do not rebuild a generic chatbot framework.**

> **Use gateways to execute; do not let gateways become the economic brain.**

> **Use routing research to learn; do not let research systems become production authority without explicit approval.**

# END — JOUS.OSS.ROUTING.1
