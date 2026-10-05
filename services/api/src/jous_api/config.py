"""Environment-only configuration; constructing settings never connects services."""

import os
from collections.abc import Mapping
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator


class ConfigurationError(ValueError):
    """Safe configuration failure containing no supplied values."""


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True, hide_input_in_errors=True)

    environment: Literal["development", "test", "production"] = "development"
    service_name: str = Field(default="jous-api", pattern=r"^[A-Za-z0-9_-]{1,64}$")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    api_host: str = Field(default="127.0.0.1", pattern=r"^[A-Za-z0-9.:-]{1,253}$")
    api_port: int = Field(default=8000, ge=1, le=65535)
    database_url: SecretStr | None = Field(default=None, repr=False)
    database_timeout_seconds: float = Field(default=5.0, ge=0.1, le=30, allow_inf_nan=False)
    auth_issuer: str | None = Field(default=None, max_length=255)
    auth_audience: str = "authenticated"
    auth_jwks_url: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def validate_authentication(self):
        if self.auth_issuer is None and self.auth_jwks_url is None:
            # An unconfigured adapter rejects all credentials, including in production.
            return self
        if not self.auth_issuer or not self.auth_jwks_url or self.auth_audience != "authenticated":
            raise ValueError("Incomplete authentication configuration")
        parsed = urlsplit(self.auth_issuer)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.port not in (None, 443)
                or parsed.path != "/auth/v1"
                or self.auth_jwks_url != self.auth_issuer + "/.well-known/jwks.json"):
            raise ValueError("Invalid authentication configuration")
        return self

    @model_validator(mode="after")
    def validate_database(self):
        if self.environment == "production" and self.database_url is None:
            raise ValueError("Production requires JOUS_DATABASE_URL")
        if self.database_url is not None:
            try:
                parsed = urlsplit(self.database_url.get_secret_value())
                valid = parsed.scheme in {"postgresql", "postgres"} and bool(parsed.hostname)
                valid = valid and bool(parsed.path.strip("/"))
                if parsed.port is not None:
                    valid = valid and 1 <= parsed.port <= 65535
            except ValueError:
                valid = False
            if not valid:
                raise ValueError("JOUS_DATABASE_URL must be a PostgreSQL URL")
        return self


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Explicit mappings make tests independent of the process environment."""
    source = os.environ if environ is None else environ
    names = {
        "environment": "JOUS_ENVIRONMENT",
        "service_name": "JOUS_SERVICE_NAME",
        "log_level": "JOUS_LOG_LEVEL",
        "api_host": "JOUS_API_HOST",
        "api_port": "JOUS_API_PORT",
        "database_url": "JOUS_DATABASE_URL",
        "database_timeout_seconds": "JOUS_DATABASE_TIMEOUT_SECONDS",
        "auth_issuer": "JOUS_AUTH_ISSUER",
        "auth_audience": "JOUS_AUTH_AUDIENCE",
        "auth_jwks_url": "JOUS_AUTH_JWKS_URL",
    }
    values = {field: source[name] for field, name in names.items() if name in source}
    try:
        return Settings.model_validate(values)
    except ValidationError as exc:
        fields = sorted({names.get(str(e["loc"][0]), "JOUS_DATABASE_URL")
                         if e["loc"] else "JOUS_DATABASE_URL"
                         for e in exc.errors(include_input=False, include_context=False)})
        raise ConfigurationError("Invalid Jous configuration: " + ", ".join(fields)) from None


def load_migration_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Admin tooling only. Runtime settings never ingest this secret; no fallback."""
    source = os.environ if environ is None else environ
    value = source.get("JOUS_MIGRATION_DATABASE_URL")
    if not value:
        raise ConfigurationError("Migrations require JOUS_MIGRATION_DATABASE_URL")
    # Reuse PostgreSQL validation without ingesting runtime/authentication settings.
    try:
        return load_settings({"JOUS_DATABASE_URL": value,
            "JOUS_ENVIRONMENT": source.get("JOUS_ENVIRONMENT", "development"),
            "JOUS_DATABASE_TIMEOUT_SECONDS": source.get("JOUS_DATABASE_TIMEOUT_SECONDS", "5")})
    except ConfigurationError:
        raise ConfigurationError("Invalid migration configuration") from None
