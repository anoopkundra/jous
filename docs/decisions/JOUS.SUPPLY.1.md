# JOUS.SUPPLY.1 — MVP AI Supply Architecture & Supplier Benchmark Decision

**Status:** APPROVED ARCHITECTURE DECISION
**Project:** Jous
**Canonical Domain:** jous.si
**Repository:** anoopkundra/jous
**Decision ID:** JOUS.SUPPLY.1
**Updated:** October 4, 2026

---

## 1. Purpose

This document defines the approved MVP architecture for acquiring, abstracting, measuring, and eventually optimizing AI inference supply for Jous.

Jous must be able to use multiple AI suppliers without allowing any supplier, gateway, model marketplace, or routing platform to become the architectural owner of the customer relationship or Jous's economic intelligence.

The objective is not merely to connect Jous to AI models.

The objective is to establish a supplier-neutral foundation from which Jous can answer:

> **How should your next AI dollar be spent?**

This decision is based on architecture review and live technical/economic benchmarking of:

- Hugging Face Inference Providers
- Vercel AI Gateway
- OpenRouter
- BYOK as a first-class architectural route

Portkey remains the leading OSS gateway-plumbing candidate for Jous-owned infrastructure where appropriate, but gateway infrastructure must remain subordinate to Jous's own economic control plane.

---

## 2. Governing Principle

> **NO AI SUPPLIER DEPENDENCY ABOVE THE ADAPTER BOUNDARY.**

Jous must own the customer-facing economic relationship.

A supplier may provide inference.

A gateway may provide transport, retries, fallbacks, telemetry, or provider abstraction.

Neither may become the source of truth for Jous economics, customer balances, rewards, projects, model identity, customer execution policy, or routing policy.

The gateway is infrastructure.

Jous's differentiated intellectual property is expected to reside primarily in:

- Jous Ledger
- Jous Balance
- Spend Intelligence
- Project Economics
- Rewards Engine
- Customer Economic Profile
- Jous Model Registry
- Jous Economic Router
- Effective-Cost Optimization
- Rewards Marketplace
- Aggregated AI purchasing intelligence

The governing product question is:

> **How should your next AI dollar be spent?**

---

## 3. Architecture Decision

The MVP will use a supplier-neutral architecture.

```text
Jous Workspace / Jous API
            |
            v
     Jous Control Plane
    +--------------------+
    | Identity           |
    | Projects           |
    | Wallet / Ledger    |
    | Spend Intelligence |
    | Rewards            |
    +---------+----------+
              |
              v
      Jous Economic Router
              |
       Jous Model Registry
              |
     +--------+---------+
     |        |         |
     v        v         v
    HF    OpenRouter  Vercel
 Adapter    Adapter    Adapter
     |        |         |
     +--------+---------+
              |
              v
     Actual AI Providers
```

BYOK is another first-class supply route and must fit behind the same Jous-owned boundary.

Future direct provider adapters may include OpenAI, Anthropic, Google, Together, Fireworks, DeepInfra, or other suppliers when economics and scale justify direct relationships.

Jous must not require architectural redesign to add, remove, suspend, or replace a supplier.

---

## 4. Gateway Is Not Supply

Jous must explicitly distinguish between gateway infrastructure and AI supply.

Gateway infrastructure may include Portkey, Vercel AI Gateway, OpenRouter routing infrastructure, Hugging Face routing infrastructure, or LiteLLM. Gateway capabilities may include provider abstraction, retries, fallbacks, request transport, telemetry, provider selection, rate-limit handling, and resilience.

Actual inference may ultimately be delivered by providers such as DeepInfra, Novita, AWS Bedrock, Friendli, Featherless, Baidu, OpenAI, Anthropic, Google, Together, Fireworks, and other eligible providers.

The distinction matters because the gateway selected by Jous is not necessarily the entity economically producing the inference.

Jous must retain visibility into the actual supply route whenever technically available.

---

## 5. Jous-Owned Supplier Interface

Supplier integrations should converge on a Jous-owned conceptual interface.

Future adapters should support operations conceptually equivalent to:

```text
quote()
execute()
get_usage()
get_balance()
health()
capabilities()
```

The exact Python or TypeScript interface is an implementation decision for the appropriate engineering gate.

The architectural contract is what matters:

> Jous calls a Jous-owned supply abstraction. Supplier-specific behavior remains below that abstraction.

No customer-facing domain object should require a Hugging Face, Vercel, OpenRouter, Portkey, LiteLLM, or individual inference-provider identifier as its primary identity.

---

## 6. Model Identity Must Be Jous-Owned

Jous must distinguish:

1. Logical Model
2. Supplier Route
3. Supplier-Specific Model Identifier

For example, a logical Jous model may represent DeepSeek V3.2 while eligible execution routes may include the same underlying model through Hugging Face → DeepInfra, Hugging Face → Featherless, Vercel → DeepInfra, Vercel → Novita, Vercel → Bedrock, OpenRouter → GMICloud, OpenRouter → DeepInfra, and other eligible suppliers.

Changing the supplier route must not require changing the customer's Project or logical model identity.

This is necessary for future Jous Auto, Model Stack, Pinned Model, supplier failover, economic optimization, negotiated supply, BYOK, and provider migration.

---

## 7. Model Selection and Supplier Selection Are Separate Decisions

Jous must never collapse model selection and supplier selection into one architectural decision.

### Model Selection

Answers:

> Which logical model should perform this task?

Model selection may eventually consider customer execution policy, task type, required capability, Project Context, context-window requirement, model quality, customer preference, and model eligibility.

### Supplier Selection

Answers:

> Through which eligible supply route should Jous acquire this model execution?

Supplier selection may eventually consider price, JEAC, reliability, latency, health, funding overhead, commercial eligibility, inventory, rate limits, and fallback economics.

A customer may therefore control the model while Jous optimizes the supplier underneath it.

This separation is a frozen architectural requirement.

---

## 8. Supplier Categories

Jous should think about supply in categories rather than permanent vendor relationships.

### 8.1 Aggregators and gateways

Examples: Hugging Face Inference Providers, Vercel AI Gateway, and OpenRouter.

### 8.2 Frontier direct providers

Potential future examples: OpenAI, Anthropic, and Google. Direct relationships may become economically useful at sufficient scale.

### 8.3 Open-model inference providers

Potential examples: Together, Fireworks, DeepInfra, Novita, Groq, Cerebras, and Featherless.

### 8.4 Media inference

Potential future examples: fal and Replicate. These are outside the initial text-centric MVP unless separately approved.

### 8.5 Infrastructure / self-hosted supply

Potential future examples: NVIDIA NIM, dedicated GPU capacity, and self-hosted open models. These should only be considered when scale and economics justify operational complexity.

---

## 9. MVP Supply Constraints

The initial Jous supply architecture should optimize for learning, flexibility, and low working-capital requirements.

The MVP should avoid dependence on negotiated enterprise agreements before product validation, high minimum commitments, large prepaid supplier balances, dependence on one supplier, architecture tied to one gateway, unnecessary direct-provider integrations, premature GPU infrastructure, supplier-specific customer-facing model IDs, and supplier-controlled economic policy.

The MVP should favor suitable self-service commercial access where permitted, low or no minimum commitments, broad model availability, easy supplier replacement, observable usage, measurable supplier economics, first-class BYOK, and progressive optimization as Jous GMV grows.

Do not start by integrating every supplier.

---

## 10. Commercial Eligibility Is Separate From Technical Availability

A model or route being technically callable does not mean Jous has approved it for every commercial use.

Jous must maintain a commercial eligibility concept independent of technical health.

Canonical status vocabulary should support:

```text
UNREVIEWED
SELF_SERVICE_APPROVED
BYOK_ONLY
NEGOTIATED
RESTRICTED
DISABLED
```

Technical benchmark success is not blanket legal approval for resale, redistribution, or every future Jous business model.

Commercial rights must be validated separately when necessary.

---

## 11. Jous Model Registry

Jous should maintain a Jous-owned Model Registry rather than treating any supplier's catalog as canonical.

The registry should be capable of representing Jous logical model ID, model family, capabilities, context-window characteristics, modality, availability, commercial status, free eligibility, eligible supplier routes, supplier-specific model IDs, relevant pricing metadata, health state, and policy eligibility.

For Jous Free, the registry should additionally be capable of representing fields conceptually equivalent to:

```text
free_eligible
free_source
free_cost_to_jous
free_daily_limit
free_monthly_limit
availability
commercial_status
```

The exact schema is deferred to its implementation gate.

---

## 12. Supply Inventory

Supplier funding must not be modeled as if each customer owns an equivalent upstream supplier balance.

Jous should eventually maintain pooled supplier inventory.

Conceptually:

```text
Customer Wallet / Ledger != Supplier Credit Balance
```

Customer funding belongs to the customer economic ledger.

Supplier credits belong to Jous's supply inventory and treasury/operational management.

Future SupplyInventory should be capable of tracking supplier, account, available credit, reserved credit if applicable, replenishment threshold, funding method, funding overhead, expiration where applicable, and reconciliation state.

Customer deposits must not automatically cause 1:1 supplier purchases.

---

## 13. Benchmark Method

The initial supplier decision used live API tests rather than relying only on marketing claims or catalog pricing.

The benchmark sought evidence for authentication, OpenAI-compatible access where applicable, logical-model availability, forced provider selection, automatic provider selection, fallback/routing behavior, token usage, cost telemetry, provider visibility, funding economics, and supplier interchangeability.

DeepSeek V3.2 was used as a useful common model for cross-route testing where available.

The benchmark was intended to validate architecture and economics, not to select a permanent exclusive supplier.

---

## 14. Vercel AI Gateway Benchmark

### 14.1 Result

**Technical benchmark: PASS**

Vercel AI Gateway successfully provided OpenAI-compatible inference through:

`https://ai-gateway.vercel.sh/v1`

The benchmark validated both free and paid model execution.

A free request using `poolside/laguna-s-2.1-free` succeeded and exposed usage including cache-read tokens while showing zero inference cost for that request.

DeepSeek V3.2 paid inference also succeeded.

### 14.2 Funding observation

Observed Vercel credit purchases:

```text
$20.00 credits
$0.88 fee
$20.88 total
```

and:

```text
$500.00 credits
$14.80 fee
$514.80 total
```

These observations correspond to approximately `2.9% + $0.30` for the tested funding method.

This funding overhead is relevant to Jous economics and must not be ignored merely because inference prices appear inexpensive.

### 14.3 DeepSeek V3.2 observed provider pricing

The benchmark observed supplier options including approximately:

```text
DeepInfra
Input:      $0.26 / 1M tokens
Output:     $0.38 / 1M tokens
Cache read: $0.13 / 1M tokens

Novita
Input:      $0.27 / 1M tokens
Output:     $0.40 / 1M tokens
Cache read: $0.13 / 1M tokens

Bedrock
Input:      $0.62 / 1M tokens
Output:     $1.85 / 1M tokens
```

These are benchmark observations, not permanent Jous pricing assumptions. Pricing must be revalidated over time.

### 14.4 Forced provider test

The benchmark successfully forced DeepInfra using Vercel gateway provider options.

Observed request:

```text
29 input tokens
120 output tokens
cost = $0.00005314
```

This matched the expected underlying token economics.

### 14.5 Cost routing test

With Vercel routing configured for cost preference, the observed attempt sequence included:

```text
DeepInfra -> failure
Novita    -> failure
Bedrock   -> success
```

Observed final request cost:

`$0.00025293`

An immediate separately forced DeepInfra retry then succeeded.

This demonstrated that transient supplier failures occur; fallback improves reliability; fallback can materially increase economic cost; cheapest advertised provider is not always the provider that ultimately executes; and provider health cannot be treated as permanently binary.

### 14.6 Latency routing test

With TTFT-oriented routing, the observed ordering favored Bedrock before lower-cost routes.

Bedrock succeeded but was materially more expensive for the tested workload.

### 14.7 Vercel conclusion

Vercel demonstrated strong managed routing, resilience, and provider abstraction.

It is a strong managed supply/gateway route for Jous.

However:

> Vercel's routing objective is not automatically identical to Jous's economic objective.

Jous must therefore own the higher-level economic policy.

Vercel is an eligible supply route, not Jous's economic brain.

---

## 15. OpenRouter Benchmark

### 15.1 Result

**Technical/economic benchmark: PASS**

Authenticated catalog access returned hundreds of available models during the benchmark, including DeepSeek V3.2.

OpenRouter demonstrated particularly strong provider breadth, endpoint visibility, pricing visibility, supplier-market telemetry, and explicit routing controls.

### 15.2 Funding observation

Observed credit purchases:

```text
$10.00 credits
$0.80 service fee
$10.80 total
```

and an observed quote of:

```text
$500.00 credits
$27.50 fee
$527.50 total
```

The $500 observation represents a 5.5% funding/service overhead.

The small $10 purchase had an 8% effective overhead because of the observed fee structure.

These funding economics were materially less favorable than the observed Vercel and Hugging Face funding results.

### 15.3 Default inference

A default DeepSeek V3.2 request selected GMICloud.

Observed request:

```text
29 prompt tokens
105 completion tokens
cost = $0.0000385632
```

OpenRouter exposed detailed upstream cost information.

### 15.4 Provider economics

Observed DeepSeek V3.2 endpoint metadata included approximately:

```text
GMICloud
Input:  ~$0.2088 / 1M tokens
Output: ~$0.3096 / 1M tokens

DeepInfra
Input:      $0.26 / 1M tokens
Output:     $0.38 / 1M tokens
Cache read: $0.13 / 1M tokens

Friendli
Input:  $0.50 / 1M tokens
Output: $1.50 / 1M tokens
```

Friendli showed substantially better latency characteristics in the observed metadata but materially higher token pricing.

This again demonstrated the economic tradeoff among cost, latency, reliability, and provider availability.

### 15.5 Forced DeepInfra

Forced DeepInfra execution succeeded.

Observed request:

```text
29 input tokens
98 output tokens
cost = $0.00004478
```

### 15.6 Routing behavior

Observed `sort = "price"` selected GMICloud.

Observed `sort = "latency"` selected Friendli.

An explicit ordered provider test using Baidu followed by DeepInfra did not produce an actual fallback because Baidu unexpectedly succeeded.

This was itself useful evidence:

> A supplier health snapshot should be an input to routing and circuit-breaking, not an unquestioned permanent binary state.

### 15.7 Credit reconciliation

The OpenRouter credit endpoint exposed account-level credit and usage information.

An observed reconciliation showed approximately:

```text
total_credits = 10
total_usage   = 0.000411708
```

### 15.8 OpenRouter conclusion

OpenRouter is the strongest benchmarked route for broad provider-market visibility and supplier diversity.

It can be strategically useful for provider discovery, market intelligence, broad fallback, model availability, and supply benchmarking.

Its observed funding overhead, however, was materially higher than the alternatives tested.

Therefore:

> OpenRouter should remain an eligible Jous supply route and intelligence source, but Jous should not assume it is the economically optimal default route.

---

## 16. Hugging Face Inference Providers Benchmark

### 16.1 Result

**Technical/economic benchmark: PASS**

Authentication succeeded using a fine-grained Hugging Face token.

DeepSeek V3.2 provider metadata exposed routes including:

```text
featherless-ai: live
deepinfra:      live
novita:         error
```

The OpenAI-compatible inference endpoint used was:

`https://router.huggingface.co/v1/chat/completions`

### 16.2 Forced DeepInfra

The benchmark successfully pinned DeepInfra using the provider suffix:

`deepseek-ai/DeepSeek-V3.2:deepinfra`

Observed request:

```text
29 prompt tokens
109 completion tokens
138 total tokens
estimated_cost = $0.00004896
```

The observed economics were consistent with the same underlying DeepInfra token pricing seen through other benchmarked routes.

### 16.3 Automatic provider selection

A request without a provider suffix succeeded.

Observed request:

```text
29 prompt tokens
130 completion tokens
159 total tokens
estimated_cost = $0.00005694
```

Hugging Face usage reporting showed that the automatic route selected DeepInfra for the tested requests.

### 16.4 Supplier switching

The same logical model was then explicitly executed through Featherless:

`deepseek-ai/DeepSeek-V3.2:featherless-ai`

The request succeeded.

Observed usage:

```text
29 prompt tokens
146 completion tokens
175 total tokens
```

The Featherless response did not expose the same `estimated_cost` field.

This proved two important architectural points:

1. the same logical model can be deliberately switched between suppliers without changing the customer's intended model;
2. supplier cost telemetry is not guaranteed to be uniform.

Jous must therefore own its pricing registry and reconciliation logic rather than assuming every supplier returns complete cost information.

### 16.5 Funding observation

The benchmark purchased:

```text
$10.00 Hugging Face credits
$10.00 charged
```

No separate Hugging Face funding/platform surcharge was observed in this benchmark.

Purchased credits showed an expiration date of `2027-11-01`.

The account also included a small Free-account inference allowance.

Free allowances must not be treated as sustainable production economics.

### 16.6 Routed inference economics

Hugging Face documentation reviewed during the benchmark stated that routed Inference Providers are charged at the underlying provider rate without an additional Hugging Face markup for the routed inference.

BYOK is also supported.

Purchased Hugging Face credits may fund multiple eligible Hugging Face pay-as-you-go services.

Therefore Jous must treat those credits as Hugging Face account inventory rather than as inventory belonging specifically to DeepInfra.

### 16.7 Required economic wording

The benchmark supports the statement:

> **No Hugging Face funding/platform surcharge was observed in our benchmark.**

It does **not** justify the broader statement:

> "Hugging Face has no overhead cost."

Jous may still incur customer payment-processing cost, inference cost, operational cost, reconciliation cost, retry/failure cost, and internal infrastructure cost.

### 16.8 Hugging Face conclusion

Among the routes benchmarked, Hugging Face showed particularly attractive observed economics for open-model supply.

It demonstrated authentication, OpenAI-compatible execution, DeepSeek V3.2 availability, automatic provider selection, forced DeepInfra selection, forced Featherless selection, supplier switching without logical-model change, token usage reporting, provider-dependent cost telemetry, no observed surcharge on the tested $10 funding transaction, and BYOK support.

Therefore:

> Hugging Face is the preferred initial economic/open-model supply candidate based on current observed benchmark economics, subject to continuing validation of availability, pricing, commercial terms, reliability, and supplier behavior.

This is not an exclusive or permanent supplier decision.

---

## 17. BYOK Is a First-Class Route

Bring Your Own Key must not be treated as an afterthought.

BYOK allows a customer to supply credentials for an eligible provider while Jous continues to provide appropriate control-plane capabilities.

Potential benefits include lower Jous working-capital requirements, customer use of existing provider agreements, enterprise flexibility, easier onboarding for customers with existing commitments, reduced supply concentration, and a useful free-tier acquisition path.

BYOK does not eliminate Jous's value.

Jous may still provide, where applicable, Projects, Spend Intelligence, Project Economics, usage normalization, model control, Project Context, routing controls, and economic visibility.

Provider credentials must eventually be securely stored, encrypted, scoped, auditable, and revocable.

Those credential-management details are outside CORE.1A unless separately approved.

---

## 18. Jous Free Supply Architecture

JOUS.FREE.1 should operate through the same supplier-neutral architecture.

Free supply may come from three economic sources:

1. Supplier-funded or zero-cost supply — preferred when commercially eligible and sustainable.
2. Jous-funded promotional supply — capped, measured, attributable, and abuse-controlled.
3. BYOK — the customer pays the underlying provider while Jous supplies the economic/control layer.

Free requests must only use routes satisfying conditions conceptually equivalent to:

```text
free_eligible = TRUE
commercial_eligible = TRUE
```

Jous must not promise unlimited free AI.

Supplier availability, free programs, model availability, and limits can change.

---

## 19. Free Usage Must Still Be Economically Observable

A customer charge of zero does not mean an execution has zero economic cost.

Every future free execution should still create the appropriate usage/economic evidence, including UsageEvent, Project attribution, logical model, supplier route, supplier usage, supplier cost where known, Jous promotional cost where applicable, and free-source classification.

This allows Jous to measure:

`Free acquisition cost ÷ free-to-funded conversion rate = CAC per funded builder`

---

## 20. Jous Economic Router

The Jous Economic Router is a Jous-owned decision layer.

It must not simply expose another gateway's auto mode as Jous Auto.

Potential routing objectives include:

### Jous Economy

Lowest expected effective acquisition cost subject to required capability and reliability.

### Jous Fast

Prioritize time-to-first-token and completion latency within customer constraints.

### Jous Balanced

Weighted evaluation of economics, reliability, latency, and capability.

This is the preferred conceptual initial general-purpose routing posture.

### Jous Auto

Jous Auto is broader than supplier routing.

Its long-term canonical flow is:

```text
Task Understanding
        ->
Customer / Project Execution Policy
        ->
Context Requirement
        ->
Context Retrieval
        ->
Context Assembly
        ->
Context Optimization
        ->
Capability Requirement
        ->
Context-Window Requirement
        ->
Eligible Model(s)
        ->
Customer Model Preference
        ->
Eligible Supplier Routes
        ->
Economic Evaluation
        ->
Execution
        ->
Measured Outcome
```

Jous Auto belongs to Jous.

---

## 21. Effective-Cost Routing

Raw token price is not sufficient for economic routing.

The canonical economic metric is defined in JOUS.ECON.1 as Jous Effective Acquisition Cost (JEAC).

Supplier architecture must expose enough evidence for the economic layer to eventually evaluate factors such as inference price, funding overhead, gateway/platform cost, supplier incentives, failure probability, retries, fallback behavior, latency where economically relevant, and operational overhead attributable to execution.

The precise accounting boundary belongs to JOUS.ECON.1 and later economic implementation gates.

JOUS.SUPPLY.1 must not independently redefine that accounting authority.

Long-term optimization should move toward:

> **JEAC per successful task**

rather than merely cost per million tokens.

---

## 22. Reliability Has Economic Value

The Vercel benchmark demonstrated why reliability cannot be separated from economics.

A nominally cheap route that fails and triggers an expensive fallback may produce a higher realized cost than a slightly more expensive but reliable route.

Future Jous routing should therefore be capable of incorporating supplier health, recent failure rate, latency, timeout probability, fallback probability, fallback cost, and rate-limit conditions.

Potential future controls may include:

```text
max_fallback_cost_multiplier
max_absolute_task_cost
minimum_provider_health
maximum_latency
```

Exact policies are deferred.

---

## 23. Supplier Health Is Not a Permanent Binary

The benchmark produced examples where a provider appeared unavailable in one context but succeeded immediately afterward or succeeded despite a prior health indication.

Therefore supplier health should eventually be treated as a dynamic signal.

Potential inputs include recent request success, recent failure, timeout rate, provider status, gateway status, rate limits, observed latency, and circuit-breaker state.

Jous should avoid permanently excluding a supplier based solely on one transient failure or one external status snapshot.

---

## 24. Cost Telemetry Must Be Reconciled

Not every supplier exposes cost information in the same way.

The benchmark demonstrated detailed cost telemetry from some routes, estimated cost from some Hugging Face routes, missing cost telemetry from another successful Hugging Face provider route, and account-level reconciliation information from supplier platforms.

Therefore Jous must eventually support multiple sources of cost truth:

1. request-level supplier telemetry;
2. Jous pricing registry;
3. supplier usage records;
4. supplier account reconciliation.

A supplier-returned `cost` field must not become the sole accounting authority.

---

## 25. Funding Overhead Is Part of Supply Economics

Supplier credit acquisition can itself have economic cost.

Observed benchmark funding examples:

```text
Vercel
$20 credits  -> $20.88 total
$500 credits -> $514.80 total

OpenRouter
$10 credits  -> $10.80 total
$500 credits -> $527.50 total

Hugging Face
$10 credits  -> $10.00 total observed
```

These observations are snapshots, not permanent contractual rates.

They nevertheless prove:

> Two routes offering the same underlying inference price can have different effective acquisition economics.

Jous must therefore consider funding overhead when evaluating supplier economics.

---

## 26. Initial MVP Supply Decision

Jous will **not** select one permanent exclusive supplier.

The approved initial posture is:

### Hugging Face

Role: **Preferred initial economic/open-model supply candidate.**

Reasons include attractive observed funding economics, underlying-provider-rate routed inference, multiple provider routes, provider pinning, automatic selection, BYOK support, and demonstrated supplier interchangeability.

### Vercel AI Gateway

Role: **Strong managed routing, resilience, and performance route.**

Reasons include strong provider abstraction, reliable gateway experience, explicit provider controls, fallback behavior, and useful cost/latency routing capabilities.

Constraint: Jous must not delegate its economic objective to Vercel's default routing policy.

### OpenRouter

Role: **Broad supplier marketplace, fallback option, and market-intelligence route.**

Reasons include exceptional provider/model breadth, strong pricing and endpoint visibility, routing controls, and useful supplier-market telemetry.

Constraint: observed funding overhead was materially higher than the other tested routes.

### BYOK

Role: **First-class customer-controlled supply route.**

Reasons include reduced Jous working-capital burden, support for customers with existing provider relationships, improved portability, and reduced supplier concentration.

---

## 27. Portkey and LiteLLM

Jous should avoid rebuilding commodity gateway infrastructure where mature permissively licensed OSS is appropriate.

Portkey OSS is the current primary candidate for Jous-owned multi-provider gateway plumbing. Potential responsibilities include request transport, provider abstraction, retries, fallbacks, observability plumbing, and gateway-level controls.

Portkey must not own Jous customer economics, Jous Model Registry authority, JEAC, Jous Rewards, customer execution policy, Jous Auto, or Project Economics.

LiteLLM Core remains a viable alternative. Only permissively licensed core components may be considered. Separately licensed enterprise components must not be imported into Jous without explicit legal and architectural review.

Do not unnecessarily fork an entire gateway.

Use gateway infrastructure where useful while keeping the Jous economic and domain layer independent.

---

## 28. Supplier Adapter Invariants

The following invariants are frozen:

1. No supplier dependency above the adapter boundary.
2. Jous owns logical model identity.
3. Supplier model IDs are not customer domain IDs.
4. Model Selection and Supplier Selection remain separate.
5. A supplier may be added or removed without redesigning Project.
6. A supplier may be added or removed without redesigning Wallet or Ledger.
7. A supplier may be added or removed without redesigning Rewards.
8. Jous Auto remains Jous-owned.
9. BYOK remains a first-class route.
10. Commercial eligibility remains separate from technical availability.
11. Supplier cost telemetry is evidence, not sole accounting authority.
12. Supplier inventory remains separate from customer balances.
13. Free inference remains economically observable.
14. Supplier health is dynamic.
15. Funding overhead may affect effective supplier economics.
16. Gateway routing objectives must not silently replace Jous economic policy.
17. Supplier switching must not destroy Project Context.
18. Customer execution policy constrains optimization.

---

## 29. CORE.1A Implications

JOUS.CORE.1A must preserve this architecture without prematurely implementing it.

CORE.1A should establish only the minimum supplier-neutral seams necessary to prevent future redesign.

It may define neutral supplier contract types, logical model identity concepts, supplier route identity concepts, execution-policy vocabulary, and test doubles proving supplier neutrality.

CORE.1A must NOT execute real paid inference, implement production Hugging Face/Vercel/OpenRouter integrations, implement production BYOK credential storage, implement Jous Auto, implement JEAC routing, implement supplier inventory, fund supplier accounts, perform production fallback, or make Portkey or LiteLLM an architectural authority.

The objective of CORE.1A is architectural readiness, not supplier functionality.

---

## 30. Later Implementation Sequence

Subject to the governing MVP implementation plan, later gates may progressively add:

```text
CORE.1A
Foundation and neutral seams
        ->
CORE.1B / CORE.1C
Ledger and wallet authority
        ->
SUPPLY implementation
Supplier adapters and usage normalization
        ->
FREE.1
Free inference acquisition layer
        ->
USE.1
Workspace execution
        ->
ROUTE.1
Jous API and economic routing
```

Exact sequencing remains governed by JOUS.MVP.0 and gate-specific specifications.

---

## 31. What Is Not Decided Here

JOUS.SUPPLY.1 does not freeze permanent supplier market share, permanent provider prices, negotiated enterprise pricing, reseller rights not yet validated, future direct-provider contracts, exact adapter programming language, exact gateway deployment topology, permanent Portkey adoption, permanent LiteLLM rejection, supplier-specific routing weights, production JEAC formula implementation, customer reward percentages, free-tier limits, exact model catalog, exact fallback thresholds, or exact supplier replenishment thresholds.

These should remain configurable or separately governed.

---

## 32. Revalidation Requirement

Supplier economics and capabilities change.

Jous should periodically revalidate provider availability, model availability, token pricing, funding fees, commercial terms, rate limits, provider quality, latency, reliability, telemetry, BYOK support, and supplier incentives.

A supplier's current benchmark position is evidence for today's architecture decision, not a permanent entitlement to Jous traffic.

---

## 33. Strategic Interpretation

The benchmark demonstrates that AI inference is increasingly a competitive supply market.

The same logical model can often be obtained through multiple routes with materially different prices, funding costs, latency, reliability, fallback behavior, and telemetry.

That fragmentation is not merely an integration problem.

It creates an economic optimization opportunity for Jous.

Jous should therefore avoid becoming another thin model proxy.

The opportunity is to combine customer economic identity, AI spend, Projects, Project Context, model control, supplier flexibility, effective-cost intelligence, rewards, and aggregated demand into a durable customer economic relationship.

---

# FINAL JOUS.SUPPLY.1 DECISION

Jous will use a supplier-neutral AI supply architecture.

Hugging Face, Vercel AI Gateway, OpenRouter, BYOK, and future direct suppliers are **replaceable supply routes**, not owners of the Jous customer relationship.

Based on the completed benchmark:

- **Hugging Face** is the preferred initial economic/open-model supply candidate.
- **Vercel AI Gateway** is the strongest managed routing/resilience route tested.
- **OpenRouter** is the strongest broad supplier-marketplace and market-intelligence route tested.
- **BYOK** is a required first-class architectural route.
- **Portkey OSS** remains the leading candidate for commodity gateway plumbing where Jous-owned infrastructure is appropriate.
- Jous will not select a permanent exclusive supplier at the MVP stage.

The benchmark does not grant blanket commercial approval. Technical availability and commercial eligibility remain separate.

Jous owns the customer relationship, logical model identity, Project economics, execution policy, economic routing, rewards, supplier reconciliation, and effective-cost intelligence.

The supplier provides inference.

The gateway provides infrastructure.

> **The gateway is not the moat. The economic relationship with the AI builder is the moat.**

# END — JOUS.SUPPLY.1
