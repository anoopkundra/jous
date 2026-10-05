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
Production authentication, CRUD, runtime-role/RLS validation, and
supplier-contract tests arrive with their corresponding implementation steps.
Tests must never require production credentials, paid inference, or customer funds.
