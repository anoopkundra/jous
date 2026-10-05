"""Bounded ES256 verification for the approved Supabase user access-token profile."""

import asyncio
import json
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import UUID

import jwt

from ..identity import AccessDenied, VerifiedPrincipal

MAX_TOKEN_BYTES = 8192
MAX_JWKS_BYTES = 65536
MAX_KEYS = 16
CACHE_SECONDS = 300
REFRESH_SECONDS = 30
NETWORK_TIMEOUT = 5
CALLER_TIMEOUT = NETWORK_TIMEOUT + 1
CLOCK_SKEW = 30
TOKEN_LIFETIME = 3600


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_jwks(url: str) -> bytes:
    # Fixed trusted URL only. Disable redirects; never follow a token's jku/x5u.
    with build_opener(NoRedirect()).open(
        Request(url, headers={"Accept": "application/json"}), timeout=NETWORK_TIMEOUT
    ) as response:
        if response.status != 200:
            raise ValueError("Key retrieval unavailable")
        data = response.read(MAX_JWKS_BYTES + 1)
    if len(data) > MAX_JWKS_BYTES:
        raise ValueError("Key response too large")
    return data


class SupabaseVerifier:
    def __init__(self, issuer: str, audience: str, jwks_url: str, *,
                 fetch=fetch_jwks, monotonic=time.monotonic, now=time.time):
        # Independently constrain configuration even when constructed outside Settings.
        from urllib.parse import urlsplit
        parsed = urlsplit(issuer)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or parsed.port not in (None, 443)
                or parsed.path != "/auth/v1" or audience != "authenticated"
                or jwks_url != issuer + "/.well-known/jwks.json"):
            raise ValueError("Invalid authentication configuration")
        self.issuer, self.audience, self.jwks_url = issuer, audience, jwks_url
        self._fetch, self._monotonic, self._now = fetch, monotonic, now
        self._keys = {}
        self._expires = 0.0
        self._next_refresh = float("-inf")
        self._lock = asyncio.Lock()
        self._executor = None
        self._inflight = None
        self._pending = None
        self._closed = False

    def _load_keys(self):
        # Run fetch AND parsing in the dedicated worker. Never mutate cache here.
        try:
            raw = self._fetch(self.jwks_url)
            if not isinstance(raw, bytes) or len(raw) > MAX_JWKS_BYTES:
                raise ValueError("Invalid key response")
            document = json.loads(raw)
            entries = document["keys"]
            if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_KEYS:
                raise ValueError("Invalid key count")
            keys = {}
            for entry in entries:
                if (not isinstance(entry, dict) or entry.get("kty") != "EC"
                        or entry.get("crv") != "P-256" or entry.get("alg") != "ES256"
                        or entry.get("use", "sig") != "sig"
                        or entry.get("key_ops", ["verify"]) != ["verify"]
                        or "d" in entry):
                    raise ValueError("Incompatible verification key")
                identifier = entry.get("kid")
                if (not isinstance(identifier, str) or not 1 <= len(identifier) <= 128
                        or identifier in keys):
                    raise ValueError("Invalid key identifier")
                keys[identifier] = jwt.PyJWK.from_dict(entry, algorithm="ES256").key
            return keys
        except Exception:
            # No exception details cross into logs or unobserved future exceptions.
            return None

    def _finish_refresh(self, future):
        # Event-loop-only, synchronous publication; no partially validated cache.
        if self._inflight is not future or not future.done():
            return
        keys = None if future.cancelled() else future.result()
        if keys is not None and not self._closed:
            self._keys = keys
            self._expires = self._monotonic() + CACHE_SECONDS
        self._inflight = None
        self._pending = None

    async def aclose(self):
        async with self._lock:
            self._closed = True
            self._keys = {}
            self._expires = 0.0
            if self._executor is not None:
                # Blocking stdlib networking cannot be forcibly stopped. Do not block
                # the event loop on shutdown; retain tracking until actual completion.
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None

    async def _key(self, kid: str):
        if not self._closed and self._monotonic() < self._expires and kid in self._keys:
            return self._keys[kid]
        async with self._lock:
            if self._closed:
                raise AccessDenied(401)
            if self._inflight is not None and self._inflight.done():
                self._finish_refresh(self._inflight)
            instant = self._monotonic()
            if instant < self._expires and kid in self._keys:
                return self._keys[kid]
            if self._inflight is None and instant >= self._next_refresh:
                # Bound all attempts, including failures and attacker-selected unknown kids.
                self._next_refresh = instant + REFRESH_SECONDS
                if self._executor is None:
                    self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="jous-jwks")
                loop = asyncio.get_running_loop()
                self._inflight = self._executor.submit(self._load_keys)
                self._pending = asyncio.wrap_future(self._inflight)

                def completed(future):
                    try:
                        loop.call_soon_threadsafe(self._finish_refresh, future)
                    except RuntimeError:
                        # The application loop is already closed; never publish from a worker.
                        pass

                self._inflight.add_done_callback(completed)
            pending = self._pending
        # No lock during I/O. Shield shared work from timeout/cancellation of callers.
        if pending is not None:
            try:
                await asyncio.wait_for(asyncio.shield(pending), CALLER_TIMEOUT)
            except TimeoutError:
                pass
        if not self._closed and self._monotonic() < self._expires and kid in self._keys:
            return self._keys[kid]
        raise AccessDenied(401)

    async def verify(self, credential: str) -> VerifiedPrincipal:
        try:
            if (not isinstance(credential, str) or not credential.isascii()
                    or not 1 <= len(credential) <= MAX_TOKEN_BYTES):
                raise ValueError("Invalid credential")
            header = jwt.get_unverified_header(credential)
            kid = header.get("kid")
            if (header.get("alg") != "ES256" or header.get("typ") != "JWT"
                    or not isinstance(kid, str) or not 1 <= len(kid) <= 128
                    or header.get("crit") or header.get("b64") is False):
                raise ValueError("Unsupported token header")
            key = await self._key(kid)
            claims = jwt.decode(credential, key, algorithms=["ES256"], issuer=self.issuer,
                                audience=self.audience, options={
                "require": ["iss", "aud", "sub", "role", "session_id", "is_anonymous", "exp", "iat"],
                # Explicit clock below allows deterministic tests and strict numeric types.
                "verify_exp": False, "verify_iat": False, "verify_nbf": False})
            if claims["role"] != "authenticated" or claims["is_anonymous"] is not False:
                raise ValueError("Unsupported user profile")
            for name in ("sub", "session_id"):
                value = claims[name]
                if not isinstance(value, str) or str(UUID(value)) != value or UUID(value).int == 0:
                    raise ValueError("Invalid user identifier")
            for name in ("exp", "iat", "nbf"):
                if name in claims and (type(claims[name]) is not int or claims[name] < 0):
                    raise ValueError("Invalid timestamp")
            now = self._now()
            exp, issued = claims["exp"], claims["iat"]
            if (now >= exp + CLOCK_SKEW or issued > now + CLOCK_SKEW
                    or exp <= issued or exp - issued > TOKEN_LIFETIME
                    or claims.get("nbf", 0) > now + CLOCK_SKEW):
                raise ValueError("Invalid token lifetime")
            return VerifiedPrincipal(claims["iss"], claims["sub"])
        except Exception:
            raise AccessDenied(401) from None
