\# JOUS.ECON.1 — Wallet Funding, Unit Economics \& Rewards Economics



\*\*Status:\*\* APPROVED FOR MVP  

\*\*Project:\*\* Jous  

\*\*Decision ID:\*\* JOUS.ECON.1  

\*\*Depends on:\*\* JOUS.SUPPLY.1  

\*\*Scope:\*\* MVP economic architecture



\---



\## 1. Purpose



This document defines the economic architecture for the Jous MVP.



It establishes how Jous will:



\- accept customer funding,

\- represent customer balances,

\- acquire AI inference,

\- calculate effective acquisition cost,

\- measure gross contribution,

\- issue Jous Rewards,

\- incentivize economically efficient funding,

\- account for free usage,

\- and protect sustainable unit economics.



The objective is not simply to sell AI inference.



Jous exists to:



> Make every AI dollar go further.



The economic system must therefore optimize customer value while maintaining a sustainable Jous business.



\---



\## 2. Core Economic Principle



Jous must not promise a permanently fixed reward percentage on gross AI spending unless the economics supporting that reward are measurable and sustainable.



The canonical rule is:



> Rewards must be funded by measurable economic capacity, not by a permanently fixed percentage of gross AI spend.



Economic capacity may come from:



\- supplier pricing advantages,

\- economic routing,

\- model optimization,

\- supplier rebates,

\- negotiated discounts,

\- payment-method savings,

\- partner-funded promotions,

\- promotional customer acquisition budgets,

\- or other measurable economic value created by Jous.



Jous Rewards are therefore rules-based and dynamic.



Do not hard-code:



`reward\_rate = 2%`



or any equivalent permanent global reward percentage.



\---



\## 3. Customer Economic Promise



Jous should help the customer answer:



> How should your next AI dollar be spent?



The customer value loop is:



\*\*SEE → OPTIMIZE → EARN → REDEEM → BUILD MORE → REPEAT\*\*



Jous should expose economic value transparently where practical, including:



\- AI spending,

\- project spending,

\- estimated task cost,

\- actual task cost,

\- savings created,

\- Jous Rewards earned,

\- funding bonuses,

\- and effective AI cost.



The economic system should reward continued building rather than obscure the economics from the customer.



\---



\## 4. Jous Balance



\### 4.1 Definition



\*\*Jous Balance\*\* represents customer-purchased prepaid value that may be used for eligible Jous services.



For the MVP:



\- Jous Balance is not a bank account.

\- It is not a peer-to-peer payment instrument.

\- It is not customer-withdrawable cash.

\- It is not transferable between unrelated customers.

\- It must not be represented as an investment.

\- It must remain distinct from Jous Rewards.



All balance movements must be represented through the Jous Ledger defined by JOUS.CORE.1.



A mutable `user.balance` field must never be the financial source of truth.



\---



\## 5. Jous Rewards



\### 5.1 Definition



\*\*Jous Rewards\*\* represent promotional or economically funded value awarded by Jous.



For the MVP, rewards should be:



\- non-cash,

\- non-withdrawable,

\- non-transferable,

\- usable only for eligible Jous services or offers,

\- subject to rules and caps,

\- and potentially subject to expiration or promotional restrictions.



Rewards must be accounted for separately from purchased Jous Balance.



\### 5.2 Reward Lifecycle



The MVP architecture should support:



\- PENDING

\- SETTLED

\- AVAILABLE

\- REDEEMED

\- EXPIRED

\- REVERSED



Reward issuance and redemption must be ledger-backed and auditable.



\---



\## 6. Reward Sources



Jous should distinguish the economic source of a reward.



Initial categories:



\### 6.1 Usage Rewards



Rewards generated from eligible AI consumption when sufficient economic capacity exists.



\### 6.2 Funding Bonus



Rewards generated because a customer uses an economically favorable funding method.



Example:



Bank/ACH funding may create lower payment-processing costs than card funding.



Jous may share part of that saving with the customer.



\### 6.3 Promotional Rewards



Rewards deliberately funded by Jous as customer acquisition or retention expense.



These must be measured as promotional/CAC expense rather than disguised as normal product gross margin.



\### 6.4 Partner-Funded Rewards



Future rewards may be funded partly or completely by:



\- AI providers,

\- software partners,

\- marketplace partners,

\- model developers,

\- or other ecosystem participants.



The rewards engine must therefore include a `funded\_by` concept.



\---



\## 7. Funding Methods



The MVP should support:



\### Credit / Debit Card



Customers may fund Jous Balance using supported cards.



Jous should not discourage card usage.



Customers may receive external benefits from their card issuer, such as points, miles, or cash-back rewards.



Jous should not assume those benefits have zero customer value.



\### Bank / ACH



ACH should be presented as an economically preferred funding method when it materially reduces Jous funding cost.



Suggested customer positioning:



\*\*Bank Account — Best Value\*\*



Jous may offer an additional Funding Bonus for eligible ACH funding.



\---



\## 8. Funding Economics Benchmark



For economic modeling, the initial Stripe-style baseline observed/researched during MVP planning is approximately:



\- Card: 2.9% + $0.30

\- US ACH Direct Debit: approximately 0.8%, capped at $5



These values must remain configurable and must not be permanently embedded as business constants.



\### Example — $100 Funding



Card:



\- Customer Jous Balance: $100.00

\- Approximate processing cost: $3.20

\- Approximate Jous cash received: $96.80



ACH:



\- Customer Jous Balance: $100.00

\- Approximate processing cost: $0.80

\- Approximate Jous cash received: $99.20



Approximate ACH economic advantage:



\*\*$2.40 per $100 funded\*\*



\### Example — $1,000 Funding



Card:



\- Approximate processing cost: $29.30



ACH:



\- Approximate processing cost: $5.00 due to the assumed cap



Approximate ACH economic advantage:



\*\*$24.30 per $1,000 funded\*\*



This economic advantage may partly fund a customer Funding Bonus while allowing Jous to retain part of the saving.



\---



\## 9. Funding Bonus Principle



Jous should not force customers to use ACH.



Instead:



\### Card



Customer receives:



\- normal eligible Jous Usage Rewards,

\- plus any rewards independently provided by their card issuer.



\### ACH



Customer receives:



\- normal eligible Jous Usage Rewards,

\- plus a configurable Jous Funding Bonus.



Example only:



If ACH saves Jous $2.40 versus card on a $100 funding event, Jous might award:



\- $1.00 Funding Bonus to customer,

\- retain $1.40 of payment-cost savings.



This is illustrative and must not be hard-coded.



Actual bonus levels should be determined by the Reward Rules Engine.



\---



\## 10. AI Supply Economics



Customer funding economics and AI supplier economics must remain separate.



Jous must not automatically mirror customer deposits into equivalent supplier credit purchases.



Instead:



\*\*Customer funding → Jous Balance\*\*



and separately:



\*\*Jous Treasury → Supplier Inventory\*\*



Jous should maintain pooled supplier inventory and replenish suppliers based on:



\- expected usage,

\- supplier economics,

\- inventory thresholds,

\- operational reliability,

\- and working-capital requirements.



\---



\## 11. Hugging Face Economic Observation



The JOUS.SUPPLY.1 benchmark identified an important economic advantage for Hugging Face.



Observed benchmark:



\- $10 of Hugging Face credits purchased

\- $10.00 customer charge

\- no separate funding/service surcharge observed



Hugging Face documentation reviewed during the benchmark also indicated that routed Inference Providers are billed at the underlying provider rate without an additional Hugging Face routed-inference markup.



Therefore:



> Hugging Face currently represents the strongest observed low-overhead open-model supply route among the suppliers benchmarked for Jous.



This must not be interpreted as:



> Hugging Face has zero total economic cost.



Jous may still incur:



\- customer payment-processing costs,

\- underlying inference cost,

\- operational costs,

\- reconciliation costs,

\- failure/retry costs,

\- and other attributable expenses.



The precise canonical statement is:



> No Hugging Face funding/platform surcharge was observed in the Jous benchmark.



Supplier pricing and commercial terms can change and must therefore remain configurable and periodically revalidated.



\---



\## 12. Comparison With Other Benchmarked Supply Routes



\### Hugging Face



Observed funding example:



\- $10 credits

\- $10.00 charged

\- observed funding surcharge: 0%



Strength:



\*\*Potentially lowest observed financial overhead for equivalent underlying open-model inference.\*\*



\### Vercel AI Gateway



Observed funding example:



\- $20 credits

\- $0.88 additional fee

\- $20.88 total



The observed fee matched approximately:



\*\*2.9% + $0.30\*\*



Strength:



\*\*Managed routing, resilience and operational simplicity.\*\*



\### OpenRouter



Observed funding example:



\- $10 credits

\- $0.80 service fee

\- $10.80 total



A larger displayed funding example indicated:



\- $500 credits

\- $27.50 fee

\- $527.50 total



Strength:



\*\*Supplier breadth, market intelligence and provider telemetry.\*\*



\### Economic Decision



Supplier selection must not be based solely on model token price.



Jous should evaluate the full effective acquisition cost.



\---



\## 13. Jous Effective Acquisition Cost — JEAC



The canonical economic metric is:



\# Jous Effective Acquisition Cost (JEAC)



Conceptually:



\*\*JEAC =\*\*



provider inference cost  

\+ gateway/platform cost  

\+ supplier funding overhead  

\+ payment/funding overhead attributable to usage  

\+ directly attributable operational cost  

\+ retry/failure economic adjustment  

− supplier discounts  

− rebates  

− supplier-funded incentives



Where appropriate, Jous should eventually optimize:



> JEAC per successful task



rather than merely:



> price per million tokens.



This allows Jous to account for situations where a nominally cheaper route produces:



\- more failures,

\- more retries,

\- greater latency,

\- lower task success,

\- or additional downstream expense.



\---



\## 14. $100 Baseline Economics



Consider a customer who funds and consumes $100.



If Jous charges $100 while acquiring exactly $100 of inference:



\### Card



Customer revenue/value: $100.00  

Payment processing: approximately $3.20  

Supplier inference: $100.00



Contribution before rewards:



\*\*-$3.20\*\*



\### ACH



Customer revenue/value: $100.00  

Payment processing: approximately $0.80  

Supplier inference: $100.00



Contribution before rewards:



\*\*-$0.80\*\*



Therefore:



> Selling inference at underlying supplier list cost while absorbing funding fees does not create sustainable reward capacity.



Jous cannot base its long-term rewards model on this structure.



\---



\## 15. Economic Optimization Example



Suppose Jous provides $100 of customer AI value while achieving an $85 JEAC through:



\- supplier selection,

\- model selection,

\- routing,

\- caching,

\- context optimization,

\- negotiated economics,

\- or other legitimate efficiency.



\### Card



Customer value/revenue: $100.00  

Payment cost: $3.20  

JEAC: $85.00



Economic capacity before rewards:



\*\*$11.80\*\*



\### ACH



Customer value/revenue: $100.00  

Payment cost: $0.80  

JEAC: $85.00



Economic capacity before rewards:



\*\*$14.20\*\*



If Jous awards $3 of eligible Rewards:



Card contribution:



\*\*$8.80\*\*



ACH contribution:



\*\*$11.20\*\*



This demonstrates the desired Jous economic model:



> Create measurable economic value and share part of that value with the customer.



\---



\## 16. Customer Value Components



Jous should distinguish at least three forms of customer economic value.



\### Routing Savings



Value created by selecting a more economically efficient execution path.



Example:



\*\*Saved with Jous: $12.40\*\*



\### Jous Usage Rewards



Reward value earned from eligible usage.



Example:



\*\*Jous Rewards earned: $2.10\*\*



\### Funding Bonus



Additional reward generated by an economically favorable funding method.



Example:



\*\*Bank funding bonus: $1.00\*\*



These must remain separately measurable.



\---



\## 17. Customer-First Economic Optimization



Jous must not build a router whose objective is simply:



> maximize Jous margin.



That would create a structural conflict with the Jous customer promise.



The economic routing objective should consider:



\- customer effective cost,

\- task capability,

\- expected quality,

\- reliability,

\- latency/performance,

\- context requirements,

\- commercial eligibility,

\- and sustainable Jous margin.



The guiding principle is:



> Jous optimizes customer value, not merely Jous margin.



\---



\## 18. Jous Auto Economic Objective



Jous Auto should eventually operate conceptually as:



Task Understanding  

→ Capability Requirements  

→ Context Optimization  

→ Model Selection  

→ Supplier Selection  

→ Economic Evaluation  

→ Execution  

→ Usage Measurement  

→ Outcome Measurement  

→ Reward Calculation



Jous Auto belongs to Jous.



It must not simply proxy another gateway's automatic routing policy.



\---



\## 19. Economic-Aware Fallback



Fallback can materially change task economics.



A failed inexpensive supplier followed by an expensive fallback may produce a successful request while destroying expected unit economics.



Jous should therefore support future controls including:



\- `max\_fallback\_cost\_multiplier`

\- `max\_absolute\_task\_cost`

\- `minimum\_provider\_health`

\- `maximum\_latency`

\- `minimum\_capability\_score`



Fallback decisions must become part of JEAC.



\---



\## 20. Rewards Rules Engine



The rewards system must be configuration-driven.



A conceptual RewardRule should support fields such as:



\- event\_type

\- funding\_method

\- customer\_segment

\- organization

\- project

\- model

\- supplier

\- route

\- commercial\_status

\- JEAC

\- promotion

\- spend\_threshold

\- reward\_rate

\- fixed\_reward

\- reward\_cap

\- funded\_by

\- starts\_at

\- ends\_at

\- status



Reward calculations must be reproducible and auditable.



\---



\## 21. Reward Guardrails



A reward must not be issued merely because a usage event occurred.



The rules engine should be capable of checking:



\- sufficient economic capacity,

\- promotion budget,

\- reward caps,

\- customer eligibility,

\- supplier eligibility,

\- funding source,

\- commercial status,

\- abuse controls,

\- and settlement status.



Jous should support both:



\- percentage rewards,

\- and fixed rewards,



but neither should be globally guaranteed without an applicable rule.



\---



\## 22. JOUS.FREE.1 — Free Inference Acquisition Layer



Freemium is part of the MVP economic architecture.



Jous Free is not intended to become an unlimited free chatbot.



Its purpose is:



> Acquire qualified AI builders and move them into the Jous economic network.



Jous Free should preferentially use:



\### Supplier-Funded / Zero-Cost Supply



Preferred whenever commercially eligible and operationally acceptable.



\### Jous Promotional Supply



Premium inference deliberately subsidized by Jous.



This must be treated as customer acquisition expense.



\### BYOK



Customers may use their own provider credentials while receiving Jous spend intelligence, project attribution and economic tooling.



\---



\## 23. Free Supply Eligibility



A route should only qualify for Jous Free when:



\- `free\_eligible = TRUE`

\- `commercial\_eligible = TRUE`



The Model Registry should support fields such as:



\- free\_eligible

\- free\_source

\- free\_cost\_to\_jous

\- free\_daily\_limit

\- free\_monthly\_limit

\- availability

\- commercial\_status



Supplier free tiers and promotional programs must not be assumed to be permanent.



\---



\## 24. Free Usage Accounting



Free customer usage must still create economic records.



Every eligible free request should create a UsageEvent including:



\- user

\- organization

\- project

\- model

\- supplier

\- route

\- tokens/units

\- supplier cost

\- customer charge

\- free subsidy amount

\- timestamp

\- commercial status



A customer charge of `$0.00` must never imply that the request had zero economic cost to Jous.



\---



\## 25. Promotional Inference as CAC



If Jous provides premium inference at no charge, that subsidy must be measurable.



Example:



New customer receives:



\*\*$2.00 of premium inference\*\*



The system should account for that economic value as:



\*\*Customer Acquisition / Promotional Cost\*\*



Jous should eventually measure:



\*\*Free acquisition cost ÷ free-to-funded conversion rate = CAC per funded builder\*\*



This allows Jous Free to be managed as an acquisition engine rather than an uncontrolled expense.



\---



\## 26. MVP Product Ladder



\### Jous Free — $0



Initial capabilities:



\- curated free/zero-cost AI capacity,

\- basic Jous Auto,

\- basic Spend Intelligence,

\- basic project attribution,

\- no payment method required merely to sign up and use eligible free capacity.



\### Jous Builder — Pay For What You Use



Capabilities:



\- premium models,

\- funded Jous Balance,

\- economic routing,

\- project economics,

\- Jous Usage Rewards,

\- eligible Funding Bonuses,

\- richer Spend Intelligence.



A conventional fixed monthly Jous Pro subscription is deferred until Jous proves recurring premium value that justifies one.



\---



\## 27. Supplier Inventory



Jous should maintain supplier inventory independently from customer wallets.



Conceptual SupplyInventory fields should include:



\- supplier

\- account

\- available\_credit

\- reserved\_credit

\- estimated\_days\_remaining

\- replenishment\_threshold

\- replenishment\_target

\- last\_reconciled\_at

\- funding\_cost

\- expiration\_date

\- status



Important:



Hugging Face purchased credits may support multiple Hugging Face pay-as-you-go services.



They must therefore not automatically be represented as DeepInfra-specific inventory merely because DeepInfra was used for a particular inference request.



\---



\## 28. Treasury Principle



Customer deposits must not be immediately and mechanically converted into supplier credits.



Supplier funding decisions should consider:



\- demand forecasts,

\- supplier pricing,

\- credit expiration,

\- working capital,

\- supplier reliability,

\- concentration risk,

\- payment overhead,

\- and replenishment requirements.



This reduces unnecessary supplier lock-in and preserves Jous's economic flexibility.



\---



\## 29. Reconciliation



Jous must reconcile internal UsageEvents with supplier-reported usage and balances.



Reconciliation should detect:



\- missing usage,

\- duplicate usage,

\- supplier price changes,

\- token discrepancies,

\- unreported costs,

\- failed-request charges,

\- credit adjustments,

\- rebates,

\- and balance discrepancies.



Supplier-reported cost should not automatically replace Jous's internal ledger history.



Corrections must use append-only adjustment transactions.



\---



\## 30. Commercial Eligibility



Technical availability does not equal commercial approval.



Every execution route must eventually carry a commercial status such as:



\- UNREVIEWED

\- SELF\_SERVICE\_APPROVED

\- BYOK\_ONLY

\- NEGOTIATED

\- RESTRICTED

\- DISABLED



Economic routing must never override commercial eligibility.



A cheaper route that Jous is not commercially permitted to use is not an eligible route.



\---



\## 31. Gross Contribution



Jous should track gross contribution at multiple levels:



\- request,

\- task,

\- model,

\- supplier,

\- route,

\- project,

\- customer,

\- organization,

\- and time period.



Conceptually:



\*\*Gross Contribution = Customer Economic Revenue − JEAC − Rewards − directly attributable economic costs\*\*



Promotional subsidies should be identifiable separately so management can distinguish:



\- product economics,

\- customer acquisition spending,

\- and partner-funded incentives.



\---



\## 32. Beta Economics



The initial beta may intentionally operate below long-term target margins.



This is acceptable only when deliberate and measurable.



Beta subsidies should be classified as:



\- acquisition cost,

\- promotional cost,

\- research/benchmarking cost,

\- or another explicit economic category.



They must not silently distort normal production unit economics.



\---



\## 33. Long-Term Economic Flywheel



The desired Jous flywheel is:



More Builders  

→ More AI Spending  

→ More Aggregated Demand  

→ Better Supplier Economics  

→ Lower JEAC  

→ Better Customer Savings and Rewards  

→ Greater Customer Retention  

→ More Builders



The long-term moat is therefore not the gateway.



It is:



\- the customer financial relationship,

\- aggregated AI demand,

\- supplier economics,

\- usage intelligence,

\- project economics,

\- rewards network,

\- and effective-cost optimization.



\---



\## 34. Long-Term Value-Sharing Example



Illustrative future economics:



Public/reference AI value: $100  

Jous effective acquisition cost: $82  

Funding cost: $1  

Direct attributable operating cost: $1



Economic capacity:



\*\*$16\*\*



Jous could theoretically allocate this value as:



\- $6 customer savings

\- $3 Jous Rewards

\- $7 Jous gross contribution



This example is illustrative only.



The important principle is:



> Jous creates economic value first and then determines how that value should be shared.



\---



\## 35. MVP Engineering Requirements



The MVP implementation must support:



1\. Separate Jous Balance and Jous Rewards.

2\. Append-only double-entry financial ledger.

3\. Configurable payment/funding costs.

4\. Configurable supplier funding costs.

5\. JEAC calculation.

6\. Usage-level supplier cost capture.

7\. Customer usage charge capture.

8\. Project attribution.

9\. Rules-based rewards.

10\. Funding-method-specific bonuses.

11\. Promotional/CAC classification.

12\. Supplier inventory.

13\. Reconciliation.

14\. Commercial eligibility.

15\. Free usage accounting.

16\. Gross contribution reporting.



\---



\## 36. Engineering Prohibitions



The MVP must NOT:



\- use a mutable user balance as financial source of truth,

\- combine purchased balance with rewards,

\- hard-code a permanent global reward percentage,

\- assume supplier list price equals JEAC,

\- assume Hugging Face or any supplier will remain permanently cheapest,

\- assume free supplier capacity will remain permanently available,

\- automatically mirror customer deposits into supplier credits,

\- allow economic routing to bypass commercial eligibility,

\- hide promotional subsidies inside normal gross margin,

\- treat zero customer price as zero Jous cost,

\- or optimize solely for Jous margin.



\---



\## 37. MVP Economic Acceptance Gate



JOUS.ECON.1 is satisfied in implementation only when Jous can reconstruct, for an individual AI task:



1\. Who initiated the task.

2\. Which project it belonged to.

3\. Which logical Jous model was selected.

4\. Which supplier executed it.

5\. What supplier usage occurred.

6\. What supplier cost was incurred.

7\. What funding/platform overhead applied.

8\. What JEAC was calculated.

9\. What the customer was charged.

10\. What Jous Reward was earned.

11\. What funded that reward.

12\. What customer savings were created where measurable.

13\. What gross contribution remained.

14\. Which ledger transactions represent the economic event.



The same economics must aggregate correctly to:



\- project,

\- customer,

\- organization,

\- supplier,

\- and Jous-wide levels.



\---



\## 38. Final Decision



Jous will launch with:



\- Jous Free as a controlled acquisition layer,

\- Jous Builder as pay-for-what-you-use,

\- Jous Balance for purchased prepaid value,

\- Jous Rewards as a separate non-cash value system,

\- cards as a supported funding method,

\- ACH positioned as Best Value,

\- configurable ACH Funding Bonuses,

\- dynamic Usage Rewards,

\- supplier-neutral JEAC,

\- Hugging Face as the strongest currently observed low-overhead open-model supply route,

\- Vercel as a strong managed routing/resilience route,

\- OpenRouter as a strong supplier-market and telemetry route,

\- BYOK as a first-class route,

\- and economic routing owned by Jous.



The governing principles are:



> Make every AI dollar go further.



> Rewards must be funded by measurable economic capacity.



> Jous optimizes customer value, not merely Jous margin.



> The gateway is not the moat. The economic relationship with the AI builder is the moat.



\---



\## 39. Next Decision



After JOUS.ECON.1 is frozen, the next architecture artifact should define the canonical MVP product and implementation boundary using:



\- JOUS.SUPPLY.1

\- JOUS.ECON.1

\- the OSS architecture decision

\- JOUS.FREE.1

\- and the previously agreed Jous product requirements.



That artifact becomes the implementation contract before Codex begins JOUS.CORE.1A.

