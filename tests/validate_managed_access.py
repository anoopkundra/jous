"""Opt-in Step 5 isolation validation. No migrations, RLS changes or committed test rows."""

import argparse
import asyncio
import hashlib
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from jous_api.access import AccessService
from jous_api.config import load_settings
from jous_api.database import Database
from jous_api.identity import AccessDenied, OrganizationScope, RequestIdentity, VerifiedPrincipal
from jous_api.models import Organization, OrganizationMembership, Project, User

TABLES = ("users", "organizations", "organization_memberships", "projects")
HEAD = "0001_identity_project"


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


async def state(connection):
    revision = (await connection.execute(text("SELECT version_num FROM public.alembic_version"))).scalars().all()
    counts = {table: await connection.scalar(text("SELECT count(*) FROM public." + table)) for table in TABLES}
    rls = (await connection.execute(text(
        "SELECT c.relname, c.oid, c.relrowsecurity, c.relforcerowsecurity FROM pg_class c "
        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' ORDER BY 1"))).all()
    policies = (await connection.execute(text("SELECT schemaname, tablename, policyname, roles, cmd, qual, with_check FROM pg_policies ORDER BY 1,2,3"))).all()
    return revision, counts, rls, policies


async def main(expected_fingerprint):
    settings = load_settings()
    require(settings.environment != "production", "Production target refused")
    require(settings.database_url is not None, "Database configuration required")
    url = make_url(settings.database_url.get_secret_value())
    fingerprint = hashlib.sha256((url.host + ':' + str(url.port) + '/' + url.database + '/' + (url.username or '')).encode()).hexdigest()[:16]
    require(fingerprint == expected_fingerprint, "Target mismatch")
    database = Database(settings)
    try:
        async with database.engine.connect() as connection:
            # Empty-table safety must not depend on an RLS-filtered view.
            visibility = await connection.scalar(text(
                "SELECT bool_and(r.rolsuper OR r.rolbypassrls OR c.relowner=r.oid) "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "CROSS JOIN pg_roles r WHERE r.rolname=current_user AND n.nspname='public' "
                "AND c.relname IN ('users','organizations','organization_memberships','projects')"))
            require(visibility, "Cannot safely establish unfiltered empty-table state")
            before = await state(connection)
            require(before[0] == [HEAD], "Unexpected migration head")
            require(all(count == 0 for count in before[1].values()), "Domain tables are not empty")
            require(all(row[2] for row in before[2]), "Expected RLS is not enabled")
            print("TARGET / HEAD / EMPTY TABLES / RLS: PASS", fingerprint)
            await connection.rollback()  # End read-only preflight transaction.
            transaction = await connection.begin()
            try:
                async with AsyncSession(bind=connection, expire_on_commit=False) as session:
                    issuer = "jous-step5-validation-" + uuid4().hex
                    users = [User(id=uuid4(), auth_issuer=issuer, auth_subject=name, status="active") for name in ("A", "B", "C")]
                    organizations = [Organization(id=uuid4(), name="temporary-validation", status="active") for _ in range(2)]
                    session.add_all(users + organizations)
                    await session.flush()
                    memberships = [OrganizationMembership(id=uuid4(), user_id=users[i].id,
                        organization_id=organizations[i].id, role="member", status="active") for i in range(2)]
                    projects = [Project(id=uuid4(), organization_id=organizations[i].id,
                        name="temporary-validation", status="active") for i in range(2)]
                    session.add_all(memberships + projects)
                    await session.flush()
                    service = AccessService(session)

                    async def deny(awaitable, label):
                        try:
                            await awaitable
                        except AccessDenied:
                            print(label + ": DENIED AS EXPECTED")
                        else:
                            raise RuntimeError("Access invariant failed")

                    identities = [await service.resolve(VerifiedPrincipal(issuer, name)) for name in ("A", "B")]
                    scopes = [await service.organization(identities[i], organizations[i].id) for i in range(2)]
                    for i in range(2):
                        require((await service.project(scopes[i], projects[i].id)).project_id == projects[i].id, "Own Project rejected")
                    print("A / B OWN ORGANIZATION AND PROJECT ACCESS: PASS")
                    for i in range(2):
                        other = 1-i
                        await deny(service.organization(identities[i], organizations[other].id), "CROSS-TENANT ORGANIZATION")
                        await deny(service.project(scopes[i], projects[other].id), "PROJECT THROUGH WRONG ORGANIZATION")
                        await deny(service.project(OrganizationScope(users[i].id, organizations[other].id), projects[other].id), "FORGED ORGANIZATION SCOPE")
                    await deny(service.organization(RequestIdentity(users[2].id), organizations[0].id), "MISSING MEMBERSHIP")
                    await deny(service.organization(RequestIdentity(uuid4()), organizations[0].id), "FORGED USER IDENTIFIER")
                    await deny(service.resolve(VerifiedPrincipal(issuer, "unknown")), "UNKNOWN EXTERNAL IDENTITY")
                    await deny(service.resolve(VerifiedPrincipal(issuer.upper(), "A")), "ISSUER EXACT MATCH")
                    await deny(service.project(scopes[0], uuid4()), "NONEXISTENT PROJECT")
                    for record, attribute, operation, label in (
                        (users[0], "status", lambda: service.resolve(VerifiedPrincipal(issuer, "A")), "USER IDENTITY"),
                        (users[0], "status", lambda: service.active_user(identities[0]), "ACTIVE USER"),
                        (users[0], "status", lambda: service.project(scopes[0], projects[0].id), "USER ACCESS"),
                        (memberships[0], "status", lambda: service.organization(identities[0], organizations[0].id), "MEMBERSHIP"),
                        (memberships[0], "status", lambda: service.project(scopes[0], projects[0].id), "REVOKED MEMBERSHIP / STALE SCOPE"),
                        (organizations[0], "status", lambda: service.project(scopes[0], projects[0].id), "ORGANIZATION"),
                        (projects[0], "status", lambda: service.project(scopes[0], projects[0].id), "PROJECT"),
                        (memberships[0], "role", lambda: service.organization(identities[0], organizations[0].id), "UNKNOWN ROLE")):
                        original = getattr(record, attribute)
                        for value in (("admin", "unknown") if attribute == "role" else ("inactive", "unknown")):
                            setattr(record, attribute, value)
                            await session.flush()
                            await deny(operation(), label + " " + value)
                        setattr(record, attribute, original)
                        await session.flush()
                    print("APPLICATION ENFORCEMENT UNDER PRIVILEGED TEST CONNECTION: PASS (not runtime RLS validation)")
            finally:
                await transaction.rollback()
            after = await state(connection)
            require(after == before, "Final database state differs from preflight")
            print("ALL TEMPORARY ROWS ROLLED BACK / EMPTY TABLES / UNCHANGED RLS: PASS")
            print("FINAL DATABASE HEAD:", HEAD)
    finally:
        await database.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-fingerprint", required=True)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.target_fingerprint))
    except Exception as error:
        print("VALIDATION STOPPED:", type(error).__name__, "(details suppressed; inspect securely)")
        raise SystemExit(1)
