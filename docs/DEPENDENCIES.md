# CORE.1A Steps 1–4 dependencies

Direct dependencies are pinned exactly. `package-lock.json` captures npm's full
resolution and integrity hashes; `services/api/requirements.lock` captures the
Python 3.12 runtime/build environment. Local Python packages install separately
with `--no-deps --no-build-isolation`. No upstream projects are modified or forked.
Released registry artifacts are used; source commit IDs were not independently
verified. Preserve upstream LICENSE/NOTICE files in any later distribution.

## Direct components

| Component | Version | License | Purpose / upstream |
| --- | --- | --- | --- |
| Next.js | 16.3.8 | MIT | Web shell; https://github.com/vercel/next.js |
| React / React DOM | 19.3.0 | MIT | Rendering; https://github.com/facebook/react |
| TypeScript | 7.0.2 | Apache-2.0 | Type checking; https://github.com/microsoft/typescript |
| @types/node | 22.20.5 | MIT | Node types; https://github.com/DefinitelyTyped/DefinitelyTyped |
| @types/react / @types/react-dom | 19.3.0 | MIT | React types; https://github.com/DefinitelyTyped/DefinitelyTyped |
| FastAPI | 0.142.2 | MIT | API shell; https://github.com/fastapi/fastapi |
| Pydantic | 2.13.5 | MIT | Required validation foundation; https://github.com/pydantic/pydantic |
| Uvicorn | 0.54.0 | BSD-3-Clause | Local ASGI server; https://github.com/Kludex/uvicorn |
| SQLAlchemy[asyncio] | 2.0.54 | MIT | Async PostgreSQL engine/session; https://github.com/sqlalchemy/sqlalchemy |
| asyncpg | 0.31.0 | Apache-2.0 | PostgreSQL async driver; https://github.com/MagicStack/asyncpg |
| Alembic | 1.20.0 | MIT | Canonical schema migrations; https://github.com/sqlalchemy/alembic |
| setuptools | 84.0.0 | MIT | Python package build/editable installs; https://github.com/pypa/setuptools |

Foundation tests use standard-library unittest. Step 3 adds PostgreSQL connectivity
only; Step 4 adds declarative models and Alembic schema history. No supplier, gateway, memory, payment,
routing, or observability platform has been introduced.

## Python transitive components

| Component | Version | License |
| --- | --- | --- |
| annotated-doc | 0.0.5 | MIT |
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| click | 8.5.0 | BSD-3-Clause |
| greenlet | 3.5.6 | MIT AND PSF-2.0 |
| h11 | 0.16.0 | MIT |
| idna | 3.20 | BSD-3-Clause |
| Mako | 1.4.3 | MIT |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| opentelemetry-api | 1.45.0 | Apache-2.0 |
| pydantic_core | 2.46.5 | MIT |
| starlette | 1.7.0 | BSD-3-Clause |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |

OpenTelemetry API is required transitively by this FastAPI release. There is no
SDK, exporter, collector, telemetry configuration, or application instrumentation.
PSF-2.0 is a permissive license; retain the supplied license and notices.
The SQLAlchemy asyncio extra requires greenlet on all supported platforms;
its exact version is pinned in the Python lock. Step 3 package metadata and
installed license files were inspected. These licenses are permissive; preserve
their license/copyright records. No Psycopg or SQLite dependency is introduced.
Step 4 adds only Alembic and its Mako/MarkupSafe transitive dependencies. Exact
installed metadata and license files were inspected; all are permissive.
Existing SQLAlchemy/asyncpg versions are retained, with no additional driver.

## Frontend transitive components

The lock includes platform variants even when not installed on this machine.
Next.js env/SWC packages are 16.3.8 (MIT); TypeScript platform packages are 7.0.2
(Apache-2.0). Other components:

| Component | Version | License |
| --- | --- | --- |
| @emnapi/runtime | 1.11.3 | MIT |
| @img/colour | 1.1.0 | MIT |
| @swc/helpers | 0.5.23 | Apache-2.0 |
| baseline-browser-mapping | 2.11.27 | Apache-2.0 |
| caniuse-lite | 1.0.30001814 | CC-BY-4.0 |
| client-only | 0.0.1 | MIT |
| csstype | 3.2.3 | MIT |
| detect-libc | 2.1.2 | Apache-2.0 |
| nanoid | 3.3.19 | MIT |
| picocolors | 1.1.1 | ISC |
| postcss | 8.5.23 | MIT |
| scheduler | 0.28.0 | MIT |
| semver | 7.8.5 | ISC |
| sharp | 0.35.5 | Apache-2.0 |
| source-map-js | 1.2.2 | BSD-3-Clause |
| styled-jsx | 5.1.6 | MIT |
| tslib | 2.8.1 | 0BSD |
| undici-types | 6.21.0 | MIT |

Sharp's platform binaries are 0.35.5. Several declare Apache-2.0, but Windows
binaries also declare LGPL-3.0-or-later and the WASM binary declares
Apache-2.0 AND LGPL-3.0-or-later AND MIT. Its libvips platform packages are 1.3.4
and declare LGPL-3.0-or-later. These are transitive Next.js image-processing
dependencies; this shell does not use image optimization.

## Founder approval and compliance policy

**Founder decision:** JOUS.CORE.1A Step 1 dependency review is
**APPROVED WITH NOTICE/ATTRIBUTION REQUIREMENTS**.

Retain the current Next.js dependency set, including transitive Sharp/libvips
and caniuse-lite dependencies. This records the review required by MVP section 44
and CONTEXT section 67, subject to the following compliance policy:

1. Sharp itself is Apache-2.0; applicable Sharp binary packages contain
   LGPL-licensed libvips/components.
2. caniuse-lite is CC-BY-4.0.
3. These dependencies are approved for the current Jous proprietary SaaS
   architecture.
4. Jous must preserve applicable license and attribution records.
5. Before Jous distributes customer software, native/WASM binaries, container
   images intended for customer possession, installers, or on-premises packages,
   perform a new distribution-license compliance review.
6. That future review must verify applicable notices/license copies,
   covered-library source availability, and LGPL replacement/relinking obligations
   where applicable.
7. This approval does NOT authorize ignoring license obligations and does NOT
   constitute a blanket approval for future distribution models.
8. Jous proprietary application source is not being relicensed or opened under
   LGPL or CC-BY by this decision.

No later-gate dependency is approved by this document.
