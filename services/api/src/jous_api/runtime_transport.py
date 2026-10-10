"""Mandatory production transport. No credential acquisition or network I/O."""
import base64
import hashlib
import re
import ssl
from pathlib import Path
from urllib.parse import urlsplit, unquote

HOST = 'aws-0-ca-central-1.pooler.supabase.com'
PROJECT = 'aqcixpoorbhjgvdkdjqd'
CA_SHA = '807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa'


class TransportRejected(ValueError):
    pass


def require(value):
    if not value:
        raise TransportRejected('RUNTIME_TRANSPORT_REJECTED')


def pinned_context(pem):
    try:
        require(type(pem) is str and re.fullmatch(
            r'\s*-----BEGIN CERTIFICATE-----\r?\n[A-Za-z0-9+/=\r\n\t ]+\r?\n-----END CERTIFICATE-----\s*', pem))
        payload = re.search(r'-----BEGIN CERTIFICATE-----\s*(.*?)\s*-----END CERTIFICATE-----', pem, re.S).group(1)
        compact = re.sub(r'[\r\n\t ]', '', payload)
        der = base64.b64decode(compact, validate=True)
        require(base64.b64encode(der).decode('ascii') == compact)
        require(hashlib.sha256(der).hexdigest() == CA_SHA)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.load_verify_locations(cadata=der)
        validate_context(context, der)
        return context
    except Exception:
        raise TransportRejected('RUNTIME_TRANSPORT_REJECTED') from None


def validate_context(context, der):
    require(isinstance(context, ssl.SSLContext) and
            context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname and
            context.get_ca_certs(binary_form=True) == [der] and
            hashlib.sha256(der).hexdigest() == CA_SHA)


def validate_target(secret):
    try:
        parsed = urlsplit(secret)
        require(parsed.scheme in ('postgres', 'postgresql') and parsed.hostname == HOST and
                parsed.port == 5432 and parsed.path == '/postgres' and
                not parsed.query and not parsed.fragment and
                unquote(parsed.username or '') == 'jous_runtime.' + PROJECT and bool(parsed.password))
    except Exception:
        raise TransportRejected('RUNTIME_TRANSPORT_REJECTED') from None


def connection_arguments(settings):
    validate_target(settings.database_url.get_secret_value())
    try:
        require(settings.database_ca_file is not None)
        context = pinned_context(Path(settings.database_ca_file).read_text(encoding='ascii'))
    except Exception:
        raise TransportRejected('RUNTIME_TRANSPORT_REJECTED') from None
    return {'ssl': context, 'timeout': settings.database_timeout_seconds,
            'target_session_attrs': 'any'}
