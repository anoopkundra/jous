# Foundation tests

Run from the repository root after installing the locked Python environment:

```text
python -m unittest discover -s tests -v
```

Step 1 verifies application import/lifespan without opening a listener. Step 2
adds offline settings, redaction, JSON logging, request correlation, liveness and
safe unexpected-error checks using a direct ASGI harness.
Step 3 adds PostgreSQL engine/session construction without connections, real
empty-session commit/rollback/close lifecycle, mocked connectivity probes,
timeout cleanup, readiness success/failure, and response/log redaction checks.
Normal tests are offline and require neither PostgreSQL nor SQLite.
Step 4 adds exact schema/column, UUID/timestamp/nullability, named relational
constraint, neutral-boundary, deterministic offline migration SQL, revision,
credential-safety and no-connection import checks. A separate explicitly invoked
`validate_managed_migrations.py` checks an empty managed PostgreSQL project; it
is not part of unittest discovery. See local-development documentation for safety
requirements and invocation. No local PostgreSQL installation is required.
Step 5 adds immutable identity/scope, exact identity mapping, scoped SQL predicates,
default identity rejection, forged-header rejection, correlated safe access errors,
identical inaccessible/missing Project responses and concurrent request-isolation
tests. Temporary routes and identity overrides exist only in test applications.
`validate_managed_access.py` separately proves actual PostgreSQL access behavior
with transactional temporary records and rollback, preserving revision and RLS.
It is not included in unittest discovery; see local-development documentation.
Step 6 adds offline real ES256 signature verification, user-token claim/time checks,
JWKS transport/cache/rotation/outage bounds, Bearer extraction, credential-safe
correlated failures, concurrent production-dependency identity isolation, and the
complete owner/member action matrix with scoped persistence revalidation. Generated
test keys and tokens exist only in memory; no real authentication credentials or
network access are needed. CRUD, runtime-role/RLS validation, and supplier-contract
tests arrive with their corresponding implementation steps.
JWKS lifecycle regressions use actual controlled blocking worker threads, with
bounded release/cleanup. They prove one real fetch survives caller timeout and
cancellation without replacement, concurrent random-key requests coalesce, valid
cached tokens do not wait for unrelated refreshes, and close rejects late results.
Tests must never require production credentials, paid inference, or customer funds.


Step 7 adds offline context sequencing, exact helper resolution, switching/mismatch
rejection, transaction/commit/cancellation cleanup, runtime/admin separation,
credential-safe guards and deterministic migration security contracts. These tests
DO NOT prove PostgreSQL policy execution. Imports of the managed validator do not
connect. Existing Step 4/5 managed scripts are retired and refuse execution to prevent
unsafe legacy downgrade/access behavior. Use the explicit Step 7 validator only
after the founder-managed execution gate; see infrastructure/local development docs.

The locked environment currently uses unittest; pytest is not a required dependency.
Do not install a test framework just to rerun the existing suite. Remove database
credentials from the shell when performing offline checks. Actual runtime login,
policy recursion, effective ACLs and pool/cancellation behavior remain managed tests.
