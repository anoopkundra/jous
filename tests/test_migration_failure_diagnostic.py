"""Offline tests for safe Alembic online-failure diagnostics."""

import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
API_SRC = ROOT / "services/api/src"
sys.path.insert(0, str(API_SRC))

ENV_PATH = ROOT / "services/api/migrations/env.py"
SPEC = importlib.util.spec_from_file_location("jous_migration_env_diagnostic_test", ENV_PATH)
migration_env = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(migration_env)


def database_error(sqlstate="XX000", message="database operation failed"):
    error = RuntimeError("secret-bearing __str__ must never be used")
    error.diag = types.SimpleNamespace(sqlstate=sqlstate, message_primary=message)
    return error


class MigrationFailureDiagnosticTests(unittest.TestCase):
    def test_emits_class_only_and_structured_sqlstate(self):
        diagnostic = migration_env._format_failure_diagnostic(
            database_error("42501", "permission denied for table tasks"),
            "ALEMBIC_MIGRATION",
        )
        self.assertIn("MIGRATION_EXCEPTION_CLASS=RuntimeError", diagnostic)
        self.assertIn("MIGRATION_SQLSTATE=42501", diagnostic)
        self.assertNotIn("secret-bearing", diagnostic)
        self.assertNotIn("RuntimeError(", diagnostic)

    def test_invalid_sqlstate_is_none(self):
        diagnostic = migration_env._format_failure_diagnostic(
            database_error("bad-state", "failure"), "CONNECTION"
        )
        self.assertIn("MIGRATION_SQLSTATE=NONE", diagnostic)

    def test_structured_primary_is_limited_to_300_characters(self):
        diagnostic = migration_env._format_failure_diagnostic(
            database_error("XX000", "x" * 500), "ALEMBIC_MIGRATION"
        )
        message = next(
            line.partition("=")[2]
            for line in diagnostic.splitlines()
            if line.startswith("MIGRATION_PRIMARY_MESSAGE=")
        )
        self.assertEqual(len(message), 300)

    def test_password_url_token_and_quoted_sql_fragments_are_redacted(self):
        message = (
            "failed password=hunter2 url=postgresql://alice:hunter2@db.example/p "
            "token:abc123 near \"DROP TABLE private_data\""
        )
        diagnostic = migration_env._format_failure_diagnostic(
            database_error("XX000", message), "ALEMBIC_MIGRATION"
        )
        for secret in ("hunter2", "postgresql://", "alice:", "abc123", "DROP TABLE"):
            self.assertNotIn(secret, diagnostic)
        self.assertTrue(
            "MIGRATION_PRIMARY_MESSAGE=UNAVAILABLE" in diagnostic
            or ("password=[REDACTED]" in diagnostic and "token=[REDACTED]" in diagnostic)
        )

    def test_missing_structured_message_does_not_fall_back_to_exception_text(self):
        class NeverStringifyError(Exception):
            def __str__(self):
                raise AssertionError("exception text must never be rendered")

        error = NeverStringifyError("postgresql://user:password@host/db secret=abc")
        diagnostic = migration_env._format_failure_diagnostic(error, "SETTINGS")
        self.assertIn("MIGRATION_PRIMARY_MESSAGE=UNAVAILABLE", diagnostic)
        self.assertNotIn("postgresql://", diagnostic)
        self.assertNotIn("secret=abc", diagnostic)

    def test_no_traceback_or_statement_is_emitted(self):
        output = io.StringIO()
        error = database_error("42601", 'syntax error at or near "REVOKE ALL"')
        with redirect_stderr(output):
            migration_env._emit_failure_diagnostic(error, "ALEMBIC_MIGRATION")
        emitted = output.getvalue()
        self.assertNotIn("Traceback", emitted)
        self.assertNotIn("REVOKE", emitted)
        self.assertEqual(len(emitted.splitlines()), 4)

    def test_main_retains_generic_runtime_error_without_exception_text(self):
        output = io.StringIO()
        def fail_after_closing(coroutine):
            coroutine.close()
            raise database_error("XX000", "safe primary")

        with patch.object(migration_env.context, "is_offline_mode", return_value=False), \
             patch.object(migration_env.context, "config", types.SimpleNamespace(attributes={}), create=True), \
             patch.object(migration_env.asyncio, "run", side_effect=fail_after_closing), \
             redirect_stderr(output):
            with self.assertRaisesRegex(
                RuntimeError,
                "^Jous migration failed; inspect target and configuration securely$",
            ) as raised:
                migration_env.main()
        self.assertIsNone(raised.exception.__cause__)
        self.assertIn("MIGRATION_SQLSTATE=XX000", output.getvalue())
        self.assertNotIn("secret-bearing", output.getvalue())

    def test_successful_online_path_emits_no_failure_diagnostic(self):
        output = io.StringIO()
        def successful_run(coroutine):
            coroutine.close()
            return None

        with patch.object(migration_env.context, "is_offline_mode", return_value=False), \
             patch.object(migration_env.context, "config", types.SimpleNamespace(attributes={}), create=True), \
             patch.object(migration_env.asyncio, "run", side_effect=successful_run), \
             redirect_stderr(output):
            migration_env.main()
        self.assertEqual(output.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
