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
    }
    values = {field: source[name] for field, name in names.items() if name in source}
    try:
        return Settings.model_validate(values)
    except ValidationError as exc:
        fields = sorted({names.get(str(e["loc"][0]), "JOUS_DATABASE_URL")
                         if e["loc"] else "JOUS_DATABASE_URL"
                         for e in exc.errors(include_input=False, include_context=False)})
        raise ConfigurationError("Invalid Jous configuration: " + ", ".join(fields)) from None
