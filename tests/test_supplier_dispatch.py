"""Funding-aware route resolution contracts; no provider sockets or credentials."""
from types import SimpleNamespace
from uuid import uuid4
import unittest

from jous_api.supplier_dispatch import DispatchAuthorityError, plan_dispatch, require_credential_match
from jous_supply.contracts import ResolvedSupplierCredential
from jous_supply.registry import HF_ROUTE


class SupplierDispatchTests(unittest.TestCase):
    def setUp(self):
        self.task = SimpleNamespace(
            id=uuid4(), organization_id=uuid4(), project_id=uuid4(), actor_user_id=uuid4(),
            dispatch_claim_id=uuid4(), logical_model_id=HF_ROUTE.logical_model_id,
            supplier_id=HF_ROUTE.supplier_id, supplier_native_model_id=HF_ROUTE.supplier_native_model_id,
            underlying_provider=HF_ROUTE.underlying_provider,
            request_parameters={"route_id": HF_ROUTE.route_id},
        )
        self.authority = {
            "funding_authority_id": uuid4(), "authority_version": 2, "authority_digest": b"x" * 32,
            "scope": "ORGANIZATION", "organization_id": self.task.organization_id,
            "supplier_id": HF_ROUTE.supplier_id, "route_id": HF_ROUTE.route_id, "route_version": 1,
            "credential_authority_ref": "ACCOUNT_A", "cost_bearer": "CUSTOMER_DIRECT",
        }
        self.decision = {
            "task_id": self.task.id, "organization_id": self.task.organization_id,
            "project_id": self.task.project_id, "actor_user_id": self.task.actor_user_id,
            "dispatch_claim_id": self.task.dispatch_claim_id,
            "logical_model_id": self.task.logical_model_id, "selected_route_id": HF_ROUTE.route_id,
            "selected_route_version": 1, "pricing_version_id": "price-v1",
            "pricing_authority_id": "price-v1", "pricing_route_id": HF_ROUTE.route_id,
            "pricing_route_version": 1, "pricing_status": "approved", "pricing_is_revoked": False,
            "funding_authority_id": self.authority["funding_authority_id"],
            "funding_authority_version": 2, "funding_authority_digest": self.authority["authority_digest"],
        }

    def test_persisted_decision_not_client_route_selects_dispatch(self):
        self.task.request_parameters = {"route_id": "client-requested-other"}
        plan = plan_dispatch(self.task, self.decision, self.authority)
        self.assertEqual(plan.route.route_id, self.decision["selected_route_id"])
        self.assertFalse(plan.legacy)

    def test_persisted_route_can_differ_from_client_task_snapshot(self):
        from unittest.mock import patch
        selected = SimpleNamespace(**{**vars(HF_ROUTE), "route_id": "server-selected-route",
            "supplier_id": "server-supplier", "supplier_native_model_id": "server/model",
            "underlying_provider": "ServerProvider"})
        authority = {**self.authority, "supplier_id": selected.supplier_id,
            "route_id": selected.route_id, "credential_authority_ref": "ACCOUNT_SERVER"}
        decision = {**self.decision, "selected_route_id": selected.route_id,
            "pricing_route_id": selected.route_id, "funding_authority_id": authority["funding_authority_id"],
            "funding_authority_digest": authority["authority_digest"]}
        self.task.request_parameters = {"route_id": HF_ROUTE.route_id}
        with patch("jous_api.supplier_dispatch.resolve", return_value=selected):
            plan = plan_dispatch(self.task, decision, authority)
        self.assertEqual(plan.route.route_id, "server-selected-route")
        self.assertEqual(plan.route.supplier_id, "server-supplier")

    def test_funding_and_credential_authority_must_match(self):
        plan = plan_dispatch(self.task, self.decision, self.authority)
        credential = ResolvedSupplierCredential("ACCOUNT_A", HF_ROUTE.supplier_id,
                                                HF_ROUTE.underlying_provider, "fake-only-secret")
        require_credential_match(plan, credential)
        wrong = ResolvedSupplierCredential("ACCOUNT_B", HF_ROUTE.supplier_id,
                                           HF_ROUTE.underlying_provider, "fake-only-secret")
        with self.assertRaises(DispatchAuthorityError):
            require_credential_match(plan, wrong)

    def test_cross_tenant_authority_and_changed_account_fail_closed(self):
        forged = {**self.authority, "organization_id": uuid4()}
        with self.assertRaises(DispatchAuthorityError):
            plan_dispatch(self.task, self.decision, forged)
        plan = plan_dispatch(self.task, self.decision, self.authority)
        with self.assertRaises(DispatchAuthorityError):
            require_credential_match(plan, ResolvedSupplierCredential(
                "ACCOUNT_B", HF_ROUTE.supplier_id, HF_ROUTE.underlying_provider, "fake-only-secret"))

    def test_enabled_route_without_decision_or_funding_fails_closed(self):
        legacy_route = SimpleNamespace(**{**vars(HF_ROUTE), "real_execution_eligible": True})
        # The production route resolver is source-owned; force the enabled-route
        # condition without mutating its frozen route object.
        from unittest.mock import patch
        with patch("jous_api.supplier_dispatch.resolve", return_value=legacy_route):
            with self.assertRaises(DispatchAuthorityError):
                plan_dispatch(self.task, None)
            unbound = {**self.decision, "funding_authority_id": None,
                       "funding_authority_version": None, "funding_authority_digest": None}
            with self.assertRaises(DispatchAuthorityError):
                plan_dispatch(self.task, unbound, None)

    def test_secret_is_not_repr_or_dispatch_identity(self):
        first = ResolvedSupplierCredential("ACCOUNT_A", HF_ROUTE.supplier_id,
                                           HF_ROUTE.underlying_provider, "secret-version-one")
        rotated = ResolvedSupplierCredential("ACCOUNT_A", HF_ROUTE.supplier_id,
                                             HF_ROUTE.underlying_provider, "secret-version-two")
        self.assertEqual(first.credential_authority_ref, rotated.credential_authority_ref)
        plan = plan_dispatch(self.task, self.decision, self.authority)
        require_credential_match(plan, first)
        require_credential_match(plan, rotated)
        self.assertNotIn("secret-version-one", repr(first))
        self.assertNotIn("secret-version-two", repr(rotated))


if __name__ == "__main__":
    unittest.main()
