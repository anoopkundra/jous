"""Pinned transport for explicitly constructed migration/admin settings."""

from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import runtime_transport

HOST = runtime_transport.HOST
PROJECT = runtime_transport.PROJECT
CA_SHA = runtime_transport.CA_SHA


class TransportRejected(ValueError):
    """Safe migration transport rejection without supplied configuration."""


def validate_target(secret):
    try:
        parsed = urlsplit(secret)
        if not (parsed.scheme in ("postgres", "postgresql")
                and parsed.hostname == HOST
                and parsed.port == 5432
                and parsed.path == "/postgres"
                and not parsed.query and not parsed.fragment
                and unquote(parsed.username or "") == "postgres." + PROJECT
                and bool(parsed.password)):
            raise ValueError
    except Exception:
        raise TransportRejected("MIGRATION_TRANSPORT_REJECTED") from None


def connection_arguments(settings):
    validate_target(settings.database_url.get_secret_value())
    try:
        if not settings.database_ca_file:
            raise ValueError
        # Share the exact certificate pinning and mandatory hostname-verifying
        # CERT_REQUIRED context implementation used by the runtime contract.
        context = runtime_transport.pinned_context(
            Path(settings.database_ca_file).read_text(encoding="ascii"))
        return {"ssl": context, "timeout": settings.database_timeout_seconds,
                "target_session_attrs": "any"}
    except Exception:
        raise TransportRejected("MIGRATION_TRANSPORT_REJECTED") from None
