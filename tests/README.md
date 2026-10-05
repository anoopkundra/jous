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
Domain persistence, authorization, migration, CRUD, isolation, and
supplier-contract tests arrive with their corresponding implementation steps.
Tests must never require production credentials, paid inference, or customer funds.
