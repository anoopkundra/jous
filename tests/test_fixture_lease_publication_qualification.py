"""Increment E synthetic/offline tests; no operational provider or register."""
import ast
import copy
from dataclasses import replace
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixture = runpy.run_path(str(ROOT / 'tests/test_fixture_lease_candidate_retention.py'))
d, c, s, cp = fixture['d'], fixture['c'], fixture['s'], fixture['cp']
name = c.__package__ + '.fixture_lease_publication_qualification'
spec = importlib.util.spec_from_file_location(name,
    ROOT / 'services/api/infrastructure/fixture_lease_publication_qualification.py')
e = importlib.util.module_from_spec(spec)
sys.modules[name] = e
spec.loader.exec_module(e)
g, o, p = e.g, e.o, e.p


def current_preparation():
    """Real synthetic B/C evaluation with a permit covering later publication.

    Unlike D's expiry-at-T2 fixture, the positive E fixture has independently
    supplied current coverage AFTER its historical T2, not a reused T1 point.
    """
    case=fixture['fixtures']['fixture']['QualifiedWriterTests']('test_valid_consumption_windows_expire_before_t2')
    case.setUp()
    try:
        case.rewrite_qualification(s.CommandPermit,'valid_until_us',20)
        completed=case.run_b()
        def rows(source,target):
            return tuple(p.decode_record(p.encode_record(c.commands._adapt(v,target)),target)
                         for v in case.store.read_rows(source))
        completions=rows(c.store.CommandRow,p.CommandRow)
        completion=next(v for v in completions if v.command_id==case.command.command_id)
        events=tuple(c.commands._event(v) for v in case.store.read_rows(c.store.EventRow)
                     if v.command_id==case.command.command_id)
        projection=p.StateProjection(rows(c.store.MetadataRow,p.MetadataRow)[0],
            rows(c.store.ReservationRow,p.ReservationRow),rows(c.store.ClaimRow,p.ClaimRow),completions)
        keys=tuple(v.canonical_key for v in projection.claims
                   if v.reservation_id==completed.completed.reservation.reservation_id)
        snapshot=c.CommittedSnapshot(completion,events,projection,case.context,keys,False)
    finally:
        case.tearDown()
    authority=s.EvidenceReference('C-independent-authority',b'a'*32)
    implementation=s.EvidenceReference('C-independent-implementation',b'i'*32)
    proof=s.EvidenceReference('C-qualified-current-fixture-transition',b'c'*32)
    def verify(request):
        return c.PreparationQualification(request,authority,implementation,s.EvidenceValidity.VALID,proof)
    return c.CandidatePreparer(c.TrustedPreparationVerifier(authority,implementation,verify)).prepare_candidate(completed,snapshot)


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        case = fixture['RetentionTests']('test_first_success_exact_graph_and_order')
        case.template = current_preparation()
        case.setUp()
        cls.template = case.run_d()
        if cls.template.state is not d.RetentionState.RETAINED:
            raise AssertionError('genuine synthetic D did not retain')

    def setUp(self):
        self.source = e._copy(self.template)
        self.authority = e._copy(d._namespace(self.source.retained.source))
        self.implementation = s.EvidenceReference('E-local-qualification', b'i'*32)
        self.reference = s.EvidenceReference('E-independent-complete-assessment', b'e'*32)
        self.calls = []
        self.request = self.response = None
        self.transform = self.hook = None
        self.validity = self.provenance = s.EvidenceValidity.VALID
        self.adapter = e.TrustedPublicationQualificationAdapter(self.authority, self.implementation, self.qualify)
        self.evaluator = e.PublicationQualifier(self.adapter)

    def inputs(self, source):
        retained = source.retained
        prepared = retained.source.prepared
        candidate, snapshot = prepared.candidate, prepared.request.snapshot
        completed = prepared.request.completion.completed
        env = candidate.envelope
        t1 = prepared.request.completion.t1
        fixing = env.fixing
        point=replace(t1.point,ticks_ns=fixing.sample.anchor.ticks_ns+5000)
        propagation=replace(t1.propagation,elapsed_ns=5000)
        interval = s.evaluate_time(fixing.sample, fixing.profile, point, propagation).interval
        local = g.LocalCompletionEvidence(candidate, o.LocalCommitState.CONFIRMED,
            s.EvidenceValidity.VALID, self.reference, snapshot.completion, snapshot.events,
            snapshot.projection, snapshot.context,
            cp.CommittedHead(completed.event_sequence, completed.event_digest, completed.state_digest),
            snapshot.keys, snapshot.definite_expiry)
        authority = g.CurrentAuthorityEvidence(candidate, candidate.operation, completed.permit,
            env.principal, env.activation, env.activation.host_identity, env.predecessor,
            env.predecessor.representation, env.predecessor.representation_authority,
            *([s.EvidenceValidity.VALID]*6), *([g.CurrentStatus.ELIGIBLE]*3),
            g.InitialOperationState.INITIAL, self.reference, point, interval)
        time = g.CurrentTimeEvidence(candidate, s.EvidenceValidity.VALID, self.reference,
            fixing.sample, fixing.profile, point, propagation, interval, None,
            s.TimingApplicability.NOT_APPLICABLE, None, s.TimingApplicability.NOT_APPLICABLE, None)
        return g.GateInputs(candidate, local, retained.retention, authority, time, None)

    def qualify(self, request):
        self.calls.append('qualify')
        self.request = request
        if self.hook:
            self.hook(request)
        # This is a separately trusted synthetic issuance/current assessment,
        # not production authentication or inference from value equality.
        inputs = self.inputs(request.source) if self.provenance is s.EvidenceValidity.VALID else None
        response = e.PublicationAssessment(e._copy(request), self.authority, self.implementation,
            self.validity, self.reference, self.provenance, inputs)
        self.response = response
        return response if self.transform is None else self.transform(response)

    def run_e(self):
        return self.evaluator.qualify_publication(self.source)

    def check(self, result, state, reason, calls=1, gate=None):
        self.assertIs(result.state, state)
        self.assertIs(result.reason, reason)
        self.assertEqual(len(self.calls), calls)
        self.assertEqual(result.qualification_attempted, bool(calls))
        if gate is not None:
            self.assertEqual(result.gate_evaluated, gate)
        self.assertEqual(sum(v is not None for v in (result.qualified, result.rejected, result.unresolved)), 1)
        payload = next(v for v in (result.qualified, result.rejected, result.unresolved) if v is not None)
        for permission in e._PERMISSIONS:
            self.assertIs(getattr(result, permission), False)
        if state is e.S.UNRESOLVED:
            self.assertTrue(payload.reconciliation_required)
        return payload

    def change(self, target, **changes):
        self.transform = lambda a: replace(a, inputs=replace(a.inputs,
            **{target: replace(getattr(a.inputs, target), **changes)}))

    def test_genuine_path_canonical_gate_and_exact_detachment(self):
        gate = self.evaluator._gate
        calls = []
        def counted(inputs):
            calls.append(inputs)
            return gate(inputs)
        with patch.object(g, 'evaluate_publication_gate', counted):
            self.evaluator = e.PublicationQualifier(self.adapter)
            result = self.run_e()
        payload = self.check(result, e.S.QUALIFIED, e.R.QUALIFIED, gate=True)
        self.assertEqual(len(calls), 1)
        self.assertIs(payload.gate.state, g.GateState.SATISFIED)
        self.assertFalse(payload.reconciliation_required)
        self.assertEqual(payload.source, self.source)
        self.assertIsNot(payload.source, self.source)
        self.assertIsNot(payload.assessment, self.response)
        self.assertIsNot(payload.gate.inputs, calls[0])
        candidate = payload.source.retained.source.prepared.candidate
        self.assertEqual(candidate, payload.gate.inputs.candidate)
        self.assertEqual(candidate.fixed_utc_us, self.source.retained.source.prepared.candidate.fixed_utc_us)
        self.assertIs(payload.source.retained.source.prepared.request.completion.local.storage_result,
                      c.store.LocalStorageResult.LOCAL_STORAGE_COMMIT_CONFIRMED)
        self.assertGreater(payload.gate.inputs.time.point.ticks_ns,
                           payload.source.retained.source.prepared.request.completion.t2.point.ticks_ns)

    def test_result_and_marker_are_closed(self):
        result = self.run_e()
        marker = result.qualified.assessment.request.evaluation
        for fn in (lambda:e.PublicationQualificationResult(), lambda:replace(result),
                   lambda:copy.copy(result), lambda:copy.deepcopy(result), lambda:bool(result),
                   lambda:e._EvaluationBinding(), lambda:copy.copy(marker), lambda:copy.deepcopy(marker)):
            with self.assertRaises(TypeError):fn()
        self.assertIs(e._copy(marker), marker)

    def test_fresh_evaluation_rejects_replayed_assessment(self):
        first = self.run_e()
        old = self.response
        self.calls.clear()
        self.transform = lambda value: old
        result = self.run_e()
        self.check(result,e.S.UNRESOLVED,e.R.ASSESSMENT_BINDING_MISMATCH,gate=False)
        self.assertIsNot(self.request.evaluation,first.qualified.assessment.request.evaluation)

    def test_forged_equal_root_requires_independent_negative_provenance(self):
        self.source = e._copy(self.source)
        self.provenance = s.EvidenceValidity.INVALID
        self.check(self.run_e(),e.S.REJECTED,e.R.UNQUALIFIED_D_PROVENANCE,gate=False)

    def test_unknown_provenance_is_not_negative(self):
        self.provenance = s.EvidenceValidity.UNKNOWN
        self.check(self.run_e(),e.S.UNRESOLVED,e.R.D_PROVENANCE_UNKNOWN,gate=False)

    def test_constructor_exact_shape(self):
        class Sub(e.TrustedPublicationQualificationAdapter):pass
        for value in (None,self.qualify,Hostile(),Sub(self.authority,self.implementation,self.qualify),
                replace(self.adapter,authority=None),replace(self.adapter,implementation=object.__new__(s.EvidenceReference)),
                replace(self.adapter,qualify=None),object.__new__(e.TrustedPublicationQualificationAdapter)):
            with self.assertRaises(TypeError):e.PublicationQualifier(value)

    def test_no_request_dependency_override(self):
        with self.assertRaises(TypeError):self.evaluator.qualify_publication(self.source,self.adapter)

    def test_upstream_nonretained(self):
        for state, reason, expected in ((c.PreparationState.REJECTED,c.PreparationReason.NOT_NEW_TRANSITION,e.S.REJECTED),
                (c.PreparationState.UNRESOLVED,c.PreparationReason.UPSTREAM_UNRESOLVED,e.S.UNRESOLVED)):
            self.source=d.CandidateRetainer(fixture_adapter(self)).retain_candidate(c._result(state,reason))
            self.check(self.run_e(),expected,e.R.NOT_RETAINED if expected is e.S.REJECTED else e.R.UPSTREAM_UNRESOLVED,0,False)

    def test_unknown_authority_precedes_negative_component(self):
        self.change('authority',permit_validity=s.EvidenceValidity.INVALID,host_validity=s.EvidenceValidity.UNKNOWN)
        self.check(self.run_e(),e.S.UNRESOLVED,e.R.CURRENT_AUTHORITY_UNKNOWN)

    def test_known_authority_negative_is_authenticated(self):
        self.change('authority',permit_validity=s.EvidenceValidity.INVALID)
        self.check(self.run_e(),e.S.REJECTED,e.R.CURRENT_AUTHORITY_INELIGIBLE)

    def test_original_request_mutation_with_detached_response(self):
        def transform(a):
            self.assertIsNot(a.request,self.request)
            self.assertIsNot(a.request.source,self.request.source)
            object.__setattr__(self.request.source.retained.source.prepared.candidate,'event_sequence',999)
            return a
        self.transform=transform
        self.check(self.run_e(),e.S.UNRESOLVED,e.R.REQUEST_INSTABILITY,gate=False)

    def test_response_mutation_during_capture(self):
        project=e._project
        def capture(value):
            projected=project(value)
            if type(value) is e.PublicationAssessment and value is self.response:
                object.__setattr__(value.reference,'identity','changed-during-capture')
            return projected
        with patch.object(e,'_project',capture):
            self.check(self.run_e(),e.S.UNRESOLVED,e.R.RESPONSE_INSTABILITY,gate=False)

    def test_gate_request_mutation_is_not_masked_by_detached_response(self):
        original=g.evaluate_publication_gate
        def gate(inputs):
            result=original(inputs)
            object.__setattr__(self.request.source.retained.source.prepared.candidate,'event_sequence',999)
            return result
        with patch.object(g,'evaluate_publication_gate',gate):
            self.evaluator=e.PublicationQualifier(self.adapter)
            self.check(self.run_e(),e.S.UNRESOLVED,e.R.REQUEST_INSTABILITY,gate=True)

    def test_post_return_aliases_cannot_mutate_issued_knowledge(self):
        result=self.run_e();before=e._project(result)
        object.__setattr__(self.source.retained.source.prepared.candidate,'event_sequence',999)
        object.__setattr__(self.request.source.retained.source.prepared.candidate,'event_sequence',998)
        object.__setattr__(self.response.inputs.candidate,'event_sequence',997)
        self.assertEqual(e._project(result),before)

    def test_shared_immutable_nodes_are_accepted(self):
        copied=e._copy((self.source,self.source))
        self.assertIs(copied[0],copied[1])
        self.check(self.run_e(),e.S.QUALIFIED,e.R.QUALIFIED)

    def test_no_effects_and_canonical_reconstruction_only(self):
        forbidden=('associate_candidate','publish_candidate','query_publication','complete_original','query_completion')
        original=cp.construct_candidate
        reconstructed=[]
        def counted(*args,**kwargs):
            value=original(*args,**kwargs);reconstructed.append(value);return value
        with (patch.object(cp,'construct_candidate',counted),
              patch.object(c.store.sqlite3,'connect',side_effect=AssertionError('SQLite')),
              patch.object(p,'state_bytes',side_effect=AssertionError('aggregate STATE'))):
            self.evaluator=e.PublicationQualifier(self.adapter)
            self.check(self.run_e(),e.S.QUALIFIED,e.R.QUALIFIED)
        self.assertGreater(len(reconstructed),0)
        tree=ast.parse((ROOT/'services/api/infrastructure/fixture_lease_publication_qualification.py').read_text())
        called=[v.func.attr if type(v.func) is ast.Attribute else v.func.id for v in ast.walk(tree)
                if type(v) is ast.Call and type(v.func) in (ast.Name,ast.Attribute)]
        self.assertEqual(called.count('_qualify'),1);self.assertEqual(called.count('_gate'),1)
        self.assertFalse(set(called)&set(forbidden+('construct_candidate','CandidatePreparer','CandidateRetainer',
            'connect','execute','open','sleep','time','monotonic','now','obtain','complete','deliver','recover')))

    def test_qualified_is_not_a_new_input_or_delayed_dispatch_token(self):
        qualified=self.run_e();self.calls.clear();self.source=qualified
        self.check(self.run_e(),e.S.REJECTED,e.R.INVALID_D_SOURCE,0,False)


def fixture_adapter(test):
    def verify(source):raise AssertionError('upstream result must not verify')
    return d.TrustedCandidateRetentionAdapter(test.authority,test.implementation,verify,verify,verify)


class Hostile:
    def __getattribute__(self,name):raise AssertionError('foreign attribute')
    def __eq__(self,value):raise AssertionError('foreign equality')
    def __hash__(self):raise AssertionError('foreign hashing')
    def __repr__(self):raise AssertionError('foreign repr')


def assessment_case(name, transform, state, reason, gate=None):
    def test(self):
        self.transform=lambda a:transform(self,a)
        self.check(self.run_e(),state,reason,gate=gate)
    setattr(PublicationTests,'test_assessment_'+name,test)


for _name,_transform,_reason in (
    ('foreign',lambda t,a:Hostile(),e.R.MALFORMED_ASSESSMENT),
    ('none',lambda t,a:None,e.R.MALFORMED_ASSESSMENT),
    ('invalid',lambda t,a:replace(a,validity=s.EvidenceValidity.INVALID),e.R.UNQUALIFIED_ASSESSMENT),
    ('unknown',lambda t,a:replace(a,validity=s.EvidenceValidity.UNKNOWN),e.R.UNQUALIFIED_ASSESSMENT),
    ('missing_inputs',lambda t,a:replace(a,inputs=None),e.R.MALFORMED_ASSESSMENT),
    ('negative_with_inputs',lambda t,a:replace(a,source_provenance=s.EvidenceValidity.INVALID),e.R.MALFORMED_ASSESSMENT),
    ('wrong_authority',lambda t,a:replace(a,authority=s.EvidenceReference('foreign',b'x'*32)),e.R.ASSESSMENT_BINDING_MISMATCH),
    ('wrong_implementation',lambda t,a:replace(a,implementation=s.EvidenceReference('foreign',b'x'*32)),e.R.ASSESSMENT_BINDING_MISMATCH),
    ('wrong_marker',lambda t,a:replace(a,request=replace(a.request,evaluation=object.__new__(e._EvaluationBinding))),e.R.ASSESSMENT_BINDING_MISMATCH),
    ('wrong_request',lambda t,a:replace(a,request=replace(a.request,source=d._issue(d.RetentionState.REJECTED,d.RetentionReason.INVALID_C_SOURCE))),e.R.ASSESSMENT_BINDING_MISMATCH),
):assessment_case(_name,_transform,e.S.UNRESOLVED,_reason,False)


def input_case(name,target,changes,state,reason):
    assessment_case(name,lambda t,a:replace(a,inputs=replace(a.inputs,
        **{target:None if changes is None else replace(getattr(a.inputs,target),**changes(t,a))})),state,reason)


for _field in ('permit_validity','activation_validity','host_validity','fencing_validity','representation_validity'):
    for _validity in (s.EvidenceValidity.INVALID,s.EvidenceValidity.UNKNOWN):
        input_case(_field+'_'+_validity,'authority',lambda t,a,f=_field,v=_validity:{f:v},
            e.S.REJECTED if _validity is s.EvidenceValidity.INVALID else e.S.UNRESOLVED,
            e.R.CURRENT_AUTHORITY_INELIGIBLE if _validity is s.EvidenceValidity.INVALID else e.R.CURRENT_AUTHORITY_UNKNOWN)
for _field in ('activation_status','host_status','fencing_status'):
    for _status in (g.CurrentStatus.INELIGIBLE,g.CurrentStatus.UNKNOWN):
        input_case(_field+'_'+_status,'authority',lambda t,a,f=_field,v=_status:{f:v},
            e.S.REJECTED if _status is g.CurrentStatus.INELIGIBLE else e.S.UNRESOLVED,
            e.R.CURRENT_AUTHORITY_INELIGIBLE if _status is g.CurrentStatus.INELIGIBLE else e.R.CURRENT_AUTHORITY_UNKNOWN)
for _validity in (s.EvidenceValidity.INVALID,s.EvidenceValidity.UNKNOWN):
    input_case('predecessor_'+_validity,'authority',lambda t,a,v=_validity:{'predecessor_validity':v},
        e.S.REJECTED if _validity is s.EvidenceValidity.INVALID else e.S.UNRESOLVED,
        e.R.PREDECESSOR_MISMATCH if _validity is s.EvidenceValidity.INVALID else e.R.PREDECESSOR_UNKNOWN)
for _history in (g.InitialOperationState.ATTEMPTED,g.InitialOperationState.UNKNOWN):
    input_case('history_'+_history,'authority',lambda t,a,v=_history:{'initial_operation':v},e.S.UNRESOLVED,
        e.R.PUBLICATION_HISTORY_NON_INITIAL if _history is g.InitialOperationState.ATTEMPTED else e.R.PUBLICATION_HISTORY_UNKNOWN)
for _target,_reason in (('local',e.R.HISTORICAL_EVIDENCE_CONTRADICTION),('retention',e.R.RETENTION_UNQUALIFIED),
        ('authority',e.R.CURRENT_AUTHORITY_UNKNOWN),('time',e.R.TIME_UNQUALIFIED)):
    input_case('missing_'+_target,_target,None,e.S.UNRESOLVED,_reason)
for _target,_field,_value,_reason in (
    ('local','qualification',s.EvidenceValidity.INVALID,e.R.HISTORICAL_EVIDENCE_CONTRADICTION),
    ('local','state',o.LocalCommitState.UNKNOWN,e.R.HISTORICAL_EVIDENCE_CONTRADICTION),
    ('retention','qualification',s.EvidenceValidity.UNKNOWN,e.R.RETENTION_UNQUALIFIED),
    ('time','qualification',s.EvidenceValidity.UNKNOWN,e.R.TIME_UNQUALIFIED),
    ('time','authorization_timing',s.TimingApplicability.UNKNOWN,e.R.TIME_UNQUALIFIED),
    ('time','freshness_timing',s.TimingApplicability.UNKNOWN,e.R.TIME_UNQUALIFIED),
):input_case('negative_'+_target+'_'+_field,_target,lambda t,a,f=_field,v=_value:{f:v},e.S.UNRESOLVED,_reason)


def exception_case(kind):
    def test(self):
        error=kind('synthetic qualification failure')
        def fail(request):self.calls.append('qualify');raise error
        self.adapter=replace(self.adapter,qualify=fail);self.evaluator=e.PublicationQualifier(self.adapter)
        if kind in (s.CapabilityUnavailable,c.a.ExternalAvailabilityFailure,TimeoutError):
            self.check(self.run_e(),e.S.UNRESOLVED,e.R.DEPENDENCY_UNAVAILABLE,gate=False)
        else:
            with self.assertRaises(kind) as raised:self.run_e()
            self.assertIs(raised.exception,error);self.assertEqual(self.calls,['qualify'])
    setattr(PublicationTests,'test_exception_'+kind.__name__,test)


for _error in (s.CapabilityUnavailable,c.a.ExternalAvailabilityFailure,TimeoutError,
        RuntimeError,AssertionError,TypeError,ValueError,MemoryError,KeyboardInterrupt,SystemExit):exception_case(_error)


def source_case(name, mutate):
    def test(self):
        replacement=mutate(self.source)
        if replacement is not None:self.source=replacement
        self.check(self.run_e(),e.S.REJECTED,e.R.INVALID_D_SOURCE,0,False)
    setattr(PublicationTests,'test_source_'+name,test)


for _name,_mutate in (
    ('foreign',lambda v:Hostile()),('bytes',lambda v:b'candidate'),
    ('bare_candidate',lambda v:v.retained.source.prepared.candidate),
    ('private_payload',lambda v:v.retained),('list',lambda v:[v]),
    ('missing_fields',lambda v:object.__new__(d.RetentionResult)),
    ('reason',lambda v:object.__setattr__(v,'reason',d.RetentionReason.UNKNOWN_HISTORY)),
    ('flag',lambda v:object.__setattr__(v,'verification_attempted',False)),
    ('cycle',lambda v:object.__setattr__(v.retained.source.prepared.request.snapshot,'events',(v,))),
    ('events_list',lambda v:object.__setattr__(v.retained.source.prepared.request.snapshot,'events',[])),
    ('iterator',lambda v:object.__setattr__(v.retained.source.prepared.request.snapshot,'keys',iter(()))),
    ('T1',lambda v:object.__setattr__(v.retained.source.prepared.request.completion,'t1',None)),
    ('COMMIT',lambda v:object.__setattr__(v.retained.source.prepared.request.completion.local,'storage_result',c.store.LocalStorageResult.LOCAL_STORAGE_ROLLBACK_CONFIRMED)),
    ('candidate_digest',lambda v:object.__setattr__(v.retained.source.prepared.candidate,'sha256',b'x'*32)),
    ('state',lambda v:object.__setattr__(v.retained.source.prepared.request.completion.completed,'state_digest',b'x'*32)),
):source_case(_name,_mutate)


def existing_case(progression):
    def test(self):
        case=fixture['RetentionTests']('test_first_success_exact_graph_and_order')
        case.template=self.template.retained.source;case.setUp()
        case.history=d.AssociationHistory.EXACT_EXISTING;case.progression=progression
        self.source=case.run_d()
        self.assertEqual(case.calls,['verify'])
        if progression is d.ProgressionStatus.CLEAR:
            self.check(self.run_e(),e.S.QUALIFIED,e.R.QUALIFIED,gate=True)
        else:
            payload=self.check(self.run_e(),e.S.UNRESOLVED,e.R.INHERITED_RECONCILIATION,0,False)
            self.assertTrue(payload.source.retained.reconciliation_required)
    setattr(PublicationTests,'test_existing_'+progression,test)


for _progression in d.ProgressionStatus:existing_case(_progression)


def binding_case(name,target,mutate,reason):
    def transform(t,a):
        value=e._copy(getattr(a.inputs,target))
        mutate(value)
        return replace(a,inputs=replace(a.inputs,**{target:value}))
    assessment_case('binding_'+name,transform,e.S.UNRESOLVED,reason,False)


binding_case('candidate','candidate',lambda v:object.__setattr__(v,'event_sequence',999),e.R.CANDIDATE_BINDING_MISMATCH)
binding_case('operation','authority',lambda v:object.__setattr__(v,'operation',s.OriginalOperation(v.operation.permit,s.OperationKind.PERMIT_COMPLETION)),e.R.ORIGINAL_OPERATION_MISMATCH)
binding_case('completion','local',lambda v:object.__setattr__(v,'completion',replace(v.completion,authenticated_principal='foreign')),e.R.COMMITTED_TRANSITION_MISMATCH)
binding_case('head','local',lambda v:object.__setattr__(v,'head',replace(v.head,state_digest=b'x'*32)),e.R.COMMITTED_TRANSITION_MISMATCH)
binding_case('events','local',lambda v:object.__setattr__(v,'events',()),e.R.COMMITTED_TRANSITION_MISMATCH)
binding_case('keys','local',lambda v:object.__setattr__(v,'keys',()),e.R.COMMITTED_TRANSITION_MISMATCH)
binding_case('retention_ref','retention',lambda v:object.__setattr__(v,'reference',s.EvidenceReference('foreign',b'x'*32)),e.R.RETENTION_BINDING_MISMATCH)
for _field,_value in (('principal','foreign'),('host','foreign'),('representation','foreign')):
    binding_case(_field,'authority',lambda v,f=_field,x=_value:object.__setattr__(v,f,x),e.R.ASSESSMENT_BINDING_MISMATCH)
binding_case('permit_interval','authority',lambda v:object.__setattr__(v,'permit',replace(v.permit,valid_until_us=1000)),e.R.ASSESSMENT_BINDING_MISMATCH)
binding_case('predecessor','authority',lambda v:object.__setattr__(v,'predecessor',replace(v.predecessor,revision=v.predecessor.revision+1)),e.R.ASSESSMENT_BINDING_MISMATCH)


def prior_case(outcome):
    def transform(t,a):
        result=s.PublicationResult(outcome,a.inputs.candidate,t.reference)
        prior=o.publication_disposition(a.inputs.candidate,result,local_commit=o.LocalCommitState.CONFIRMED,
                                        qualification=s.EvidenceValidity.VALID)
        return replace(a,inputs=replace(a.inputs,prior=prior))
    assessment_case('prior_'+outcome,transform,e.S.UNRESOLVED,
        e.R.PUBLICATION_HISTORY_NON_INITIAL if outcome is s.ExternalOutcome.CONFIRMED else e.R.PUBLICATION_HISTORY_UNKNOWN)


for _outcome in s.ExternalOutcome:prior_case(_outcome)


def foreign_prior(operation=False):
    def transform(t,a):
        candidate=a.inputs.candidate if operation else replace(a.inputs.candidate,event_sequence=999)
        published=s.PublicationResult(s.ExternalOutcome.CONFIRMED,candidate,t.reference)
        prior=o.publication_disposition(candidate,published,local_commit=o.LocalCommitState.CONFIRMED,
                                        qualification=s.EvidenceValidity.VALID)
        inputs=replace(a.inputs,prior=prior)
        if operation:
            object.__setattr__(prior,'operation',s.OriginalOperation(
                s.EvidenceReference('foreign-permit',b'x'*32),s.OperationKind.CHECKPOINT_PUBLICATION))
        return replace(a,inputs=inputs)
    assessment_case('prior_foreign_'+('operation' if operation else 'candidate'),transform,e.S.UNRESOLVED,
        e.R.ORIGINAL_OPERATION_MISMATCH if operation else e.R.CANDIDATE_BINDING_MISMATCH,False)


foreign_prior();foreign_prior(True)


def time_at(inputs, elapsed_ns, error_ns=0):
    time=inputs.time
    point=replace(time.point,ticks_ns=time.sample.anchor.ticks_ns+elapsed_ns)
    propagation=replace(time.propagation,elapsed_ns=elapsed_ns,error_ns=error_ns)
    interval=s.evaluate_time(time.sample,time.profile,point,propagation).interval
    return replace(inputs,time=replace(time,point=point,propagation=propagation,covered_interval=interval),
                   authority=replace(inputs.authority,point=point,interval=interval))


def temporal_case(name,elapsed,error,state,reason):
    assessment_case('temporal_'+name,lambda t,a:replace(a,inputs=time_at(a.inputs,elapsed,error)),state,reason)


temporal_case('permit_inside',9000,0,e.S.QUALIFIED,e.R.QUALIFIED)
temporal_case('permit_equal',10000,0,e.S.REJECTED,e.R.TEMPORAL_OUTSIDE)
temporal_case('permit_after',11000,0,e.S.REJECTED,e.R.TEMPORAL_OUTSIDE)
temporal_case('permit_overlap',9500,100,e.S.UNRESOLVED,e.R.TEMPORAL_UNCERTAIN)


def deadline_case(kind,name,deadline,state,reason):
    def transform(t,a):
        time=a.inputs.time
        field='authorization' if kind=='inclusive' else 'freshness'
        cls=s.InclusiveDeadline if kind=='inclusive' else s.StrictDeadline
        value=replace(time,**{field+'_timing':s.TimingApplicability.REQUIRED,field+'_deadline':cls(deadline)})
        return replace(a,inputs=replace(a.inputs,time=value))
    assessment_case(kind+'_'+name,transform,state,reason)


for _kind in ('inclusive','strict'):
    deadline_case(_kind,'future',16,e.S.QUALIFIED,e.R.QUALIFIED)
    deadline_case(_kind,'equal',15,e.S.QUALIFIED if _kind=='inclusive' else e.S.REJECTED,
                  e.R.QUALIFIED if _kind=='inclusive' else e.R.TEMPORAL_OUTSIDE)
    deadline_case(_kind,'past',14,e.S.REJECTED,e.R.TEMPORAL_OUTSIDE)
    def overlap(t,a,kind=_kind):
        inputs=time_at(a.inputs,5000,100)
        field='authorization' if kind=='inclusive' else 'freshness'
        cls=s.InclusiveDeadline if kind=='inclusive' else s.StrictDeadline
        return replace(a,inputs=replace(inputs,time=replace(inputs.time,
            **{field+'_timing':s.TimingApplicability.REQUIRED,field+'_deadline':cls(15)})))
    assessment_case(_kind+'_overlap',overlap,e.S.UNRESOLVED,e.R.TEMPORAL_UNCERTAIN)


def valid_from_diagnostics(self):
    inputs=self.inputs(self.source)
    # Bound arithmetic unit cases use a synthetic subject with valid_from=15.
    # This does not qualify a changed permit for the evaluated D operation.
    authority=replace(inputs.authority,permit=replace(inputs.authority.permit,valid_from_us=15))
    for elapsed,error,expected in ((5000,0,None),(4000,0,(e.S.REJECTED,e.R.TEMPORAL_OUTSIDE)),
                                   (4500,0,(e.S.UNRESOLVED,e.R.TEMPORAL_UNCERTAIN))):
        current=time_at(inputs,elapsed,error)
        authority=replace(authority,point=current.time.point,interval=current.time.covered_interval)
        self.assertEqual(e._time_reason(inputs.candidate,authority,current.time),expected)


PublicationTests.test_valid_from_boundaries_without_permit_substitution=valid_from_diagnostics


def time_change(name,changes,reason):
    input_case('time_'+name,'time',changes,e.S.UNRESOLVED,reason)


time_change('domain',lambda t,a:{'point':replace(a.inputs.time.point,domain_id='foreign')},e.R.TIME_UNQUALIFIED)
time_change('process',lambda t,a:{'point':replace(a.inputs.time.point,process_id='foreign')},e.R.TIME_UNQUALIFIED)
time_change('range',lambda t,a:{'point':replace(a.inputs.time.point,ticks_ns=100001)},e.R.TIME_UNQUALIFIED)
time_change('error_binding',lambda t,a:{'propagation':replace(a.inputs.time.propagation,elapsed_ns=999)},e.R.TIME_UNQUALIFIED)
time_change('sample_source',lambda t,a:{'sample':replace(a.inputs.time.sample,source='foreign')},e.R.TIME_BINDING_MISMATCH)
time_change('width',lambda t,a:{'propagation':replace(a.inputs.time.propagation,error_ns=6000)},e.R.TIME_UNQUALIFIED)
time_change('interval',lambda t,a:{'covered_interval':s.UtcInterval(99,99)},e.R.TIME_BINDING_MISMATCH)
time_change('profile',lambda t,a:{'profile':replace(a.inputs.time.profile,source='foreign')},e.R.TIME_BINDING_MISMATCH)
time_change('missing_refresh',lambda t,a:{'sample':replace(a.inputs.time.sample,sample=t.reference)},e.R.TIME_BINDING_MISMATCH)


def refresh_case(valid):
    def transform(t,a):
        old=a.inputs.time
        sample=replace(old.sample,sample=t.reference,anchor=old.point,
                       utc=old.covered_interval if valid else s.UtcInterval(50,50))
        propagation=replace(old.propagation,sample=t.reference,elapsed_ns=0)
        time=replace(old,sample=sample,propagation=propagation,covered_interval=sample.utc,
                     fixing_to_refresh=old.propagation)
        return replace(a,inputs=replace(a.inputs,time=time,authority=replace(a.inputs.authority,interval=sample.utc)))
    assessment_case('refresh_'+str(valid),transform,e.S.QUALIFIED if valid else e.S.UNRESOLVED,
                    e.R.QUALIFIED if valid else e.R.TIME_BINDING_MISMATCH)


refresh_case(True);refresh_case(False)


def instability_case(target,stage):
    def test(self):
        def mutate():
            if target=='source':object.__setattr__(self.source.retained.source.prepared.candidate,'event_sequence',999)
            elif target=='request':object.__setattr__(self.request.source.retained.source.prepared.candidate,'event_sequence',999)
            elif target=='response':object.__setattr__(self.response.reference,'identity','changed')
            elif target=='adapter':object.__setattr__(self.adapter,'qualify',lambda value:self.fail('replacement'))
            elif target=='reference':object.__setattr__(self.adapter.implementation,'identity','changed')
            elif target=='canonical':g.evaluate_publication_gate=lambda value:self.fail('replacement')
            elif target=='captured_gate':object.__setattr__(self.evaluator,'_gate',lambda value:self.fail('replacement'))
            elif target=='checkpoint':cp.validate_candidate=lambda *a,**k:self.fail('replacement')
            elif target=='timing':s.evaluate_time=lambda *a:self.fail('replacement')
        reasons={'source':e.R.SOURCE_INSTABILITY,'request':e.R.REQUEST_INSTABILITY,
            'response':e.R.RESPONSE_INSTABILITY}
        if target=='reference' and stage=='gate':
            reasons[target]=e.R.RESPONSE_INSTABILITY
        original=g.evaluate_publication_gate
        if stage=='qualify':
            def change(a):mutate();return a
            self.transform=change
        elif stage=='gate':
            def gate(inputs):
                value=original(inputs)
                if target=='gate_input':object.__setattr__(inputs.time,'qualification',s.EvidenceValidity.UNKNOWN)
                else:mutate()
                return value
            g.evaluate_publication_gate=gate
            self.evaluator=e.PublicationQualifier(self.adapter)
        elif stage=='availability':
            def fail(request):
                self.request=request;self.calls.append('qualify');mutate();raise TimeoutError('synthetic')
            self.adapter=replace(self.adapter,qualify=fail);self.evaluator=e.PublicationQualifier(self.adapter)
        try:
            self.check(self.run_e(),e.S.UNRESOLVED,reasons.get(target,
                e.R.GATE_INSTABILITY if target=='gate_input' else e.R.DEPENDENCY_INSTABILITY))
        finally:
            # Restore synthetic monkeypatches only; no repository file changes.
            for owner,name,captured in self.evaluator._bindings:
                if owner is not g or name!='evaluate_publication_gate':setattr(owner,name,captured)
            g.evaluate_publication_gate=original
    setattr(PublicationTests,'test_instability_'+target+'_'+stage,test)


for _target in ('source','request','adapter','reference','canonical','captured_gate','checkpoint','timing'):
    for _stage in ('qualify','gate','availability'):instability_case(_target,_stage)
instability_case('response','gate');instability_case('gate_input','gate')


def gate_return_case(name,returned):
    def test(self):
        original=g.evaluate_publication_gate
        def gate(inputs):return returned(self,original(inputs))
        with patch.object(g,'evaluate_publication_gate',gate):
            self.evaluator=e.PublicationQualifier(self.adapter)
            self.check(self.run_e(),e.S.UNRESOLVED,e.R.CANONICAL_GATE_CONTRADICTION,gate=True)
    setattr(PublicationTests,'test_gate_return_'+name,test)


gate_return_case('foreign',lambda t,v:Hostile())
gate_return_case('none',lambda t,v:None)
def wrong_gate(t,v):
    value=e._copy(v);object.__setattr__(value.inputs.time,'qualification',s.EvidenceValidity.UNKNOWN);return value
gate_return_case('wrong_inputs',wrong_gate)


def source_subclass(self):
    class Foreign(d.RetentionResult):pass
    value=object.__new__(Foreign)
    self.source=value
    self.check(self.run_e(),e.S.REJECTED,e.R.INVALID_D_SOURCE,0,False)
PublicationTests.test_source_subclass=source_subclass


def large_snapshot(self):
    case=fixture['RetentionTests']('test_approved_large_complete_history_has_no_D_graph_or_state_cap')
    case.template=self.template.retained.source;case.setUp()
    results=[]
    original=case.run_d
    def record():
        result=original();results.append(result);return result
    case.run_d=record
    case.test_approved_large_complete_history_has_no_D_graph_or_state_cap()
    self.source=results[0]
    self.assertGreater(len(self.source.retained.source.prepared.request.snapshot.projection.commands),409)
    with patch.object(p,'state_bytes',side_effect=AssertionError('whole STATE')):
        self.evaluator=e.PublicationQualifier(self.adapter)
        result=self.run_e()
    self.check(result,e.S.QUALIFIED,e.R.QUALIFIED,gate=True)
PublicationTests.test_large_history_streaming_without_aggregate_budget=large_snapshot


def final_source_check(self):
    issue=e._issue
    def allocate(state,*args,**kwargs):
        result=issue(state,*args,**kwargs)
        if state is e.S.QUALIFIED:
            object.__setattr__(self.source.retained.source.prepared.candidate,'event_sequence',999)
        return result
    with patch.object(e,'_issue',allocate):
        self.check(self.run_e(),e.S.UNRESOLVED,e.R.SOURCE_INSTABILITY)
PublicationTests.test_final_output_allocation_does_not_skip_source_recheck=final_source_check


def priority(self):
    def mutate(a):
        object.__setattr__(self.source.retained.source.prepared.candidate,'event_sequence',999)
        object.__setattr__(self.request.source.retained.source.prepared.candidate,'event_sequence',998)
        object.__setattr__(self.adapter.implementation,'identity','changed')
        return a
    self.transform=mutate
    self.check(self.run_e(),e.S.UNRESOLVED,e.R.SOURCE_INSTABILITY,gate=False)
PublicationTests.test_instability_priority_source_before_request_dependency=priority


def rejected_handoff(self):
    case=fixture['RetentionTests']('test_first_success_exact_graph_and_order')
    case.template=self.template.retained.source;case.setUp();case.history=d.AssociationHistory.CONFLICT
    self.source=case.run_d()
    payload=self.check(self.run_e(),e.S.REJECTED,e.R.NOT_RETAINED,0,False)
    self.assertTrue(payload.reconciliation_required)
    self.assertTrue(payload.source.rejected.reconciliation_required)
PublicationTests.test_upstream_rejected_committed_handoff_is_preserved=rejected_handoff


def pre_entry_dependency(self):
    with patch.object(cp,'validate_candidate',side_effect=AssertionError('replacement must not run')):
        self.check(self.run_e(),e.S.UNRESOLVED,e.R.DEPENDENCY_INSTABILITY,0,False)
PublicationTests.test_dependency_replacement_before_validation_is_not_invoked=pre_entry_dependency


def returned_gate_stability(self):
    original=g.evaluate_publication_gate;issued=[]
    def gate(inputs):
        value=original(inputs);issued.append(value);return value
    issue=e._issue
    def allocate(state,*args,**kwargs):
        value=issue(state,*args,**kwargs)
        if state is e.S.QUALIFIED:object.__setattr__(issued[0],'reason',g.GateReason.TIME)
        return value
    with patch.object(g,'evaluate_publication_gate',gate),patch.object(e,'_issue',allocate):
        self.evaluator=e.PublicationQualifier(self.adapter)
        self.check(self.run_e(),e.S.UNRESOLVED,e.R.GATE_INSTABILITY)
PublicationTests.test_original_gate_response_stability_after_output_capture=returned_gate_stability


def expired_after_retention(self):
    case=fixture['RetentionTests']('test_first_success_exact_graph_and_order')
    case.template=fixture['genuine_source']();case.setUp()
    self.source=case.run_d()
    self.assertIs(self.source.state,d.RetentionState.RETAINED)
    self.check(self.run_e(),e.S.REJECTED,e.R.TEMPORAL_OUTSIDE,gate=True)
PublicationTests.test_D_allows_later_expiry_E_rejects_current_publication_expiry=expired_after_retention


time_change('age',lambda t,a:{'point':replace(a.inputs.time.point,ticks_ns=100000),
    'propagation':replace(a.inputs.time.propagation,elapsed_ns=100000,error_ns=1000)},e.R.TIME_UNQUALIFIED)


def gate_exception_case(kind):
    def test(self):
        error=kind('synthetic canonical defect')
        def fail(inputs):raise error
        with patch.object(g,'evaluate_publication_gate',fail):
            self.evaluator=e.PublicationQualifier(self.adapter)
            with self.assertRaises(kind) as raised:self.run_e()
            self.assertIs(raised.exception,error);self.assertEqual(self.calls,['qualify'])
    setattr(PublicationTests,'test_canonical_exception_'+kind.__name__,test)


for _kind in (RuntimeError,AssertionError,TypeError,MemoryError,KeyboardInterrupt,SystemExit):gate_exception_case(_kind)


def projection_equivalence(self):
    ref=s.EvidenceReference('shared',b'x'*32)
    for left,right in (((ref,ref),(e._copy(ref),e._copy(ref))),
            ((ref,ref),(ref,s.EvidenceReference('different',b'x'*32))),
            ((1,True,b'x'),(1,True,b'x')),((1,),(True,)),
            ((s.EvidenceValidity.VALID,),(s.EvidenceValidity.UNKNOWN,))):
        a,b=e._project(left),e._project(right)
        self.assertEqual(e._equal(a,b),a==b)
    marker=object.__new__(e._EvaluationBinding)
    self.assertTrue(e._equal(e._project(marker),e._project(marker)))
    self.assertFalse(e._equal(e._project(marker),e._project(object.__new__(e._EvaluationBinding))))
PublicationTests.test_memoized_projection_comparison_preserves_exact_semantics=projection_equivalence


def hostile_class(self):
    class Meta(type):
        def __hash__(cls):raise AssertionError('foreign class hashing')
        def __eq__(cls,other):raise AssertionError('foreign class equality')
    class Foreign(metaclass=Meta):pass
    self.source=Foreign()
    self.check(self.run_e(),e.S.REJECTED,e.R.INVALID_D_SOURCE,0,False)
PublicationTests.test_class_identity_lookup_never_hashes_foreign_classes=hostile_class


def protocol_completion_replacement(self):
    original=p.validate_completed_command
    replacements=[]
    def delegated(*args,**kwargs):
        replacements.append(True)
        return original(*args,**kwargs)
    def change(assessment):
        patcher=patch.object(p,'validate_completed_command',delegated)
        patcher.start();self.addCleanup(patcher.stop)
        return assessment
    self.transform=change
    result=self.run_e()
    print('E-IMPL-01',result.state,result.reason,'replacement_calls',len(replacements),
          'trusted_calls',len(self.calls),'gate_evaluated',result.gate_evaluated,flush=True)
    self.check(result,e.S.UNRESOLVED,e.R.DEPENDENCY_INSTABILITY,gate=False)
    self.assertEqual(replacements,[])
PublicationTests.test_protocol_completion_replacement_after_trusted_call=protocol_completion_replacement


def audited_replacements(self,groups):
    """Each named boundary is statically reached, not discovered from E's guard."""
    for owner,names in groups:
        for name in names:
            with self.subTest(module=getattr(owner,'__name__','class'),binding=name):
                original=getattr(owner,name);calls=[]
                def delegated(*args,**kwargs):
                    calls.append(True)
                    return original(*args,**kwargs)
                with patch.object(owner,name,delegated):
                    result=self.run_e()
                    self.check(result,e.S.UNRESOLVED,e.R.DEPENDENCY_INSTABILITY,0,False)
                # Annotation projection precedes the source's semantic check;
                # delegated stdlib metadata cannot reach canonical validation.
                if owner is not c or name not in ('get_args','get_origin'):
                    self.assertEqual(calls,[])


def protocol_dependency_closure(self):
    audited_replacements(self,((p,('validate_ack','validate_event_chain','event_order','key_set_digest',
        'command_digest','event_digest','event_bytes','_validate_record','validate_command','validate_primary',
        '_validate_binding','validate_references','_encode','_decode','_enum','frame','parse_frame','_read_frame',
        'collection','u32','uint','utc','identifier','digest_value','blob','require','sha256')),
        (p._Reader,('__init__','take','count','end'))))
PublicationTests.test_dependency_audit_protocol_codec_ack_event_STATE=protocol_dependency_closure


def checkpoint_conflict_dependency_closure(self):
    audited_replacements(self,((cp,('_command_result_coherent','sha256')),
        (p.contract,('decode_conflict','frame_conflict','_text','_require','sha256_evidence','sha256')),
        (p.contract.ConflictKey,('__post_init__','canonical_bytes')),
        (p.contract.ArtifactBytes,('evidence_sha256',))))
PublicationTests.test_dependency_audit_checkpoint_conflict_and_approval=checkpoint_conflict_dependency_closure


def historical_dependency_closure(self):
    audited_replacements(self,((d,('_reference','_require','sha256')),(c,('_need','get_args','get_origin','fields','sha256')),
        (c.q,('_validate','_children','_own_types','_project','_validities','_check','fields')),
        (c.r,('_validate','_children','_project','_authority','_receipt_checks','_confirmation_checks','_map_envelope','fields')),
        (c.e,('_source_validate','_evaluation')),
        (c.a,('_validate','_children','_projection','_qualification_checks','fields','sha256')),
        (c.g,('_kind','_children','_revalidate','_check','_snapshot','fields','sha256')),
        (c.pr,('_dataclass_type','_children','_revalidate','_precheck','_postcheck','fields','sha256'))))
PublicationTests.test_dependency_audit_historical_admission_snapshot=historical_dependency_closure


def service_disposition_dependency_closure(self):
    audited_replacements(self,((s,('verify_publication_result','verify_completion_result','sha256','Fraction')),
        (o,('_history','_observe','_publication_knowledge','_qualified_outcome','_knowledge','_required')),
        (g,('fields',))))
PublicationTests.test_dependency_audit_timing_and_retained_disposition=service_disposition_dependency_closure


def constructor_dependency_closure(self):
    groups=((g,('GateResult',)),(cp,('NormalReference','NormalCheckpoint','CommittedHead')),
        (s,('EvidenceReference','CommandContext','OriginalOperation','CheckpointCandidate','RetainedTimeFixing',
            'RetainedAdmissionEnvelope','UtcInterval','TimeEvaluation','StrictDeadline')),
        (p,('_Reader','Reference','Parameters','CommandPayload','AckPayload','EventPayload','ReservationRow','StateProjection','EventType')),
        (c.r,('OriginalRecordIndex',)),(p.contract,('ConflictKey','ConflictFamily')))
    audited_replacements(self,groups)
    constructors=(g.GateResult,cp.NormalReference,cp.NormalCheckpoint,cp.CommittedHead,
        s.EvidenceReference,s.CommandContext,s.OriginalOperation,s.CheckpointCandidate,s.RetainedTimeFixing,
        s.RetainedAdmissionEnvelope,s.UtcInterval,s.TimeEvaluation,s.StrictDeadline,
        p.Reference,p.Parameters,p.CommandPayload,p.AckPayload,p.EventPayload,p.ReservationRow,p.StateProjection,
        c.r.OriginalRecordIndex,p.contract.ConflictKey)
    audited_replacements(self,tuple((cls,('__init__',)) for cls in constructors))
PublicationTests.test_dependency_audit_reached_constructor_bindings=constructor_dependency_closure


def mid_gate_dependency(self):
    original_construct=cp.construct_candidate;original_validate=p.validate_completed_command
    replacements=[];patched=[]
    def delegated(*args,**kwargs):
        replacements.append(True)
        return original_validate(*args,**kwargs)
    def construct(*args,**kwargs):
        if not patched:
            patcher=patch.object(p,'validate_completed_command',delegated)
            patcher.start();self.addCleanup(patcher.stop);patched.append(True)
        return original_construct(*args,**kwargs)
    with patch.object(cp,'construct_candidate',construct):
        self.evaluator=e.PublicationQualifier(self.adapter)
        result=self.run_e()
    self.check(result,e.S.UNRESOLVED,e.R.DEPENDENCY_INSTABILITY,gate=True)
    self.assertEqual(len(replacements),2)
PublicationTests.test_dependency_replaced_inside_canonical_reconstruction_is_not_positive=mid_gate_dependency


def enum_dispatch_change(self,whole=False):
    original=p._ENUMS['Command'];calls=[]
    def delegated(value):
        calls.append(True);return original(value)
    def change(assessment):
        replacement=dict(p._ENUMS);replacement['Command']=delegated
        manager=patch.object(p,'_ENUMS',replacement) if whole else patch.dict(p._ENUMS,{'Command':delegated})
        manager.start();self.addCleanup(manager.stop)
        return assessment
    self.transform=change
    result=self.run_e()
    print('ENUM_MAPPING' if whole else 'ENUM_ENTRY',result.state,result.reason,
        'replacement_calls',len(calls),'trusted_calls',len(self.calls),'gate_evaluated',result.gate_evaluated,flush=True)
    self.check(result,e.S.UNRESOLVED,e.R.DEPENDENCY_INSTABILITY,gate=False)
    self.assertEqual(calls,[])
PublicationTests.test_enum_Command_entry_replacement_after_assessment=lambda self:enum_dispatch_change(self)
PublicationTests.test_enum_whole_mapping_replacement_after_assessment=lambda self:enum_dispatch_change(self,True)


def schema_dispatch_change(self,whole=False):
    original=p._SCHEMAS[p.CommandPayload]
    replacement=tuple(list(original))
    self.assertIsNot(replacement,original);self.assertEqual(replacement,original)
    def change(assessment):
        manager=(patch.object(p,'_SCHEMAS',dict(p._SCHEMAS)) if whole else
            patch.dict(p._SCHEMAS,{p.CommandPayload:replacement}))
        manager.start();self.addCleanup(manager.stop)
        return assessment
    self.transform=change
    self.check(self.run_e(),e.S.UNRESOLVED,e.R.DEPENDENCY_INSTABILITY,gate=False)
PublicationTests.test_schema_entry_replacement_after_assessment=lambda self:schema_dispatch_change(self)
PublicationTests.test_schema_whole_mapping_replacement_after_assessment=lambda self:schema_dispatch_change(self,True)


def fixed_dispatch_scope(self):
    expected_domains=('Command','Operation','Phase','ArtifactType','LeaseStatus',
        'ExecutionState','QuarantineReason','EventType','OutcomeCode')
    expected_records=(p.Reference,p.Parameters,p.CommandPayload,p.EventPayload,p.AckPayload,
        p.MetadataRow,p.ReservationRow,p.ClaimRow,p.CommandRow)
    tables=self.evaluator._dispatch
    self.assertEqual(tuple(name for owner,name,mapping,entries in tables),('_ENUMS','_SCHEMAS'))
    for (owner,name,mapping,entries),keys in zip(tables,(expected_domains,expected_records)):
        self.assertIs(owner,p);self.assertIs(mapping,getattr(p,name))
        self.assertEqual(tuple(key for key,value in entries),keys)
        self.assertEqual(len(entries),len(set(keys)))
        for key,value in entries:
            with self.subTest(container=name,key=key):
                self.assertIs(value,dict.__getitem__(mapping,key))
                with patch.dict(mapping,{key:object()}):
                    self.assertFalse(self.evaluator._composition_stable())
                with patch.dict(mapping,clear=True):
                    self.assertFalse(self.evaluator._composition_stable())
                self.assertTrue(self.evaluator._composition_stable())
        with patch.object(owner,name,dict(mapping)):
            self.assertFalse(self.evaluator._composition_stable())
        class Hostile(dict):
            def __eq__(self,other):raise AssertionError('mapping equality')
            def __getitem__(self,key):raise AssertionError('mapping dispatch')
            def get(self,*args):raise AssertionError('mapping get')
        with patch.object(owner,name,Hostile()):
            self.assertFalse(self.evaluator._composition_stable())
        self.assertTrue(self.evaluator._composition_stable())
    self.assertEqual(self.calls,[])
PublicationTests.test_fixed_dispatch_domain_and_record_scope_identity=fixed_dispatch_scope


if __name__=='__main__':unittest.main()
