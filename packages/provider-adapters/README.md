# Supplier contract boundary

This dependency-free Python package reserves the Jous-owned supply interface.
Contracts and test doubles will be added in a later CORE.1A step.

Logical model identity, supplier route identity, and supplier-specific model
identifiers must remain separate. Model selection and supplier selection are
separate decisions. Future supplier implementations remain replaceable below
this boundary; no provider SDK is required here.

JOUS_AUTO, MODEL_STACK, and PINNED_MODEL are future execution-policy vocabulary,
not implemented behavior. Ordered model preferences and explicit permission for
pinned cross-model fallback remain customer policy.
# V1.2 offline supplier boundary

The `jous_supply` package contains neutral request/outcome contracts, a
source-owned admission catalog, provisional local token counting and a bounded
HF wire adapter. The HF/Qwen3-32B/DeepInfra route is **not operationally eligible**:
`HOSTED_TOKEN_TEMPLATE_AUTHORITY_UNRESOLVED`. No configuration or credential can
activate it. `execute()` denies before credential access or network activity.

`exercise_offline()` accepts only an in-memory HTTPX MockTransport and cannot
open a provider socket. Production composition never uses that seam. Requests
are non-streaming with no application retry/fallback. Only normalized allowlisted
evidence can leave the adapter; reasoning/raw envelopes are discarded.

Use only hash-checked packaged assets under `model_assets/qwen3_32b`.
`Tokenizer.from_pretrained` and runtime Hub downloads are prohibited. The local
count is `LOCAL_PROVISIONAL`; it does not establish hosted-template equivalence.

Package/dependency and build evidence live in `docs/DEPENDENCIES.md` and
`docs/build-journey/V1.2-task-context-execution.md` at the repository root.
