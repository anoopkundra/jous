# CORE.1A Step 1 local development

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
python -m uvicorn jous_api.main:app --host 127.0.0.1 --port 8000
```

The API can start but intentionally has no routes; requests return 404.
The provider package has no runtime dependencies or implementations. Editable
installs use the build backend pinned in the lock, avoiding a second resolver.

Environment examples contain reserved names/placeholders only and are not loaded
yet. Do not supply production credentials. Step 2 will implement typed settings,
validation, liveness/readiness semantics, and logging. PostgreSQL connectivity,
ORM, migrations, domain persistence and tenant CRUD remain subsequent work.

## Repository safety

Existing untracked backup/review/website artifacts are outside Step 1. Preserve
them. Review explicit paths before any future staging; never use broad staging.
No CI is introduced in this step; full gate CI follows the verification suite.
