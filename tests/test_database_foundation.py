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
        context = engine.connect.return_value
        connection = context.__aenter__.return_value
        connection.scalar = AsyncMock(return_value=1)
        database.engine = engine
        await database.check()
        self.assertEqual(str(connection.scalar.call_args.args[0]), "SELECT 1")
        context.__aexit__.assert_awaited_once()
        connection.scalar.return_value = 0
        with self.assertRaises(DatabaseUnavailable):
            await database.check()

    async def test_probe_timeout_releases_connection(self):
        database = Database(Settings(environment="test", database_timeout_seconds=0.1))
        engine = MagicMock()
        context = engine.connect.return_value

        async def hang(statement):
            await asyncio.Event().wait()

        context.__aenter__.return_value.scalar = AsyncMock(side_effect=hang)
        database.engine = engine
        with self.assertRaises(TimeoutError):
            await database.check()
        context.__aexit__.assert_awaited_once()

    async def test_application_lifespan_disposes_without_connecting(self):
        with patch("asyncpg.connect", new_callable=AsyncMock) as connect:
            app = create_app(Settings(environment="test", database_url=DATABASE_URL))
            with patch.object(app.state.database, "dispose", wraps=app.state.database.dispose) as dispose:
                async with app.router.lifespan_context(app):
                    connect.assert_not_called()
                dispose.assert_awaited_once()
            connect.assert_not_called()


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
        self.assertEqual(load_settings({"JOUS_DATABASE_TIMEOUT_SECONDS": "2"}).database_timeout_seconds, 2)
        for value in ("0", "31", "nan", "inf", "credential-secret"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError) as error:
                load_settings({"JOUS_DATABASE_TIMEOUT_SECONDS": value})
            self.assertEqual(str(error.exception), "Invalid Jous configuration: JOUS_DATABASE_TIMEOUT_SECONDS")
