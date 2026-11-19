"""Offline tests for the separate pinned migration/admin transport."""

import ssl
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/api/src"))

from jous_api import migration_transport, runtime_transport
from jous_api.config import (
    ConfigurationError, MigrationSettings, Settings, load_migration_settings,
    load_settings,
)
from jous_api.database import Database, DatabaseUnavailable


HOST = "aws-0-ca-central-1.pooler.supabase.com"
PROJECT = "aqcixpoorbhjgvdkdjqd"
ADMIN_URL = f"postgresql://postgres.{PROJECT}:INERT@{HOST}:5432/postgres"
RUNTIME_URL = f"postgresql://jous_runtime.{PROJECT}:INERT@{HOST}:5432/postgres"


class MigrationTargetTests(unittest.TestCase):
    def test_exact_admin_target_accepted(self):
        migration_transport.validate_target(ADMIN_URL)

    def test_runtime_identity_rejected_by_admin_target(self):
        with self.assertRaises(migration_transport.TransportRejected):
            migration_transport.validate_target(RUNTIME_URL)

    def test_target_mutations_rejected(self):
        invalid = (
            ADMIN_URL.replace(HOST, "attacker.invalid"),
            ADMIN_URL.replace(PROJECT, "other-project"),
            ADMIN_URL.replace(":5432", ":6543"),
            ADMIN_URL.replace("/postgres", "/other"),
            ADMIN_URL + "?sslmode=disable",
            ADMIN_URL + "#fragment",
            f"postgresql://postgres.{PROJECT}:@{HOST}:5432/postgres",
        )
        for url in invalid:
            with self.subTest(url=url.split("@")[0]), self.assertRaises(
                    migration_transport.TransportRejected):
                migration_transport.validate_target(url)

    def test_missing_and_wrong_ca_fail_closed(self):
        settings = MigrationSettings(database_url=ADMIN_URL)
        with self.assertRaises(migration_transport.TransportRejected):
            migration_transport.connection_arguments(settings)
        settings = MigrationSettings(database_url=ADMIN_URL, database_ca_file="offline-ca")
        with patch.object(Path, "read_text", return_value="not-the-approved-ca"):
            with self.assertRaises(migration_transport.TransportRejected):
                migration_transport.connection_arguments(settings)

    def test_uses_shared_pinned_hostname_verifying_tls(self):
        settings = MigrationSettings(database_url=ADMIN_URL, database_ca_file="approved-ca")
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        with patch.object(Path, "read_text", return_value="approved-pem"), \
             patch.object(runtime_transport, "pinned_context", return_value=context) as pin:
            arguments = migration_transport.connection_arguments(settings)
        pin.assert_called_once_with("approved-pem")
        self.assertIs(arguments["ssl"], context)
        self.assertEqual(arguments["ssl"].verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(arguments["ssl"].check_hostname)
        self.assertEqual(arguments["target_session_attrs"], "any")
        self.assertEqual(arguments["timeout"], 5.0)


class MigrationConfigurationTests(unittest.TestCase):
    def test_migration_loader_accepts_canonical_url_and_propagates_ca(self):
        settings = load_migration_settings({
            "JOUS_MIGRATION_DATABASE_URL": ADMIN_URL,
            "JOUS_DATABASE_CA_FILE": "operator-pinned-ca.crt",
            "JOUS_DATABASE_TIMEOUT_SECONDS": "4",
            "JOUS_DATABASE_SECURITY_VALIDATION_TIMEOUT_SECONDS": "30",
        })
        self.assertIsInstance(settings, MigrationSettings)
        self.assertEqual(settings.database_url.get_secret_value(), ADMIN_URL)
        self.assertEqual(settings.database_ca_file, "operator-pinned-ca.crt")
        self.assertEqual(settings.database_timeout_seconds, 4)
        self.assertEqual(settings.database_security_validation_timeout_seconds, 30)

    def test_runtime_and_migration_credentials_never_fallback(self):
        with self.assertRaises(ConfigurationError):
            load_migration_settings({"JOUS_DATABASE_URL": RUNTIME_URL})
        runtime = load_settings({"JOUS_MIGRATION_DATABASE_URL": ADMIN_URL})
        self.assertIsNone(runtime.database_url)
        with self.assertRaises(ConfigurationError):
            load_migration_settings({
                "JOUS_DATABASE_URL": RUNTIME_URL,
                "JOUS_MIGRATION_DATABASE_URL": "",
            })


class DatabaseTransportSelectionTests(unittest.TestCase):
    def test_migration_settings_select_only_admin_transport_and_asyncpg(self):
        settings = load_migration_settings({
            "JOUS_MIGRATION_DATABASE_URL": ADMIN_URL,
            "JOUS_DATABASE_CA_FILE": "approved-ca",
            "JOUS_ENVIRONMENT": "production",
        })
        with patch("jous_api.database.migration_transport.connection_arguments",
                   return_value={"ssl": object(), "timeout": 5, "target_session_attrs": "any"}) as admin, \
             patch("jous_api.database.runtime_transport.connection_arguments") as runtime, \
             patch("jous_api.database.step7_execution_contract.load_final_contract") as step7, \
             patch("jous_api.database.create_async_engine", return_value=MagicMock()) as create:
            database = Database(settings)
        admin.assert_called_once_with(settings)
        runtime.assert_not_called()
        step7.assert_not_called()
        self.assertEqual(create.call_args.args[0].drivername, "postgresql+asyncpg")
        self.assertIs(create.call_args.kwargs["connect_args"]["ssl"],
                      admin.return_value["ssl"])
        database.engine.dispose()

    def test_runtime_settings_select_only_runtime_transport(self):
        settings = Settings(environment="production", database_url=RUNTIME_URL,
                            database_ca_file="approved-ca")
        with patch("jous_api.database.runtime_transport.connection_arguments",
                   return_value={"ssl": object(), "timeout": 5, "target_session_attrs": "any"}) as runtime, \
             patch("jous_api.database.migration_transport.connection_arguments") as admin, \
             patch("jous_api.database.step7_execution_contract.load_final_contract"), \
             patch("jous_api.database.create_async_engine", return_value=MagicMock()):
            database = Database(settings)
        runtime.assert_called_once_with(settings)
        admin.assert_not_called()
        database.engine.dispose()

    def test_migration_transport_failure_prevents_engine_creation(self):
        settings = load_migration_settings({"JOUS_MIGRATION_DATABASE_URL": ADMIN_URL})
        with patch("jous_api.database.create_async_engine") as create:
            with self.assertRaises(DatabaseUnavailable):
                Database(settings)
        create.assert_not_called()


if __name__ == "__main__":
    unittest.main()
