"""Offline real ES256 signatures, bounded JWKS transport, and production dependencies."""

import asyncio
import io
import json
import threading
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import Depends

from jous_api.auth_adapters.supabase import SupabaseVerifier, fetch_jwks, MAX_JWKS_BYTES
from jous_api.config import Settings, load_settings, ConfigurationError
from jous_api.dependencies import get_access_service, get_request_identity
from jous_api.identity import AccessDenied, RequestIdentity
from jous_api.main import create_app
from jous_api.access import AccessService
from test_process_foundation import request

ISSUER = "https://aqcixpoorbhjgvdkdjqd.supabase.co/auth/v1"
JWKS = ISSUER + "/.well-known/jwks.json"
NOW = 2000000000


class BlockingFetch:
    """Actual synchronous worker with bounded release even if a test fails."""
    def __init__(self, data):
        self.data = data
        self.started = threading.Event()
        self.release = threading.Event()
        self.finished = threading.Event()
        self.calls = self.active = self.maximum = 0
        self.thread_names = []
        self.lock = threading.Lock()

    def __call__(self, url):
        with self.lock:
            self.calls += 1
            self.active += 1
            self.maximum = max(self.maximum, self.active)
            self.thread_names.append(threading.current_thread().name)
        self.started.set()
        try:
            if not self.release.wait(3):
                raise TimeoutError("Controlled test worker release deadline")
            return self.data
        finally:
            with self.lock:
                self.active -= 1
            self.finished.set()


class AuthenticationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.private = ec.generate_private_key(ec.SECP256R1())
        self.public = json.loads(jwt.algorithms.ECAlgorithm.to_jwk(self.private.public_key()))
        self.public.update(kid="current", alg="ES256", use="sig", key_ops=["verify"])
        self.document = {"keys": [self.public]}
        self.clock = 10.0
        self.fetches = []
        self.failure = False

        def fetch(url):
            self.fetches.append(url)
            if self.failure:
                raise OSError("sensitive network details")
            return json.dumps(self.document).encode()

        self.verifier = SupabaseVerifier(ISSUER, "authenticated", JWKS, fetch=fetch,
                                        monotonic=lambda: self.clock, now=lambda: NOW)
        self.addAsyncCleanup(self.verifier.aclose)
        self.claims = dict(iss=ISSUER, aud="authenticated", sub=str(uuid4()),
                          session_id=str(uuid4()), role="authenticated", is_anonymous=False,
                          iat=NOW - 60, exp=NOW + 3540)

    async def wait_until(self, predicate):
        async def poll():
            while not predicate():
                await asyncio.sleep(0.001)
        await asyncio.wait_for(poll(), 1)

    async def release_worker(self, worker):
        worker.release.set()
        await self.wait_until(worker.finished.is_set)
        await self.wait_until(lambda: self.verifier._inflight is None)

    def token(self, changes=None, *, missing=None, key=None, headers=None):
        claims = self.claims | (changes or {})
        if missing:
            claims.pop(missing)
        return jwt.encode(claims, key or self.private, algorithm="ES256",
                          headers={"kid": "current"} | (headers or {}))

    async def denied(self, token):
        with self.assertRaises(AccessDenied) as error:
            await self.verifier.verify(token)
        self.assertEqual(error.exception.status_code, 401)
        if token:
            self.assertNotIn(token, str(error.exception))

    async def test_valid_signature_profile_and_cache(self):
        self.assertEqual(self.fetches, [])
        token = self.token()
        for _ in range(2):
            principal = await self.verifier.verify(token)
            self.assertEqual((principal.issuer, principal.subject), (ISSUER, self.claims["sub"]))
        self.assertEqual(self.fetches, [JWKS])
        principal = await self.verifier.verify(self.token({"aud": ["authenticated"]}))
        self.assertEqual(principal.subject, self.claims["sub"])

    async def test_invalid_claim_matrix(self):
        cases = [{"iss": ISSUER + "/"}, {"aud": "anon"}, {"aud": 123},
            {"role": "service_role"}, {"role": "owner"}, {"role": "anon"},
            {"is_anonymous": True}, {"is_anonymous": 0}, {"is_anonymous": "false"},
            {"sub": ""}, {"sub": "not-a-uuid"}, {"sub": 12},
            {"session_id": ""}, {"session_id": "not-a-uuid"},
            {"iat": NOW + 31, "exp": NOW + 100}, {"exp": NOW - 31},
            {"exp": NOW - 60}, {"iat": NOW, "exp": NOW},
            {"exp": self.claims["iat"] + 3601}, {"nbf": NOW + 31},
            {"nbf": "2000000000"}, {"iat": True}, {"exp": "2000000000"},
            {"exp": 2000000001.5}, {"iat": -1}]
        for changes in cases:
            with self.subTest(changes=changes):
                await self.denied(self.token(changes))
        for name in self.claims:
            with self.subTest(missing=name):
                await self.denied(self.token(missing=name))

    async def test_time_skew_boundary_and_optional_nbf(self):
        for changes in ({"iat": NOW + 30, "exp": NOW + 100},
                        {"exp": NOW - 29}, {"nbf": NOW + 30}):
            await self.verifier.verify(self.token(changes))
        await self.denied(self.token({"exp": NOW - 30}))

    async def test_signature_algorithm_and_malformed_tokens(self):
        await self.denied(self.token(key=ec.generate_private_key(ec.SECP256R1())))
        for value in ("not-a-jwt", "", "x" * 8193, "refresh-token",
                      jwt.encode(self.claims, "untrusted-test-secret-" * 4, algorithm="HS256"),
                      jwt.encode(self.claims, None, algorithm="none")):
            await self.denied(value)
        await self.denied(self.token(headers={"typ": "other"}))
        await self.denied(self.token(headers={"crit": ["unknown"]}))
        # Algorithm rejected before key lookup, even if a valid JWT header advertises RS256.
        import base64
        rs_header = base64.urlsafe_b64encode(b'{"alg":"RS256","kid":"current","typ":"JWT"}').rstrip(b"=").decode()
        await self.denied(rs_header + "." + self.token().split(".", 1)[1])

    async def test_token_key_urls_have_no_authority(self):
        await self.verifier.verify(self.token(headers={"jku": "https://attacker.invalid/keys",
                                                       "x5u": "https://attacker.invalid/key"}))
        self.assertEqual(self.fetches, [JWKS])

    async def test_unknown_kid_refresh_rate_rotation_and_concurrency(self):
        await self.verifier.verify(self.token())
        for _ in range(10):
            await self.denied(self.token(headers={"kid": "unknown"}))
        self.assertEqual(len(self.fetches), 1)
        self.clock += 30
        self.document["keys"][0] = self.public | {"kid": "rotated"}
        tokens = [self.token(headers={"kid": "rotated"}) for _ in range(10)]
        await asyncio.gather(*(self.verifier.verify(token) for token in tokens))
        self.assertEqual(len(self.fetches), 2)
        await self.denied(self.token())

    async def test_outage_cached_key_then_expiry_and_retry_bound(self):
        await self.verifier.verify(self.token())
        self.failure = True
        self.clock += 30
        await self.denied(self.token(headers={"kid": "unknown"}))
        await self.verifier.verify(self.token())
        self.clock += 300
        await self.denied(self.token())
        await self.denied(self.token())
        self.assertEqual(len(self.fetches), 3)

    async def test_malformed_and_incompatible_jwks(self):
        documents = [{}, {"keys": []}, {"keys": [self.public] * 17},
            {"keys": [self.public, self.public]}, {"keys": [self.public | {"crv": "P-384"}]},
            {"keys": [self.public | {"alg": "HS256"}]},
            {"keys": [self.public | {"use": "enc"}]},
            {"keys": [self.public | {"key_ops": ["sign"]}]},
            {"keys": [self.public | {"d": "private-key-disallowed"}]},
            {"keys": [self.public | {"x": "invalid"}]}]
        for document in documents:
            self.document = document
            self.clock += 30
            await self.denied(self.token())
        for raw in (b"not-json", b"x" * (MAX_JWKS_BYTES + 1)):
            verifier = SupabaseVerifier(ISSUER, "authenticated", JWKS, fetch=lambda _: raw)
            self.addAsyncCleanup(verifier.aclose)
            with self.assertRaises(AccessDenied):
                await verifier.verify(self.token())

    async def test_real_fetch_bounds_and_timeout(self):
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.read.return_value = b'{"keys":[]}'
        with patch("jous_api.auth_adapters.supabase.build_opener") as factory:
            factory.return_value.open.return_value = response
            self.assertEqual(fetch_jwks(JWKS), b'{"keys":[]}')
            args = factory.return_value.open.call_args
            self.assertEqual(args.args[0].full_url, JWKS)
            self.assertEqual(args.kwargs["timeout"], 5)
            response.read.assert_called_once_with(MAX_JWKS_BYTES + 1)
            response.read.return_value = b"x" * (MAX_JWKS_BYTES + 1)
            with self.assertRaises(ValueError):
                fetch_jwks(JWKS)

    async def test_timeout_retains_actual_worker_and_recovers_after_completion(self):
        worker = BlockingFetch(b"malformed-first-response")
        self.verifier._fetch = worker
        try:
            with patch("jous_api.auth_adapters.supabase.CALLER_TIMEOUT", 0.03):
                await self.denied(self.token())
                self.assertTrue(worker.started.is_set())
                self.assertFalse(worker.finished.is_set())
                actual = self.verifier._inflight
                self.assertIsNotNone(actual)
                self.assertFalse(actual.done())
                for index in range(3):
                    self.clock += 31  # Throttle expiry must not permit replacement work.
                    await self.denied(self.token(headers={"kid": f"random-{index}"}))
                self.assertIs(self.verifier._inflight, actual)
                self.assertEqual(worker.calls, 1)
                self.assertEqual(worker.maximum, 1)
                self.assertTrue(all(name.startswith("jous-jwks") for name in worker.thread_names))
            await self.release_worker(worker)
            self.assertEqual(self.verifier._keys, {})
            self.verifier._fetch = lambda _: json.dumps(self.document).encode()
            self.clock += 31
            await self.verifier.verify(self.token())
            self.assertIsNone(self.verifier._inflight)
        finally:
            worker.release.set()

    async def test_cancellation_preserves_worker_and_completion_publishes_without_waiters(self):
        worker = BlockingFetch(json.dumps(self.document).encode())
        self.verifier._fetch = worker
        task = asyncio.create_task(self.verifier.verify(self.token()))
        try:
            await self.wait_until(worker.started.is_set)
            actual = self.verifier._inflight
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertIs(self.verifier._inflight, actual)
            self.assertFalse(actual.done())
            self.clock += 31
            with patch("jous_api.auth_adapters.supabase.CALLER_TIMEOUT", 0.03):
                await self.denied(self.token(headers={"kid": "different"}))
            self.assertEqual(worker.calls, 1)
            await self.release_worker(worker)
            self.assertIsNone(self.verifier._pending)
            await self.verifier.verify(self.token())
            self.assertEqual(worker.calls, 1)
        finally:
            worker.release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_concurrent_unknown_kids_share_one_actual_worker(self):
        worker = BlockingFetch(json.dumps(self.document).encode())
        self.verifier._fetch = worker
        try:
            with patch("jous_api.auth_adapters.supabase.CALLER_TIMEOUT", 0.03):
                await asyncio.gather(*(self.denied(self.token(headers={"kid": f"random-{i}"}))
                                       for i in range(12)))
                self.clock += 31
                await asyncio.gather(*(self.denied(self.token(headers={"kid": f"new-{i}"}))
                                       for i in range(12)))
            self.assertEqual(worker.calls, 1)
            self.assertEqual(worker.maximum, 1)
            await self.release_worker(worker)
        finally:
            worker.release.set()

    async def test_valid_cached_token_does_not_wait_for_blocked_unknown_kid_refresh(self):
        await self.verifier.verify(self.token())
        worker = BlockingFetch(b"malformed-refresh")
        self.verifier._fetch = worker
        self.clock += 31
        refresh = asyncio.create_task(self.verifier.verify(self.token(headers={"kid": "unknown"})))
        try:
            await self.wait_until(worker.started.is_set)
            principal = await asyncio.wait_for(self.verifier.verify(self.token()), 0.2)
            self.assertEqual(principal.subject, self.claims["sub"])
            self.assertFalse(worker.finished.is_set())
            await self.release_worker(worker)
            with self.assertRaises(AccessDenied):
                await refresh
            await self.verifier.verify(self.token())  # Malformed refresh did not replace cache.
            self.clock += 300
            with patch("jous_api.auth_adapters.supabase.CALLER_TIMEOUT", 0.03):
                await self.denied(self.token())  # Expired cache is never extended on failure.
        finally:
            worker.release.set()
            refresh.cancel()
            await asyncio.gather(refresh, return_exceptions=True)

    async def test_close_rejects_new_work_and_does_not_publish_late_result(self):
        worker = BlockingFetch(json.dumps(self.document).encode())
        self.verifier._fetch = worker
        task = asyncio.create_task(self.verifier.verify(self.token()))
        try:
            await self.wait_until(worker.started.is_set)
            actual = self.verifier._inflight
            await self.verifier.aclose()
            self.assertIs(self.verifier._inflight, actual)
            await self.denied(self.token())
            await self.release_worker(worker)
            with self.assertRaises(AccessDenied):
                await task
            self.assertEqual(self.verifier._keys, {})
            self.assertIsNone(self.verifier._executor)
            self.assertEqual(worker.calls, 1)
        finally:
            worker.release.set()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_application_lifespan_closes_owned_verifier_without_network(self):
        app = create_app(Settings(environment="test", auth_issuer=ISSUER, auth_jwks_url=JWKS))
        verifier = app.state.credential_verifier
        async with app.router.lifespan_context(app):
            self.assertFalse(verifier._closed)
            self.assertIsNone(verifier._executor)
        self.assertTrue(verifier._closed)
        with self.assertRaises(AccessDenied):
            await verifier.verify(self.token())

    async def test_production_dependency_safe_headers_identity_and_concurrency(self):
        app = create_app(Settings(environment="test", auth_issuer=ISSUER, auth_jwks_url=JWKS))
        self.assertIsInstance(app.state.credential_verifier, SupabaseVerifier)
        app.state.credential_verifier = self.verifier
        output = io.StringIO()
        app.state.logger.handlers[0].setStream(output)
        service = AsyncMock()
        async def resolve(principal):
            await asyncio.sleep(0)
            return RequestIdentity(__import__("uuid").UUID(principal.subject))
        service.resolve.side_effect = resolve
        app.dependency_overrides[get_access_service] = lambda: service

        @app.get("/test-auth")
        async def probe(identity=Depends(get_request_identity)):
            return {"user": str(identity.user_id)}

        for header in (None, b"Basic secret", b"Bearer", b"Bearer  bad", b"Bearer bad\tvalue",
                       b"Bearer " + b"x" * 8193, b"Bearer forged-token"):
            headers = [(b"x-request-id", b"safe-error"), (b"x-user-id", b"forged")]
            if header:
                headers.append((b"authorization", header))
            start, body = await request(app, headers, "/test-auth")
            self.assertEqual(start["status"], 401)
            self.assertEqual(body["request_id"], "safe-error")
            self.assertNotIn("secret", json.dumps(body))
        duplicate = [(b"authorization", b"Bearer one"), (b"authorization", b"Bearer two")]
        self.assertEqual((await request(app, duplicate, "/test-auth"))[0]["status"], 401)
        subjects = [str(uuid4()) for _ in range(10)]
        tokens = [self.token({"sub": subject}) for subject in subjects]
        results = await asyncio.gather(*(request(app, [(b"authorization", ("Bearer " + token).encode())],
                                                "/test-auth") for token in tokens))
        for subject, (start, body) in zip(subjects, results):
            self.assertEqual(start["status"], 200)
            self.assertEqual(body["user"], subject)
        for token in tokens:
            self.assertNotIn(token, output.getvalue())
        self.assertNotIn("forged-token", output.getvalue())

    def test_settings_trusted_url_and_fail_closed_default(self):
        self.assertEqual(load_settings({"JOUS_AUTH_ISSUER": ISSUER, "JOUS_AUTH_JWKS_URL": JWKS}).auth_issuer, ISSUER)
        for issuer, url in (("http://unsafe/auth/v1", "http://unsafe/auth/v1/.well-known/jwks.json"),
                            (ISSUER, "https://attacker.invalid/jwks"), (ISSUER, None),
                            ("https://user:secret@host/auth/v1", "https://user:secret@host/auth/v1/.well-known/jwks.json")):
            with self.assertRaises(ConfigurationError):
                load_settings({"JOUS_AUTH_ISSUER": issuer, "JOUS_AUTH_JWKS_URL": url})
        self.assertEqual([route.path for route in create_app().routes], ["/health/live", "/health/ready"])

    async def test_verified_token_unknown_or_inactive_internal_user_denied_without_provisioning(self):
        from sqlalchemy.dialects import postgresql
        app = create_app(Settings(environment="test"))
        app.state.credential_verifier = self.verifier
        session = AsyncMock()
        session.scalar.return_value = None
        app.dependency_overrides[get_access_service] = lambda: AccessService(session)

        @app.get("/test-mapping")
        async def probe(identity=Depends(get_request_identity)):
            self.fail("Unmapped/inactive identities must never reach the endpoint")

        token = self.token({"email": "same-as-another-account@example.invalid"})
        start, body = await request(app, [(b"authorization", ("Bearer " + token).encode())], "/test-mapping")
        self.assertEqual(start["status"], 401)
        self.assertEqual(body["error"]["code"], "identity_required")
        sql = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
        self.assertEqual(set(sql.params.values()), {ISSUER, self.claims["sub"], "active"})
        self.assertNotIn("email", str(sql))
        session.add.assert_not_called()
        session.execute.assert_not_called()

    async def test_redirect_and_http_failure_are_rejected(self):
        from jous_api.auth_adapters.supabase import NoRedirect
        self.assertIsNone(NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.invalid"))
        from unittest.mock import MagicMock
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 503
        with patch("jous_api.auth_adapters.supabase.build_opener") as factory:
            factory.return_value.open.return_value = response
            with self.assertRaises(ValueError):
                fetch_jwks(JWKS)
