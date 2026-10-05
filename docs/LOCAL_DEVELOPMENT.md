# CORE.1A Steps 1–2 local development

Use Node 22.22.0 / npm 10.9.4 and Python 3.12.10. Python metadata currently targets
3.12 only; widening support requires validation. Run commands from the repository
root. On Windows use `npm.cmd` if PowerShell blocks `npm.ps1`.

## Frontend

```text
npm ci
npm run typecheck:web
npm run build:web
npm run dev:web
```

The static foundation page runs on localhost:3000. No external fonts or services
are requested. `package-lock.json` pins transitive packages and integrity values.

## Backend

Create an isolated environment; do not install into system Python:

```text
python -m venv .venv
```

On Windows use `.venv\Scripts\python.exe` for the following `python` commands;
on POSIX use `.venv/bin/python`.

```text
python -m pip install -r services/api/requirements.lock
python -m pip install --no-deps --no-build-isolation -e services/api -e packages/provider-adapters
python -m pip check
python -m unittest discover -s tests -v
python -m jous_api.main
```

The API exposes `GET /health/live`, returning `{"status":"alive"}`. It does not
claim database, supplier, or inference readiness. No readiness endpoint exists.
The module launcher applies `JOUS_API_HOST`/`JOUS_API_PORT` and disables Uvicorn
access logs. If using Uvicorn's CLI instead, pass host/port explicitly and use
`--no-access-log`; CLI bind options are independent of Jous settings.
The provider package has no runtime dependencies or implementations. Editable
installs use the build backend pinned in the lock, avoiding a second resolver.

Environment examples contain placeholders only. Export values in your shell;
`.env` files are not automatically loaded. Never copy placeholder values into
an active environment. No secrets are required for local process-health checks.

| Variable | Default / requirement |
| --- | --- |
| JOUS_ENVIRONMENT | development; accepts development, test, production |
| JOUS_SERVICE_NAME | jous-api; 1–64 ASCII letters, digits, underscore or hyphen |
| JOUS_LOG_LEVEL | INFO; DEBUG, INFO, WARNING, ERROR, CRITICAL |
| JOUS_API_HOST | 127.0.0.1; bind hostname/IP |
| JOUS_API_PORT | 8000; integer 1–65535 |
| JOUS_DATABASE_URL | optional locally; required in production, PostgreSQL URL with host/database |

Database configuration is masked and validated syntactically only: this step
does not connect, validate credentials, or establish readiness. For tests,
`load_settings({ ... })` avoids process-environment inheritance, and
`create_app(Settings(environment="test"))` allows explicit application setup.
Production configuration errors report variable names, not supplied values.
No CORS middleware is needed by the current static frontend, which does not
call the API. Origin configuration will be introduced with actual connectivity.

Application logs are JSON with UTC timestamp, severity, service, environment,
event, request ID and status where applicable. Startup/shutdown events and
request success/failure events are logged. Arbitrary log messages, exception
text/tracebacks, request bodies, query strings, paths and credentials are omitted.
Uvicorn's own lifecycle logs remain separate from application JSON logs.

`X-Request-ID` is an untrusted correlation label, never identity/authorization.
Exactly one incoming ASCII identifier of 1–64 characters is accepted when it
starts with a letter/digit and contains only letters, digits, dots, underscores
or hyphens. Missing, duplicate, oversized or malformed IDs are replaced by UUID
hex values. The ID is returned in responses and exposed through request state
and a task-local logging context. Clients must not put secrets in IDs.

Unexpected exceptions before response headers produce HTTP 500 with
`{"error":{"code":"internal_error","message":"Internal server error"},"request_id":"..."}`.
Failures after headers cannot replace the response/status; the boundary logs a
failure and terminates any unfinished body without internal details. Request
context is reset in all cases. More detailed diagnostics and streaming semantics
require a later bounded review; this gate does not implement streaming inference.

PostgreSQL connectivity, ORM, migrations, domain persistence, authorization and
tenant CRUD remain subsequent work.

## Repository safety

Existing untracked backup/review/website artifacts are outside Step 1. Preserve
them. Review explicit paths before any future staging; never use broad staging.
No CI is introduced in this step; full gate CI follows the verification suite.
