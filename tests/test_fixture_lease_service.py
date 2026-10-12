"""Synthetic IL.2 tests; imports inspect source but never acquire operational facts."""
import ast
from dataclasses import FrozenInstanceError, replace
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
for name in ('fixture_lease_contract', 'fixture_lease_service'):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'services/api/infrastructure' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
s = sys.modules['fixture_lease_service']
c = sys.modules['fixture_lease_contract']


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.ref = s.EvidenceReference('synthetic', b'x' * 32)
        self.profile = s.QualifiedClockProfile(self.ref, 'synthetic-source', self.ref,
                                             10000000, 20000, 10000, 0)
        self.anchor = s.MonotonicPoint('synthetic-process', 'synthetic-domain', 100)
        self.sample = s.QualifiedSample(self.ref, 'synthetic-source', self.ref, self.ref,
                                       s.UtcInterval(1000, 1002), self.anchor)

    def error(self, elapsed=0, error=0):
        return s.QualifiedPropagationError(self.ref, self.ref, elapsed, error, self.ref)

    def evaluate(self, elapsed=0, error=0):
        return s.evaluate_time(self.sample, self.profile,
                               replace(self.anchor, ticks_ns=100 + elapsed), self.error(elapsed, error))

    def test_every_rejecting_default(self):
        default = s.RejectingCapabilities()
        methods = {'authenticate': 1, 'verify': 3, 'observe': 1, 'obtain': 2,
                   'complete': 2, 'reconcile': 2, 'read': 1, 'publish': 3,
                   'qualify': 2, 'measure': 0}
        for name, count in methods.items():
            with self.subTest(name=name), self.assertRaises(s.CapabilityUnavailable):
                getattr(default, name)(*([None] * count))

    def test_absence_is_positive_evidence(self):
        absent = s.ActivationObservation(s.AuthorityPresence.AUTHORITATIVE_ABSENT, self.ref, None)
        self.assertEqual(absent.evidence, self.ref)
        for presence in ('UNKNOWN', 'UNAVAILABLE', 'STALE', 'LOOKUP_FAILED', None, False):
            with self.subTest(presence=presence), self.assertRaises(s.TimeRejected):
                s.ActivationObservation(presence, self.ref, None)
        with self.assertRaises(s.TimeRejected):
            s.ActivationObservation(s.AuthorityPresence.AUTHORITATIVE_ABSENT, None, None)

    def test_inclusive_matrix(self):
        deadline = s.InclusiveDeadline(10)
        for lower, upper, result in [(1, 9, 'SATISFIED'), (10, 10, 'SATISFIED'),
                                     (11, 12, 'OUTSIDE'), (9, 11, 'UNCERTAIN')]:
            self.assertEqual(s.inclusive_bound(s.UtcInterval(lower, upper), deadline).value, result)

    def test_strict_matrix(self):
        deadline = s.StrictDeadline(10)
        for lower, upper, result in [(1, 9, 'SATISFIED'), (10, 10, 'OUTSIDE'),
                                     (11, 12, 'OUTSIDE'), (9, 10, 'UNCERTAIN')]:
            self.assertEqual(s.strict_bound(s.UtcInterval(lower, upper), deadline).value, result)

    def test_deadline_types_not_interchangeable(self):
        for fn, deadline in [(s.strict_bound, s.InclusiveDeadline(10)),
                             (s.inclusive_bound, s.StrictDeadline(10))]:
            with self.assertRaises(s.TimeRejected): fn(s.UtcInterval(1, 2), deadline)

    def test_valid_from(self):
        for lower, upper, result in [(9, 11, False), (10, 11, True), (11, 12, True)]:
            self.assertIs(s.valid_from_satisfied(s.UtcInterval(lower, upper), 10), result)

    def test_zero_elapsed(self):
        self.assertEqual(self.evaluate(), s.TimeEvaluation(s.UtcInterval(1000, 1002), 2, 0))

    def test_positive_elapsed_error_growth_and_outward_rounding(self):
        value = self.evaluate(1501, 502)
        self.assertEqual(value.interval, s.UtcInterval(1000, 1005))
        self.assertEqual(value.sample_age_upper_us, 3)
        self.assertEqual(value.command_uncertainty_us, 5)
        self.assertEqual(value, self.evaluate(1501, 502))

    def test_lower_rounds_down(self):
        self.assertEqual(self.evaluate(0, 1).interval, s.UtcInterval(999, 1003))

    def test_negative_elapsed(self):
        with self.assertRaises(s.TimeRejected):
            s.evaluate_time(self.sample, self.profile, replace(self.anchor, ticks_ns=99), self.error())

    def test_reversed_interval(self):
        with self.assertRaises(s.TimeRejected): s.UtcInterval(2, 1)

    def test_invalid_numeric_values(self):
        for bad in (True, False, 1.0, '1', None, 1 << 63):
            for make in (lambda: s.UtcInterval(bad, bad), lambda: s.StrictDeadline(bad),
                         lambda: replace(self.anchor, ticks_ns=bad),
                         lambda: self.error(error=bad)):
                with self.subTest(bad=bad), self.assertRaises(s.TimeRejected): make()
        with self.assertRaises(s.TimeRejected): self.error(error=-1)
        with self.assertRaises(s.TimeRejected): replace(self.profile, max_sample_age_us=-1)

    def test_overflow_rejected(self):
        sample = replace(self.sample, utc=s.UtcInterval((1 << 63)-1, (1 << 63)-1))
        with self.assertRaises(s.TimeRejected):
            s.evaluate_time(sample, self.profile, replace(self.anchor, ticks_ns=1100), self.error(1000))

    def test_qualification_limits(self):
        for profile in (replace(self.profile, max_elapsed_ns=0),
                        replace(self.profile, max_sample_age_us=0),
                        replace(self.profile, max_command_uncertainty_us=1)):
            with self.assertRaises(s.TimeRejected):
                s.evaluate_time(self.sample, profile, replace(self.anchor, ticks_ns=1100), self.error(1000))

    def test_error_evidence_binding(self):
        for error in (self.error(1), replace(self.error(), sample=s.EvidenceReference('other', b'y'*32)),
                      replace(self.error(), profile=s.EvidenceReference('other', b'y'*32))):
            with self.assertRaises(s.TimeRejected):
                s.evaluate_time(self.sample, self.profile, self.anchor, error)

    def test_restart_and_domain_rejected(self):
        for point in (replace(self.anchor, process_id='restarted'),
                      replace(self.anchor, domain_id='other-domain')):
            with self.assertRaises(s.TimeRejected):
                s.evaluate_time(self.sample, self.profile, point, self.error())

    def test_raw_evidence_not_qualified_sample(self):
        with self.assertRaises(s.TimeRejected):
            s.evaluate_time(s.RawTimeEvidence('synthetic-source', self.ref), self.profile,
                            self.anchor, self.error())

    def test_source_profile_mismatch(self):
        for sample in (replace(self.sample, source='other'),
                       replace(self.sample, profile=s.EvidenceReference('other', b'y'*32))):
            with self.assertRaises(s.TimeRejected):
                s.evaluate_time(sample, self.profile, self.anchor, self.error())

    def test_refresh_independent_and_no_narrowing(self):
        new = replace(self.sample, sample=s.EvidenceReference('fresh', b'y'*32),
                      anchor=replace(self.anchor, ticks_ns=1100), utc=s.UtcInterval(1000, 1005))
        self.assertTrue(s.refresh_consistent(self.sample, new, self.profile, self.error(1000)))
        self.assertEqual(new.utc, s.UtcInterval(1000, 1005))
        contradictory = replace(new, utc=s.UtcInterval(2000, 2001))
        self.assertFalse(s.refresh_consistent(self.sample, contradictory, self.profile, self.error(1000)))
        with self.assertRaises(s.TimeRejected):
            s.refresh_consistent(self.sample, self.sample, self.profile, self.error())

    def test_immutable_values(self):
        for value in (self.sample, self.profile, self.ref, self.anchor, self.error(), self.evaluate()):
            with self.assertRaises(FrozenInstanceError): value.unapproved = True

    def test_timing_is_not_permission_or_availability(self):
        value = self.evaluate()
        self.assertFalse(hasattr(value, 'authorized'))
        self.assertFalse(hasattr(value, 'available'))
        self.assertTrue(c.claims_remain_blocking(c.LeaseStatus.EXPIRED))
        self.assertTrue(c.claims_remain_blocking(c.LeaseStatus.QUARANTINED))

    def test_supporting_capability_values(self):
        context = s.CommandContext('synthetic-command', b'x'*32, c.Command.ACQUIRE,
                                   c.Operation.FIXTURE_PROVISIONING, c.Phase.PRE_AUTH, 0, self.ref)
        actor = s.AuthenticatedRequester('synthetic-requester', self.ref)
        artifact = c.ArtifactBytes(c.ArtifactType.PROVISIONING_REQUEST, b'synthetic')
        approval = s.VerifiedApproval('synthetic-reviewer', actor.principal, context, artifact, self.ref)
        activation = s.ActivationIdentity('synthetic-register', 1, 'synthetic-activation',
                                          'synthetic-host', self.ref)
        observation = s.ActivationObservation(s.AuthorityPresence.AUTHORITATIVE_PRESENT,
                                              self.ref, activation)
        permit = s.CommandPermit(context, activation, 1, 2, self.ref)
        self.assertEqual(observation.activation, permit.activation)
        self.assertEqual(approval.context, permit.context)
        with self.assertRaises(s.TimeRejected): replace(approval, approver=actor.principal)
        with self.assertRaises(s.TimeRejected): replace(context, reservation_revision=True)
        with self.assertRaises(s.TimeRejected): replace(permit, valid_until_us=0)
        with self.assertRaises(s.TimeRejected): replace(activation, generation=0)
        with self.assertRaises(s.TimeRejected): replace(observation, activation=None)

    def test_import_boundary(self):
        tree = ast.parse((ROOT / 'services/api/infrastructure/fixture_lease_service.py').read_text())
        imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        self.assertEqual(imports, {'dataclasses', 'enum', 'fractions', 'hashlib', 'typing', 'fixture_lease_contract'})
        self.assertFalse(any(isinstance(node, ast.Import) for node in ast.walk(tree)))
        forbidden = {'open', 'eval', 'exec', '__import__'}
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                             and node.func.id in forbidden for node in ast.walk(tree)))

    def admission_fixture(self, kind=c.Command.ACQUIRE):
        raw=b'synthetic-canonical-command'
        cp=s.EvidenceReference('checkpoint',s.sha256(b'checkpoint').digest())
        activation=s.ActivationIdentity('g',1,'x','h',cp)
        context=s.CommandContext('c',s.sha256(raw).digest(),kind,c.Operation.FIXTURE_PROVISIONING,
                                 c.Phase.PRE_AUTH,0,self.ref)
        predecessor=s.ResolvedCheckpointEvidence(cp,b'checkpoint',activation,0,0,b'q'*32,b'w'*32,
                         'JOUS_CORE1A_STATE_REPRESENTATION_2',self.ref)
        permit=s.CommandPermit(context,activation,900,2000,self.ref)
        required=kind in (c.Command.ACQUIRE,c.Command.ADVANCE,c.Command.RELEASE,c.Command.RECOVER)
        approval=s.EvidenceReference('approval',b'a'*32) if required else None
        envelope=s.RetainedAdmissionEnvelope(self.ref,raw,context,'p',permit.evidence,activation,
            predecessor,s.ApprovalApplicability.REQUIRED if required else s.ApprovalApplicability.NOT_APPLICABLE,
            approval,1000,self.sample.utc,self.sample.validation,
            s.RetainedTimeFixing(self.ref,context,activation,self.sample,self.profile,self.anchor,self.error()))
        evidence=s.AdmissionEvidence(envelope,permit,self.sample,self.profile,self.anchor,self.error(),
                                    s.AdmissionCoverage(self.ref,envelope.reference,context,activation,self.anchor,self.sample.utc),
                                    s.InclusiveDeadline(2000),s.StrictDeadline(2000),
                                    s.EvidenceValidity.VALID,s.EvidenceValidity.VALID,
                                    s.TimingApplicability.REQUIRED,s.TimingApplicability.REQUIRED)
        facts=s.AdmissionFacts(raw,context,'p','g',1,'x','h',predecessor.representation,self.ref,
            0,b'q'*32,b'w'*32,False,None if kind is c.Command.ACQUIRE else 0,(),(self.ref,),b'a'*32,0,1000,1000)
        return evidence,facts

    def test_il5a_valid_required_and_not_applicable(self):
        for kind in (c.Command.ACQUIRE,c.Command.RECORD_EXECUTION,c.Command.QUARANTINE):
            evidence,facts=self.admission_fixture(kind)
            self.assertEqual(s.validate_admission(evidence,facts).disposition,s.AdmissionDisposition.ADMIT)
            with self.assertRaises(FrozenInstanceError):facts.generation=2

    def test_il5a_strict_numeric_and_decision_types(self):
        evidence,facts=self.admission_fixture()
        for kwargs in ({'generation':True},{'event_sequence':True},{'target_revision':True},
                       {'proposed_utc_us':1.0},{'last_valid_utc_us':True}):
            with self.assertRaises(s.TimeRejected):replace(facts,**kwargs)
        for args in ((True,None),(s.AdmissionDisposition.ADMIT,s.AdmissionReason.TIME),
                     (s.AdmissionDisposition.REJECT,None)):
            with self.assertRaises(s.TimeRejected):s.AdmissionDecision(*args)

    def test_il5a_binding_rejections(self):
        evidence,facts=self.admission_fixture()
        changes=({'principal':'other'},{'generation':2},{'activation_id':'other'},
            {'host_identity':'other'},{'state_digest':b'z'*32},{'event_sequence':1},
            {'representation':'unknown'},{'representation_authority':s.EvidenceReference('other',b'z'*32)},
            {'proposed_utc_us':999},{'recovery_required':True},{'target_revision':0})
        for kwargs in changes:
            with self.subTest(kwargs=kwargs):
                self.assertEqual(s.validate_admission(evidence,replace(facts,**kwargs)).disposition,
                                 s.AdmissionDisposition.REJECT)
        changed=replace(evidence,permit=replace(evidence.permit,evidence=s.EvidenceReference('other',b'z'*32)))
        self.assertEqual(s.validate_admission(changed,facts).reason,s.AdmissionReason.COMMAND)

    def test_il5a_permit_and_time_fail_closed(self):
        evidence,facts=self.admission_fixture()
        cases=(replace(evidence,permit=None),
            replace(evidence,permit_validity=s.EvidenceValidity.INVALID),
            replace(evidence,permit_validity=s.EvidenceValidity.UNKNOWN),
            replace(evidence,permit=replace(evidence.permit,valid_until_us=1000)),
            replace(evidence,permit=replace(evidence.permit,valid_until_us=1001)),
            replace(evidence,permit=replace(evidence.permit,valid_from_us=1001)),
            replace(evidence,admission_coverage=None),
            replace(evidence,current=replace(self.anchor,domain_id='restart')),
            replace(evidence,authorization_deadline=s.InclusiveDeadline(1001)),
            replace(evidence,freshness_deadline=s.StrictDeadline(1002)))
        for value in cases:
            self.assertEqual(s.validate_admission(value,facts).disposition,s.AdmissionDisposition.REJECT)
        self.assertEqual(s.validate_admission(evidence,replace(facts,last_valid_utc_us=1001)).reason,
                         s.AdmissionReason.TIME)

    def test_il5a_approval_and_utc_rejections(self):
        evidence,facts=self.admission_fixture()
        for kwargs in ({'approval':None},{'approval_applicability':s.ApprovalApplicability.UNKNOWN},
            {'approval_applicability':s.ApprovalApplicability.NOT_APPLICABLE,'approval':None},
            {'approval':s.EvidenceReference('approval',b'z'*32)}):
            changed=replace(evidence,envelope=replace(evidence.envelope,**kwargs))
            self.assertEqual(s.validate_admission(changed,facts).reason,s.AdmissionReason.APPROVAL)
        for validity in (s.EvidenceValidity.INVALID,s.EvidenceValidity.UNKNOWN):
            self.assertEqual(s.validate_admission(replace(evidence,approval_validity=validity),facts).reason,
                             s.AdmissionReason.APPROVAL)
        evidence,facts=self.admission_fixture(c.Command.RECORD_EXECUTION)
        changed=replace(evidence,envelope=replace(evidence.envelope,
            approval_applicability=s.ApprovalApplicability.REQUIRED,approval=self.ref))
        self.assertEqual(s.validate_admission(changed,facts).reason,s.AdmissionReason.APPROVAL)
        self.assertEqual(s.validate_admission(evidence,replace(facts,proposed_last_valid_utc_us=1001)).reason,
                         s.AdmissionReason.UTC)

    def candidate_fixture(self):
        evidence,_=self.admission_fixture()
        operation=s.OriginalOperation(evidence.permit.evidence,s.OperationKind.CHECKPOINT_PUBLICATION)
        raw=b'synthetic-prequalified-candidate'
        return s.CheckpointCandidate(raw,s.sha256(raw).digest(),evidence.envelope,operation,1,1000,1,b'e'*32,b'd'*32)

    def test_il5a_candidate_association_substitution(self):
        candidate=self.candidate_fixture()
        self.assertEqual(s.verify_candidate_association(candidate,candidate),candidate)
        for changed in (replace(candidate,exact_bytes=b'changed',sha256=s.sha256(b'changed').digest()),
                        replace(candidate,envelope=replace(candidate.envelope,principal='other'))):
            with self.assertRaises(s.TimeRejected):s.verify_candidate_association(candidate,changed)
        for kwargs in ({'revision':True},{'revision':2},{'fixed_utc_us':1001},{'event_sequence':True},{'event_sequence':0},{'sha256':b'z'*32},
                       {'operation':s.OriginalOperation(self.ref,s.OperationKind.PERMIT_COMPLETION)}):
            with self.assertRaises(s.TimeRejected):replace(candidate,**kwargs)

    def test_il5a_publication_outcomes_bind_exact_candidate(self):
        candidate=self.candidate_fixture()
        for outcome in s.ExternalOutcome:
            result=s.PublicationResult(outcome,candidate,self.ref if outcome is not s.ExternalOutcome.UNKNOWN else None)
            self.assertIs(s.verify_publication_result(candidate,result),result)
        for outcome in (s.ExternalOutcome.CONFIRMED,s.ExternalOutcome.DEFINITELY_REJECTED):
            with self.assertRaises(s.TimeRejected):s.PublicationResult(outcome,candidate,None)
        changed=replace(candidate,exact_bytes=b'other',sha256=s.sha256(b'other').digest())
        with self.assertRaises(s.TimeRejected):
            s.verify_publication_result(candidate,s.PublicationResult(s.ExternalOutcome.CONFIRMED,changed,self.ref))

    def test_il5a_completion_requires_confirmed_original_publication(self):
        candidate=self.candidate_fixture()
        operation=s.OriginalOperation(candidate.operation.permit,s.OperationKind.PERMIT_COMPLETION)
        publication=s.PublicationResult(s.ExternalOutcome.CONFIRMED,candidate,self.ref)
        for outcome in s.ExternalOutcome:
            result=s.CompletionResult(outcome,operation,publication,
                                     None if outcome is s.ExternalOutcome.UNKNOWN else self.ref)
            self.assertIs(s.verify_completion_result(operation,publication,result),result)
        for outcome in (s.ExternalOutcome.UNKNOWN,s.ExternalOutcome.DEFINITELY_REJECTED):
            with self.assertRaises(s.TimeRejected):
                s.CompletionResult(s.ExternalOutcome.UNKNOWN,operation,
                    s.PublicationResult(outcome,candidate,self.ref),None)
        wrong=s.OriginalOperation(s.EvidenceReference('wrong',b'z'*32),s.OperationKind.PERMIT_COMPLETION)
        with self.assertRaises(s.TimeRejected):s.CompletionResult(s.ExternalOutcome.CONFIRMED,wrong,publication,self.ref)

    def test_il5a_rejecting_defaults_never_create_success(self):
        default=s.RejectingNormalCapabilities();evidence,facts=self.admission_fixture();candidate=self.candidate_fixture()
        self.assertEqual(default(evidence,facts).disposition,s.AdmissionDisposition.REJECT)
        for name,args in (('resolve_predecessor',(evidence.envelope.activation,)),
            ('resolve_envelope',(facts.context,facts.principal,evidence.envelope.activation)),('associate_candidate',(candidate,)),
            ('publish_candidate',(candidate,))):
            with self.assertRaises(s.CapabilityUnavailable):getattr(default,name)(*args)
        publication=default.query_publication(candidate)
        self.assertEqual(publication.outcome,s.ExternalOutcome.UNKNOWN)
        publication=s.PublicationResult(s.ExternalOutcome.CONFIRMED,candidate,self.ref)
        operation=s.OriginalOperation(candidate.operation.permit,s.OperationKind.PERMIT_COMPLETION)
        with self.assertRaises(s.CapabilityUnavailable):default.complete_original(operation,publication)
        self.assertEqual(default.query_completion(operation,publication).outcome,s.ExternalOutcome.UNKNOWN)

    def test_il5a_queries_do_not_resubmit(self):
        class QueryOnly(s.RejectingNormalCapabilities):
            def publish_candidate(self,*args):raise AssertionError('submit')
            def complete_original(self,*args):raise AssertionError('complete')
        candidate=self.candidate_fixture();fake=QueryOnly()
        self.assertEqual(fake.query_publication(candidate).outcome,s.ExternalOutcome.UNKNOWN)
        publication=s.PublicationResult(s.ExternalOutcome.CONFIRMED,candidate,self.ref)
        operation=s.OriginalOperation(candidate.operation.permit,s.OperationKind.PERMIT_COMPLETION)
        self.assertEqual(fake.query_completion(operation,publication).outcome,s.ExternalOutcome.UNKNOWN)

    def test_il5a_published_candidate_byte_identity(self):
        doc=(ROOT/'docs/decisions/JOUS.CORE.1A.il5-normal-checkpoint-orchestration-amendment.md').read_text()
        raw=bytes.fromhex(doc.split('C_success: 460 bytes;',1)[1].split('```text\n',1)[1].split('\n```',1)[0])
        self.assertEqual(len(raw),460)
        self.assertEqual(s.sha256(raw).hexdigest(),'c976358de765d6337e3f8c8b48e9e62a7f43b7e5df21857ced144a297a06c7a7')

    def test_il5a_coverage_context_binding(self):
        evidence,facts=self.admission_fixture()
        coverage=evidence.admission_coverage
        for kwargs in ({'envelope':s.EvidenceReference('wrong',b'z'*32)},
                       {'context':replace(facts.context,command_id='wrong')},
                       {'activation':replace(evidence.envelope.activation,host_identity='wrong')},
                       {'point':replace(self.anchor,ticks_ns=101)},
                       {'interval':s.UtcInterval(1000,1001)}):
            self.assertEqual(s.validate_admission(replace(evidence,admission_coverage=replace(coverage,**kwargs)),facts).reason,
                             s.AdmissionReason.COVERAGE)

    def test_il5a_candidate_operation_and_result_mismatch(self):
        candidate=self.candidate_fixture()
        wrong=s.OriginalOperation(s.EvidenceReference('wrong',b'z'*32),s.OperationKind.CHECKPOINT_PUBLICATION)
        with self.assertRaises(s.TimeRejected):replace(candidate,operation=wrong)
        for kwargs in ({'activation':replace(candidate.envelope.activation,activation_id='wrong')},
                       {'approval_applicability':s.ApprovalApplicability.UNKNOWN}):
            with self.assertRaises(s.TimeRejected):replace(candidate,envelope=replace(candidate.envelope,**kwargs))
        confirmed=s.PublicationResult(s.ExternalOutcome.CONFIRMED,candidate,self.ref)
        operation=s.OriginalOperation(candidate.operation.permit,s.OperationKind.PERMIT_COMPLETION)
        result=s.CompletionResult(s.ExternalOutcome.CONFIRMED,operation,confirmed,self.ref)
        with self.assertRaises(s.TimeRejected):s.verify_completion_result(candidate.operation,confirmed,result)
        substituted=replace(candidate,state_digest=b'z'*32)
        with self.assertRaises(s.TimeRejected):
            s.verify_completion_result(operation,s.PublicationResult(s.ExternalOutcome.CONFIRMED,substituted,self.ref),result)

    def test_il5a_timing_not_applicable_is_distinct_from_unknown(self):
        evidence,facts=self.admission_fixture()
        for changed in (replace(evidence,authorization_deadline=None),
                        replace(evidence,authorization_timing=s.TimingApplicability.UNKNOWN),
                        replace(evidence,freshness_timing=s.TimingApplicability.UNKNOWN),
                        replace(evidence,freshness_timing=s.TimingApplicability.NOT_APPLICABLE)):
            self.assertEqual(s.validate_admission(changed,facts).disposition,s.AdmissionDisposition.REJECT)
        changed=replace(evidence,authorization_deadline=None,freshness_deadline=None,
            authorization_timing=s.TimingApplicability.NOT_APPLICABLE,freshness_timing=s.TimingApplicability.NOT_APPLICABLE)
        self.assertEqual(s.validate_admission(changed,facts).disposition,s.AdmissionDisposition.ADMIT)

    def refreshed_admission_fixture(self):
        evidence,facts=self.admission_fixture()
        fixing=evidence.envelope.fixing
        sample=replace(fixing.sample,sample=s.EvidenceReference('refresh',b'r'*32),
            validation=s.EvidenceReference('current-validation',b'v'*32),
            utc=s.UtcInterval(1001,1003),anchor=replace(fixing.sample.anchor,ticks_ns=1100))
        current=replace(sample.anchor,ticks_ns=2100)
        old_error=s.QualifiedPropagationError(fixing.sample.sample,fixing.sample.profile,1000,0,self.ref)
        propagation=s.QualifiedPropagationError(sample.sample,sample.profile,1000,0,self.ref)
        interval=s.evaluate_time(sample,evidence.profile,current,propagation).interval
        refreshed=replace(evidence,sample=sample,current=current,propagation=propagation,
            fixing_to_refresh=old_error,admission_coverage=replace(evidence.admission_coverage,
                point=current,interval=interval))
        return refreshed,replace(facts,proposed_last_valid_utc_us=interval.lower_us)

    def test_il5a_refresh_distinct_current_qualification_admits(self):
        evidence,facts=self.refreshed_admission_fixture();original=evidence.envelope
        self.assertNotEqual(original.time_qualification,evidence.sample.validation)
        self.assertTrue(s.refresh_consistent(original.fixing.sample,evidence.sample,
                                             evidence.profile,evidence.fixing_to_refresh))
        self.assertEqual(s.validate_admission(evidence,facts).disposition,s.AdmissionDisposition.ADMIT)
        self.assertEqual(original.fixed_utc_us,1000)
        self.assertEqual(original.time_qualification,self.sample.validation)
        self.assertIs(evidence.envelope,original)
        self.assertEqual(original.fixing.sample,self.sample)

    def test_il5a_refresh_inconsistency_rejects(self):
        evidence,facts=self.refreshed_admission_fixture()
        sample=replace(evidence.sample,utc=s.UtcInterval(1500,1502))
        interval=s.evaluate_time(sample,evidence.profile,evidence.current,evidence.propagation).interval
        invalid=replace(evidence,sample=sample,admission_coverage=replace(evidence.admission_coverage,interval=interval))
        self.assertFalse(s.refresh_consistent(evidence.envelope.fixing.sample,sample,
                                              evidence.profile,evidence.fixing_to_refresh))
        self.assertEqual(s.validate_admission(invalid,replace(facts,proposed_last_valid_utc_us=interval.lower_us)).disposition,
                         s.AdmissionDisposition.REJECT)

    def test_il5a_refresh_domain_coverage_fixed_utc_and_original_chain_reject(self):
        evidence,facts=self.refreshed_admission_fixture();fixing=evidence.envelope.fixing
        variants=(replace(evidence,current=replace(evidence.current,domain_id='restart')),
            replace(evidence,admission_coverage=None),
            replace(evidence,envelope=replace(evidence.envelope,fixed_utc_us=1001,fixing_interval=s.UtcInterval(1001,1003))),
            replace(evidence,envelope=replace(evidence.envelope,time_qualification=evidence.sample.validation)),
            replace(evidence,envelope=replace(evidence.envelope,reference=s.EvidenceReference('mutated',b'z'*32))),
            replace(evidence,envelope=replace(evidence.envelope,fixing=None)),
            replace(evidence,envelope=replace(evidence.envelope,fixing=replace(fixing,
                context=replace(fixing.context,command_id='other')))),
            replace(evidence,envelope=replace(evidence.envelope,fixing=replace(fixing,
                activation=replace(fixing.activation,host_identity='other')))))
        for invalid in variants:
            with self.subTest(invalid=variants.index(invalid)):
                self.assertEqual(s.validate_admission(invalid,facts).disposition,s.AdmissionDisposition.REJECT)
        malformed=replace(fixing.propagation,sample=s.EvidenceReference('wrong-sample',b'z'*32))
        invalid=replace(evidence,envelope=replace(evidence.envelope,fixing=replace(fixing,propagation=malformed)))
        self.assertEqual(s.validate_admission(invalid,facts).disposition,s.AdmissionDisposition.REJECT)

    def test_il5a_refresh_current_qualification_consistency_proof_and_bounds_reject(self):
        evidence,facts=self.refreshed_admission_fixture()
        variants=(replace(evidence,fixing_to_refresh=None),
            replace(evidence,propagation=replace(evidence.propagation,sample=evidence.envelope.fixing.sample.sample)),
            replace(evidence,sample=replace(evidence.sample,profile=s.EvidenceReference('wrong',b'z'*32))),
            replace(evidence,authorization_deadline=s.InclusiveDeadline(1003)),
            replace(evidence,freshness_deadline=s.StrictDeadline(1004)),
            replace(evidence,permit=replace(evidence.permit,valid_until_us=1003)))
        for invalid in variants:
            self.assertEqual(s.validate_admission(invalid,facts).disposition,s.AdmissionDisposition.REJECT)


if __name__ == '__main__':
    unittest.main(verbosity=2)
