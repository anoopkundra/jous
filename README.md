# Jous

Jous is the economic layer for AI builders. This checkout implements only
JOUS.CORE.1A Step 1: repository boundaries and reproducible dependencies.

| Path | Responsibility |
| --- | --- |
| `apps/web` | Minimal Next.js / React / TypeScript application shell |
| `services/api` | Minimal FastAPI application package |
| `packages/provider-adapters` | Reserved neutral Python supplier-contract package |
| `packages/ledger`, `packages/rewards`, `packages/spend` | Documentation-only future boundaries |
| `tests` | Offline backend foundation checks |

Read architecture authority in order: [SUPPLY.1](docs/decisions/JOUS.SUPPLY.1.md),
[ECON.1](docs/decisions/JOUS.ECON.1.md),
[CONTEXT.1](docs/decisions/JOUS.CONTEXT.1.md),
[MVP.0](docs/JOUS.MVP.0.md), then [CORE.1A](docs/decisions/JOUS.CORE.1A.md).

Project remains the future primary context-continuity and economic-attribution
boundary within Organization ownership. Model, supplier, and memory-provider
choices must not own Project identity. Source truth and derived memory remain
distinct future concepts. No mutable balance is financial authority.

This shell has no API routes, API connectivity, database, authentication, model
execution, routing, ledger, wallet, rewards, payments, or memory engine.
It is not deployment-ready and does not complete CORE.1A.

See [local development](docs/LOCAL_DEVELOPMENT.md) and
[dependencies](docs/DEPENDENCIES.md). Jous source remains proprietary; dependency
licenses do not license Jous itself.
