# JOUS.CONTEXT.1 --- Project Context, Memory & Execution Policy Architecture

**Status:** APPROVED ARCHITECTURE DECISION --- IMPLEMENTATION ENGINE NOT
YET SELECTED\
**Decision:** JOUS.CONTEXT.1\
**Project:** Jous\
**Repository:** `anoopkundra/jous`\
**Depends on:** JOUS.SUPPLY.1, JOUS.ECON.1, JOUS.MVP.0 v2\
**Implementation begins after:** JOUS.CORE.1A foundation\
**Updated:** October 4, 2026

------------------------------------------------------------------------

# 1. Purpose

JOUS.CONTEXT.1 defines how Jous preserves useful project continuity
while remaining independent of any AI model, model provider, inference
supplier, gateway, memory engine, or context vendor.

Jous targets serious AI builders whose projects may accumulate
conversations, architecture decisions, code, documents, research, tests,
requirements, current state, completed work, unresolved issues,
preferences, instructions, and connected sources over months or years.

> **Jous owns context continuity. Models and suppliers are replaceable
> execution resources.**

> **Optimize context before optimizing model price.**

The cheapest call is not economically optimal if insufficient or
incorrect context causes poor answers, repeated prompts, rework, extra
inference, incorrect code, stale recommendations, or failed tasks.
Context intelligence is therefore part of Jous's economic optimization
system, not merely chat history.

# 2. Problem

A naive router is
`User Request → Economic Router → Cheapest Eligible Model`. This is
insufficient because the selected model may lack prior decisions,
current state, files, conversations, constraints, completed work, or the
current objective. Model switching must not destroy continuity or make
the customer's work more expensive overall.

# 3. Required Jous Architecture

``` text
User → Organization → Project
                         |
                         +-- Conversations
                         +-- Project Memory
                         +-- Project State
                         +-- Decisions
                         +-- Connected Sources
                         +-- Files / Code / Instructions
                                   |
                                   v
                           JOUS CONTEXT LAYER
                    Retrieve / Rank / Resolve / Compress
                           Assemble / Budget
                                   |
                                   v
                             ContextPackage
                                   |
                                   v
                            EXECUTION POLICY
                       /           |           \
                 JOUS_AUTO    MODEL_STACK    PINNED_MODEL
                       \           |           /
                                   v
                          Model Eligibility
                                   |
                                   v
                         Supplier Eligibility
                                   |
                                   v
                          Economic Routing
                                   |
                                   v
                           Supplier Adapter
                                   |
                                   v
                                 Model
```

Economic routing operates downstream of sufficient task/context
understanding and within customer policy.

# 4. Memory Is Not the Model

Provider-native memory may be an optional optimization but must never
become Jous's canonical memory system. Jous must be able to switch
model, supplier, gateway, inference provider, or memory engine without
inherently losing continuity.

> **Model switching must never inherently mean context loss.**

# 5. Context Is Not One Thing

Jous distinguishes conversation context, project memory, project state,
source context, user instructions, and working context.

# 6. Conversation Context

Recent user and assistant messages, the current follow-up, and immediate
task instructions. It is generally short-lived and high priority and is
not the complete Project Memory.

# 7. Project Memory

Durable information useful across sessions: architecture/product
decisions, terminology, constraints, milestones, operating rules,
important user decisions, and stable project facts. It is derived
information, not automatically source truth, and requires provenance.

# 8. Project State

Project State represents what is operationally relevant now: current
objective, implementation gate, blocker, last completed gate, production
status, pending decisions, and next approved action. Jous must
eventually support supersession, correction, effective timestamps,
provenance, and current-state resolution.

# 9. Source Context

Authoritative or semi-authoritative material such as GitHub, project
documents, uploads, specifications, databases, Google Drive, Slack,
issue trackers, tests, deployments, APIs, and future connectors.
Retrieve relevant source context rather than inserting everything into
every prompt.

# 10. User Instructions

Durable or session-level rules such as output preferences, operating
rules, approval requirements, technical constraints, and communication
preferences. Instructions must be scoped so project-specific rules do
not leak into unrelated projects.

# 11. Working Context

Temporary task state such as active files, branch, feature, error,
latest test, hypothesis, or coding objective. It may expire quickly and
must not automatically become durable Project Memory.

# 12. Canonical Source vs Derived Memory

Jous must distinguish **Source Truth** from **Derived AI Memory**. A
GitHub commit, architecture document, or conversation may be a source;
an extracted statement such as "Certification passed" is derived memory.
Derived memory can be incomplete, stale, wrong, superseded, or
contradicted. Preserve provenance and retrieve underlying sources when
confidence matters.

# 13. Jous-Owned Canonical Objects

Potential Jous-owned objects include `Conversation`,
`ConversationMessage`, `ProjectSource`, `SourceDocument`,
`SourceReference`, `ProjectMemory`, `MemorySource`, `MemoryVersion`,
`ProjectState`, `ProjectDecision`, `ContextRequest`, `ContextCandidate`,
`ContextPackage`, `ContextUsage`, `ContextEvaluation`, and
`ExecutionPolicy`. Exact schemas are deferred; ownership is not.

# 14. Memory Engine Boundary

``` text
Jous Context Layer → MemoryAdapter → Mem0 OSS / Letta / Graphiti / future engines
```

Customer continuity must not depend on one memory vendor.

# 15. Conceptual MemoryAdapter

The future adapter should accommodate operations conceptually equivalent
to `store()`, `retrieve()`, `update()`, `invalidate()`, `search()`,
`summarize()`, `health()`, and `capabilities()`. Exact interfaces are
deferred.

# 16. Initial Candidate --- Mem0 OSS

Mem0 OSS is the leading first prototype candidate because of permissive
Apache-2.0 licensing, self-hosting, persistent-memory focus, Python
compatibility, and ability to operate as a memory layer rather than an
entire application architecture.

> **JOUS.CONTEXT.1 does not approve Mem0 as a production dependency.**

It must pass the Jous Context Benchmark. Managed-only capabilities must
not silently become Jous requirements.

# 17. Candidate --- Letta

Letta is the primary comparison candidate because of stateful agents,
long-running identity, persistent memory, cross-session continuity, and
model portability. Evaluate whether its broader agent-runtime
architecture creates unnecessary coupling.

# 18. Candidate --- Graphiti

Graphiti is a serious temporal/project-state candidate. It may help Jous
understand that a newer state such as "certification passed" supersedes
an older "certification pending." It is not required for CORE.1A.

# 19. Candidate --- LangMem

LangMem may be evaluated for memory primitives, but Jous should avoid
broader framework dependency unless benefits materially exceed coupling.

# 20. PostgreSQL Remains Important

Dedicated Jous PostgreSQL remains the primary application database.
Structured canonical records should remain Jous-controlled where
practical. PostgreSQL full-text search, pgvector, vector stores, graph
databases, search indexes, and memory engines are implementation
choices, not the Jous product model.

# 21. Do Not Prematurely Add Infrastructure

This decision does not authorize immediate standalone vector databases,
graph databases, Redis, Kafka, Elasticsearch, dedicated retrieval
clusters, or memory microservices. Specialized infrastructure requires
measured justification.

# 22. Context Assembly

A bounded `ContextPackage` may include system instructions,
user/organization instructions, project instructions, current Project
State, recent conversation, relevant durable memory, relevant decisions,
relevant source excerpts, active Working Context, and the current
request.

# 23. Context Budget

Jous should estimate available task context as maximum usable context
minus system requirements, expected output allowance, and safety margin.
Context assembly must respect this budget.

# 24. Context Optimization

Instead of repeatedly sending an entire 120K-token history, Jous may
assemble only relevant recent conversation, state, decisions, sources,
and task instructions. Any numbers are illustrative.

> **Deliver sufficient context using the minimum economically justified
> token footprint.**

# 25. Context Quality Before Context Compression

Token reduction is not success if it damages the outcome. Optimize
relevance, freshness, authority, completeness, contradiction handling,
and token efficiency. Quality comes before maximum compression.

# 26. Context and Model Eligibility

Eligibility may consider reasoning capability, modality, context window,
coding capability, structured output, latency, commercial status, and
safety. A cheap model is not eligible if it cannot safely handle the
task's required context/capability.

# 27. Customer Execution Policy

Persistent context must not require surrendering model control. Jous
separates **Context Intelligence** from **Execution Policy**. The
architecture must support at least `JOUS_AUTO`, `MODEL_STACK`, and
`PINNED_MODEL` at appropriate account, organization, project,
conversation, or task scope. Commercial entitlements are deferred.

# 28. JOUS_AUTO

The customer delegates model and supplier optimization to Jous within
configured constraints. Jous may determine context, capabilities,
eligible models, model selection, suppliers, fallback, and route based
on task/context requirements, expected quality, reliability, latency,
commercial eligibility, customer policy, and economics.

Jous Auto means choosing an appropriate execution path while optimizing
effective economics---not merely choosing the cheapest model.

# 29. MODEL_STACK

The customer selects an ordered logical-model preference stack, for
example:

``` text
1. Claude
2. GPT
3. Gemini
```

An advanced user may configure up to three logical models as an example;
the exact limit must remain configurable. Jous respects model order
while optimizing eligible supplier routes underneath each model.

# 30. MODEL_STACK Fallback Policy

Fallback may eventually trigger on supplier failure, model
unavailability, timeout, context incompatibility, commercial
ineligibility, customer cost/latency ceilings, or provider degradation.
Jous must not replace a model merely because another is cheaper when
that violates policy. Requested model, executed model, and fallback
reason should be observable.

# 31. PINNED_MODEL

The customer explicitly selects one logical model. Jous respects it
while optimizing among eligible suppliers serving that model.
Cross-model fallback occurs only when explicitly enabled by the
customer.

# 32. Model Selection vs Supplier Selection

Model Selection answers **which logical model performs the task** and
may be controlled by Jous or the customer. Supplier Selection answers
**where Jous acquires execution of that logical model** and may normally
remain Jous-controlled.

Jous must not silently replace a preferred model merely to improve Jous
economics.

# 33. Context Continuity Across Execution Modes

The same Project Context remains usable across `JOUS_AUTO`,
`MODEL_STACK`, and `PINNED_MODEL`. Changing models or suppliers must not
require rebuilding Project Memory.

# 34. Project-Specific Execution Policy

Different projects may use different policies: a production coding
project may pin Claude; a research project may use Jous Auto; a content
project may use a Gemini → Claude → GPT stack. Task-level overrides may
come later.

# 35. Revised Jous Auto Flow

``` text
Task Understanding
→ Project / Customer Execution Policy
→ Context Requirement
→ Context Retrieval
→ Context Assembly
→ Context Optimization
→ Capability Requirement
→ Eligible Model(s)
→ Customer Model Preference
→ Eligible Supplier Routes
→ Economic Evaluation
→ Execution
→ Outcome Measurement
```

Customer policy constrains optimization; Jous optimizes within those
constraints.

# 36. Three Optimization Axes

Jous optimizes Context, Model, and Supplier. Under `JOUS_AUTO`, Jous
controls all three. Under `MODEL_STACK`, Jous controls context and
supplier while the customer controls model preference. Under
`PINNED_MODEL`, Jous controls context and supplier while the customer
controls the model.

# 37. JEAC vs Effective Task Economics

JOUS.ECON.1's JEAC remains a supply-side metric. Long term, Jous may
define **Jous Effective Task Cost (JETC)** including context
preparation, retrieval, memory processing, inference JEAC, retry/rework,
and attributable execution overhead. Exact accounting definition is
deferred.

# 38. Context Economics

Eventually measure stored, retrieved, and injected context; model input
tokens; context/memory processing cost; retrieval cost; cache use;
context reduction; retries; and task outcome.

# 39. Storage Cost vs Processing Cost

Separate **Storage Cost** (retaining messages, metadata, memories,
summaries, embeddings, state), **Memory Processing Cost** (extraction,
summarization, consolidation, embedding, classification, conflict
resolution), and **Context Execution Cost** (tokens supplied to
execution models).

# 40. Asynchronous Memory Processing

Extraction, consolidation, summarization, embedding, and stale-memory
review may eventually run asynchronously to reduce request latency and
potentially use lower-cost background models. Implementation is
deferred.

# 41. Memory Promotion

Not every message deserves permanent memory. Future promotion may
consider repeated relevance, explicit instruction, project importance,
decision status, source authority, expected future utility, and
confidence.

# 42. Memory Correction

Jous must support correction, supersession, invalidation, timestamps,
and provenance. Never silently rewrite authoritative source history;
derived memory may be superseded while remaining auditable.

# 43. Temporal Awareness

Jous should eventually distinguish historically true, currently true,
planned, proposed, rejected, completed, and superseded states.

# 44. Provenance

Durable memory should retain provenance such as conversation/message,
document, repository, commit, issue, external source, API record, or
user-entered fact. High-value decisions should be traceable where
practical.

# 45. Confidence

Potential conceptual states include `USER_CONFIRMED`, `SOURCE_VERIFIED`,
`DERIVED_HIGH_CONFIDENCE`, `DERIVED`, `CONFLICTED`, and `SUPERSEDED`.
Exact vocabulary is deferred.

# 46. Project Isolation

A retrieval for Organization A / Project X must never accidentally
retrieve private context from Organization B / Project Y. Organization
and Project boundaries are explicit regardless of memory engine.

# 47. User-Level vs Project-Level Memory

Some preferences may eventually apply across projects, but cross-project
memory creates privacy/relevance risk. Initially prefer explicit user,
organization, project, and conversation scopes.

# 48. Team Memory

Future team memory may share decisions, state, sources, and operating
instructions, requiring permissions, provenance, visibility, deletion,
and governance. It is not part of initial implementation.

# 49. Privacy

Treat Project Memory as customer data. Future implementation must
address encryption, access control, deletion, retention, export, tenant
isolation, provider exposure, logging, and backups. No memory vendor
receives unrestricted project data by default.

# 50. Provider Exposure

Only the ContextPackage needed for a task should be sent to the selected
execution route. Future controls may prevent particular sources from
being sent to particular providers.

# 51. Deletion

Meaningful deletion must eventually address source data, derived memory,
embeddings, summaries, caches, backups, and provider-side retention.
Memory-engine choices must not make customer data effectively
undeletable.

# 52. Exportability

Canonical project knowledge should remain exportable where practical to
support vendor replacement, customer portability, disaster recovery, and
migration.

# 53. Subscription Opportunity

Persistent Project Context and advanced execution control may become
paid differentiators without hard-coding plans into memory/routing
infrastructure.

**Jous Free** may offer recent conversation context, limited
retained/project context, basic assembly, and basic Jous Auto.

**Jous Builder** may offer persistent Project Memory, longer history,
connected sources, intelligent retrieval, context optimization, model
portability, and premium execution.

**Advanced Builder / Pro** may offer deeper memory, larger source
corpus, temporal state, advanced context optimization, more sources,
background consolidation, Jous Auto, pinned models, configurable model
stacks/fallback, and project-specific policies.

**Team / future organization offerings** may add shared memory,
organization context, role-aware sources, team policies, and governance.

Names, prices, limits, and entitlements are not approved here.

# 54. Memory as Customer Value

Do not market memory merely as "we store your chats."

> **Jous maintains the working intelligence of your project so you can
> use the right AI model without rebuilding context every time.**

This supports: **Make every AI dollar go further.**

# 55. Customer Control as Value

A customer should be able to say "optimize everything," "use these three
models in this order," or "always use this model for this project" while
still receiving Project Context, supplier optimization, Spend
Intelligence, Project Economics, and eligible Rewards.

# 56. Potential Customer Metrics

Potential metrics include Project Knowledge Stored, Context Used,
Context Sources, Estimated Full-History Context, Optimized Context Size,
Context Reduction, Execution Policy, Requested Model, Executed Model,
Fallback Reason, Supplier Route, and Task Cost.

# 57. No Fake Savings

Do not claim savings merely because fewer tokens were sent. Savings
require a defensible baseline such as measured full-history execution,
prior customer patterns, or equivalent-model comparison.

# 58. Context Caching

Prompt caching may reduce cost but is an optimization, not a dependency.
Canonical context must never exist only inside a provider cache.

# 59. Model Portability Test

The same project should remain useful as execution models change.
Benchmark tasks must switch models and also switch among `JOUS_AUTO`,
`MODEL_STACK`, and `PINNED_MODEL` while preserving continuity.

# 60. Jous Context Benchmark

Before adopting a production memory engine, run a realistic
builder-project benchmark rather than toy preference tests.

# 61. Benchmark Dataset

Use approximately 100+ durable facts/decisions plus changing state,
superseded decisions, source documents, code references, test results,
recent conversation, temporary working information, and irrelevant
history. Exact size may evolve.

# 62. Benchmark Question Classes

Test current state, historical state, decision retrieval, source
retrieval, contradictions, working context, cross-session continuity,
model switching, and execution-policy switching.

# 63. Benchmark Metrics

Measure retrieval accuracy, current-state accuracy, stale-memory error
rate, contradiction handling, provenance quality, context tokens,
processing tokens, memory-processing cost, retrieval latency, execution
latency, storage footprint, model portability, execution-policy
portability, and operational complexity.

# 64. Benchmark Candidates

Initial candidates:

1.  Mem0 OSS
2.  Letta
3.  PostgreSQL-based Jous baseline

Add Graphiti if temporal-state tests show material need; add LangMem if
its primitives provide meaningful advantage.

# 65. PostgreSQL Baseline

A simple Jous-owned baseline may use structured ProjectState,
ProjectDecision, recent conversation, PostgreSQL search, and optional
pgvector if justified. Specialized middleware must prove enough value to
justify complexity.

# 66. Engine Selection Criteria

Evaluate retrieval quality, temporal correctness, token efficiency,
model/provider independence, self-hosting, license, operational
complexity, cost, portability, observability, deletion, isolation, and
developer velocity. No single score determines adoption.

# 67. Licensing

Prefer Apache-2.0, MIT, BSD, and similarly permissive licenses.
Copyleft, source-available, non-commercial, field-of-use, or
mandatory-branding restrictions require explicit review. Hosted terms
are separate from OSS licenses.

# 68. No Memory Vendor Lock-In

A memory engine must not define the Jous Project, customer identity,
subscription entitlement, economic routing, execution policy, canonical
state/source ownership, or billing. Those belong to Jous.

# 69. No Model Lock-In

A Jous Project must not become structurally dependent on one model
family. Model-specific prompt adaptation/optimization may occur, but
canonical project intelligence remains Jous-owned.

# 70. No Supplier Lock-In

Model choice remains separate from supplier choice where technically and
commercially possible. Jous may optimize among eligible suppliers for a
customer-selected logical model.

# 71. CORE.1A Requirement

CORE.1A does not implement the complete Context Layer, but it must
preserve Organization and Project boundaries, conversation/source-ready
architecture, execution-policy-ready architecture, provider-independent
execution contracts, and environment/configuration boundaries.

It must not assume conversation history is permanently sent to one
provider or that Jous always chooses the customer's model.

# 72. Initial Implementation Timing

``` text
JOUS.CORE.1A Foundation
→ Jous Context Benchmark
→ Memory Engine Decision
→ JOUS.CONTEXT Implementation Gate
→ JOUS.USE.1 / Jous Workspace Integration
```

Do not implement Mem0, Letta, or Graphiti in CORE.1A unless separately
approved.

# 73. Workspace Requirement

A Project becomes more than a chat folder:

``` text
Project
+-- Conversations
+-- Sources
+-- Memory
+-- Current State
+-- Decisions
+-- Execution Policy
+-- Usage
+-- Spend
+-- Rewards
+-- Economics
```

This connects **Project Intelligence** with **Project Economics**.

# 74. Execution Policy UX

Future Workspace may expose:

``` text
Execution

( ) Jous Auto

( ) Model Stack
    1. Model A
    2. Model B
    3. Model C

( ) Pinned Model
    Model: Model A
```

Advanced settings may expose fallback policy, cost ceiling, latency
preference, supplier restrictions, and provider privacy restrictions.
Jous Auto remains the simplest path; advanced control remains available.

# 75. Fallback Transparency

When fallback occurs, customers should eventually see requested model,
executed model, supplier route, fallback reason, and material cost
impact. Fallback is a reliability feature, not invisible substitution.

# 76. Customer Policy Overrides Economics

If a customer pins Model A, Jous must not silently switch to cheaper
Model B for margin. If the customer orders A → B → C, Jous must not
reorder solely for Jous economics. Supplier optimization may occur
underneath allowed choices.

> **Customer policy constrains optimization. Jous optimizes within those
> constraints.**

# 77. Subscription Flexibility

Commercial plans may expose Jous Auto, persistent Project Context,
pinned models, configurable model stacks/fallback, project-specific
policies, context optimization, connected sources, and advanced memory.
Exact plan names, prices, stack/memory/context limits, and entitlements
are deferred and must remain configuration, not architectural constants.

# 78. Jous Moat

The gateway, memory engine, model, and supplier are not the moat.

Jous's potential moat is the combination of customer economic
relationship, project context intelligence, customer execution policy,
usage intelligence, aggregated AI demand, supplier economics, project
economics, rewards, and effective-cost optimization.

The long-term system understands both **what the builder is trying to
accomplish** and **within the builder's constraints, the economically
best way to accomplish it**.

# 79. Product Flywheel

``` text
More Builders
→ More Project Activity
→ Better Context Intelligence
→ Better Task Execution
→ Lower Effective Task Cost
→ Higher Customer Value
→ More AI Usage Through Jous
→ Greater Aggregated Demand
→ Better Supplier Economics
→ Better Rewards / Effective Cost
→ More Builders
```

Privacy and tenant isolation must not be compromised to create this
flywheel.

# 80. Explicit Non-Goals

This decision does not authorize proprietary foundation-model training,
building a vector/graph database or memory engine from scratch,
unlimited permanent memory, automatic ingestion of every customer
system, cross-customer memory, selling customer memory, provider/model
project lock-in, uncontrolled background inference, silent model
substitution, or guaranteed token-savings claims.

# 81. Architectural Invariants

### CONTEXT-1

**Jous owns context continuity. Models and suppliers are replaceable
execution resources.**

### CONTEXT-2

**Model switching must never inherently mean context loss.**

### CONTEXT-3

**Optimize context before optimizing model price.**

### CONTEXT-4

**Source truth and derived AI memory must remain distinguishable.**

### CONTEXT-5

**Canonical project semantics belong to Jous, not the memory vendor.**

### CONTEXT-6

**Memory infrastructure must remain replaceable.**

### CONTEXT-7

**Context retrieval must respect organization and project isolation.**

### CONTEXT-8

**Historical information must not automatically be treated as current
truth.**

### CONTEXT-9

**Context optimization succeeds only when task quality is preserved or
improved.**

### CONTEXT-10

**Persistent context may become a paid entitlement, but commercial plans
remain separate from memory-engine implementation.**

### CONTEXT-11

**Jous Auto is optional. Advanced customers may control model
selection.**

### CONTEXT-12

**Model selection and supplier selection are separate architectural
decisions.**

### CONTEXT-13

**A customer may use Jous economics without surrendering control over
the logical model.**

### CONTEXT-14

**Pinned-model execution must not silently switch models unless customer
policy explicitly permits fallback.**

### CONTEXT-15

**Model-stack order is customer policy and must not be silently
reordered for Jous economic benefit.**

### CONTEXT-16

**Context continuity must survive transitions between Jous Auto, Model
Stack, and Pinned Model execution.**

### CONTEXT-17

**Customer policy constrains optimization. Jous optimizes within those
constraints.**

# 82. Stop Conditions

Stop for architectural review if implementation requires a third-party
memory vendor as canonical Project DB; exposing all context to every
provider; coupling Project identity to a provider; storing production
data without tenant isolation; losing provenance; restrictive OSS
licensing; impractical deletion; context loss on model switching;
silently overriding pinned models or reordering model stacks; coupling
subscription entitlements to a memory vendor; or substantial unmeasured
infrastructure.

# 83. Decision

Jous will build around a **Jous-owned Context Layer** that eventually
assembles task-specific ContextPackages from conversation, durable
Project Memory, current Project State, source material, instructions,
and Working Context.

Memory engines are replaceable infrastructure behind a Jous-controlled
boundary.

Mem0 OSS is the leading first prototype candidate; Letta is the primary
comparison candidate; a Jous/PostgreSQL implementation is the baseline;
Graphiti is considered particularly for temporal/project-state
requirements.

No production memory engine is selected here. Selection follows the
controlled Jous Context Benchmark.

Jous also maintains a separate customer-controlled Execution Policy
layer supporting:

-   `JOUS_AUTO`
-   `MODEL_STACK`
-   `PINNED_MODEL`

Model selection and supplier selection remain separate decisions.

# 84. Final Principle

Jous is not trying to make individual model calls as cheap as possible.
Jous is trying to make productive AI work economically better while
preserving customer choice.

> **The economically best AI request is not necessarily the request sent
> to the cheapest model. It is the request containing the right context,
> executed according to the customer's policy by an appropriate model,
> through the best eligible supply route, at the lowest effective cost
> consistent with a successful outcome.**

> **Jous gives builders both optimization and control: let Jous choose,
> define your own model stack, or pin the model you trust --- while Jous
> preserves project context and optimizes the economics underneath.**

# END --- JOUS.CONTEXT.1
