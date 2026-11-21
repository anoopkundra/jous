"""Supplier-neutral, bounded execution evidence. No credentials in value objects."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

DISPOSITIONS = ('succeeded', 'refused', 'known_error', 'unknown')
ERRORS = ('not_dispatched', 'supplier_rejected', 'rate_limited', 'malformed_response',
          'response_too_large', 'metadata_inconsistent', 'transport_ambiguous', 'provider_timeout')
USAGE_KEYS = frozenset({'input_tokens', 'output_tokens', 'total_tokens',
                        'cached_input_tokens', 'reasoning_tokens'})


@dataclass(frozen=True)
class ExecutionRequest:
    system: str
    user: str
    deadline: datetime
    max_tokens: int = 1024
    route_id: str | None = None
    supplier_id: str | None = None
    supplier_native_model_id: str | None = None
    underlying_provider: str | None = None


@dataclass(frozen=True)
class ResolvedSupplierCredential:
    """Server-resolved dispatch credential; only its opaque account ref is evidence."""
    credential_authority_ref: str
    supplier_id: str
    underlying_provider: str
    secret: str = field(repr=False, compare=False)

    def __post_init__(self):
        if (not isinstance(self.credential_authority_ref, str) or not self.credential_authority_ref.strip()
                or len(self.credential_authority_ref.encode("utf-8")) > 255
                or not isinstance(self.supplier_id, str) or not self.supplier_id.strip()
                or len(self.supplier_id.encode("utf-8")) > 255
                or not isinstance(self.underlying_provider, str) or not self.underlying_provider.strip()
                or len(self.underlying_provider.encode("utf-8")) > 255
                or not isinstance(self.secret, str) or not self.secret):
            raise ValueError("Invalid resolved supplier credential")


@dataclass(frozen=True)
class Outcome:
    status: Literal['succeeded', 'refused', 'known_error', 'unknown']
    response_text: str | None = None
    reported_model_id: str | None = None
    reported_provider_id: str | None = None
    provider_request_id: str | None = None
    provider_response_id: str | None = None
    finish_reason: str | None = None
    usage: dict | None = None
    usage_status: str = 'unavailable'
    error_code: str | None = None
    request_started_at: datetime | None = None
    response_received_at: datetime | None = None
    credential_authority_ref: str | None = None

    def __post_init__(self):
        if self.status not in DISPOSITIONS or self.usage_status not in ('available', 'partial', 'unavailable'):
            raise ValueError('Invalid outcome')
        if self.error_code is not None and self.error_code not in ERRORS:
            raise ValueError('Invalid outcome')
        if self.response_text is not None and len(self.response_text.encode('utf-8')) > 65536:
            raise ValueError('Invalid outcome')
        for value in (self.reported_model_id,self.reported_provider_id,self.provider_request_id,self.provider_response_id,self.finish_reason,self.credential_authority_ref):
            if value is not None and (not isinstance(value,str) or not value.strip() or len(value.encode('utf-8'))>255):
                raise ValueError('Invalid evidence identifier')
        for value in (self.request_started_at,self.response_received_at):
            if value is not None and (not isinstance(value,datetime) or value.tzinfo is None or value.utcoffset() is None):
                raise ValueError('Invalid evidence timestamp')
        if self.response_received_at is not None and (self.request_started_at is None or self.response_received_at<self.request_started_at):
            raise ValueError('Invalid evidence timestamp order')
        if self.usage_status == 'unavailable':
            if self.usage is not None: raise ValueError('Invalid usage')
        elif not self.usage or set(self.usage) - USAGE_KEYS or any(type(v) is not int or v < 0 for v in self.usage.values()):
            raise ValueError('Invalid usage')
        if self.status == 'succeeded' and (self.response_text is None or self.error_code is not None):
            raise ValueError('Invalid success')
        if self.status == 'refused' and self.error_code is not None: raise ValueError('Invalid refusal')
        if self.status == 'known_error' and (self.error_code not in ERRORS[:6] or self.response_text is not None):
            raise ValueError('Invalid known error')
        if self.status == 'unknown' and (self.error_code not in ERRORS[6:] or self.response_text is not None):
            raise ValueError('Invalid ambiguity')
        if self.error_code == 'not_dispatched' and any(v is not None for v in (
            self.request_started_at, self.response_received_at, self.reported_model_id,
            self.reported_provider_id, self.provider_request_id, self.provider_response_id,
            self.credential_authority_ref, self.usage)):
            raise ValueError('Invalid non-dispatch')


class RouteUnavailable(RuntimeError):
    """Safe admission failure; contains no upstream data."""
