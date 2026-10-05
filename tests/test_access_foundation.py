"""Offline access contracts, scoped SQL predicates and test-only dependency routes."""

import asyncio
from dataclasses import FrozenInstanceError, fields
from contextlib import asynccontextmanager
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import Depends, Request
from sqlalchemy.dialects import postgresql

from jous_api.access import AccessService
from jous_api.config import Settings
from jous_api.dependencies import (get_access_service, get_project_scope, get_request_identity, get_session,
                                   get_verified_principal)
from jous_api.identity import (AccessDenied, OrganizationScope, ProjectScope, RequestIdentity,
                               VerifiedPrincipal)
from jous_api.main import create_app
from jous_api.observability import request_id
from test_process_foundation import request


def context_session(user=None, organization=None):
    from jous_api.database_context import DatabaseContext
    session = AsyncMock()
    session.info = {}
    session.in_transaction = lambda: True
    session.in_nested_transaction = lambda: False
    context = DatabaseContext(session)
    context.initialized = True
    context.user_id, context.organization_id = user, organization
    session.info['jous_context'] = context
    return session


class IdentityTests(unittest.TestCase):
    def test_minimal_immutable_values(self):
        user, organization, project = uuid4(), uuid4(), uuid4()
        self.assertEqual([f.name for f in fields(RequestIdentity)], ["user_id"])
        self.assertEqual([f.name for f in fields(ProjectScope)], ["user_id", "organization_id", "project_id"])
        for value, attribute in ((RequestIdentity(user), "user_id"),
                                 (OrganizationScope(user, organization), "organization_id"),
                                 (ProjectScope(user, organization, project), "project_id")):
            with self.assertRaises(FrozenInstanceError):
                setattr(value, attribute, uuid4())

    def test_principal_exact_values_and_safe_repr(self):
        principal = VerifiedPrincipal("Issuer/", "Subject")
        self.assertEqual((principal.issuer, principal.subject), ("Issuer/", "Subject"))
        self.assertNotIn("Issuer", repr(principal))
        self.assertNotIn("Subject", repr(principal))
        with self.assertRaises(FrozenInstanceError):
            principal.subject = "different"
        for value in ("", " ", "x" * 256):
            with self.assertRaises(ValueError):
                VerifiedPrincipal(value, "subject")


class AccessQueryTests(unittest.IsolatedAsyncioTestCase):
    async def test_identity_exact_match_and_active_user_predicates(self):
        session = context_session()
        user_id = uuid4()
        session.scalar.return_value = user_id
        service = AccessService(session)
        self.assertEqual(await service.resolve(VerifiedPrincipal("Issuer/", "Subject")), RequestIdentity(user_id))
        statement = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
        self.assertEqual(session.scalar.call_args.args[1], {"issuer": "Issuer/", "subject": "Subject"})
        for predicate in ("jous_security.resolve_user",):
            self.assertIn(predicate, str(statement))
        session.scalar.return_value = None
        service.context.clear()
        service.context.initialized = True
        with self.assertRaises(AccessDenied) as failure:
            await service.resolve(VerifiedPrincipal("unknown", "unknown"))
        self.assertEqual(failure.exception.status_code, 401)
        service.context.user_id = user_id
        with self.assertRaises(AccessDenied):
            await service.active_user(RequestIdentity(user_id))
        session.scalar.return_value = user_id
        self.assertEqual(await service.active_user(RequestIdentity(user_id)), RequestIdentity(user_id))

    async def test_organization_and_project_predicates_fail_closed(self):
        session = context_session()
        session.scalar.return_value = None
        user, organization, project = uuid4(), uuid4(), uuid4()
        session.info["jous_context"].user_id = user
        session.info["jous_context"].organization_id = organization
        service = AccessService(session)
        with self.assertRaises(AccessDenied):
            await service.organization(RequestIdentity(user), organization)
        organization_sql = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
        for predicate in ("users.id =", "users.status =", "organizations.id =", "organizations.status =",
                          "organization_memberships.status =", "organization_memberships.role IN"):
            self.assertIn(predicate, str(organization_sql))
        self.assertEqual(organization_sql.params["role_1"], ["member", "owner"])
        self.assertNotIn("admin", organization_sql.params.values())
        with self.assertRaises(AccessDenied):
            await service.project(OrganizationScope(user, organization), project)
        project_sql = session.scalar.call_args.args[0].compile(dialect=postgresql.dialect())
        for predicate in ("projects.id =", "projects.organization_id =", "projects.status =",
                          "users.id =", "organization_memberships.status =", "organization_memberships.role IN"):
            self.assertIn(predicate, str(project_sql))
        self.assertIn(organization, project_sql.params.values())
        self.assertIn(project, project_sql.params.values())
        session.scalar.return_value = project
        self.assertEqual(await service.project(OrganizationScope(user, organization), project),
                         ProjectScope(user, organization, project))


class DependencyTests(unittest.IsolatedAsyncioTestCase):
    def application(self):
        app = create_app(Settings(environment="test"))
        output = io.StringIO()
        app.state.logger.handlers[0].setStream(output)
        return app, output

    async def test_request_sessions_are_distinct_and_close_on_denial(self):
        closed = []

        class Database:
            @asynccontextmanager
            async def scoped_transaction(self):
                session = object()
                try:
                    yield session
                finally:
                    closed.append(session)

        fake_request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(database=Database())))
        first, second = get_session(fake_request), get_session(fake_request)
        session_a, session_b = await asyncio.gather(anext(first), anext(second))
        self.assertIsNot(session_a, session_b)
        with self.assertRaises(AccessDenied):
            await first.athrow(AccessDenied())
        await second.aclose()
        self.assertEqual(set(closed), {session_a, session_b})

    async def test_unknown_external_identity_error_omits_principal(self):
        app, output = self.application()
        session = context_session()
        session.scalar.return_value = None
        app.dependency_overrides[get_verified_principal] = lambda: VerifiedPrincipal("private-issuer", "private-subject")
        app.dependency_overrides[get_access_service] = lambda: AccessService(session)

        @app.get("/test-identity")
        async def probe(identity: RequestIdentity = Depends(get_request_identity)):
            self.fail("Unknown principal cannot establish identity")

        start, body = await request(app, [(b"x-request-id", b"unknown-123")], "/test-identity")
        self.assertEqual(start["status"], 401)
        for secret in ("private-issuer", "private-subject"):
            self.assertNotIn(secret, json.dumps(body) + output.getvalue())

    async def test_missing_identity_and_forged_headers_cannot_authenticate(self):
        app, output = self.application()

        @app.get("/test-identity")
        async def probe(identity: RequestIdentity = Depends(get_request_identity)):
            self.fail("Default resolver must reject before accessing persistence")

        service = AsyncMock()
        app.dependency_overrides[get_access_service] = lambda: service
        for headers in ([], [(b"x-user-id", str(uuid4()).encode()), (b"x-test-user", b"secret-user"),
                             (b"x-organization-id", str(uuid4()).encode()),
                             (b"authorization", b"Bearer secret-token"), (b"x-request-id", b"denial-123")]):
            start, body = await request(app, headers, "/test-identity")
            self.assertEqual(start["status"], 401)
            self.assertEqual(body["error"]["code"], "identity_required")
            self.assertEqual(body["request_id"], dict(start["headers"])[b"x-request-id"].decode())
        service.resolve.assert_not_called()
        self.assertNotIn("secret-token", output.getvalue())
        self.assertNotIn("secret-user", output.getvalue())

    async def test_inaccessible_and_missing_project_have_identical_correlated_errors(self):
        app, output = self.application()
        user, organization = uuid4(), uuid4()
        service = AsyncMock()
        service.resolve.return_value = RequestIdentity(user)
        service.organization.return_value = OrganizationScope(user, organization)
        service.project.side_effect = AccessDenied()
        app.dependency_overrides[get_verified_principal] = lambda: VerifiedPrincipal("test", "test")
        app.dependency_overrides[get_access_service] = lambda: service

        @app.get("/test/{organization_id}/{project_id}")
        async def probe(scope: ProjectScope = Depends(get_project_scope)):
            return {"project_id": str(scope.project_id)}

        results = [await request(app, [(b"x-request-id", b"same-request")],
                                 f"/test/{organization}/{uuid4()}") for _ in range(2)]
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0][0]["status"], 404)
        self.assertEqual(results[0][1]["error"]["code"], "resource_unavailable")
        self.assertTrue(all(json.loads(line)["request_id"] == "same-request"
                            for line in output.getvalue().splitlines()))

    async def test_concurrent_requests_keep_identity_scopes_and_correlation_separate(self):
        app, _ = self.application()
        actors = {name: (uuid4(), uuid4(), uuid4()) for name in ("A", "B")}

        async def principal(request: Request):
            await asyncio.sleep(0)
            return VerifiedPrincipal("test", request.path_params["test_actor"])

        class Service:
            async def resolve(self, principal):
                await asyncio.sleep(0)
                return RequestIdentity(actors[principal.subject][0])

            async def organization(self, identity, organization_id):
                await asyncio.sleep(0)
                return OrganizationScope(identity.user_id, organization_id)

            async def project(self, organization, project_id):
                await asyncio.sleep(0)
                return ProjectScope(organization.user_id, organization.organization_id, project_id)

        app.dependency_overrides[get_verified_principal] = principal
        app.dependency_overrides[get_access_service] = Service

        @app.get("/test/{test_actor}/{organization_id}/{project_id}")
        async def probe(scope: ProjectScope = Depends(get_project_scope)):
            await asyncio.sleep(0)
            return {"user": str(scope.user_id), "organization": str(scope.organization_id),
                    "project": str(scope.project_id), "correlation": request_id.get()}

        names = ["A", "B"] * 10
        results = await asyncio.gather(*(request(app, [(b"x-request-id", name.encode())],
            f"/test/{name}/{actors[name][1]}/{actors[name][2]}") for name in names))
        for name, (start, body) in zip(names, results):
            self.assertEqual(start["status"], 200)
            self.assertEqual(body, dict(zip(("user", "organization", "project", "correlation"),
                                           [*(str(value) for value in actors[name]), name])))
        self.assertIsNone(request_id.get())

    async def test_normal_application_exposes_only_health_and_no_overrides(self):
        app, _ = self.application()
        self.assertEqual([route.path for route in app.routes], ["/health/live", "/health/ready"])
        self.assertEqual(app.dependency_overrides, {})
        start, _ = await request(app, path="/test-identity")
        self.assertEqual(start["status"], 404)
