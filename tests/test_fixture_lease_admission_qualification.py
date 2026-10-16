"""Increment A synthetic read-only qualification tests; no SQLite or providers."""
import ast
import copy
from contextlib import ExitStack
from dataclasses import replace, FrozenInstanceError
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
old = runpy.run_path(str(ROOT / 'tests/test_fixture_lease_admission_retention.py'))
r, s, a, g = (old[name] for name in ('r', 's', 'a', 'g'))
spec = importlib.util.spec_from_file_location('_il4a_pure.fixture_lease_admission_qualification',
    ROOT / 'services/api/infrastructure/fixture_lease_admission_qualification.py')
q = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = q
spec.loader.exec_module(q)

PERMISSIONS = old['PERMISSIONS'] + ('commit_permitted', 'renewal_permitted', 'cancellation_permitted')
VALID = s.EvidenceValidity.VALID
INVALID = s.EvidenceValidity.INVALID
UNKNOWN = s.EvidenceValidity.UNKNOWN
_DEFAULT = object()


def forged(value, **changes):
    result = object.__new__(type(value))
    for field in q.fields(type(value)):
        object.__setattr__(result, field.name, changes.get(field.name, object.__getattribute__(value, field.name)))
    return result


def set_path(value, path, replacement):
    names = path.split('.')
    for name in names[:-1]: value = object.__getattribute__(value, name)
    object.__setattr__(value, names[-1], replacement)


class QualificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture = old['RetentionTests']
        fixture.setUpClass()
        owner = fixture()
        owner.setUp()
        cls.template = owner.run_gate()

    def setUp(self):
        self.source = q._copy(self.template)
        self.expected = q._copy(self.template)
        self.authority = q._copy(r._authority(self.expected.prepared))
        self.proof = s.EvidenceReference('current-independent-proof', b'c' * 32)
        time = self.expected.prepared.material.source.qualification.time
        self.support = q.ModelSupport(s.EvidenceReference('synthetic-approved-model', b'm' * 32),
            s.EvidenceReference('synthetic-local-interpretation', b'i' * 32), self.proof,
            time.profile.profile, time.sample.source, time.profile.max_elapsed_ns,
            q.ErrorConventions.DESIGN7_NS_OUTWARD)
        self.calls = 0
        self.value = _DEFAULT
        self.error = None
        self.mutate = None
        self.response_alias = None
        self.request_alias = None
        self.adapter = q.TrustedQualificationAdapter(self.authority, (self.support,), self.qualify)

    def response(self):
        bundle = self.expected.prepared.material.source.attempt.bundle
        original = self.expected.prepared.material.source.qualification.time
        point = replace(original.point, ticks_ns=original.point.ticks_ns + 1000)
        elapsed = point.ticks_ns - original.sample.anchor.ticks_ns
        error = s.QualifiedPropagationError(original.sample.sample, original.sample.profile, elapsed, 0, self.proof)
        time = replace(original, point=point, propagation=error)
        binding = q.PropagationModelBinding(self.support, time.sample.sample,
            point.process_id, point.domain_id, elapsed, elapsed + 4000, VALID, self.proof)
        return q.CurrentQualification(q._copy(self.expected), self.authority, self.proof,
            *([VALID] * 9), q._copy(bundle.authorization), q._copy(bundle.approval), time, binding)

    def qualify(self, source):
        self.calls += 1
        self.request_alias = source
        if self.mutate == 'request': object.__setattr__(source.envelope, 'fixed_utc_us', 99)
        if self.mutate == 'caller': object.__setattr__(self.source.envelope, 'fixed_utc_us', 99)
        if self.mutate == 'adapter':
            object.__setattr__(self.adapter, 'qualify', lambda value: self.fail('replacement called'))
            object.__setattr__(self.adapter, 'supported_models', ())
        if self.error: raise self.error('sensitive diagnostic')
        self.response_alias = self.response() if self.value is _DEFAULT else self.value
        return self.response_alias

    def evaluate(self): return q.qualify_admission_inputs(self.source, self.adapter)

    def assert_state(self, state, reason=None):
        result = self.evaluate()
        self.assertIs(result.state, state)
        if reason is not None: self.assertIs(result.reason, reason)
        for name in PERMISSIONS: self.assertIs(getattr(result, name), False)
        if result.inputs is not None:
            for name in PERMISSIONS: self.assertIs(getattr(result.inputs, name), False)
        return result

    def test_success_one_read_detached_knowledge(self):
        result = self.assert_state(q.QualificationState.QUALIFIED)
        self.assertEqual(self.calls, 1)
        self.assertEqual(result.inputs.evaluation.interval, s.UtcInterval(11, 11))
        self.assertEqual(result.inputs.observation.source.envelope.fixed_utc_us, 10)
        self.assertEqual(result.inputs.observation.time.sample.anchor.ticks_ns, 0)
        self.assertEqual(result.inputs.observation.time.point.ticks_ns, 1000)

    def test_default_unavailable_zero_calls(self):
        result = q.qualify_admission_inputs(self.source)
        self.assertIs(result.state, q.QualificationState.UNRESOLVED)
        self.assertFalse(result.attempted)
        self.assertEqual(self.calls, 0)

    def test_historical_acquisition_not_a_source(self):
        self.source = self.source.prepared.material.source
        self.assert_state(q.QualificationState.REJECTED)
        self.assertEqual(self.calls, 0)

    def test_retention_alone_not_current_qualification(self):
        self.value = self.source
        self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.RESPONSE)
        self.assertEqual(self.calls, 1)

    def test_non_success_retention_rejected_without_read(self):
        self.source = r.retain_original_envelope(self.source.prepared)
        self.assert_state(q.QualificationState.REJECTED)
        self.assertEqual(self.calls, 0)

    def test_retention_upstream_unresolved_rejected_without_read(self):
        owner = old['RetentionTests']()
        owner.setUp()
        self.source = r.retain_original_envelope(owner.upstream)
        self.assert_state(q.QualificationState.REJECTED)
        self.assertEqual(self.calls, 0)

    def test_foreign_source_zero_hooks_and_calls(self):
        Foreign.calls = []
        self.source = Foreign()
        self.assert_state(q.QualificationState.REJECTED)
        self.assertEqual(Foreign.calls, [])
        self.assertEqual(self.calls, 0)

    def test_foreign_dependency_no_hooks(self):
        Foreign.calls = []
        self.adapter = Foreign()
        self.assert_state(q.QualificationState.UNRESOLVED)
        self.assertEqual(Foreign.calls, [])

    def test_dependency_subclass_not_authority(self):
        class Sub(q.TrustedQualificationAdapter): pass
        self.adapter = object.__new__(Sub)
        self.assert_state(q.QualificationState.UNRESOLVED)
        self.assertEqual(self.calls, 0)

    def test_request_supplied_callback_not_dependency(self):
        self.adapter = self.qualify
        self.assert_state(q.QualificationState.UNRESOLVED)
        self.assertEqual(self.calls, 0)

    def test_wrong_composed_authority_no_dispatch(self):
        self.adapter = replace(self.adapter, authority=s.EvidenceReference('other', b'x' * 32))
        self.assert_state(q.QualificationState.UNRESOLVED)
        self.assertEqual(self.calls, 0)

    def test_model_reference_alone_not_support(self):
        self.adapter = forged(self.adapter, supported_models=(self.support.model,))
        self.assert_state(q.QualificationState.UNRESOLVED)
        self.assertEqual(self.calls, 0)

    def test_success_outputs_have_no_callback_aliases(self):
        result = self.evaluate()
        object.__setattr__(self.request_alias.envelope, 'fixed_utc_us', 99)
        object.__setattr__(self.response_alias.source.envelope.reference, 'identity', 'changed')
        object.__setattr__(self.response_alias.time.sample, 'source', 'changed')
        object.__setattr__(self.support.model, 'identity', 'changed')
        q.AdmissionQualificationResult.__post_init__(result)
        self.assertEqual(result.inputs.observation.source.envelope.fixed_utc_us, 10)
        self.assertEqual(result.inputs.observation.model.support.model.identity, 'synthetic-approved-model')

    def test_adapter_replacement_does_not_change_captured_dependency(self):
        self.mutate = 'adapter'
        self.assert_state(q.QualificationState.QUALIFIED)
        self.assertEqual(self.calls, 1)

    def test_construction_replacement_copy_truthiness_denied(self):
        result = self.evaluate()
        for value in (result, result.inputs):
            with self.assertRaises(TypeError): type(value)()
            with self.assertRaises(TypeError): replace(value)
            with self.assertRaises(TypeError): copy.copy(value)
            with self.assertRaises(TypeError): copy.deepcopy(value)
            with self.assertRaises(TypeError): bool(value)
            with self.assertRaises(FrozenInstanceError): value.unapproved = True

    def test_all_states_deny_permissions_and_truthiness(self):
        success = self.evaluate()
        rejected = q.qualify_admission_inputs(None)
        unresolved = q.qualify_admission_inputs(self.source)
        for result in (success, rejected, unresolved):
            for name in PERMISSIONS: self.assertIs(getattr(result, name), False)
            with self.assertRaises(TypeError): bool(result)
        self.assertIsNone(rejected.inputs)
        self.assertIsNone(unresolved.inputs)

    def test_mutated_result_contradiction_cannot_validate(self):
        result = q.qualify_admission_inputs(self.source)
        object.__setattr__(result, 'state', q.QualificationState.QUALIFIED)
        with self.assertRaises(s.TimeRejected): q.AdmissionQualificationResult.__post_init__(result)

    def test_current_observation_not_sample_anchor(self):
        self.value = self.response()
        self.value = replace(self.value, time=replace(self.value.time,
            point=replace(self.value.time.point, ticks_ns=200000),
            propagation=replace(self.value.time.propagation, elapsed_ns=200000)),
            model=replace(self.value.model, min_elapsed_ns=200000, max_elapsed_ns=200001))
        self.assert_state(q.QualificationState.REJECTED)

    def test_observation_age_uses_error_not_just_elapsed(self):
        self.value = self.response()
        self.value = replace(self.value, time=replace(self.value.time,
            propagation=replace(self.value.time.propagation, error_ns=100001)))
        self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.TIME)

    def test_scope_profile_upper_boundary_is_inclusive(self):
        self.value = self.response()
        self.value = replace(self.value, model=replace(self.value.model,
            max_elapsed_ns=self.value.time.profile.max_elapsed_ns))
        self.assert_state(q.QualificationState.QUALIFIED)

    def test_original_fixing_graph_preserved(self):
        before = q._project(self.source)
        result = self.evaluate()
        self.assertEqual(q._project(result.inputs.observation.source), before)
        self.assertEqual(result.inputs.observation.source.envelope.fixing,
                         self.source.envelope.fixing)

    def refreshed(self):
        value = self.response()
        old_sample = value.time.sample
        anchor = replace(old_sample.anchor, ticks_ns=1000)
        sample = replace(old_sample, sample=s.EvidenceReference('refresh', b'f' * 32),
            validation=s.EvidenceReference('refresh-proof', b'v' * 32), utc=s.UtcInterval(11, 11), anchor=anchor)
        time = replace(value.time, sample=sample, point=replace(anchor, ticks_ns=2000),
            propagation=s.QualifiedPropagationError(sample.sample, sample.profile, 1000, 0, self.proof))
        return replace(value, time=time, model=replace(value.model, sample=sample.sample),
            fixing_to_refresh=s.QualifiedPropagationError(old_sample.sample, old_sample.profile, 1000, 0, self.proof))

    def test_qualified_refresh_preserves_original_fixing(self):
        self.value = self.refreshed()
        result = self.assert_state(q.QualificationState.QUALIFIED)
        self.assertEqual(result.inputs.evaluation.interval, s.UtcInterval(12, 12))
        self.assertEqual(result.inputs.observation.source.envelope.fixed_utc_us, 10)
        self.assertNotEqual(result.inputs.observation.time.sample,
                            result.inputs.observation.source.envelope.fixing.sample)

    def test_refresh_without_bridge_rejected(self):
        self.value = replace(self.refreshed(), fixing_to_refresh=None)
        self.assert_state(q.QualificationState.REJECTED)

    def test_foreign_source_subclass_and_metaclass_no_hooks(self):
        class Meta(type):
            def __getattribute__(self, name): Foreign.calls.append('meta_attribute'); raise AssertionError()
            def __eq__(self, other): Foreign.calls.append('meta_equality'); raise AssertionError()
            def __hash__(self): Foreign.calls.append('meta_hash'); raise AssertionError()
        class Bad(metaclass=Meta): pass
        Foreign.calls = []
        self.source = object.__new__(Bad)
        self.assert_state(q.QualificationState.REJECTED)
        self.assertEqual(Foreign.calls, [])
        self.assertEqual(self.calls, 0)

    def test_foreign_nested_source_no_hooks(self):
        Foreign.calls = []
        set_path(self.source, 'envelope.fixing.sample', Foreign())
        self.assert_state(q.QualificationState.REJECTED)
        self.assertEqual(Foreign.calls, [])
        self.assertEqual(self.calls, 0)

    def test_response_subclass_rejected(self):
        class Sub(q.CurrentQualification): pass
        self.value = object.__new__(Sub)
        self.assert_state(q.QualificationState.REJECTED)

    def rewrite_original(self, row_type, field, replacement):
        # Synthetic fixture transformation updates every duplicate witness;
        # production accepts no such mutation or source-fabrication interface.
        def rewrite(projection):
            kind, data = projection
            if type(data) is tuple and data and type(data[0]) is tuple and type(data[0][0]) is str:
                data = tuple((name, (type(replacement), replacement) if kind is row_type and name == field
                              else rewrite(child)) for name, child in data)
            return kind, data
        self.source = a._copy_projection(rewrite(q._project(self.source)))
        q._validate(self.source)
        self.expected = q._copy(self.source)

    def observe_at(self, ticks):
        value = self.response()
        elapsed = ticks - value.time.sample.anchor.ticks_ns
        return replace(value, time=replace(value.time, point=replace(value.time.point, ticks_ns=ticks),
            propagation=replace(value.time.propagation, elapsed_ns=elapsed)),
            model=replace(value.model, min_elapsed_ns=elapsed, max_elapsed_ns=elapsed + 1000))

    def test_permit_expiry_equality_rejects(self):
        self.value = self.observe_at(10000)  # UTC 20 == original permit.valid_until
        self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.TIME)

    def test_permit_just_before_expiry_accepts(self):
        self.value = self.observe_at(9000)  # UTC 19
        self.assert_state(q.QualificationState.QUALIFIED)

    def test_inclusive_authorization_deadline_equality_accepts(self):
        self.rewrite_original(s.CommandPermit, 'valid_until_us', 100)
        self.value = self.observe_at(10000)  # UTC 20 == inclusive authorization
        self.assert_state(q.QualificationState.QUALIFIED)

    def test_authorization_deadline_exceeded_rejects(self):
        self.rewrite_original(s.CommandPermit, 'valid_until_us', 100)
        self.value = self.observe_at(11000)
        self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.TIME)

    def test_approval_deadline_exceeded_rejects(self):
        self.rewrite_original(s.CommandPermit, 'valid_until_us', 100)
        self.rewrite_original(g.AuthorizationEvidence, 'deadline', s.InclusiveDeadline(80))
        self.value = self.observe_at(21000)  # UTC 31 > approval 30
        self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.TIME)

    def test_inclusive_approval_deadline_equality_accepts(self):
        self.rewrite_original(s.CommandPermit, 'valid_until_us', 100)
        self.rewrite_original(g.AuthorizationEvidence, 'deadline', s.InclusiveDeadline(80))
        self.value = self.observe_at(20000)
        self.assert_state(q.QualificationState.QUALIFIED)

    def test_strict_freshness_deadline_equality_rejects(self):
        self.rewrite_original(s.CommandPermit, 'valid_until_us', 100)
        self.rewrite_original(g.AuthorizationEvidence, 'deadline', s.InclusiveDeadline(80))
        self.rewrite_original(g.ApprovalEvidence, 'deadline', s.InclusiveDeadline(80))
        self.value = self.observe_at(30000)  # UTC 40 == strict freshness
        self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.TIME)

    def test_uncertainty_limit_rejects(self):
        value = self.response()
        self.value = replace(value, time=replace(value.time,
            propagation=replace(value.time.propagation, error_ns=51000)))
        self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.TIME)

    def test_unsupported_composed_profile_limit_rejects(self):
        self.support = replace(self.support, max_elapsed_ns=self.support.max_elapsed_ns + 1)
        self.adapter = replace(self.adapter, supported_models=(self.support,))
        self.value = self.response()
        self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.MODEL)

    def test_internal_validator_programming_errors_propagate(self):
        for error in (AssertionError, RuntimeError, TypeError):
            with patch.object(r.RetentionResult, '__post_init__', side_effect=error('internal')):
                with self.assertRaises(error): self.evaluate()
        self.assertEqual(self.calls, 0)

    def test_detached_snapshot_validated_before_dispatch(self):
        validate = q._validate
        seen = []
        def validation(value):
            validate(value)
            if type(value) is r.RetentionResult:
                seen.append(value)
                # Simulate caller mutation while its detached snapshot is being
                # validated. No qualifier may observe this inconsistent input.
                object.__setattr__(self.source.envelope, 'fixed_utc_us', 99)
        with patch.object(q, '_validate', validation):
            self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.SOURCE)
        self.assertEqual(self.calls, 0)
        self.assertEqual(len(seen), 1)
        self.assertIsNot(seen[0], self.source)
        self.assertEqual(seen[0].envelope.fixed_utc_us, 10)

    def test_contradictory_refresh_rejected(self):
        value = self.refreshed()
        self.value = replace(value, time=replace(value.time, sample=replace(value.time.sample, utc=s.UtcInterval(500, 500))))
        self.assert_state(q.QualificationState.REJECTED)

    def test_no_future_writer_point_coverage_or_executable_in_output(self):
        result = self.evaluate()
        forbidden_types = (s.AdmissionEvidence, s.AdmissionCoverage)
        def visit(value):
            self.assertFalse(any(type(value) is t for t in forbidden_types))
            self.assertNotIn(type(value), (q.FunctionType, q.MethodType))
            if type(value) in q._own_types():
                for field in q.fields(type(value)):
                    self.assertNotIn(field.name, ('m1', 'writer', 'admission_coverage', 'consume'))
                    visit(object.__getattribute__(value, field.name))
        visit(result.inputs)
        # Existing point-specific errors are only historical/observation data.
        observed = result.inputs.observation
        self.assertEqual(observed.time.propagation.elapsed_ns,
            observed.time.point.ticks_ns - observed.time.sample.anchor.ticks_ns)
        self.assertFalse(hasattr(observed.model, 'error_ns'))

    def test_forbidden_effect_sentinels(self):
        def forbidden(*args, **kwargs): raise AssertionError('forbidden effect')
        names = ('obtain', 'complete', 'reconcile', 'publish', 'measure')
        with patch.object(r, 'retain_original_envelope', forbidden):
            with patch.object(a, 'acquire_original_permit', forbidden):
                with ExitStack() as stack:
                    for name in names: stack.enter_context(patch.object(s.RejectingCapabilities, name, forbidden))
                    for name in ('associate_candidate', 'publish_candidate', 'complete_original', 'query_completion'):
                        stack.enter_context(patch.object(s.RejectingNormalCapabilities, name, forbidden))
                    self.assert_state(q.QualificationState.QUALIFIED)

    def test_complete_source_effect_boundary(self):
        text = (ROOT / 'services/api/infrastructure/fixture_lease_admission_qualification.py').read_text()
        tree = ast.parse(text)
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))
        imports = [(node.level, node.module) for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
        self.assertEqual(imports, [(0, 'dataclasses'), (0, 'enum'), (0, 'types'), (1, None)])
        forbidden = {'open', 'connect', 'transaction', 'execute', 'obtain', 'renew', 'cancel', 'consume',
            'complete', 'retain', 'publish', 'send', 'measure', 'now', 'sleep', 'getenv', 'eval', 'exec',
            'deepcopy', 'getattr', 'hasattr', 'repr', 'str', 'AdmissionCoverage', 'AdmissionEvidence'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ''
                self.assertNotIn(name, forbidden)
            if isinstance(node, ast.ExceptHandler) and node.type is not None:
                self.assertNotEqual(ast.unparse(node.type), 'Exception')


class Foreign:
    calls = []
    def __getattribute__(self, name): Foreign.calls.append('attribute'); raise AssertionError()
    def __eq__(self, other): Foreign.calls.append('equality'); raise AssertionError()
    def __hash__(self): Foreign.calls.append('hash'); raise AssertionError()
    def __iter__(self): Foreign.calls.append('iteration'); raise AssertionError()
    def __repr__(self): Foreign.calls.append('repr'); raise AssertionError()
    def __call__(self, *args): Foreign.calls.append('call'); raise AssertionError()


def response_case(name, change, state=q.QualificationState.REJECTED):
    def test(self):
        Foreign.calls = []
        self.value = change(self, self.response())
        self.assert_state(state)
        self.assertEqual(self.calls, 1)
        self.assertEqual(Foreign.calls, [])
    setattr(QualificationTests, 'test_response_' + name, test)


for field in ('continuity', 'single_flight', 'activation', 'host', 'fencing', 'predecessor',
              'provenance', 'process_domain', 'freshness'):
    for validity, state in ((INVALID, q.QualificationState.REJECTED), (UNKNOWN, q.QualificationState.UNRESOLVED)):
        response_case(field + '_' + validity.value, lambda t, v, f=field, x=validity: replace(v, **{f: x}), state)

for name, change, state in (
    ('boolean', lambda t, v: True, q.QualificationState.REJECTED),
    ('reference', lambda t, v: t.proof, q.QualificationState.REJECTED),
    ('bare_valid', lambda t, v: VALID, q.QualificationState.REJECTED),
    ('none', lambda t, v: None, q.QualificationState.REJECTED),
    ('foreign', lambda t, v: Foreign(), q.QualificationState.REJECTED),
    ('foreign_nested', lambda t, v: forged(v, model=Foreign()), q.QualificationState.REJECTED),
    ('authority', lambda t, v: replace(v, authority=t.proof), q.QualificationState.REJECTED),
    ('authorization_invalid', lambda t, v: replace(v, authorization=replace(v.authorization, validity=INVALID)), q.QualificationState.REJECTED),
    ('authorization_unknown', lambda t, v: replace(v, authorization=replace(v.authorization, validity=UNKNOWN)), q.QualificationState.UNRESOLVED),
    ('approval_invalid', lambda t, v: replace(v, approval=replace(v.approval, validity=INVALID)), q.QualificationState.REJECTED),
    ('approval_unknown', lambda t, v: replace(v, approval=replace(v.approval, validity=UNKNOWN)), q.QualificationState.UNRESOLVED),
    ('applicability_unknown', lambda t, v: replace(v, approval=replace(v.approval, applicability=s.ApprovalApplicability.UNKNOWN)), q.QualificationState.UNRESOLVED),
    ('applicability_substitution', lambda t, v: replace(v, approval=replace(v.approval, applicability=s.ApprovalApplicability.NOT_APPLICABLE)), q.QualificationState.REJECTED),
    ('authorization_deadline', lambda t, v: replace(v, authorization=replace(v.authorization, deadline=s.InclusiveDeadline(99))), q.QualificationState.REJECTED),
    ('approval_deadline', lambda t, v: replace(v, approval=replace(v.approval, deadline=s.InclusiveDeadline(99))), q.QualificationState.REJECTED),
    ('unsupported_model', lambda t, v: replace(v, model=replace(v.model, support=replace(v.model.support, model=t.proof))), q.QualificationState.REJECTED),
    ('unsupported_interpretation', lambda t, v: replace(v, model=replace(v.model, support=replace(v.model.support, interpretation=t.proof))), q.QualificationState.REJECTED),
    ('model_unknown', lambda t, v: replace(v, model=replace(v.model, applicability=UNKNOWN)), q.QualificationState.UNRESOLVED),
    ('model_sample', lambda t, v: replace(v, model=replace(v.model, sample=t.proof)), q.QualificationState.REJECTED),
    ('model_process', lambda t, v: replace(v, model=replace(v.model, process_id='other')), q.QualificationState.REJECTED),
    ('model_domain', lambda t, v: replace(v, model=replace(v.model, domain_id='other')), q.QualificationState.REJECTED),
    ('missing_process', lambda t, v: replace(v, model=replace(v.model, process_id=None)), q.QualificationState.UNRESOLVED),
    ('missing_domain', lambda t, v: replace(v, model=replace(v.model, domain_id=None)), q.QualificationState.UNRESOLVED),
    ('instantaneous_scope', lambda t, v: replace(v, model=replace(v.model, max_elapsed_ns=v.model.min_elapsed_ns)), q.QualificationState.REJECTED),
    ('scope_too_small', lambda t, v: replace(v, model=replace(v.model, max_elapsed_ns=0)), q.QualificationState.REJECTED),
    ('scope_enlarged', lambda t, v: replace(v, model=replace(v.model, max_elapsed_ns=v.time.profile.max_elapsed_ns + 1)), q.QualificationState.REJECTED),
    ('scope_not_observation', lambda t, v: replace(v, model=replace(v.model, min_elapsed_ns=0)), q.QualificationState.REJECTED),
    ('overflow', lambda t, v: forged(v, model=forged(v.model, max_elapsed_ns=1 << 63)), q.QualificationState.REJECTED),
    ('bool_scope', lambda t, v: forged(v, model=forged(v.model, max_elapsed_ns=True)), q.QualificationState.REJECTED),
    ('negative_scope', lambda t, v: forged(v, model=forged(v.model, min_elapsed_ns=-1)), q.QualificationState.REJECTED),
    ('float_scope', lambda t, v: forged(v, model=forged(v.model, max_elapsed_ns=1.0)), q.QualificationState.REJECTED),
    ('wrong_profile', lambda t, v: replace(v, time=replace(v.time, profile=replace(v.time.profile, profile=t.proof))), q.QualificationState.REJECTED),
    ('wrong_source', lambda t, v: replace(v, time=replace(v.time, sample=replace(v.time.sample, source='other'))), q.QualificationState.REJECTED),
    ('point_process', lambda t, v: replace(v, time=replace(v.time, point=replace(v.time.point, process_id='other'))), q.QualificationState.REJECTED),
    ('point_domain', lambda t, v: replace(v, time=replace(v.time, point=replace(v.time.point, domain_id='other'))), q.QualificationState.REJECTED),
    ('conventions', lambda t, v: forged(v, model=forged(v.model, support=forged(v.model.support, conventions='default'))), q.QualificationState.REJECTED),
): response_case(name, change, state)


def binding_case(name, path, value):
    def test(self):
        changed = q._copy(self.expected)
        set_path(changed, path, value)
        self.value = forged(self.response(), source=changed)
        self.assert_state(q.QualificationState.REJECTED)
        self.assertEqual(self.calls, 1)
    setattr(QualificationTests, 'test_binding_' + name, test)
    def source_test(self):
        set_path(self.source, path, value)
        self.assert_state(q.QualificationState.REJECTED)
        self.assertEqual(self.calls, 0)
    setattr(QualificationTests, 'test_source_' + name, source_test)


for name, path, value in (
    ('command', 'envelope.context.command_id', 'other'),
    ('bytes', 'envelope.canonical_command_bytes', b'other'),
    ('hash', 'envelope.context.payload_sha256', b'x' * 32),
    ('principal', 'envelope.principal', 'other'),
    ('permit', 'envelope.permit_reference.identity', 'other'),
    ('envelope', 'envelope.reference.identity', 'other'),
    ('activation', 'envelope.activation.activation_id', 'other'),
    ('host', 'envelope.activation.host_identity', 'other'),
    ('predecessor', 'envelope.predecessor.exact_bytes', b'other'),
    ('representation', 'envelope.predecessor.representation', 'other'),
    ('representation_authority', 'envelope.predecessor.representation_authority.identity', 'other'),
    ('fixed_utc', 'envelope.fixed_utc_us', 99),
    ('historical_fixing', 'envelope.fixing.sample.validation.identity', 'other'),
    ('index', 'confirmation.receipt.index.principal', 'other'),
): binding_case(name, path, value)


def exception_case(error, bounded, mutation=None):
    def test(self):
        self.error = error
        self.mutate = mutation
        if bounded:
            result = self.assert_state(q.QualificationState.REJECTED if mutation else q.QualificationState.UNRESOLVED)
            self.assertNotIn('sensitive', result.reason.value)
            self.assertEqual(result.source.envelope.fixed_utc_us, 10)
        else:
            with self.assertRaises(error): self.evaluate()
        self.assertEqual(self.calls, 1)
    setattr(QualificationTests, 'test_exception_' + error.__name__ + '_' + str(mutation), test)


for error in (s.CapabilityUnavailable, a.ExternalAvailabilityFailure, TimeoutError):
    for mutation in (None, 'request', 'caller'): exception_case(error, True, mutation)
for error in (AssertionError, RuntimeError, TypeError): exception_case(error, False)
for mutation in ('request', 'caller'):
    def mutation_test(self, where=mutation):
        self.mutate = where
        self.assert_state(q.QualificationState.REJECTED, q.QualificationReason.MUTATED)
        self.assertEqual(self.calls, 1)
    setattr(QualificationTests, 'test_mutation_' + mutation, mutation_test)


if __name__ == '__main__': unittest.main(verbosity=2)
