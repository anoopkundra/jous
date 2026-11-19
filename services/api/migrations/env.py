"""Asyncpg migrations through Jous settings; offline SQL requires no credentials."""

import asyncio
import re
import sys

from alembic import context

from jous_api.config import ConfigurationError, load_migration_settings
from jous_api.database import Database
from jous_api.models import Base
from jous_api import task_models  # explicitly register only approved additive tables


_FAILURE_STAGE = "SETTINGS"
_SAFE_STAGES = {
    "SETTINGS", "DATABASE_CONSTRUCTION", "CONNECTION",
    "ALEMBIC_MIGRATION", "CLEANUP",
}
_SQLSTATE_PATTERN = re.compile(r"[0-9A-Z]{5}\Z")
_URI_PATTERN = re.compile(r"\b[a-z][a-z0-9+.-]*://[^\s\]\[()<>]+", re.IGNORECASE)
_SENSITIVE_KV_PATTERN = re.compile(
    r"(?i)\b(password|passwd|pwd|token|secret|api[_-]?key|"
    r"username|user|dsn|database[_-]?url|database|host|port|dbname|"
    r"sslmode|sslrootcert|application[_-]?name|options|passfile)\s*[:=]\s*"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)"
)
_QUOTED_FRAGMENT_PATTERN = re.compile(r"(['\"]).*?\1")
_SQL_STATEMENT_PATTERN = re.compile(
    r"(?i)\b(select|insert|update|delete|truncate|create|alter|drop|grant|"
    r"revoke|execute|set\s+(?:local|session))\b"
)


def _exception_chain(candidate):
    """Yield exception objects without rendering them or their arguments."""
    pending = [candidate]
    seen = set()
    while pending:
        current = pending.pop(0)
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        for attribute in ("__cause__", "__context__", "orig"):
            try:
                nested = getattr(current, attribute, None)
            except Exception:
                nested = None
            if isinstance(nested, BaseException):
                pending.append(nested)


def _sanitized_primary_message(candidate):
    for current in _exception_chain(candidate):
        try:
            diagnostic = getattr(current, "diag", None)
            message = getattr(diagnostic, "message_primary", None)
        except Exception:
            continue
        if not isinstance(message, str):
            continue

        message = re.sub(r"[\x00-\x1f\x7f]+", " ", message)
        message = _URI_PATTERN.sub("[REDACTED_URI]", message)
        message = _SENSITIVE_KV_PATTERN.sub(r"\1=[REDACTED]", message)
        # PostgreSQL often quotes the token near a syntax error. Do not emit
        # quoted fragments, which could otherwise reproduce part of the SQL.
        message = _QUOTED_FRAGMENT_PATTERN.sub("[REDACTED]", message)
        if _URI_PATTERN.search(message) or _SENSITIVE_KV_PATTERN.search(message):
            return "UNAVAILABLE"
        if _SQL_STATEMENT_PATTERN.search(message):
            return "UNAVAILABLE"
        message = " ".join(message.split())[:300]
        return message or "UNAVAILABLE"
    return "UNAVAILABLE"


def _safe_sqlstate(candidate):
    for current in _exception_chain(candidate):
        for attribute in ("sqlstate", "pgcode"):
            try:
                value = getattr(current, attribute, None)
            except Exception:
                value = None
            if isinstance(value, str) and _SQLSTATE_PATTERN.fullmatch(value):
                return value
        try:
            diagnostic = getattr(current, "diag", None)
            value = getattr(diagnostic, "sqlstate", None)
        except Exception:
            value = None
        if isinstance(value, str) and _SQLSTATE_PATTERN.fullmatch(value):
            return value
    return "NONE"


def _format_failure_diagnostic(candidate, stage):
    stage = stage if stage in _SAFE_STAGES else "ALEMBIC_MIGRATION"
    class_name = type(candidate).__name__
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", class_name):
        class_name = "Exception"
    return (
        f"MIGRATION_FAILURE_STAGE={stage}\n"
        f"MIGRATION_EXCEPTION_CLASS={class_name}\n"
        f"MIGRATION_SQLSTATE={_safe_sqlstate(candidate)}\n"
        f"MIGRATION_PRIMARY_MESSAGE={_sanitized_primary_message(candidate)}"
    )


def _emit_failure_diagnostic(candidate, stage):
    print(_format_failure_diagnostic(candidate, stage), file=sys.stderr)


def include_name(name, type_, parent_names):
    """Never autogenerate against Supabase-managed or unrelated objects."""
    if type_ == "schema":
        return name in (None, "public")
    if type_ == "table":
        return name in {table.name for table in Base.metadata.tables.values()}
    return True


def run_migrations(connection):
    context.configure(connection=connection, target_metadata=Base.metadata,
                      include_schemas=True, include_name=include_name,
                      version_table_schema="public", compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    global _FAILURE_STAGE
    _FAILURE_STAGE = "SETTINGS"
    settings = load_migration_settings()
    _FAILURE_STAGE = "DATABASE_CONSTRUCTION"
    database = Database(settings)
    if database.engine is None:
        raise ConfigurationError("Migrations require JOUS_MIGRATION_DATABASE_URL")
    try:
        _FAILURE_STAGE = "CONNECTION"
        async with database.engine.connect() as connection:
            _FAILURE_STAGE = "ALEMBIC_MIGRATION"
            await connection.run_sync(run_migrations)
    finally:
        if sys.exc_info()[0] is None:
            _FAILURE_STAGE = "CLEANUP"
        await database.dispose()


def main():
    if context.is_offline_mode():
        context.configure(dialect_name="postgresql", literal_binds=True,
                          target_metadata=Base.metadata, version_table_schema="public")
        with context.begin_transaction():
            context.run_migrations()
    elif context.config.attributes.get("connection") is not None:
        run_migrations(context.config.attributes["connection"])
    else:
        # Migration failures must not print driver exceptions containing secrets.
        try:
            asyncio.run(run_online())
        except ConfigurationError:
            raise
        except Exception as exc:
            _emit_failure_diagnostic(exc, _FAILURE_STAGE)
            raise RuntimeError("Jous migration failed; inspect target and configuration securely") from None


if __name__ in {"env_py", "__main__"}:
    main()
