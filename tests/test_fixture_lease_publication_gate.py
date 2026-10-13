"""Synthetic offline prerequisite evidence; no provider or operational effects."""
import ast
import copy
from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
import importlib.util
from itertools import product
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixtures = runpy.run_path(str(ROOT / 'tests/test_fixture_lease_checkpoints.py'))
s, p, q = fixtures['s'], fixtures['p'], fixtures['q']
for name in ('fixture_lease_outcomes', 'fixture_lease_publication_gate'):
    spec = importlib.util.spec_from_file_location('_il4a_pure.' + name,
        ROOT / 'services/api/infrastructure' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
o = sys.modules['_il4a_pure.fixture_lease_outcomes']
g = sys.modules['_il4a_pure.fixture_lease_publication_gate']


def import_boundary(tree):
    expected = {(0, 'dataclasses', (('dataclass', None), ('fields', None))),
        (0, 'enum', (('StrEnum', None),)),
        (1, None, (('fixture_lease_protocol', 'p'),)),
        (1, None, (('fixture_lease_service', 's'),)),
        (1, None, (('fixture_lease_checkpoints', 'checkpoints'),)),
        (1, None, (('fixture_lease_outcomes', 'outcomes'),))}
    seen = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): return False
        if isinstance(node, ast.ImportFrom):
            seen.append((node.level, node.module, tuple((a.name, a.asname) for a in node.names)))
    return len(seen) == len(expected) and set(seen) == expected


class PublicationGateTests(unittest.TestCase):
    def setUp(self):
        f = fixtures['CheckpointsTests'](); f.setUp()
        material = f.material()
        env = material[0]
        self.ref = s.EvidenceReference('synthetic-qualified', b'f'*32)
        self.profile = s.QualifiedClockProfile(self.ref, 'synthetic', self.ref, 100000, 100, 10, 0)
        point = s.MonotonicPoint('process', 'domain', 0)
        sample = s.QualifiedSample(self.ref, 'synthetic', self.ref, env.time_qualification,
                                   s.UtcInterval(1, 1), point)
        error = s.QualifiedPropagationError(sample.sample, sample.profile, 0, 0, self.ref)
        fixing = s.RetainedTimeFixing(env.reference, env.context, env.activation, sample, self.profile, point, error)
        env = replace(env, fixing=fixing)
        material[0] = env
        candidate = q.construct_candidate(*material, keys=())
        local = g.LocalCompletionEvidence(candidate, o.LocalCommitState.CONFIRMED, s.EvidenceValidity.VALID,
            self.ref, material[1], material[2], material[3], material[4], material[5], (), False)
        retention = g.CandidateRetentionEvidence(candidate, candidate.operation, s.EvidenceValidity.VALID, self.ref)
        permit = s.CommandPermit(env.context, env.activation, 0, 100, env.permit_reference)
        authority = g.CurrentAuthorityEvidence(candidate, candidate.operation, permit, env.principal,
            env.activation, env.activation.host_identity, env.predecessor, p.STATE_2,
            env.predecessor.representation_authority, *([s.EvidenceValidity.VALID]*6),
            *([g.CurrentStatus.ELIGIBLE]*3), g.InitialOperationState.INITIAL, self.ref, point, sample.utc)
        time = g.CurrentTimeEvidence(candidate, s.EvidenceValidity.VALID, self.ref, sample, self.profile,
            point, error, sample.utc, None, s.TimingApplicability.REQUIRED, s.InclusiveDeadline(100),
            s.TimingApplicability.REQUIRED, s.StrictDeadline(100))
        self.inputs = g.GateInputs(candidate, local, retention, authority, time, None)

    def closed(self, inputs, reason=None):
        result = g.evaluate_publication_gate(inputs)
        self.assertIs(result.state, g.GateState.FAIL_CLOSED)
        if reason is not None: self.assertIs(result.reason, reason)
        self.no_permission(result)
        return result

    def no_permission(self, result):
        for field in ('publication_permitted', 'completion_permitted', 'ack_delivery_permitted',
                      'runtime_active_permitted', 'retry_permitted', 'fence_clearance_permitted'):
            self.assertIs(getattr(result, field), False)

    def changed(self, field, **changes):
        return replace(self.inputs, **{field: replace(getattr(self.inputs, field), **changes)})

    def forged_inputs(self, base=None, **changes):
        value=copy.copy(self.inputs if base is None else base)
        for field,changed in changes.items():object.__setattr__(value,field,changed)
        return value

    def test_exact_prerequisites(self):
        result = g.evaluate_publication_gate(self.inputs)
        self.assertIs(result.state, g.GateState.SATISFIED)
        self.assertIs(result.reason, g.GateReason.SATISFIED)
        self.no_permission(result)

    def test_no_publication_permission(self): self.no_permission(g.evaluate_publication_gate(self.inputs))
    def test_missing_inputs(self): self.closed(None, g.GateReason.MISSING)
    def test_missing_commit(self): self.closed(replace(self.inputs, local=None), g.GateReason.LOCAL_COMMIT)
    def test_unknown_commit(self): self.closed(self.changed('local', state=o.LocalCommitState.UNKNOWN))
    def test_not_committed(self): self.closed(self.changed('local', state=o.LocalCommitState.NOT_COMMITTED))
    def test_unqualified_commit(self): self.closed(self.changed('local', qualification=s.EvidenceValidity.UNKNOWN))
    def test_ack_does_not_prove_commit(self): self.closed(self.changed('local', state=o.LocalCommitState.UNKNOWN))
    def test_supplied_expiry_fact_is_strict_boolean(self):
        with self.assertRaises(s.TimeRejected):replace(self.inputs.local,definite_expiry=1)
        # Frozen event-order validation owns applicability, not the new gate.
        self.closed(self.changed('local',definite_expiry=True),g.GateReason.CANDIDATE)
    def test_expiry_completion_reuses_frozen_order(self):
        f=fixtures['CheckpointsTests']();f.setUp()
        material=f.directed_material(kind=fixtures['c'].Command.QUARANTINE)
        prior=material[0].predecessor.event_digest;events=[]
        for sequence,event_type in enumerate(p.event_order(fixtures['c'].Command.QUARANTINE,definite_expiry=True),4):
            event=replace(material[2][0],event_sequence=sequence,event_type=event_type,prior_digest=prior)
            events.append(event);prior=p.event_digest(event)
        ack=replace(p.decode_record(material[1].durable_ack_bytes,p.AckPayload),event_count=3,
            final_event_sequence=6,final_event_digest=prior)
        row=replace(material[1],durable_ack_bytes=p.ack_bytes(ack),transition_event_sequence=6)
        projection=replace(material[3],commands=(material[3].commands[0],row))
        env=material[0]
        fixing=replace(self.inputs.candidate.envelope.fixing,context=env.context)
        env=replace(env,fixing=fixing)
        head=q.CommittedHead(6,prior,p.state_digest(projection,material[4]))
        candidate=q.construct_candidate(env,row,tuple(events),projection,material[4],head,material[6],keys=(),definite_expiry=True)
        inputs=replace(self.inputs,candidate=candidate,
            local=replace(self.inputs.local,candidate=candidate,completion=row,events=tuple(events),
                          projection=projection,head=head,definite_expiry=True),
            retention=replace(self.inputs.retention,candidate=candidate),
            authority=replace(self.inputs.authority,candidate=candidate,
                              permit=replace(self.inputs.authority.permit,context=env.context)),
            time=replace(self.inputs.time,candidate=candidate))
        self.assertIs(g.evaluate_publication_gate(inputs).state,g.GateState.SATISFIED)
    def test_candidate_equality_without_retention(self): self.closed(replace(self.inputs, retention=None), g.GateReason.RETENTION)
    def test_unknown_retention(self): self.closed(self.changed('retention', qualification=s.EvidenceValidity.UNKNOWN))
    def test_unqualified_retention(self): self.closed(self.changed('retention', qualification=s.EvidenceValidity.INVALID))

    def test_candidate_bytes_substitution(self):
        raw=b'other'; candidate=replace(self.inputs.candidate, exact_bytes=raw, sha256=sha256(raw).digest())
        self.closed(replace(self.inputs, candidate=candidate), g.GateReason.CANDIDATE)

    def test_candidate_digest_substitution(self):
        forged=copy.copy(self.inputs.candidate);object.__setattr__(forged,'sha256',b'x'*32)
        with self.assertRaises(s.TimeRejected):replace(self.inputs,candidate=forged)
        self.closed(self.forged_inputs(candidate=forged),g.GateReason.MALFORMED)

    def test_original_operation_substitution(self):
        other=s.OriginalOperation(s.EvidenceReference('other',b'x'*32),s.OperationKind.CHECKPOINT_PUBLICATION)
        self.closed(self.changed('authority',operation=other))

    def test_command_substitution(self):
        context=replace(self.inputs.authority.permit.context,command_id='other')
        self.closed(self.changed('authority',permit=replace(self.inputs.authority.permit,context=context)))

    def test_principal_substitution(self): self.closed(self.changed('authority',principal='other'))
    def test_permit_identity_substitution(self):
        self.closed(self.changed('authority',permit=replace(self.inputs.authority.permit,evidence=s.EvidenceReference('other',b'x'*32))))
    def test_expired_permit(self):
        self.closed(self.changed('authority',permit=replace(self.inputs.authority.permit,valid_until_us=1)),g.GateReason.TIME)
    def test_valid_from_failure(self):
        self.closed(self.changed('authority',permit=replace(self.inputs.authority.permit,valid_from_us=2)),g.GateReason.TIME)
    def test_inclusive_equality(self):
        result=g.evaluate_publication_gate(self.changed('time',authorization_deadline=s.InclusiveDeadline(1)))
        self.assertIs(result.state,g.GateState.SATISFIED)
    def test_strict_equality(self): self.closed(self.changed('time',freshness_deadline=s.StrictDeadline(1)),g.GateReason.TIME)

    def interval_inputs(self, lower=1, upper=2):
        interval=s.UtcInterval(lower,upper);sample=replace(self.inputs.time.sample,utc=interval)
        env=self.inputs.candidate.envelope
        fixing=replace(env.fixing,sample=sample)
        env=replace(env,fixing_interval=interval,fixing=fixing)
        candidate=replace(self.inputs.candidate,envelope=env)
        time=replace(self.inputs.time,candidate=candidate,sample=sample,covered_interval=interval)
        authority=replace(self.inputs.authority,candidate=candidate,interval=interval)
        return replace(self.inputs,candidate=candidate,time=time,authority=authority,
            local=replace(self.inputs.local,candidate=candidate),
            retention=replace(self.inputs.retention,candidate=candidate))

    def test_overlap_authorization(self):
        inputs=self.interval_inputs()
        self.closed(replace(inputs,time=replace(inputs.time,authorization_deadline=s.InclusiveDeadline(1))),g.GateReason.TIME)
    def test_overlap_strict_permit(self):
        inputs=self.interval_inputs()
        self.closed(replace(inputs,authority=replace(inputs.authority,permit=replace(inputs.authority.permit,valid_until_us=2))),g.GateReason.TIME)
    def test_profile_mismatch(self): self.closed(self.changed('time',profile=replace(self.profile,profile=s.EvidenceReference('other',b'x'*32))))
    def test_domain_mismatch(self): self.closed(self.changed('time',point=replace(self.inputs.time.point,domain_id='other')))
    def test_restart_mismatch(self): self.closed(self.changed('time',point=replace(self.inputs.time.point,process_id='other')))
    def test_coverage_gap(self): self.closed(self.changed('time',covered_interval=s.UtcInterval(2,2)))
    def test_unqualified_time(self): self.closed(self.changed('time',qualification=s.EvidenceValidity.UNKNOWN))
    def test_missing_time(self): self.closed(replace(self.inputs,time=None))
    def test_unknown_timing(self): self.closed(self.changed('time',authorization_timing=s.TimingApplicability.UNKNOWN,authorization_deadline=None))

    def refreshed(self, utc=2):
        old=self.inputs.time;point=replace(old.point,ticks_ns=1000)
        sample=replace(old.sample,sample=s.EvidenceReference('refresh',b'r'*32),validation=self.ref,
                       anchor=point,utc=s.UtcInterval(utc,utc))
        error=s.QualifiedPropagationError(sample.sample,sample.profile,0,0,self.ref)
        old_error=replace(old.propagation,elapsed_ns=1000)
        time=replace(old,sample=sample,point=point,propagation=error,covered_interval=sample.utc,fixing_to_refresh=old_error)
        return replace(self.inputs,time=time,authority=replace(self.inputs.authority,point=point,interval=sample.utc))

    def test_refresh_preserves_utc_and_candidate(self):
        inputs=self.refreshed();result=g.evaluate_publication_gate(inputs)
        self.assertIs(result.state,g.GateState.SATISFIED)
        self.assertEqual(inputs.candidate,self.inputs.candidate)
        self.assertEqual(inputs.candidate.fixed_utc_us,1)
        self.assertNotEqual(inputs.time.sample.validation,inputs.candidate.envelope.time_qualification)
    def test_inconsistent_refresh(self): self.closed(self.refreshed(50),g.GateReason.TIME)
    def test_refresh_cannot_rewrite_fixed_utc(self):
        forged=copy.copy(self.inputs.candidate);object.__setattr__(forged,'fixed_utc_us',2)
        self.closed(self.forged_inputs(self.refreshed(),candidate=forged))
    def test_host_substitution(self): self.closed(self.changed('authority',host='foreign'))
    def test_unapproved_host(self): self.closed(self.changed('authority',host_status=g.CurrentStatus.INELIGIBLE))
    def test_stale_host(self): self.closed(self.changed('authority',host_validity=s.EvidenceValidity.UNKNOWN))
    def test_activation_substitution(self): self.closed(self.changed('authority',activation=replace(self.inputs.authority.activation,activation_id='foreign')))
    def test_generation_substitution(self): self.closed(self.changed('authority',activation=replace(self.inputs.authority.activation,generation=2)))
    def test_superseded_activation(self): self.closed(self.changed('authority',activation_status=g.CurrentStatus.INELIGIBLE))
    def test_stale_activation(self): self.closed(self.changed('authority',activation_validity=s.EvidenceValidity.UNKNOWN))
    def test_predecessor_substitution(self): self.closed(self.changed('authority',predecessor=replace(self.inputs.authority.predecessor,revision=2)))
    def test_representation_id_substitution(self): self.closed(self.changed('authority',representation='other'))
    def test_representation_authority_substitution(self): self.closed(self.changed('authority',representation_authority=replace(self.inputs.authority.representation_authority,identity='other')))
    def test_representation_digest_substitution(self): self.closed(self.changed('authority',representation_authority=replace(self.inputs.authority.representation_authority,sha256=b'x'*32)))
    def test_unresolved_fencing(self): self.closed(self.changed('authority',fencing_validity=s.EvidenceValidity.UNKNOWN))
    def test_recovery_only(self): self.closed(self.changed('authority',fencing_status=g.CurrentStatus.INELIGIBLE))
    def test_attempted_operation(self): self.closed(self.changed('authority',initial_operation=g.InitialOperationState.ATTEMPTED))
    def test_unknown_operation(self): self.closed(self.changed('authority',initial_operation=g.InitialOperationState.UNKNOWN))

    def prior(self,outcome):
        result=s.PublicationResult(outcome,self.inputs.candidate,None if outcome is s.ExternalOutcome.UNKNOWN else self.ref)
        return o.publication_disposition(self.inputs.candidate,result,local_commit=o.LocalCommitState.CONFIRMED,
                                         qualification=s.EvidenceValidity.VALID)
    def test_prior_unknown(self): self.closed(replace(self.inputs,prior=self.prior(s.ExternalOutcome.UNKNOWN)),g.GateReason.HISTORY)
    def test_prior_rejection_not_retry(self): self.closed(replace(self.inputs,prior=self.prior(s.ExternalOutcome.DEFINITELY_REJECTED)),g.GateReason.HISTORY)
    def test_same_lineage_confirmed_descriptive_only(self):
        prior=self.prior(s.ExternalOutcome.CONFIRMED)
        result=self.closed(replace(self.inputs,prior=prior),g.GateReason.HISTORY)
        self.assertIs(result.inputs.prior,prior)
    def test_foreign_history(self):
        prior=self.prior(s.ExternalOutcome.UNKNOWN);forged=copy.copy(prior)
        object.__setattr__(forged,'candidate',replace(prior.candidate,envelope=replace(prior.candidate.envelope,principal='other')))
        with self.assertRaises(s.TimeRejected):replace(self.inputs,prior=forged)
        self.closed(self.forged_inputs(prior=forged))
    def test_well_formed_foreign_history_reaches_lineage_check(self):
        env=replace(self.inputs.candidate.envelope,principal='foreign')
        foreign=replace(self.inputs.candidate,envelope=env)
        observed=s.PublicationResult(s.ExternalOutcome.UNKNOWN,foreign,None)
        prior=o.publication_disposition(foreign,observed,local_commit=o.LocalCommitState.CONFIRMED)
        self.closed(replace(self.inputs,prior=prior),g.GateReason.HISTORY)
    def test_completion_recovery_history_blocks_initial_progression(self):
        publication=s.PublicationResult(s.ExternalOutcome.CONFIRMED,self.inputs.candidate,self.ref)
        operation=s.OriginalOperation(self.inputs.candidate.operation.permit,s.OperationKind.PERMIT_COMPLETION)
        completion=s.CompletionResult(s.ExternalOutcome.UNKNOWN,operation,publication,None)
        prior=o.completion_disposition(self.inputs.candidate,publication,completion,
            local_commit=o.LocalCommitState.CONFIRMED,publication_qualification=s.EvidenceValidity.VALID)
        self.closed(replace(self.inputs,prior=prior),g.GateReason.HISTORY)
    def test_malformed_retention_revalidated(self):
        forged=copy.copy(self.inputs.retention);object.__setattr__(forged,'qualification',True)
        with self.assertRaises(s.TimeRejected):replace(self.inputs,retention=forged)
        self.closed(self.forged_inputs(retention=forged),g.GateReason.MALFORMED)
    def test_direct_result_contradictions(self):
        good=g.evaluate_publication_gate(self.inputs);bad=self.closed(replace(self.inputs,retention=None))
        for result in (good,bad):
            with self.assertRaises(s.TimeRejected):replace(result,state=g.GateState.FAIL_CLOSED if result.state is g.GateState.SATISFIED else g.GateState.SATISFIED)
            with self.assertRaises(s.TimeRejected):replace(result,reason=g.GateReason.TIME)
    def test_mutated_input_reuse(self):
        forged=copy.copy(self.inputs.local);object.__setattr__(forged,'state','CONFIRMED')
        with self.assertRaises(s.TimeRejected):replace(self.inputs,local=forged)
        self.closed(self.forged_inputs(local=forged),g.GateReason.MALFORMED)
    def test_bool_integer_revalidation(self):
        for field,value in (('generation',True),):
            activation=copy.copy(self.inputs.authority.activation);object.__setattr__(activation,field,value)
            with self.assertRaises(s.TimeRejected):self.changed('authority',activation=activation)
            authority=copy.copy(self.inputs.authority);object.__setattr__(authority,'activation',activation)
            self.closed(self.forged_inputs(authority=authority),g.GateReason.MALFORMED)
        with self.assertRaises(s.TimeRejected):s.MonotonicPoint('p','d',True)
    def test_immutable_values(self):
        for value in (self.inputs,self.inputs.local,self.inputs.retention,self.inputs.authority,self.inputs.time,g.evaluate_publication_gate(self.inputs)):
            with self.assertRaises(FrozenInstanceError):value.extra=True
    def test_no_arbitrary_diagnostics(self):
        result=g.evaluate_publication_gate(self.inputs)
        self.assertLess(len(repr(result)),128);self.assertNotIn('synthetic',repr(result))
        self.assertTrue(all(len(x.value)<=32 for x in g.GateReason))
    def test_frozen_helpers_exercised(self):
        with (patch.object(q,'validate_candidate',wraps=q.validate_candidate) as candidate,
              patch.object(s,'verify_candidate_association',wraps=s.verify_candidate_association) as association,
              patch.object(s,'evaluate_time',wraps=s.evaluate_time) as timing):
            g.evaluate_publication_gate(self.inputs)
            self.assertGreater(candidate.call_count,0);self.assertGreater(association.call_count,0);self.assertGreater(timing.call_count,0)
        # Preserve the actual bound constructor when exercising history separately.
        with patch.object(s,'verify_publication_result',wraps=s.verify_publication_result) as binding:
            self.closed(replace(self.inputs,prior=self.prior(s.ExternalOutcome.UNKNOWN)))
            self.assertGreater(binding.call_count,0)
    def test_malformed_payload_is_not_retained(self):
        forged=self.forged_inputs(retention={'unbounded':'x'*10000})
        result=self.closed(forged,g.GateReason.MALFORMED)
        self.assertIsNone(result.inputs)
        with self.assertRaises(s.TimeRejected):g.GateResult(forged,g.GateState.FAIL_CLOSED,g.GateReason.MALFORMED)
    def test_foreign_dataclass_validator_is_never_invoked(self):
        from dataclasses import dataclass
        calls=[]
        @dataclass(frozen=True)
        class Foreign:
            def __getattribute__(self,name):
                calls.append(name)
                raise AssertionError('untrusted attribute callback')
            def __post_init__(self):
                calls.append('post_init')
                raise AssertionError('untrusted callback')
        Foreign.__module__=p.__name__
        foreign=object.__new__(Foreign)
        projection=replace(self.inputs.local.projection,metadata=foreign)
        local=copy.copy(self.inputs.local);object.__setattr__(local,'projection',projection)
        self.closed(self.forged_inputs(local=local),g.GateReason.MALFORMED)
        self.assertEqual(calls,[])

    def hostile_metadata(self,foreign):
        projection=replace(self.inputs.local.projection,metadata=foreign)
        local=copy.copy(self.inputs.local);object.__setattr__(local,'projection',projection)
        return self.forged_inputs(local=local)

    def assert_no_foreign_callback(self,method,raising=False):
        calls=[]
        def callback(instance,*args):
            calls.append(method)
            if raising:raise AssertionError('foreign callback executed')
            if method=='__getattribute__':return object.__getattribute__(instance,*args)
            if method=='__iter__':return iter(())
            if method=='__eq__':return False
            if method=='__hash__':return 0
            return 'foreign'
        foreign_type=type('Foreign',(),{method:callback})
        foreign=object.__new__(foreign_type)
        result=self.closed(self.hostile_metadata(foreign),g.GateReason.MALFORMED)
        self.assertIsNone(result.inputs)
        self.assertEqual(calls,[])

    def test_foreign_getattribute_records_zero_calls(self):self.assert_no_foreign_callback('__getattribute__')
    def test_foreign_getattribute_assertion_never_escapes(self):self.assert_no_foreign_callback('__getattribute__',True)
    def test_foreign_getattr_zero_calls(self):self.assert_no_foreign_callback('__getattr__',True)
    def test_foreign_iter_zero_calls(self):self.assert_no_foreign_callback('__iter__',True)
    def test_foreign_equality_zero_calls(self):self.assert_no_foreign_callback('__eq__',True)
    def test_foreign_hash_zero_calls(self):self.assert_no_foreign_callback('__hash__',True)
    def test_foreign_repr_zero_calls(self):self.assert_no_foreign_callback('__repr__',True)
    def test_foreign_str_zero_calls(self):self.assert_no_foreign_callback('__str__',True)

    def test_foreign_primitive_subclasses_reject_before_callbacks(self):
        for base,arg in ((str,'foreign'),(bytes,b'foreign'),(int,1),(tuple,())):
            calls=[]
            def access(instance,name):
                calls.append(name);raise AssertionError('foreign subclass callback')
            subtype=type('ForeignPrimitive',(base,),{'__getattribute__':access})
            foreign=subtype(arg)
            self.closed(self.hostile_metadata(foreign),g.GateReason.MALFORMED)
            self.assertEqual(calls,[])

    def test_foreign_frozen_value_subclass_rejects_before_callbacks(self):
        calls=[]
        class ForeignInterval(s.UtcInterval):
            def __getattribute__(self,name):
                calls.append(name);raise AssertionError('foreign value callback')
        foreign=object.__new__(ForeignInterval)
        self.closed(self.hostile_metadata(foreign),g.GateReason.MALFORMED)
        self.assertEqual(calls,[])

    def test_foreign_enum_rejected_before_callbacks(self):
        from enum import StrEnum
        calls=[]
        class ForeignEnum(StrEnum):
            ITEM='foreign'
            def __getattribute__(self,name):
                calls.append(name)
                return object.__getattribute__(self,name)
        foreign=ForeignEnum.ITEM
        calls.clear()
        self.closed(self.hostile_metadata(foreign),g.GateReason.MALFORMED)
        self.assertEqual(calls,[])

    def test_foreign_metaclass_equality_hash_and_attributes_never_called(self):
        calls=[]
        class ForeignMeta(type):
            def __getattribute__(cls,name):
                calls.append('class_attribute');raise AssertionError('metaclass attribute')
            def __eq__(cls,other):
                calls.append('class_equality');raise AssertionError('metaclass equality')
            def __hash__(cls):
                calls.append('class_hash');raise AssertionError('metaclass hash')
        class Foreign(metaclass=ForeignMeta):pass
        foreign=object.__new__(Foreign)
        self.closed(self.hostile_metadata(foreign),g.GateReason.MALFORMED)
        self.assertEqual(calls,[])

    def test_foreign_root_rejected_without_callbacks(self):
        calls=[]
        class Foreign:
            def __getattribute__(self,name):
                calls.append(name);raise AssertionError('root callback')
        self.closed(object.__new__(Foreign),g.GateReason.MALFORMED)
        self.assertEqual(calls,[])

    def test_retention_constructor_rejects_foreign_before_equality(self):
        calls=[]
        class Foreign:
            def __getattribute__(self,name):
                calls.append(name);raise AssertionError('attribute callback')
            def __eq__(self,other):
                calls.append('equality');raise AssertionError('equality callback')
        operation=copy.copy(self.inputs.retention.operation)
        object.__setattr__(operation,'permit',object.__new__(Foreign))
        with self.assertRaises(s.TimeRejected):replace(self.inputs.retention,operation=operation)
        self.assertEqual(calls,[])

    def test_closed_revalidator_has_no_generic_instance_classifier(self):
        tree=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_publication_gate.py').read_text())
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name):
                self.assertNotIn(node.func.id,('isinstance','is_dataclass','hasattr'))
    def test_result_invariant_matrix(self):
        for inputs in (self.inputs,None,replace(self.inputs,local=None),replace(self.inputs,retention=None)):
            expected=g.evaluate_publication_gate(inputs)
            for state,reason in product(g.GateState,g.GateReason):
                if state is expected.state and reason is expected.reason:
                    self.assertEqual(g.GateResult(inputs,state,reason),expected)
                elif inputs is None and state is g.GateState.FAIL_CLOSED and reason is g.GateReason.MALFORMED:
                    self.no_permission(g.GateResult(inputs,state,reason))
                else:
                    with self.assertRaises(s.TimeRejected):g.GateResult(inputs,state,reason)
    def test_no_external_io_or_clock(self):
        with (patch('builtins.open',side_effect=AssertionError('filesystem')),
              patch.object(Path,'read_bytes',side_effect=AssertionError('filesystem')),
              patch.object(Path,'write_bytes',side_effect=AssertionError('filesystem')),
              patch('time.time',side_effect=AssertionError('clock')),
              patch('time.monotonic',side_effect=AssertionError('clock')),
              patch('os.getenv',side_effect=AssertionError('environment'))):
            self.assertIs(g.evaluate_publication_gate(self.inputs).state,g.GateState.SATISFIED)
    def test_no_capability_invocation(self):
        names=('resolve_predecessor','resolve_envelope','associate_candidate','publish_candidate',
               'query_publication','complete_original','query_completion')
        from contextlib import ExitStack
        with ExitStack() as stack:
            for name in names:stack.enter_context(patch.object(s.RejectingNormalCapabilities,name,side_effect=AssertionError('effect')))
            self.assertIs(g.evaluate_publication_gate(self.inputs).state,g.GateState.SATISFIED)
    def test_purity_import_boundary(self):
        tree=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_publication_gate.py').read_text())
        self.assertTrue(import_boundary(tree))
        forbidden={'open','connect','execute','getenv','now','time','sleep','run','associate_candidate',
                   'publish_candidate','query_publication','complete_original','query_completion','obtain','measure'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                self.assertNotIn(node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr',''),forbidden)
    def test_prohibited_import_probes(self):
        for module in ('fixture_lease_commands','fixture_lease_store','provider','sqlite3','requests','subprocess','os','runtime_configuration'):
            self.assertFalse(import_boundary(ast.parse('from . import '+module)))
        self.assertFalse(import_boundary(ast.parse('from .orchestration_service import fixture_lease_service')))
    def test_authority_validity_matrix(self):
        for field in ('permit_validity','activation_validity','host_validity','fencing_validity','predecessor_validity','representation_validity'):
            for value in (s.EvidenceValidity.INVALID,s.EvidenceValidity.UNKNOWN):self.closed(self.changed('authority',**{field:value}))
    def test_local_retention_matrix(self):
        for state,local_q,retention_q in product(o.LocalCommitState,s.EvidenceValidity,s.EvidenceValidity):
            inputs=self.changed('local',state=state,qualification=local_q)
            inputs=replace(inputs,retention=replace(inputs.retention,qualification=retention_q))
            result=g.evaluate_publication_gate(inputs)
            self.assertEqual(result.state is g.GateState.SATISFIED,state is o.LocalCommitState.CONFIRMED and local_q is s.EvidenceValidity.VALID and retention_q is s.EvidenceValidity.VALID)
            self.no_permission(result)


if __name__ == '__main__':unittest.main(verbosity=2)
