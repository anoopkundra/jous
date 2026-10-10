"""Runtime consumes the migration's frozen authority, never observed expectations."""
from sqlalchemy import text
from .runtime_resolution import catalog_resolution_sync
from . import step7_catalog, step7_execution_contract as final


def verify(connection):
    contract = final.load_final_contract()
    def query(connection, sql, parameters=None):
        return [dict(row) for row in connection.execute(
            text(sql), parameters or {}).mappings().all()]
    with catalog_resolution_sync(connection):
        existing = final.freeze_runtime_bindings(connection, contract, query)
        created = final.verify_created_security_objects(connection, contract, existing, query)
        expected = final.instantiate_policy_expectations(contract, existing, created)
        # Observation is deliberately last. Policy OIDs are opaque unique identities,
        # exactly as in migration verification; they never enter template binding.
        actual = final.collect_actual_policy_rows(connection, query, step7_catalog.POLICY_SQL)
        return final.verify_policy_rows(expected, actual)


async def verify_runtime_policy_authority(connection):
    await connection.run_sync(verify)
