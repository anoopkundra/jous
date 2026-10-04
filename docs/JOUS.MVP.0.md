\# JOUS.MVP.0 — Product Requirements \& Architecture



\*\*Status:\*\* APPROVED IMPLEMENTATION CONTRACT  

\*\*Version:\*\* 2.0  

\*\*Project:\*\* Jous  

\*\*Canonical Domain:\*\* jous.si  

\*\*Depends on:\*\* JOUS.SUPPLY.1, JOUS.ECON.1, JOUS.CONTEXT.1  

\*\*Implementation Owner:\*\* Jous  

\*\*Primary Engineering Agent:\*\* Codex  

\*\*Updated:\*\* October 4, 2026



\---



\# 1. Purpose



JOUS.MVP.0 defines the canonical product, economic, technical and implementation boundary for the first Jous MVP.



This specification supersedes the earlier pre-implementation JOUS.MVP.0 planning specification where the two conflict.



Detailed supplier decisions remain authoritative in:



\- `docs/decisions/JOUS.SUPPLY.1.md`



Detailed wallet, funding, unit economics and rewards decisions remain authoritative in:



\- `docs/decisions/JOUS.ECON.1.md`


Detailed project context, memory and customer execution-policy decisions remain authoritative in:


\- `docs/decisions/JOUS.CONTEXT.1.md`



This document converts those decisions into an implementation contract.



The objective is to prevent implementation drift while allowing engineering flexibility inside explicitly defined boundaries.



\---



\# 2. Product Thesis



Jous is the economic layer between AI builders and the AI ecosystem.



Jous is not primarily:



\- another chatbot,

\- another generic LLM gateway,

\- another model marketplace,

\- another vibe-coding IDE,

\- or another AI subscription bundle.



Jous exists to help people who build with AI understand, optimize and recover value from their AI spending.



Primary customer promise:



> Make every AI dollar go further.



Primary economic question:



> How should your next AI dollar be spent?



Rewards proposition:



> Earn Jous Rewards on eligible AI spending and unlock value across the tools you use to build with AI.



Spend Intelligence proposition:



> See what it really costs to build with AI.



Community idea:



> keep building.



\---



\# 3. Product Flywheel



The customer loop is:



\*\*SEE → OPTIMIZE → EARN → REDEEM → BUILD MORE → REPEAT\*\*



The long-term business flywheel is:



\*\*More Builders  

→ More AI Spending  

→ More Aggregated Demand  

→ Better Supplier Economics  

→ Lower Effective Acquisition Cost  

→ Better Customer Savings and Rewards  

→ Greater Retention  

→ More Builders\*\*



The long-term moat is not gateway technology.



The moat is the combination of:



\- customer financial relationships,

\- aggregated AI demand,

\- supplier economics,

\- usage intelligence,

\- project economics,

\- rewards,

\- customer economic profiles,

\- effective-cost optimization,

\- and eventually a broader authorized value network.



Canonical principle:



> The gateway is not the moat. The economic relationship with the AI builder is the moat.



\---



\# 4. Initial Customer



Jous should initially serve people who have crossed from merely using AI to building with AI.



\## Initial Segments



| Segment | Monthly AI / Build Spend | MVP Priority |

|---|---:|---|

| AI Explorer | Under $50 | Not initial target |

| AI User | $50–$199 | Future |

| AI Builder | $200–$499 | Core |

| AI Power Builder | $500–$1,999 | Highest |

| AI Studio / Team | $2,000–$9,999 | Expansion |

| AI Business | $10,000+ | Later B2B / enterprise |



The MVP should optimize primarily for:



\- founders,

\- developers,

\- vibe coders,

\- indie hackers,

\- creators,

\- consultants,

\- agencies,

\- technical operators,

\- and small AI-building teams.



\## Beta Cohort



Target approximately 50 qualified builders.



Suggested initial distribution:



\- 20 spending approximately $200–$500/month,

\- 20 spending approximately $500–$2,000/month,

\- 10 spending $2,000+/month.



The purpose of the beta is not simply account growth.



It is to prove that serious builders will move meaningful economic activity through Jous.



\---



\# 5. Customer Problem



AI-building spend is fragmented across:



\- AI subscriptions,

\- model APIs,

\- coding tools,

\- media generation,

\- hosting,

\- databases,

\- domains,

\- observability,

\- communication infrastructure,

\- and developer tools.



Builders often cannot answer:



> What did it actually cost me to build this project?



Common problems include:



\- no unified AI/build spend view,

\- unclear effective cost,

\- fragmented credits and balances,

\- weak project-level attribution,

\- overlapping subscriptions,

\- poor visibility into model/provider economics,

\- and little economic value returned after spending.



Jous should progressively turn fragmented AI spending into an understandable economic system.



\---



\# 6. MVP Success Condition



JOUS.MVP.0 is a closed-loop economic proof.



A qualified builder should be able to:



1\. create a Jous account,

2\. create or select a project,

3\. use eligible free AI or fund Jous Balance,

4\. choose Jous Auto, an allowed model stack, or a pinned logical model according to available execution-policy controls,

5\. submit a request,

6\. receive a streaming response,

7\. have usage captured,

8\. see the actual or reconciled economic cost,

9\. have the correct balance deducted when applicable,

10\. receive an eligible reward,

11\. see project-level spend,

12\. understand measurable savings where defensible,

13\. and review economic history.



Every material financial event must be reconstructable.



The MVP succeeds when serious AI builders move meaningful activity through Jous because the combination of:



\- Spend Intelligence,

\- Project Economics,

\- effective cost,

\- AI access,

\- and rewards



is materially better than their fragmented alternative.



\---



\# 7. Jous Usage Modes



Jous ultimately supports three modes.



\## USE



Consume AI directly through Jous Workspace.



\*\*MVP:\*\* YES.



The Workspace should provide a focused multi-model experience without attempting to recreate a full development environment.



\## CONNECT



Connect external AI/build services to Jous Spend Intelligence.



\*\*MVP:\*\* LIMITED.



Support only integrations necessary to validate Spend Intelligence, BYOK and economic attribution.



Do not build a broad connector catalog.



\## BUILD



Use the Jous API/SDK from applications and agents.



\*\*MVP:\*\* YES, after the Workspace economic path is proven.



Provide a narrow OpenAI-compatible API using the same:



\- model registry,

\- supply adapters,

\- UsageEvents,

\- ledger,

\- project attribution,

\- pricing,

\- rewards,

\- and reconciliation path.



No mode may create a parallel economic system.



\---



\# 8. Product Architecture Principle



Jous should not rebuild mature commodity AI infrastructure when commercially permissive open-source components already exist.



Engineering effort should concentrate on Jous's differentiated IP:



\- Jous Ledger,

\- Jous Balance,

\- Spend Intelligence,

\- Project Economics,

\- Rewards Engine,

\- Customer Economic Profile,

\- Effective-Cost Engine,

\- Economic Routing,

\- supplier economics,

\- and future Rewards Marketplace economics.



Commodity infrastructure should remain replaceable.



\---



\# 9. Classification Model



Every major capability should be classified as:



\## BUILD



Jous creates and owns it as differentiated product or authoritative control plane.



\## ADOPT



Jous uses commercially permissive open-source infrastructure.



Components must be:



\- pinned,

\- reviewed,

\- documented,

\- isolated,

\- and replaceable.



\## INTEGRATE



Jous connects to an external provider or service through a replaceable adapter.



\## DEFER



Capability is intentionally excluded from MVP.



Do not create unnecessary scaffolding for deferred capabilities.



\---



\# 10. MVP Architecture Layers



\## Layer 1 — Jous Customer Experience



Includes:



\- Jous Workspace,

\- Spend Dashboard,

\- Projects,

\- Wallet,

\- Rewards,

\- Offers,

\- funding,

\- account,

\- usage history.



\*\*Ownership:\*\* BUILD.



\## Layer 2 — Jous Economic Control Plane



Includes:



\- Ledger,

\- Wallet,

\- Spend Intelligence,

\- Project Economics,

\- Customer Economic Profile,

\- Rewards Engine,

\- pricing,

\- JEAC,

\- economic policy,

\- reconciliation,

\- supplier inventory.



\*\*Ownership:\*\* BUILD.



\## Layer 3 — Jous Supply Control



Includes:



\- Jous Model Registry,

\- SupplyAdapter interface,

\- SupplyQuote,

\- RouteDecision,

\- UsageEvent normalization,

\- commercial eligibility,

\- fallback policy.



\*\*Ownership:\*\* BUILD.



\## Layer 4 — Commodity AI Infrastructure



Includes:



\- gateway plumbing,

\- streaming SDKs,

\- retries,

\- provider abstraction,

\- observability,

\- metering infrastructure.



\*\*Ownership:\*\* ADOPT where appropriate.



\## Layer 5 — AI Suppliers



Includes:



\- Hugging Face,

\- Vercel AI Gateway,

\- OpenRouter,

\- BYOK,

\- and future direct suppliers.



\*\*Ownership:\*\* INTEGRATE.



\---



\# 11. Supplier-Neutral Rule



Hard architectural principle:



> NO AI SUPPLIER DEPENDENCY ABOVE THE ADAPTER BOUNDARY.



Jous domain objects must not depend directly on supplier-specific model IDs or supplier response schemas.



Conceptual flow:



\*\*Customer / Workspace  

→ api.jous.si  

→ Jous Control Plane  

→ Jous Economic Router  

→ Gateway / Supply Adapters  

→ AI Suppliers\*\*



Jous owns the economic decision.



Suppliers execute inference.



Gateways provide plumbing.



\---



\# 12. Canonical Supply Routes



JOUS.SUPPLY.1 establishes the initial supply architecture.



The MVP must support replaceable adapters for:



\### Hugging Face



Primary current candidate for economically efficient open-model supply.



Benchmark observations included:



\- successful authentication,

\- OpenAI-compatible execution,

\- DeepSeek V3.2,

\- automatic provider selection,

\- forced DeepInfra,

\- forced Featherless,

\- supplier switching without changing logical model,

\- token usage capture,

\- and no observed HF funding/platform surcharge on the tested credit purchase.



\### Vercel AI Gateway



Strong managed routing/resilience supply route.



Validated capabilities included:



\- provider forcing,

\- provider sorting,

\- fallback,

\- TTFT sorting,

\- token accounting,

\- cost accounting.



Jous must not assume Vercel's default routing is economically optimal for Jous.



\### OpenRouter



Strong broad supplier marketplace and market-intelligence route.



Useful for:



\- supplier breadth,

\- provider telemetry,

\- pricing comparison,

\- model availability,

\- fallback options.



Funding overhead must be included in JEAC.



\### BYOK



BYOK is a first-class Jous route.



Customers may supply eligible provider credentials while Jous provides:



\- Workspace,

\- project attribution,

\- Spend Intelligence,

\- usage normalization,

\- and economic context.



\---



\# 13. Supply Adapter Contract



Each supply adapter should conceptually support:



\- `quote()`

\- `execute()`

\- `get\_usage()`

\- `get\_balance()`

\- `health()`

\- `capabilities()`



Initial adapter implementations:



\- `HuggingFaceSupplyAdapter`

\- `VercelSupplyAdapter`

\- `OpenRouterSupplyAdapter`

\- `BYOKSupplyAdapter`



Future suppliers must enter through the same boundary.



\---



\# 14. Jous Model Registry



Jous must maintain an internal model registry.



Customer-facing and internal logical model identities must not depend on a single supplier.



A logical model may map to multiple execution routes.



The registry should support concepts including:



\- Jous model ID,

\- display name,

\- model family,

\- capabilities,

\- context limit,

\- input modalities,

\- output modalities,

\- supplier routes,

\- provider-specific IDs,

\- availability,

\- pricing evidence,

\- free eligibility,

\- commercial eligibility,

\- quality metadata,

\- and operational status.



For JOUS.FREE.1 also support:



\- `free\_eligible`

\- `free\_source`

\- `free\_cost\_to\_jous`

\- `free\_daily\_limit`

\- `free\_monthly\_limit`



Commercial status should support:



\- UNREVIEWED

\- SELF\_SERVICE\_APPROVED

\- BYOK\_ONLY

\- NEGOTIATED

\- RESTRICTED

\- DISABLED



Technical availability never overrides commercial status.



\---



\# 15. JOUS.CORE.1 — Foundation



JOUS.CORE.1 establishes the authoritative Jous domain.



Core entities should include:



\- User,

\- Organization,

\- OrganizationMembership,

\- Project,

\- Wallet,

\- LedgerAccount,

\- LedgerEntry,

\- Transaction,

\- Provider,

\- ProviderCredential,

\- Model,

\- ModelRoute,

\- UsageEvent,

\- PriceQuote,

\- RouteDecision,

\- Reward,

\- RewardRule,

\- Promotion,

\- SupplyInventory,

\- Settlement,

\- Offer,

\- Redemption.



PostgreSQL is the durable financial and operational system of record.



Supabase may provide managed PostgreSQL infrastructure, but Jous domain logic must not depend unnecessarily on Supabase-specific semantics.



\---



\# 16. Jous Ledger



The Jous Ledger is differentiated Jous IP.



It must use:



> append-only double-entry accounting.



Every financial movement must be reconstructable.



Never use a mutable:



`user.balance`



as the financial source of truth.



Balance is derived from ledger state.



Ledger architecture must support:



\- customer funding,

\- Jous Balance,

\- usage charges,

\- refunds,

\- adjustments,

\- Jous Rewards,

\- reward reversals,

\- promotional subsidies,

\- supplier economics,

\- and reconciliation adjustments.



History must never be silently rewritten.



Corrections require compensating entries.



\---



\# 17. Jous Balance



Jous Balance represents customer-purchased prepaid value usable for eligible Jous services.



For MVP it is:



\- not a bank account,

\- not peer-to-peer money,

\- not freely transferable,

\- not customer-withdrawable cash,

\- and not an investment.



Purchased Jous Balance must remain distinct from Jous Rewards.



\---



\# 18. Jous Rewards



Jous Rewards represent promotional or economically funded value.



MVP rewards are:



\- non-cash,

\- non-withdrawable,

\- non-transferable,

\- rule-based,

\- capped where appropriate,

\- and usable only for eligible Jous services/offers.



Reward states should support:



\- PENDING

\- SETTLED

\- AVAILABLE

\- REDEEMED

\- EXPIRED

\- REVERSED



Reward events must be ledger-backed and auditable.



\---



\# 19. Rewards Economic Principle



Do not hard-code:



`reward\_rate = 2%`



or any permanent universal percentage.



Canonical principle:



> Rewards must be funded by measurable economic capacity, not by a permanently fixed percentage of gross AI spend.



Economic capacity may come from:



\- supplier savings,

\- routing efficiency,

\- model optimization,

\- negotiated discounts,

\- rebates,

\- payment-method savings,

\- partner funding,

\- or deliberate promotional/CAC budgets.



\---



\# 20. Reward Types



The MVP architecture should distinguish:



\## Usage Rewards



Generated from eligible AI usage where economics permit.



\## Funding Bonus



Generated from economically favorable funding behavior.



\## Promotional Rewards



Explicitly funded by Jous as CAC or retention expense.



\## Partner-Funded Rewards



Future rewards funded by providers or ecosystem partners.



Every reward must record its funding source.



\---



\# 21. JOUS.PAY.1 — Funding



Initial funding rail:



\*\*Stripe or another approved processor after final commercial/legal validation.\*\*



Support:



\- card,

\- ACH/bank where approved,

\- funding intent,

\- authorization,

\- settlement,

\- failure,

\- refund,

\- dispute,

\- fee,

\- reconciliation.



Cards remain fully supported.



ACH should be positioned as:



> Bank Account — Best Value



when lower funding cost justifies an additional Funding Bonus.



Funding costs must be configurable.



Do not hard-code processor rates.



\---



\# 22. Customer and Supplier Money Separation



Customer funding and supplier funding are separate systems.



Do not implement:



\*\*Customer deposits $100 → immediately buy $100 supplier credits.\*\*



Instead:



\*\*Customer Funding → Jous Balance\*\*



and separately:



\*\*Jous Treasury → Supplier Inventory\*\*



Supplier replenishment should consider:



\- demand,

\- JEAC,

\- supplier reliability,

\- expiration,

\- concentration,

\- working capital,

\- and funding overhead.



\---



\# 23. Supplier Inventory



Jous must maintain supplier inventory independently from customer wallets.



Conceptual fields:



\- supplier,

\- account,

\- available\_credit,

\- reserved\_credit,

\- estimated\_days\_remaining,

\- replenishment\_threshold,

\- replenishment\_target,

\- funding\_cost,

\- expiration\_date,

\- last\_reconciled\_at,

\- status.



Supplier inventory must reflect the actual economic instrument.



Example:



Hugging Face account credits must not automatically be represented as DeepInfra inventory merely because DeepInfra executes a request.



\---



\# 24. JEAC



Canonical metric:



\# Jous Effective Acquisition Cost



Conceptually:



\*\*JEAC =\*\*



provider inference cost  

\+ gateway/platform cost  

\+ supplier funding overhead  

\+ attributable payment/funding overhead  

\+ directly attributable operational cost  

\+ retry/failure economic adjustment  

− supplier discounts  

− rebates  

− supplier-funded incentives



Long-term optimization should increasingly focus on:



> JEAC per successful task



rather than merely token price.



\---



\# 25. Customer-First Economic Optimization



Jous must never optimize solely for Jous margin.



Economic decisions should consider:



\- customer effective cost,

\- model capability,

\- expected quality,

\- reliability,

\- latency,

\- context requirements,

\- commercial eligibility,

\- customer constraints,

\- and sustainable Jous economics.



Canonical principle:



> Jous optimizes customer value, not merely Jous margin.



\---



\# 26. Jous Auto



Jous Auto is a Jous product capability.



It must not simply expose another gateway's automatic routing as though that were proprietary Jous intelligence.



Conceptually:



\*\*Task Understanding  

→ Project / Customer Execution Policy  

→ Context Requirement  

→ Context Retrieval  

→ Context Assembly  

→ Context Optimization  

→ Capability Requirements  

→ Eligible Model(s)  

→ Customer Model Preference  

→ Eligible Supplier Routes  

→ Economic Evaluation  

→ Execution  

→ Usage Measurement  

→ Outcome Measurement  

→ Reward Calculation\*\*



For the earliest MVP stage, Jous may use simple deterministic policy and underlying infrastructure capabilities while collecting proprietary economic evidence.



Complex autonomous routing should not be built before enough evidence exists.



\---



\# 27. Execution Policy and Routing Modes


JOUS.CONTEXT.1 establishes three canonical customer execution-policy modes:


\### JOUS_AUTO


Jous selects the logical model and eligible supplier route within customer constraints.


\### MODEL_STACK


The customer defines an ordered logical-model preference stack. Jous must respect that order and may optimize eligible supplier selection underneath each logical model.


\### PINNED_MODEL


The customer pins one logical model. Jous may optimize eligible supplier selection underneath that model. Cross-model fallback is allowed only when customer policy explicitly permits it.


Canonical principle:


> Customer policy constrains optimization. Jous optimizes within those constraints.


Model selection and supplier selection are separate architectural decisions.


Context continuity must survive transitions among JOUS_AUTO, MODEL_STACK and PINNED_MODEL.


Within JOUS_AUTO and other permitted execution policies, architecture should allow routing preferences such as:



Architecture should allow future modes such as:



\### Jous Economy



Optimize expected JEAC subject to capability and reliability constraints.



\### Jous Fast



Prioritize TTFT and completion latency subject to economic guardrails.



\### Jous Balanced



Balance:



\- cost,

\- reliability,

\- latency,

\- and capability.



This is the preferred conceptual general-purpose policy.



\### Jous Auto



Uses task and customer context to select the appropriate model, route and economic policy.



Not all modes need to be exposed in the first UI.



\---



\# 28. Economic-Aware Fallback



Fallback must be treated as an economic event.



Future controls should support:



\- `max\_fallback\_cost\_multiplier`

\- `max\_absolute\_task\_cost`

\- `minimum\_provider\_health`

\- `maximum\_latency`

\- capability requirements.



A cheap failed route followed by an expensive fallback may produce a successful task with poor economics.



All upstream attempts must therefore be observable to JEAC.



A retry chain must never create duplicate customer deductions.



\---



\# 29. JOUS.FREE.1 — Free Inference Acquisition Layer



Freemium is part of MVP.



Jous Free is not intended to become an unlimited free chatbot.



Its purpose is:



> Acquire qualified AI builders and bring them into the Jous economic network.



Three supply classes may support Free.



\## Supplier-Funded / Zero-Cost Supply



Preferred.



Use commercially eligible free or zero-cost capacity where sustainable.



\## Jous Promotional Supply



Jous may deliberately subsidize limited premium inference.



This must be recorded as CAC/promotional expense.



\## BYOK



Customer supplies provider economics while Jous supplies economic intelligence and workflow.



\---



\# 30. Free Eligibility



Free execution routes require:



`free\_eligible = TRUE`



and:



`commercial\_eligible = TRUE`



Supplier free tiers and promotions must never be assumed permanent.



Limits must be configurable.



Support:



\- daily limits,

\- monthly limits,

\- abuse controls,

\- route availability,

\- supplier availability.



\---



\# 31. Free Usage Accounting



Free does not mean economically invisible.



Every free request must still create a UsageEvent.



Record:



\- user,

\- organization,

\- project,

\- logical model,

\- supplier,

\- route,

\- units/tokens,

\- supplier cost,

\- JEAC where applicable,

\- customer charge,

\- subsidy,

\- timestamp,

\- commercial status.



A customer charge of $0 does not imply Jous cost of $0.



\---



\# 32. Product Ladder



\## Jous Free — $0



Initial capabilities:



\- curated free/zero-cost AI capacity,

\- basic Jous Auto,

\- basic Spend Intelligence,

\- basic project attribution,

\- no payment method required merely to use eligible free capacity.



\## Jous Builder — Pay For What You Use



Capabilities:



\- premium models,

\- funded Jous Balance,

\- fuller economic routing,

\- Project Economics,

\- Jous Rewards,

\- Funding Bonuses,

\- richer Spend Intelligence.



Do not introduce a conventional fixed-price Jous Pro subscription until recurring premium value has been demonstrated.



\---



\# 33. JOUS.USE.1 — Jous Workspace



Jous Workspace is a focused multi-model interface.



MVP should support:



\- text/chat,

\- execution-policy selection,

\- Jous Auto,

\- model-stack controls where entitled,

\- pinned-model controls where entitled,

\- project context continuity,

\- streaming,

\- projects,

\- usage cost,

\- Jous Balance,

\- rewards visibility,

\- basic conversation history.



The Workspace exists to prove the Jous economic loop.



It must not attempt to recreate:



\- Cursor,

\- Emergent,

\- Replit,

\- Runway,

\- full agent IDEs,

\- image studios,

\- video studios,

\- voice studios.



Use Vercel AI SDK or equivalent approved permissive infrastructure for streaming/provider interface plumbing where appropriate.



Jous owns the economic experience around it.



\---



\# 34. JOUS.SPEND.1 — Spend Intelligence



Spend Intelligence is differentiated Jous IP.



MVP should support:



\- onboarding spend profile,

\- normalized AI spending,

\- categories,

\- projects,

\- monthly views,

\- annualized views,

\- supplier/model attribution,

\- Jous-routed spend,

\- basic manual/imported external spend where practical.



Jous must distinguish:



\- actual settled cost,

\- estimated cost,

\- reference price,

\- savings estimate,

\- and promotional value.



Never present an estimate as settled financial fact.



Savings claims require defensible evidence.



\---



\# 35. JOUS.PROJECT.1 — Project Economics



Project is the primary unit for understanding what AI spending produced.

Project is also the primary context-continuity boundary for builder work.

JOUS.CONTEXT.1 governs Project Memory, Project State, source context, context assembly and execution policy. Project intelligence and Project Economics must remain connected without making a memory engine authoritative for the Jous Project.



Support:



\- project creation,

\- ownership,

\- membership,

\- status,

\- budget,

\- tags,

\- optional client/product context.



Every eligible usage event should belong to:



\- exactly one project,

\- or an explicit Unassigned bucket.



Aggregate:



\- supplier cost,

\- JEAC,

\- customer charge,

\- rewards,

\- savings,

\- model mix,

\- supplier mix,

\- usage over time.



Do not claim ROI unless supported by customer-supplied outcome evidence.



\---



\# 36. Customer Economic Profile



Jous should maintain customer-specific economic context independently of gateway infrastructure.



Potential facts include:



\- customer segment,

\- usage patterns,

\- project context,

\- provider preferences,

\- BYOK relationships,

\- known provider credits,

\- funding method,

\- reward eligibility,

\- economic constraints,

\- policy limits.



Distinguish:



\- customer-entered facts,

\- supplier-reported facts,

\- Jous-observed facts,

\- inferred preferences,

\- negotiated Jous economics.



Material facts used in economic decisions should be reproducible.



\---



\# 37. Rewards Engine



The Reward Rules Engine must be configuration-driven.



Conceptual rule dimensions include:



\- event\_type,

\- funding\_method,

\- customer\_segment,

\- organization,

\- project,

\- model,

\- supplier,

\- route,

\- commercial\_status,

\- JEAC,

\- promotion,

\- spend\_threshold,

\- reward\_rate,

\- fixed\_reward,

\- reward\_cap,

\- funded\_by,

\- starts\_at,

\- ends\_at,

\- status.



Rewards must be reproducible and auditable.



Ordinary rewards should not knowingly create structurally negative direct transaction economics.



Approved negative-margin promotions require explicit promotional/CAC classification.



\---



\# 38. Rewards Marketplace



A broad Rewards Marketplace is:



\*\*DEFERRED from MVP.\*\*



However, the architecture should preserve the ability for future rewards to be funded by:



\- AI providers,

\- cloud providers,

\- databases,

\- hosting platforms,

\- security tools,

\- observability tools,

\- domain providers,

\- communications vendors,

\- developer tools.



MVP may test a small number of manually administered offers.



Do not build a generalized marketplace platform yet.



\---



\# 39. Canonical Request Flow



1\. Customer authenticates.

2\. Customer selects organization and project.

3\. Jous resolves the applicable ExecutionPolicy: JOUS_AUTO, MODEL_STACK or PINNED_MODEL.

4\. Jous checks account and project status.

5\. Jous determines the task's context requirement.

6\. Jous retrieves relevant conversation, Project Memory, Project State, decisions, sources, instructions and Working Context as available.

7\. Jous assembles a bounded ContextPackage with provenance and project isolation.

8\. Jous determines capability requirements and eligible logical model(s) within customer policy.

9\. Jous checks Free eligibility or available Jous Balance/BYOK.

10\. Jous checks commercial eligibility.

11\. Jous determines eligible supplier routes for the allowed logical model(s).

12\. Jous produces or records RouteDecision.

13\. SupplyAdapter executes the request using the approved ContextPackage.

14\. Workspace streams the response.

15\. Jous captures provisional usage and context evidence.

16\. Supplier/gateway returns usage/cost evidence.

17\. Jous creates canonical UsageEvent.

18\. Jous calculates supplier cost and JEAC.

19\. Jous determines customer charge.

20\. Ledger posts customer deduction when applicable.

21\. Project Economics receives attribution.

22\. Spend Intelligence updates.

23\. Rewards Engine evaluates eligibility.

24\. Eligible reward enters appropriate lifecycle state.

25\. Reconciliation confirms or adjusts economic evidence.

26\. Customer-facing context and economic history update according to policy.



\---



\# 40. Failure Rules



\### Failed Request With No Billable Supplier Usage



\- no customer charge,

\- no usage reward.



\### Failed Request With Billable Supplier Usage



Record supplier cost accurately.



Customer charging policy must be explicit and independent from internal supplier cost.



\### Partial / Cancelled Stream



Use actual billable usage where available.



UI must distinguish estimated from finalized economics.



\### Retry / Fallback



Record every upstream attempt needed for JEAC.



Never duplicate customer deductions.



\### Missing Supplier Evidence



Place event in reconciliation-pending state.



Do not finalize dependent reward economics until evidence is resolved according to policy.



\### Correction



Never edit financial history.



Use linked compensating transactions.



\---



\# 41. Reconciliation



Jous must reconcile internal records against supplier evidence.



Detect:



\- missing usage,

\- duplicate usage,

\- price changes,

\- token discrepancies,

\- unreported costs,

\- retry charges,

\- failed-request costs,

\- rebates,

\- credit adjustments,

\- balance discrepancies.



Supplier data does not automatically overwrite Jous Ledger history.



Corrections create adjustment transactions.



\---



\# 42. Gross Contribution



Track economic contribution at:



\- request,

\- task,

\- route,

\- model,

\- supplier,

\- project,

\- customer,

\- organization,

\- time period,

\- Jous-wide level.



Conceptually:



\*\*Gross Contribution  

= Customer Economic Revenue  

− JEAC  

− Rewards  

− Directly Attributable Economic Costs\*\*



Promotional/CAC expense must remain separately identifiable.



\---



\# 43. OSS Foundation



Jous should adopt mature, commercially permissive OSS for commodity capabilities.



\## Portkey AI Gateway — MIT



Primary current gateway plumbing candidate.



Potential responsibilities:



\- multi-provider gateway,

\- retries,

\- fallbacks,

\- provider abstraction.



Portkey does not own Jous economic decisions.



\## LiteLLM Core — MIT



Alternative gateway candidate.



Do not incorporate separately licensed enterprise components without review.



Do not operate Portkey and LiteLLM simultaneously merely for architectural elegance.



Select based on bounded implementation evidence.



\## Vercel AI SDK — Apache-2.0



Use where appropriate for:



\- Workspace streaming,

\- model/provider interface plumbing,

\- frontend AI interaction.



Jous Workspace remains proprietary.



\## OpenMeter — Apache-2.0



Candidate for later metering support.



Do not adopt until it demonstrably reduces implementation/reconciliation risk.



\## Langfuse OSS Core — MIT



Candidate for later observability.



Adopt only after:



\- privacy,

\- prompt retention,

\- tenant isolation,

\- operational cost



are acceptable.



\---



\# 44. OSS Licensing Policy



Default acceptable families:



\- MIT

\- Apache-2.0

\- BSD-2-Clause

\- BSD-3-Clause

\- PostgreSQL License

\- similarly permissive licenses after review.



Explicit review required for:



\- GPL,

\- AGPL,

\- SSPL,

\- BSL,

\- Elastic License,

\- Commons Clause,

\- source-available licenses,

\- non-commercial restrictions,

\- field-of-use restrictions,

\- hosted-service restrictions,

\- branding restrictions,

\- enterprise-only components.



For every material OSS dependency record:



\- project,

\- repository,

\- version,

\- commit,

\- license,

\- NOTICE requirements,

\- modifications,

\- purpose,

\- approval.



Avoid unnecessary forks.



\---



\# 45. Technical Stack



Canonical MVP direction:



\## Frontend



\- Next.js

\- TypeScript

\- React

\- Vercel AI SDK where appropriate



\## Backend



\- FastAPI

\- Python

\- Pydantic



\## Database



\- PostgreSQL

\- separate Jous Supabase project/database



\## Infrastructure



\- Cloudflare

\- GitHub

\- GitHub Actions

\- Resend

\- Webflow for marketing site



\## Payments



\- Stripe or approved equivalent after final validation



\## AI Infrastructure



\- Portkey or LiteLLM selected through bounded evaluation

\- Jous-owned supply adapters

\- HF / Vercel / OpenRouter / BYOK supply routes



\---



\# 46. Domain Boundaries



\## jous.si



Marketing website.



Webflow may own:



\- branding,

\- content,

\- SEO,

\- landing pages,

\- waitlist,

\- campaigns.



\## app.jous.si



Jous product.



Owns:



\- Workspace,

\- Spend Intelligence,

\- Projects,

\- Wallet,

\- Rewards,

\- offers,

\- billing UX,

\- account.



\## api.jous.si



Jous backend/control plane.



Owns:



\- authentication APIs,

\- ledger APIs,

\- supply abstraction,

\- UsageEvents,

\- pricing,

\- JEAC,

\- rewards,

\- routing,

\- reconciliation.



\## docs.jous.si



Developer/API documentation and OSS notices.



\## status.jous.si



Operational status when implemented.



Webflow must never become authoritative for:



\- authentication,

\- balances,

\- rewards,

\- transactions,

\- provider credentials,

\- financial state,

\- pricing,

\- routing,

\- or settlement.



\---



\# 47. Security and Trust



Provider credentials must be:



\- encrypted,

\- access-controlled,

\- redacted from logs,

\- isolated by organization/customer.



Financial operations require:



\- idempotency,

\- audit trails,

\- append-only accounting,

\- explicit authorization.



Observability must not unnecessarily expose:



\- prompts,

\- customer secrets,

\- provider credentials,

\- sensitive economic terms.



Least privilege should apply throughout the system.



\---



\# 48. MVP Non-Goals



Do NOT build in JOUS.MVP.0:



\- full vibe-coding environment,

\- repository coding agent,

\- autonomous software factory,

\- image generation studio,

\- video generation studio,

\- voice generation studio,

\- application hosting,

\- cloud resale,

\- development sandbox,

\- P2P provider-credit trading,

\- unrestricted reward transfer,

\- cash-withdrawable rewards,

\- cryptocurrency/token economy,

\- elaborate loyalty tiers,

\- large Rewards Marketplace,

\- 50 service integrations,

\- enterprise procurement suite,

\- enterprise governance suite,

\- mobile apps,

\- proprietary frontier-model routing before sufficient evidence exists.



Scope discipline is part of the MVP.



\---



\# 49. Engineering Repository Structure



Canonical repository:



`jous/`



Suggested structure:



`apps/web`



Jous Workspace and customer product.



`services/api`



FastAPI control plane.



`packages/ledger`



Financial domain and posting rules.



`packages/rewards`



Reward rules and lifecycle.



`packages/spend`



Spend Intelligence normalization and analytics.



`packages/provider-adapters`



Supplier-neutral adapter contracts and implementations.



`docs/`



Architecture and implementation documentation.



`docs/decisions/`



Frozen architecture decisions.



`tests/`



Cross-domain acceptance and integration tests.



Structure may evolve, but domain ownership boundaries must remain clear.



\---



\# 50. Implementation Sequence



Engineering should proceed through explicit gates.



Do not implement the entire MVP in one autonomous coding task.



\---



\# 51. JOUS.CORE.1A — Foundation Gate



Implement only the structural foundation.



Includes:



\- repository structure,

\- backend service,

\- frontend shell,

\- configuration,

\- environment handling,

\- database connectivity,

\- migrations,

\- User,

\- Organization,

\- OrganizationMembership,

\- Project,

\- context-ready project boundaries,

\- execution-policy-ready architecture,

\- conversation/source-ready architecture,

\- supplier/model abstractions,

\- baseline tests.



Do NOT yet implement:



\- real payments,

\- reward issuance,

\- production inference spending,

\- autonomous routing,

\- customer fund handling,

\- production memory-engine integration,

\- full Project Memory retrieval,

\- complex context optimization.



Acceptance:



\- clean local setup,

\- migrations reproducible,

\- tests pass,

\- no supplier-specific leakage into core domain,

\- no memory-vendor-specific leakage into canonical Project semantics,

\- foundation permits future JOUS_AUTO, MODEL_STACK and PINNED_MODEL execution policies without schema or domain redesign.



\---



\# 52. JOUS.CORE.1B — Ledger Gate



Implement:



\- LedgerAccount,

\- Transaction,

\- LedgerEntry,

\- double-entry posting engine,

\- idempotency,

\- reversals/adjustments,

\- audit linkage.



Acceptance:



Every test financial event balances exactly.



No mutable balance is authoritative.



Historical entries cannot be silently edited.



\---



\# 53. JOUS.CORE.1C — Wallet Gate



Implement:



\- Wallet,

\- Jous Balance semantics,

\- reward account separation,

\- available/pending concepts where required,

\- balance derivation from ledger,

\- wallet statement API.



Use test/simulated funding initially.



Acceptance:



Wallet state can always be reconstructed from ledger postings.



\---



\# 54. JOUS.SUPPLY.2 — Supply Implementation Gate



Implement:



\- Jous Model Registry,

\- SupplyAdapter contract,

\- SupplyQuote,

\- RouteDecision,

\- normalized UsageEvent,

\- commercial status,

\- supplier inventory primitives.



Initial adapters:



1\. Hugging Face

2\. Vercel

3\. OpenRouter

4\. BYOK



Begin with test credentials and controlled execution.



Acceptance:



The same logical Jous model can execute through more than one eligible supplier without changing Jous domain semantics.



\---



\# 55. JOUS.FREE.1 — Free Gate



Implement controlled free inference.



Includes:



\- free route eligibility,

\- free limits,

\- UsageEvents,

\- project attribution,

\- supplier cost capture,

\- $0 customer charge,

\- promotional subsidy classification,

\- abuse controls.



Acceptance:



Jous can explain exactly what every free request cost Jous and why it was free to the customer.



\---



\# 56. JOUS.USE.1 — Workspace Gate



Implement focused multi-model Workspace.



Includes:



\- streaming chat,

\- project selection,

\- execution-policy selection,

\- Jous Auto basic policy,

\- model-stack and pinned-model controls as approved for the gate,

\- project context continuity,

\- bounded ContextPackage assembly using the approved JOUS.CONTEXT implementation for this gate,

\- usage display,

\- economic event linkage.



Acceptance:



A customer request creates one reconstructable chain:



\*\*Request → ContextPackage → ExecutionPolicy → RouteDecision → Supplier Execution → UsageEvent → Project Attribution\*\*



\---



\# 57. JOUS.SPEND.1 — Spend Intelligence Gate



Implement:



\- normalized spend,

\- project spend,

\- supplier/model spend,

\- time-period views,

\- basic external/manual spend capture where justified,

\- savings evidence model.



Acceptance:



Displayed settled spend reconciles to canonical economic records.



\---



\# 58. JOUS.REWARD.1 — Rewards Gate



Implement:



\- RewardRule,

\- reward lifecycle,

\- funding source,

\- caps,

\- Usage Rewards,

\- Funding Bonus support,

\- promotional reward support,

\- ledger postings,

\- reversals.



Acceptance:



Every reward can answer:



\- why it was issued,

\- what rule issued it,

\- what funded it,

\- what event caused it,

\- and what ledger entries represent it.



\---



\# 59. JOUS.PAY.1 — Payment Gate



Only after economic/legal approval.



Implement approved funding path using test mode first.



Includes:



\- funding intent,

\- processor event,

\- settlement,

\- fees,

\- failure,

\- refund,

\- dispute,

\- reconciliation,

\- Jous Balance ledger posting.



Acceptance:



Processor activity and Jous Ledger reconcile without manual balance mutation.



\---



\# 60. JOUS.ROUTE.1 — API Gate



Implement narrow OpenAI-compatible Jous API.



It must use the same:



\- authentication,

\- organization/project model,

\- Model Registry,

\- SupplyAdapters,

\- UsageEvents,

\- JEAC,

\- ledger,

\- rewards,

\- Spend Intelligence.



Acceptance:



Workspace and API usage produce economically equivalent canonical records.



\---



\# 61. JOUS.INTELLIGENCE.1 — Economic Routing Gate



Only after sufficient economic evidence exists.



Implement proprietary effective-cost recommendations using:



\- capability,

\- quality,

\- JEAC,

\- reliability,

\- latency,

\- customer constraints,

\- provider economics,

\- reward economics.



Begin offline or shadow mode.



Acceptance:



Jous can demonstrate improved expected customer economic value without violating customer-declared constraints.



Production activation requires explicit approval.



\---



\# 62. JOUS.BETA.1 — Beta Gate



Target approximately 50 qualified builders.



Measure:



\- activated users,

\- Free → funded conversion,

\- monthly routed spend,

\- project attribution rate,

\- average JEAC,

\- customer effective savings,

\- reward cost,

\- gross contribution,

\- supplier mix,

\- funding mix,

\- retention,

\- meaningful activity moved through Jous.



The beta should answer:



> Does Jous create enough economic value that serious AI builders change their behavior?



\---



\# 63. Canonical Economic Acceptance Test



For an individual AI task, Jous must eventually be able to reconstruct:



1\. user,

2\. organization,

3\. project,

4\. logical Jous model,

5\. route decision,

6\. supplier,

7\. supplier model,

8\. supplier usage,

9\. supplier cost,

10\. gateway/platform cost,

11\. funding overhead,

12\. JEAC,

13\. customer charge,

14\. customer savings where defensible,

15\. reward,

16\. reward funding source,

17\. promotional subsidy where applicable,

18\. gross contribution,

19\. commercial eligibility,

20\. ledger transactions.



The same data must aggregate consistently to:



\- project,

\- customer,

\- organization,

\- supplier,

\- and Jous-wide views.



\---



\# 64. Development Agent Policy



Codex is the primary canonical implementation agent.



Claude Code may be used as a secondary reviewer.



Rapid prototyping tools may be used for UI exploration but must not become authoritative for:



\- ledger,

\- financial state,

\- rewards,

\- pricing,

\- supplier economics,

\- reconciliation,

\- or economic routing.



GitHub is the source of truth.



Every implementation gate should:



1\. start from clean `main`,

2\. create a bounded change,

3\. include tests,

4\. produce an implementation report,

5\. pass review,

6\. then commit.



Do not allow coding agents to expand product scope without an approved architecture decision.



\---



\# 65. Implementation Guardrails



Engineering must NOT:



\- hard-code supplier dependence above adapters,

\- hard-code a permanent reward percentage,

\- treat supplier price as complete JEAC,

\- combine purchased funds and rewards,

\- mutate historical ledger entries,

\- silently rewrite reconciled usage,

\- assume zero customer charge means zero Jous cost,

\- bypass commercial eligibility,

\- hide promotional subsidies,

\- automatically convert customer funding into supplier credits,

\- optimize only for Jous margin,

\- or build deferred product surfaces.



\---



\# 66. Launch and Legal Gate



Before public customer funds or economically meaningful rewards are enabled:



\- funding structure must be reviewed,

\- reward semantics must be reviewed,

\- customer disclosures must be approved,

\- supplier commercial rights must be confirmed,

\- payment/refund/dispute flows must be validated,

\- privacy/security controls must pass review,

\- reconciliation must pass test scenarios.



Technical success alone does not authorize financial launch.



\---



\# 67. Final MVP Decision



Jous MVP will be:



\*\*A focused economic operating layer for serious AI builders.\*\*



It will combine:



\- controlled free AI acquisition,

\- multi-model AI access,

\- Jous Balance,

\- append-only double-entry ledger,

\- Spend Intelligence,

\- Project Economics,

\- dynamic Jous Rewards,

\- supplier-neutral execution,

\- JEAC,

\- BYOK,

\- and a focused Jous Workspace.



It will reuse commodity infrastructure while keeping Jous's differentiated economic system proprietary.



It will not attempt to become an all-purpose AI creation platform during MVP.



The product should prove one thing exceptionally well:



> Jous can make the economics of building with AI materially better for the customer.



\---



\# 68. Canonical Decision Chain



Implementation authority should be read in this order:



1\. `JOUS.SUPPLY.1`

2\. `JOUS.ECON.1`

3\. `JOUS.CONTEXT.1`

4\. `JOUS.MVP.0`

5\. Gate-specific implementation specification

6\. Code and tests



If implementation discovers a material contradiction with an approved decision, engineering should stop and create a new decision or amendment rather than silently changing the architecture.



\---



\# 69. First Engineering Gate



The first coding gate after this specification is frozen is:



\# JOUS.CORE.1A



Foundation only.



No real customer funds.



No production reward issuance.



No uncontrolled AI spend.



No complex routing.

No production memory engine.

No full context-retrieval implementation.

The foundation must preserve the Project Context and Execution Policy seams required by JOUS.CONTEXT.1.



The goal is to create the smallest trustworthy foundation on which the Jous economic system can be built.



\---



\# END — JOUS.MVP.0 v2

