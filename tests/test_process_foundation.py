import io
import json
import logging
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

from jous_api.config import ConfigurationError, Settings, load_settings
from jous_api.main import create_app
from jous_api.middleware import RequestBoundary
from jous_api.observability import JsonFormatter, request_id


async def request(app, headers=(), path="/health/live"):
    messages = []
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "GET", "scheme": "http", "path": path, "raw_path": path.encode(),
             "query_string": b"", "headers": list(headers), "server": ("test", 80),
             "client": ("test", 1)}

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start, json.loads(body)


class ConfigurationTests(unittest.TestCase):
    def test_defaults_and_production(self):
        self.assertEqual(load_settings({}).environment, "development")
        settings = load_settings({"JOUS_ENVIRONMENT": "production",
                                  "JOUS_DATABASE_URL": "postgresql://user:secret@db/jous",
                                  "JOUS_API_PORT": "9000"})
        self.assertEqual(settings.api_port, 9000)
        self.assertNotIn("secret", repr(settings))
        self.assertNotIn("secret", settings.model_dump_json())

    def test_invalid_configuration_is_safe(self):
        for values in ({"JOUS_ENVIRONMENT": "production"},
                       {"JOUS_API_PORT": "secret-value"},
                       {"JOUS_DATABASE_URL": "secret-value"},
                       {"JOUS_LOG_LEVEL": "secret-value"},
                       {"JOUS_ENVIRONMENT": "secret-value"}):
            with self.subTest(values=values), self.assertRaises(ConfigurationError) as error:
                load_settings(values)
            self.assertNotIn("secret-value", str(error.exception))
            self.assertIn("JOUS_", str(error.exception))

    def test_json_logs_drop_sensitive_data(self):
        formatter = JsonFormatter(Settings(environment="test"))
        record = logging.LogRecord("test", logging.ERROR, "/private/path", 1,
                                   "Bearer secret postgres://password", (), None)
        record.secret = "secret"
        result = formatter.format(record)
        self.assertNotIn("secret", result)
        self.assertNotIn("private", result)
        self.assertEqual(json.loads(result)["environment"], "test")

    def test_configuration_failure_logs_are_safe(self):
        output = io.StringIO()
        with patch.dict("os.environ", {"JOUS_API_PORT": "credential-secret"}, clear=True):
            with redirect_stderr(output), self.assertRaises(ConfigurationError):
                create_app()
        entry = json.loads(output.getvalue())
        self.assertEqual(entry["event"], "configuration_failed")
        self.assertNotIn("credential-secret", output.getvalue())


class RequestTests(unittest.IsolatedAsyncioTestCase):
    async def test_liveness_and_propagation(self):
        app = create_app(Settings(environment="test"))
        start, body = await request(app, [(b"x-request-id", b"safe-123")])
        self.assertEqual(start["status"], 200)
        self.assertEqual(body, {"status": "alive"})
        self.assertIn((b"x-request-id", b"safe-123"), start["headers"])
        self.assertIsNone(request_id.get())

    async def test_default_id_generation(self):
        app = create_app(Settings(environment="test"))
        start, _ = await request(app)
        identity = dict(start["headers"])[b"x-request-id"].decode()
        self.assertEqual(len(identity), 32)
        self.assertEqual(int(identity, 16) >= 0, True)
        self.assertIsNone(request_id.get())

    async def test_unsafe_and_missing_ids_are_replaced(self):
        logger = logging.Logger("test")

        async def inner(scope, receive, send):
            self.assertEqual(request_id.get(), "generated")
            self.assertEqual(scope["state"]["request_id"], "generated")
            await send({"type": "http.response.start", "status": 200, "headers": []})
            await send({"type": "http.response.body", "body": b"{}"})

        for headers in ([], [(b"x-request-id", b"x" * 65)],
                        [(b"x-request-id", b"bad\r\nheader")],
                        [(b"x-request-id", b"\xff")],
                        [(b"x-request-id", b"one"), (b"x-request-id", b"two")]):
            start, _ = await request(RequestBoundary(inner, logger, lambda: "generated"), headers)
            self.assertIn((b"x-request-id", b"generated"), start["headers"])

    async def test_unexpected_exception_is_safe_and_correlated(self):
        app = create_app(Settings(environment="test"))
        output = io.StringIO()
        app.state.logger.handlers[0].setStream(output)

        @app.get("/failure")
        async def failure():
            raise RuntimeError("secret-password C:\\private\\file SQL SELECT token")

        start, body = await request(app, [(b"x-request-id", b"error-123")], "/failure")
        self.assertEqual(start["status"], 500)
        self.assertEqual(body, {"error": {"code": "internal_error", "message": "Internal server error"},
                                "request_id": "error-123"})
        self.assertIn((b"x-request-id", b"error-123"), start["headers"])
        for value in ("secret-password", "private", "SELECT", "token", "Traceback"):
            self.assertNotIn(value, json.dumps(body) + output.getvalue())
        entry = json.loads(output.getvalue())
        self.assertEqual(entry["event"], "request_failed")
        self.assertEqual(entry["request_id"], "error-123")
