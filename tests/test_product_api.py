"""Product HTTP boundary tests with deterministic identity and persistence doubles."""
from datetime import datetime, timezone
import json
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

from jous_api.config import Settings
from jous_api.dependencies import get_access_service
from jous_api.identity import AccessDenied, RequestIdentity, VerifiedPrincipal
from jous_api.product_api import service
from jous_api.product_app import create_product_app


async def call(app, path="/api/me", method="GET", token="valid", body=None, headers=(), query=""):
    raw = json.dumps(body).encode() if body is not None and not isinstance(body, bytes) else body or b""
    request_headers = list(headers)
    if token is not None: request_headers.append((b"authorization", ("Bearer " + token).encode()))
    if method == "POST" and not any(k == b"content-type" for k, _ in headers):
        request_headers.append((b"content-type", b"application/json"))
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": method,
             "scheme": "http", "path": path, "raw_path": path.encode(), "query_string": query.encode(),
             "headers": request_headers, "server": ("test", 80), "client": ("test", 1)}
    messages = []; delivered = False
    async def receive():
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": raw, "more_body": False}
        return {"type": "http.disconnect"}
    async def send(message): messages.append(message)
    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    response = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], json.loads(response) if response else None, dict(start["headers"])


class ProductApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.app = create_product_app(Settings(environment="test"))
        self.user, self.org, self.project_id = uuid4(), uuid4(), uuid4()
        async def verify(token):
            if token in ("invalid", "expired"): raise AccessDenied(401)
            return VerifiedPrincipal("approved", token)
        self.app.state.credential_verifier = SimpleNamespace(verify=verify)
        self.access = AsyncMock()
        async def resolve(principal):
            if principal.subject in ("unknown", "inactive"): raise AccessDenied(401)
            return RequestIdentity(self.user)
        self.access.resolve.side_effect = resolve
        self.app.dependency_overrides[get_access_service] = lambda: self.access
        self.projects = AsyncMock()
        self.projects.me.return_value = {"user_id": self.user, "organization": {"id": self.org, "name": "My organization"}}
        now = datetime.now(timezone.utc)
        self.project = dict(id=self.project_id, name="My First Project", description=None, status="active", created_at=now, updated_at=now)
        self.projects.create.return_value = self.project
        self.projects.read.return_value = self.project
        self.projects.list.return_value = {"projects": [self.project], "next_cursor": None}
        self.app.dependency_overrides[service] = lambda: self.projects

    async def test_valid_mapped_identity(self):
        status, value, headers = await call(self.app)
        self.assertEqual(status, 200)
        self.assertEqual(value["user_id"], str(self.user))
        self.assertEqual(headers[b"cache-control"], b"private, no-store")
        self.access.resolve.assert_awaited_once()

    async def test_invalid_expired_unknown_inactive_identity(self):
        for token in (None, "invalid", "expired", "unknown", "inactive"):
            with self.subTest(token=token): self.assertEqual((await call(self.app, token=token))[0], 401)
        self.projects.me.assert_not_awaited()

    async def test_list_create_read_and_no_tenant_header_authority(self):
        self.assertEqual((await call(self.app, "/api/projects"))[0], 200)
        status, value, _ = await call(self.app, "/api/projects", "POST", body={"name": " My First Project "},
                                      headers=[(b"x-organization-id", str(uuid4()).encode())])
        self.assertEqual(status, 201)
        self.assertEqual(value["id"], str(self.project_id))
        identity, data = self.projects.create.call_args.args
        self.assertEqual(identity.user_id, self.user)
        self.assertEqual(data.name, "My First Project")
        self.assertFalse(hasattr(data, "organization_id"))
        self.assertEqual((await call(self.app, "/api/projects/" + str(self.project_id)))[0], 200)

    async def test_invalid_input_and_unknown_fields(self):
        for data in ({"name": ""}, {"name": "x", "organization_id": str(self.org)},
                     {"name": "x", "description": "x" * 2001}, {"name": "x\n"}, {"name": "x", "owner": "me"}):
            self.assertEqual((await call(self.app, "/api/projects", "POST", body=data))[0], 422)
        self.assertEqual((await call(self.app, "/api/projects", "POST", body=b"x" * 16385))[0], 413)
        self.assertEqual((await call(self.app, "/api/projects", "POST", body=b"bad"))[0], 422)
        self.assertEqual((await call(self.app, "/api/projects", "POST", body={}, headers=[(b"content-type", b"text/plain")]))[0], 415)
        self.projects.create.assert_not_awaited()

    async def test_query_pagination_and_tenant_spoof_rejection(self):
        for query in ("limit=0", "limit=101", "after=bad", "organization_id=" + str(self.org)):
            self.assertEqual((await call(self.app, "/api/projects", query=query))[0], 422)
        self.assertEqual((await call(self.app, "/api/projects", query="limit=1&after=" + str(uuid4())))[0], 200)

    async def test_project_denial_does_not_reveal_existence(self):
        self.projects.read.side_effect = AccessDenied()
        values = [(await call(self.app, "/api/projects/" + str(uuid4())))[:2] for _ in range(2)]
        self.assertEqual(values[0][0], 404)
        self.assertEqual(values[0][1]["error"], values[1][1]["error"])
