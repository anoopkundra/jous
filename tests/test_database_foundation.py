"""Offline PostgreSQL infrastructure tests; no alternate database or network needed."""

import asyncio
import io
import json
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import event

from jous_api.config import ConfigurationError, Settings, load_settings
from jous_api.database import Database, DatabaseUnavailable
from jous_api.main import create_app
from test_process_foundation import request


DATABASE_URL = "postgresql://test-user:secret-password@private-host/jous"


class DatabaseTests(unittest.IsolatedAsyncioTestCase):
    async def test_construction_and_empty_transactions_never_connect(self):
        with patch("asyncpg.connect", new_callable=AsyncMock) as connect:
            settings = Settings(environment="test", database_url=DATABASE_URL)
            database = Database(settings)
            self.assertEqual(database.engine.dialect.name, "postgresql")
            self.assertEqual(database.engine.dialect.driver, "asyncpg")
            self.assertEqual(database.engine.pool.size(), 2)
            self.assertEqual(database.timeout_seconds, 5.0)
            self.assertEqual(database.security_validation_timeout_seconds, 20.0)
            self.assertEqual(database.engine.pool._timeout, 5.0)
            self.assertFalse(database.engine.echo)
            self.assertTrue(database.engine.sync_engine.hide_parameters)
            for fail in (False, True):
                events = []
                try:
                    async with database.transaction() as session:
                        event.listen(session.sync_session, "after_commit",
                                     lambda session: events.append("commit"))
                        event.listen(session.sync_session, "after_rollback",
                                     lambda session: events.append("rollback"))
                        close = AsyncMock(wraps=session.close)
                        session.close = close
                        self.assertTrue(session.in_transaction())
                        if fail:
                            raise RuntimeError("unit-of-work failure")
                except RuntimeError:
                    if not fail:
                        raise
                self.assertEqual(events, ["rollback" if fail else "commit"])
                close.assert_awaited_once()
                self.assertFalse(session.in_transaction())
            await database.dispose()
            connect.assert_not_called()

    async def test_engine_connection_and_pool_timeouts_do_not_follow_validation_budget(self):
        settings = Settings(environment="test", database_url=DATABASE_URL,
                            database_timeout_seconds=5,
                            database_security_validation_timeout_seconds=20)
        engine = MagicMock()
        engine.dispose = AsyncMock()
        with patch("jous_api.database.create_async_engine", return_value=engine) as create:
            database = Database(settings)
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs["pool_timeout"], 5)
        self.assertEqual(kwargs["connect_args"]["timeout"], 5)
        self.assertEqual(database.security_validation_timeout_seconds, 20)
        await database.dispose()

    async def test_missing_configuration(self):
        database = Database(Settings(environment="test"))
        with self.assertRaises(DatabaseUnavailable):
            await database.check()
        with self.assertRaises(DatabaseUnavailable):
            async with database.transaction():
                self.fail("Unconfigured session must not be yielded")
        await database.dispose()

    async def test_probe_checks_result_and_releases_connection(self):
        database = Database(Settings(environment="test"))
        engine = MagicMock()
        connection = engine.connect.return_value
        connection.start = AsyncMock()
        connection.sync_connection = MagicMock()
        connection.scalar = AsyncMock(return_value=1)
        connection.__aexit__ = AsyncMock()
        database.engine = engine
        with patch("jous_api.database.validate_runtime", new_callable=AsyncMock):
            await database.check()
        self.assertEqual(str(connection.scalar.call_args.args[0]), "SELECT 1")
        connection.start.assert_awaited_once()
        connection.__aexit__.assert_awaited_once()
        connection.scalar.return_value = 0
        with patch("jous_api.database.validate_runtime", new_callable=AsyncMock):
            with self.assertRaises(DatabaseUnavailable):
                await database.check()

    async def test_validator_can_exceed_connection_timeout_within_validation_budget(self):
        database = Database(Settings(environment="test", database_timeout_seconds=5,
                                     database_security_validation_timeout_seconds=5.5))
        engine = MagicMock()
        connection = engine.connect.return_value
        connection.start = AsyncMock()
        connection.sync_connection = MagicMock()
        connection.scalar = AsyncMock(return_value=1)
        connection.__aexit__ = AsyncMock()
        database.engine = engine

        async def slow_validator(_connection):
            await asyncio.sleep(5.05)

        with patch("jous_api.database.validate_runtime", new=slow_validator):
            await database.check()
        connection.__aexit__.assert_awaited_once()

    async def test_validator_over_security_budget_fails_closed_and_discards(self):
        database = Database(Settings(environment="test", database_security_validation_timeout_seconds=0.1))
        engine = MagicMock()
        connection = engine.connect.return_value
        connection.start = AsyncMock()
        connection.sync_connection = MagicMock()
        connection.scalar = AsyncMock(return_value=1)
        connection.__aexit__ = AsyncMock()
        database.engine = engine

        async def hang(_connection):
            await asyncio.Event().wait()

        with patch("jous_api.database.validate_runtime", new=hang), \
             patch.object(database, "discard_connection", new_callable=AsyncMock) as discard:
            with self.assertRaises(TimeoutError):
                await database.check()
        discard.assert_awaited_once_with(connection)
        connection.__aexit__.assert_awaited_once()

    async def test_final_readiness_select_is_inside_security_budget(self):
        database = Database(Settings(environment="test", database_security_validation_timeout_seconds=0.1))
        engine = MagicMock()
        connection = engine.connect.return_value
        connection.start = AsyncMock()
        connection.sync_connection = MagicMock()
        connection.__aexit__ = AsyncMock()
        database.engine = engine

        async def hang(_statement):
            await asyncio.Event().wait()

        connection.scalar = AsyncMock(side_effect=hang)
        with patch("jous_api.database.validate_runtime", new_callable=AsyncMock), \
             patch.object(database, "discard_connection", new_callable=AsyncMock) as discard:
            with self.assertRaises(TimeoutError):
                await database.check()
        connection.scalar.assert_awaited_once()
        discard.assert_awaited_once_with(connection)
        connection.__aexit__.assert_awaited_once()

    async def test_connection_acquisition_uses_short_timeout(self):
        database = Database(Settings(environment="test", database_timeout_seconds=0.1,
                                     database_security_validation_timeout_seconds=0.2))
        engine = MagicMock()
        connection = engine.connect.return_value
        connection.sync_connection = MagicMock()
        async def slow_start():
            await asyncio.sleep(0.2)
        connection.start = AsyncMock(side_effect=slow_start)
        connection.__aexit__ = AsyncMock()
        database.engine = engine
        validator = AsyncMock()
        with patch("jous_api.database.validate_runtime", validator):
            with self.assertRaises(TimeoutError):
                await database.check()
        validator.assert_not_awaited()
        connection.__aexit__.assert_awaited_once()

    async def test_application_lifespan_disposes_without_connecting(self):
        with patch("asyncpg.connect", new_callable=AsyncMock) as connect:
            app = create_app(Settings(environment="test", database_url=DATABASE_URL))
            with patch.object(app.state.database, "dispose", wraps=app.state.database.dispose) as dispose, patch.object(app.state.database, "check", new_callable=AsyncMock):
                async with app.router.lifespan_context(app):
                    connect.assert_not_called()
                dispose.assert_awaited_once()
            connect.assert_not_called()

    async def test_application_startup_waits_for_security_certification(self):
        app = create_app(Settings(environment="test", database_url=DATABASE_URL))
        entered = asyncio.Event()
        release = asyncio.Event()

        async def certify():
            entered.set()
            await release.wait()

        app.state.database.check = AsyncMock(side_effect=certify)
        lifespan = app.router.lifespan_context(app)
        startup = asyncio.create_task(lifespan.__aenter__())
        await entered.wait()
        self.assertFalse(startup.done())
        release.set()
        await startup
        app.state.database.check.assert_awaited_once()
        await lifespan.__aexit__(None, None, None)

    async def test_application_startup_fails_when_certification_fails(self):
        app = create_app(Settings(environment="test", database_url=DATABASE_URL))
        app.state.database.check = AsyncMock(side_effect=DatabaseUnavailable("validation failed"))
        lifespan = app.router.lifespan_context(app)
        with self.assertRaises(DatabaseUnavailable):
            await lifespan.__aenter__()
        app.state.database.check.assert_awaited_once()


class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_probe_driver_failure_is_safe(self):
        app = create_app(Settings(environment="test", database_url=DATABASE_URL))
        output = io.StringIO()
        app.state.logger.handlers[0].setStream(output)
        with patch("asyncpg.connect", new_callable=AsyncMock,
                   side_effect=RuntimeError(DATABASE_URL)) as connect:
            start, body = await request(app, path="/health/ready")
            connect.assert_awaited_once()
        self.assertEqual(start["status"], 503)
        self.assertNotIn("secret-password", json.dumps(body) + output.getvalue())
        self.assertNotIn("private-host", json.dumps(body) + output.getvalue())
        await app.state.database.dispose()

    async def test_ready_success_and_correlation(self):
        app = create_app(Settings(environment="test"))
        app.state.database.check = AsyncMock()
        start, body = await request(app, [(b"x-request-id", b"ready-123")], "/health/ready")
        self.assertEqual(start["status"], 200)
        self.assertEqual(body, {"status": "ready", "database": "reachable", "request_id": "ready-123"})
        self.assertIn((b"x-request-id", b"ready-123"), start["headers"])
        app.state.database.check.assert_awaited_once()

    async def test_database_failure_is_safe_and_liveness_independent(self):
        app = create_app(Settings(environment="test", database_url=DATABASE_URL))
        output = io.StringIO()
        app.state.logger.handlers[0].setStream(output)
        app.state.database.check = AsyncMock(side_effect=RuntimeError(
            DATABASE_URL + " SQL SELECT /private/file Traceback"))
        start, body = await request(app, [(b"x-request-id", b"failure-123")], "/health/ready")
        self.assertEqual(start["status"], 503)
        self.assertEqual(body, {"status": "not_ready", "database": "unavailable", "request_id": "failure-123"})
        self.assertIn((b"x-request-id", b"failure-123"), start["headers"])
        logs = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(logs[0]["event"], "database_unavailable")
        self.assertTrue(all(entry["request_id"] == "failure-123" for entry in logs))
        for sensitive in (DATABASE_URL, "secret-password", "test-user", "private-host",
                          "SQL", "SELECT", "/private/file", "Traceback"):
            self.assertNotIn(sensitive, json.dumps(body) + output.getvalue())
        app.state.database.check.reset_mock()
        live, live_body = await request(app)
        self.assertEqual(live["status"], 200)
        self.assertEqual(live_body, {"status": "alive"})
        app.state.database.check.assert_not_called()
        await app.state.database.dispose()

    async def test_unconfigured_database_is_not_ready_with_generated_id(self):
        app = create_app(Settings(environment="test"))
        start, body = await request(app, path="/health/ready")
        self.assertEqual(start["status"], 503)
        self.assertEqual(body["request_id"], dict(start["headers"])[b"x-request-id"].decode())


class DatabaseConfigurationTests(unittest.TestCase):
    def test_timeout_configuration(self):
        defaults = load_settings({})
        self.assertEqual(defaults.database_timeout_seconds, 5.0)
        self.assertEqual(defaults.database_security_validation_timeout_seconds, 20.0)
        configured = load_settings({"JOUS_DATABASE_TIMEOUT_SECONDS": "2",
                                    "JOUS_DATABASE_SECURITY_VALIDATION_TIMEOUT_SECONDS": "25"})
        self.assertEqual(configured.database_timeout_seconds, 2)
        self.assertEqual(configured.database_security_validation_timeout_seconds, 25)
        connection_only = load_settings({"JOUS_DATABASE_TIMEOUT_SECONDS": "3"})
        validation_only = load_settings({"JOUS_DATABASE_SECURITY_VALIDATION_TIMEOUT_SECONDS": "30"})
        self.assertEqual(connection_only.database_security_validation_timeout_seconds, 20.0)
        self.assertEqual(validation_only.database_timeout_seconds, 5.0)
        for value in ("0", "31", "nan", "inf", "credential-secret"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError) as error:
                load_settings({"JOUS_DATABASE_SECURITY_VALIDATION_TIMEOUT_SECONDS": value})
            self.assertEqual(str(error.exception),
                             "Invalid Jous configuration: JOUS_DATABASE_SECURITY_VALIDATION_TIMEOUT_SECONDS")

    def test_migration_settings_preserve_independent_validation_timeout(self):
        from jous_api.config import load_migration_settings
        settings = load_migration_settings({
            "JOUS_MIGRATION_DATABASE_URL": "postgresql://admin:secret@host/db",
            "JOUS_DATABASE_TIMEOUT_SECONDS": "4",
            "JOUS_DATABASE_SECURITY_VALIDATION_TIMEOUT_SECONDS": "30",
        })
        self.assertEqual(settings.database_timeout_seconds, 4)
        self.assertEqual(settings.database_security_validation_timeout_seconds, 30)
