"""Offline comparison of the default CHECK parser to its frozen HEAD baseline."""
import subprocess
import types
import unittest

from jous_api import product_runtime_validation as current
from jous_api.task_models import TASK_CHECKS, EXECUTION_CHECKS
import test_product_runtime_validation as product_tests


def head_parser():
    source = subprocess.check_output(['git', 'show', '00ee01fbadc9afbe27724dfd4a317c47ad14a62d:services/api/src/jous_api/product_runtime_validation.py'])
    module = types.ModuleType('jous_api._head_check_parser')
    module.__package__ = 'jous_api'
    exec(compile(source, '<frozen-check-parser>', 'exec'), module.__dict__)
    return module


class CheckProfileScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.head = head_parser()

    def test_frozen_source_expressions(self):
        self.assertEqual(len(TASK_CHECKS) + len(EXECUTION_CHECKS), 16)
        for table, checks in (('tasks', TASK_CHECKS), ('executions', EXECUTION_CHECKS)):
            for name, expression in checks.items():
                with self.subTest(table=table, name=name):
                    self.assertEqual(current.canonical_check_expression(expression, table, name),
                                     self.head.canonical_check_expression(expression, table, name))

    def test_catalog_fixtures_and_malformed_corpus(self):
        fixtures = product_tests.CheckGroupingCanonicalizationTests
        expressions = [fixtures.MANAGED_TASK_JSON_SHAPES,
                       fixtures.MANAGED_IDENTIFIER_BOUNDS_RENDERING,
                       fixtures.EXPECTED_IDENTIFIER_BOUNDS_RENDERING,
                       'length(name) BETWEEN 1 AND 128', 'x BETWEEN 0 AND',
                       'length(name) BETWEEN 1 AND', 'length(name) BETWEEN low AND 128',
                       'length(name) BETWEEN 1 OR 128', 'x = 1 AND',
                       "currency = ANY (ARRAY['USD'::varchar]::integer[])",
                       "(x::unknown) = 'x'", "x::text:: = 'x'",
                       'x BETWEEN 1 AND 9', 'x > 1 AND x <= 9',
                       "(payload->>'key')::integer = 1"]
        for expression in expressions:
            with self.subTest(expression=expression):
                self.assertEqual(current.canonical_check_expression(expression),
                                 self.head.canonical_check_expression(expression))

    def test_between_is_successor_scoped_and_fail_closed(self):
        name = 'ck_route_decisions_snapshot'
        def scoped(value):
            return current.canonical_check_expression(value, 'route_decisions', name, route_economics=True)
        expression = 'length(name) BETWEEN 1 AND 128'
        self.assertIsNone(current.canonical_check_expression(expression))
        expected = scoped(expression)
        self.assertIsNotNone(expected)
        self.assertEqual(expected, scoped('length(name) >= 1 AND length(name) <= 128'))
        for malformed in ('length(name) BETWEEN 1 AND', 'length(name) BETWEEN low AND 128',
                          'length(name) BETWEEN 1 OR 128'):
            self.assertIsNone(scoped(malformed))
        for different in ('length(name) BETWEEN 2 AND 128', 'length(name) > 1 AND length(name) <= 128'):
            self.assertNotEqual(scoped(different), expected)

    def test_successor_fee_and_binding_mutations_remain_distinct(self):
        def scoped(table, name, expression):
            return current.canonical_check_expression(expression, table, name, route_economics=True)
        for table, name, original, mutation in (
            ('route_pricing_versions', 'ck_route_pricing_approval',
             'provider_fee_applicable AND provider_request_fee_usd IS NOT NULL',
             'provider_fee_applicable AND provider_request_fee_usd IS NULL'),
            ('route_pricing_versions', 'ck_route_pricing_approval',
             'provider_fee_applicable AND fee_basis_verified',
             'provider_fee_applicable OR fee_basis_verified'),
            ('route_decisions', 'ck_route_decisions_snapshot_binding',
             "decision_snapshot::jsonb->>'selected_route_id'=selected_route_id",
             "decision_snapshot::jsonb->>'selected_route_id'=logical_model_id"),
        ):
            with self.subTest(name=name):
                expected = scoped(table, name, original)
                self.assertIsNotNone(expected)
                self.assertNotEqual(expected, scoped(table, name, mutation))

    def test_successor_rejects_malformed_cast_and_unsupported_arrays(self):
        for expression in ("currency = 'USD'::",
                           "currency = ANY (ARRAY['USD'::varchar]::integer[])",
                           "currency = ANY (ARRAY['USD'::text]::varchar[])"):
            with self.subTest(expression=expression):
                self.assertIsNone(current.canonical_check_expression(
                    expression, 'route_pricing_versions', 'ck_route_pricing_currency',
                    route_economics=True))
