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
