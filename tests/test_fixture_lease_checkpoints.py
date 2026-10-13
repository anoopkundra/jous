"""Synthetic offline IL.5B codec/binding tests. No providers or storage."""
import ast
from dataclasses import replace
from hashlib import sha256
import importlib.util
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
fixture_module = runpy.run_path(str(ROOT / 'tests/test_fixture_lease_protocol.py'))
p = fixture_module['p']
c = fixture_module['c']
sys.modules['fixture_lease_contract'] = c
for name in ('fixture_lease_service', 'fixture_lease_checkpoints'):
    spec = importlib.util.spec_from_file_location('_il4a_pure.' + name,
        ROOT / 'services/api/infrastructure' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
s = sys.modules['_il4a_pure.fixture_lease_service']
q = sys.modules['_il4a_pure.fixture_lease_checkpoints']
doc = (ROOT / 'docs/decisions/JOUS.CORE.1A.il5-normal-checkpoint-orchestration-amendment.md').read_text()


def vector(label):
    return bytes.fromhex(doc.split(label + ': ', 1)[1].split('```text\n', 1)[1].split('\n```', 1)[0])


N = vector('N_c reference')
FIRST = vector('C_success')
D = vector('COMMAND d')
E4 = vector('EVENT 4')
E5 = vector('EVENT 5')
ACK = vector('ACK d')
SECOND = vector('C_not_applicable')


def import_boundary(tree):
    expected = {(0, 'dataclasses', (('dataclass', None),)),
                (0, 'hashlib', (('sha256', None),)),
                (1, None, (('fixture_lease_protocol', 'p'),)),
                (1, None, (('fixture_lease_service', 'service'),))}
    observed = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): return False
        if isinstance(node, ast.ImportFrom):
            observed.append((node.level, node.module, tuple((a.name, a.asname) for a in node.names)))
    return len(observed) == len(expected) and set(observed) == expected


class CheckpointsTests(unittest.TestCase):
    def setUp(self):
        values = fixture_module['fixtures']()
        # Published fixture function returns a named mapping; no DB involved.
        self.values = values

    def material(self):
        # Reconstruct the exact published STATE delta, with retained successful d.
        values = self.values
        completed = values['completed']
        context = values['context']
        command = p.decode_record(D, p.CommandPayload)
        ack = p.decode_record(ACK, p.AckPayload)
        row = p.CommandRow('d', 'p', command.command_kind, D, sha256(D).digest(), 0,
                           'r', p.OutcomeCode.SUCCESS, ACK, 5)
        projection = p.StateProjection(replace(completed.metadata, last_valid_utc=1),
            (replace(completed.reservations[0], revision=1, execution_state=p.ExecutionState.STARTED),),
            completed.claims, completed.commands + (row,))
        checkpoint = q.decode_checkpoint(FIRST)
        cp = s.EvidenceReference('predecessor', sha256(FIRST).digest())
        activation = s.ActivationIdentity('g', 1, 'x', 'h', cp)
        authority = s.EvidenceReference('state-authority', b'\x55' * 32)
        prior = s.ResolvedCheckpointEvidence(cp, FIRST, activation, checkpoint.revision,
            checkpoint.event_sequence, checkpoint.event_digest, checkpoint.state_digest, p.STATE_2, authority)
        command_context = s.CommandContext('d', sha256(D).digest(), command.command_kind,
            command.operation, command.phase, command.expected_revision,
            s.EvidenceReference('z', b'\x22' * 32))
        permit = s.EvidenceReference('p2', b'\x99' * 32)
        envelope = s.RetainedAdmissionEnvelope(s.EvidenceReference('admission2', b'\xaa' * 32),
            D, command_context, 'p', permit, activation, prior,
            s.ApprovalApplicability.NOT_APPLICABLE, None, 1, s.UtcInterval(1, 1),
            s.EvidenceReference('original-fixing', b'f' * 32))
        head = q.CommittedHead(5, sha256(E5).digest(), p.state_digest(projection, context))
        operation = s.OriginalOperation(permit, s.OperationKind.CHECKPOINT_PUBLICATION)
        return [envelope, row, (p.decode_record(E4, p.EventPayload), p.decode_record(E5, p.EventPayload)),
                projection, context, head, operation]

    def candidate(self, material=None):
        return q.construct_candidate(*(self.material() if material is None else material), keys=())

    def test_seven_authority_vectors(self):
        expected = ((N,253,'f4792a0f8e77ec375e0467b0bb114300d606442f0130dfd41834f2e2fee2e4f3'),
            (FIRST,460,'c976358de765d6337e3f8c8b48e9e62a7f43b7e5df21857ced144a297a06c7a7'),
            (D,785,'cb000e52112b845e91abe827de5a716a64d539d6156129becd71802d2e7e2ba5'),
            (E4,163,'1a51e72405b19119dedbfbe2ebc2c6b242f87eff66b47aac91823a792be8c47c'),
            (E5,157,'3438dfeb7c037b8e861853cceae16cedba86c2fae9c6a4d0f049227100acda99'),
            (ACK,616,'4dab1c70efb3feb69042b397708537411a0c2b119426016669c79122c04dfe80'),
            (SECOND,454,'1fea19201a0f738c8b014c2c2d56e5edeec88055c942361fdbdfbdcf6445e7cc'))
        for raw, length, digest in expected:
            self.assertEqual(len(raw), length); self.assertEqual(sha256(raw).hexdigest(), digest)
        self.assertEqual(q.reference_bytes(q.decode_reference(N)), N)
        for raw in (FIRST, SECOND): self.assertEqual(q.checkpoint_bytes(q.decode_checkpoint(raw)), raw)
        for raw, cls in ((D,p.CommandPayload),(E4,p.EventPayload),(E5,p.EventPayload),(ACK,p.AckPayload)):
            self.assertEqual(p.encode_record(p.decode_record(raw,cls)),raw)

    def test_linked_state_and_constructed_vector(self):
        material = self.material()
        raw = p.state_bytes(material[3], material[4])
        self.assertEqual(len(raw), 3415)
        self.assertEqual(sha256(raw).hexdigest(), 'eaf7f9378718deb706e74a9910fc3e7520cc0bffa6852eb0efebbc4bb39ef1c3')
        self.assertEqual(self.candidate(material).exact_bytes, SECOND)

    def test_independent_normal_reference_and_successor_encoding(self):
        reference=q.NormalReference('c',p.command_digest(self.values['command']),
            'p',b'\x44'*32,'h',p.STATE_2,'state-authority',b'\x55'*32,'admission',b'\x66'*32)
        self.assertEqual(q.reference_bytes(reference),N)
        ack=self.values['ack']
        checkpoint=q.NormalCheckpoint('g',1,'x',1,3,ack.final_event_digest,
            p.state_digest(self.values['completed'],self.values['context']),0,b'\x33'*32,reference,'approval')
        self.assertEqual(q.checkpoint_bytes(checkpoint),FIRST)

    def test_reference_bad_frames(self):
        for raw in (b'',N[:-1],N+b'0',N[:18]+b'\x07'+N[19:],N[:19]+b'\x00\x00\x00\x09'+N[23:]):
            with self.assertRaises(p.ProtocolRejected): q.decode_reference(raw)

    def test_reference_field_domains(self):
        fields = list(p.parse_frame(N,1,18,10))
        for index, bad in ((0,b''),(0,b' '),(0,b'\xff'),(1,b'x'*31),(3,b'x'*33),(5,b'UNKNOWN')):
            changed=fields.copy();changed[index]=bad
            with self.assertRaises(p.ProtocolRejected):q.decode_reference(p.frame(1,18,changed))

    def test_checkpoint_bad_frames(self):
        for raw in (b'',FIRST[:-1],FIRST+b'0',FIRST[:18]+b'\x12'+FIRST[19:]):
            with self.assertRaises(p.ProtocolRejected): q.decode_checkpoint(raw)

    def test_checkpoint_scalar_and_optional_domains(self):
        fields=list(p.parse_frame(FIRST,1,7,11))
        for index,bad in ((1,b'\x01'),(1,b'\xff'*8),(3,b'\x00'*8),(4,b'\x00'*8),
                          (5,b'x'*31),(7,b'x'*7),(10,b''),(10,b'\x02x'),(10,b'\x00x'),(10,b'\x01')):
            changed=fields.copy();changed[index]=bad
            with self.assertRaises(p.ProtocolRejected):q.decode_checkpoint(p.frame(1,7,changed))

    def test_bool_and_integer_bounds(self):
        value=q.decode_checkpoint(FIRST)
        for name in ('generation','revision','event_sequence','utc_us'):
            for bad in (True,1.0,p.MAX_UINT+1):
                with self.assertRaises(p.ProtocolRejected):replace(value,**{name:bad})

    def test_deterministic_reconstruction(self):
        first=self.candidate();second=self.candidate()
        self.assertEqual(first,second)
        self.assertEqual(first.revision,2);self.assertEqual(first.fixed_utc_us,1)
        self.assertEqual(q.validate_candidate(first,*self.material(),keys=()),first)

    def test_candidate_substitution(self):
        candidate=self.candidate()
        for bad in (replace(candidate,exact_bytes=b'other',sha256=sha256(b'other').digest()),
                    replace(candidate,state_digest=b'x'*32),
                    replace(candidate,envelope=replace(candidate.envelope,principal='other'))):
            with self.assertRaises((p.ProtocolRejected,s.TimeRejected)):
                q.validate_candidate(bad,*self.material(),keys=())

    def test_predecessor_metadata_mismatch(self):
        for name,bad in (('revision',2),('event_sequence',2),('event_digest',b'x'*32),('state_digest',b'x'*32)):
            material=self.material();e=material[0]
            material[0]=replace(e,predecessor=replace(e.predecessor,**{name:bad}))
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_revision_overflow(self):
        material=self.material();e=material[0];prior=q.decode_checkpoint(FIRST)
        raw=q.checkpoint_bytes(replace(prior,revision=p.MAX_UINT));ref=s.EvidenceReference('predecessor',sha256(raw).digest())
        activation=replace(e.activation,checkpoint=ref)
        predecessor=replace(e.predecessor,reference=ref,exact_bytes=raw,revision=p.MAX_UINT,activation=activation)
        material[0]=replace(e,activation=activation,predecessor=predecessor)
        with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_command_envelope_substitution(self):
        for name,bad in (('principal','other'),('context',replace(self.material()[0].context,command_id='other'))):
            material=self.material();material[0]=replace(material[0],**{name:bad})
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_command_malformed_retention(self):
        material=self.material();row=material[1];raw=b'bad'
        material[1]=replace(row,canonical_payload_bytes=raw,canonical_payload_hash=sha256(raw).digest())
        with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_event_chain_substitution(self):
        for field,bad in (('prior_digest',b'x'*32),('event_sequence',9),('command_id','other'),('utc_time',2)):
            material=self.material();material[2]=(replace(material[2][0],**{field:bad}),material[2][1])
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_ack_substitution(self):
        for field,bad in (('command_id','other'),('final_event_digest',b'x'*32),('issued_at',2),('principal','other')):
            material=self.material();ack=p.decode_record(ACK,p.AckPayload)
            material[1]=replace(material[1],durable_ack_bytes=p.ack_bytes(replace(ack,**{field:bad})))
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_head_and_state_substitution(self):
        for field,bad in (('event_sequence',6),('event_digest',b'x'*32),('state_digest',b'x'*32)):
            material=self.material();material[5]=replace(material[5],**{field:bad})
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_representation_binding_substitution(self):
        material=self.material();material[4]=replace(material[4],representation=p.STATE_1)
        with self.assertRaises(p.ProtocolRejected):self.candidate(material)
        material=self.material();e=material[0]
        material[0]=replace(e,predecessor=replace(e.predecessor,
            representation_authority=s.EvidenceReference('other',b'x'*32)))
        with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_fixed_utc_substitution(self):
        material=self.material();material[0]=replace(material[0],fixed_utc_us=2,fixing_interval=s.UtcInterval(2,2))
        with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_approval_unknown_and_unexpected_presence(self):
        for applicability,approval in ((s.ApprovalApplicability.UNKNOWN,None),
            (s.ApprovalApplicability.REQUIRED,s.EvidenceReference('approval',b'x'*32))):
            material=self.material();material[0]=replace(material[0],approval_applicability=applicability,approval=approval)
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_host_and_operation_substitution(self):
        material=self.material();e=material[0];activation=replace(e.activation,host_identity='other')
        material[0]=replace(e,activation=activation,predecessor=replace(e.predecessor,activation=activation))
        with self.assertRaises(p.ProtocolRejected):self.candidate(material)
        for operation in (s.OriginalOperation(s.EvidenceReference('other',b'x'*32),s.OperationKind.CHECKPOINT_PUBLICATION),
                          s.OriginalOperation(self.material()[0].permit_reference,s.OperationKind.PERMIT_COMPLETION)):
            material=self.material();material[6]=operation
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_large_state_one_pass(self):
        material=self.material();projection=material[3]
        class Once:
            def __init__(self):self.used=False
            def __iter__(self):
                if self.used:raise AssertionError('second pass')
                self.used=True
                for i in range(4098):
                    identity='a%05d'%i
                    original=projection.commands[0]
                    command=replace(p.decode_record(original.canonical_payload_bytes,p.CommandPayload),command_id=identity)
                    ack=replace(p.decode_record(original.durable_ack_bytes,p.AckPayload),command_id=identity,
                                command_payload_sha256=p.command_digest(command))
                    yield replace(original,command_id=identity,canonical_payload_bytes=p.command_bytes(command),
                                  canonical_payload_hash=p.command_digest(command),durable_ack_bytes=p.ack_bytes(ack))
                yield material[1]
        def state():return p.StateProjection(projection.metadata,projection.reservations,projection.claims,Once())
        digest=p.state_digest(state(),material[4]);material[3]=state();material[5]=replace(material[5],state_digest=digest)
        candidate=self.candidate(material)
        self.assertEqual(candidate.state_digest,digest)

    def test_complete_command_required_in_state(self):
        material=self.material();material[3]=replace(material[3],commands=())
        material[5]=replace(material[5],state_digest=p.state_digest(material[3],material[4]))
        with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_architecture_and_purity(self):
        source=(ROOT/'services/api/infrastructure/fixture_lease_checkpoints.py').read_text()
        tree=ast.parse(source);self.assertTrue(import_boundary(tree))
        for module in ('fixture_lease_commands','fixture_lease_store','provider','sqlite3','requests','runtime_config'):
            bad=ast.parse(source+'\nfrom .'+module+' import value\n')
            self.assertFalse(import_boundary(bad))
        forbidden={'open','connect','getenv','now','time','sleep','publish','complete','obtain','execute','run'}
        for node in ast.walk(tree):
            if isinstance(node,ast.Call):
                name=node.func.id if isinstance(node.func,ast.Name) else getattr(node.func,'attr','')
                self.assertNotIn(name,forbidden)

    def acquire_material(self):
        material=self.material();envelope=material[0]
        command=replace(self.values['command'],command_id='e',
                        parameters=replace(self.values['command'].parameters,target_reservation_id='r2'))
        prior=envelope.predecessor.event_digest;events=[]
        for sequence,kind in enumerate(p.event_order(c.Command.ACQUIRE),4):
            event=p.EventPayload(sequence,'e','r2','g',1,'x',kind,1,prior,0,'a',None)
            events.append(event);prior=p.event_digest(event)
        ack=replace(self.values['ack'],command_id='e',command_payload_sha256=p.command_digest(command),
                    reservation_id='r2',issued_at=1,first_event_sequence=4,final_event_sequence=6,final_event_digest=prior)
        row=p.CommandRow('e','p',c.Command.ACQUIRE,p.command_bytes(command),p.command_digest(command),0,
                         'r2',p.OutcomeCode.SUCCESS,p.ack_bytes(ack),6)
        reservation=replace(self.values['completed'].reservations[0],reservation_id='r2')
        projection=replace(material[3],reservations=self.values['completed'].reservations+(reservation,),
                           commands=self.values['completed'].commands+(row,))
        context=s.CommandContext('e',p.command_digest(command),command.command_kind,command.operation,
                                  command.phase,0,envelope.context.authorization)
        material[0]=replace(envelope,canonical_command_bytes=p.command_bytes(command),context=context,
            approval_applicability=s.ApprovalApplicability.REQUIRED,
            approval=s.EvidenceReference('approval',command.approval_record_hash))
        material[1]=row;material[2]=tuple(events);material[3]=projection
        material[5]=q.CommittedHead(6,prior,p.state_digest(projection,material[4]))
        return material

    def test_required_approval_and_new_acquire(self):
        material=self.acquire_material();candidate=self.candidate(material)
        self.assertEqual(q.decode_checkpoint(candidate.exact_bytes).approval_id,'approval')
        for approval in (None,s.EvidenceReference('approval',b'x'*32)):
            bad=self.acquire_material();bad[0]=replace(bad[0],approval=approval)
            with self.assertRaises(p.ProtocolRejected):self.candidate(bad)

    def test_context_operation_revision_substitutions(self):
        for kwargs in ({'command_id':'other'},{'payload_sha256':b'x'*32},
                       {'reservation_revision':1},{'operation':c.Operation.CANARY},
                       {'phase':c.Phase.AUTH_IDENTITIES_BOUND}):
            material=self.material()
            with self.assertRaises((p.ProtocolRejected,s.TimeRejected)):
                material[0]=replace(material[0],context=replace(material[0].context,**kwargs))
                self.candidate(material)

    def test_permit_admission_and_host_candidate_substitution(self):
        candidate=self.candidate()
        for field in ('permit_reference','reference'):
            material=self.material();envelope=replace(material[0],**{field:s.EvidenceReference('other',b'x'*32)})
            material[0]=envelope
            if field=='permit_reference':material[6]=s.OriginalOperation(envelope.permit_reference,s.OperationKind.CHECKPOINT_PUBLICATION)
            with self.assertRaises((p.ProtocolRejected,s.TimeRejected)):
                q.validate_candidate(candidate,*material,keys=())

    def test_incoherent_reservation_and_claim_state(self):
        for kwargs in ({'revision':2},{'owner':'other'},{'binding_artifact_id':'other'}):
            material=self.material();projection=material[3]
            material[3]=replace(projection,reservations=(replace(projection.reservations[0],**kwargs),))
            material[5]=replace(material[5],state_digest=p.state_digest(material[3],material[4]))
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)
        material=self.material();material[3]=replace(material[3],reservations=())
        material[5]=replace(material[5],state_digest=p.state_digest(material[3],material[4]))
        with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_wrong_counts_and_unsupported_profiles(self):
        for raw,tag,count,decoder in ((N,18,10,q.decode_reference),(FIRST,7,11,q.decode_checkpoint)):
            fields=p.parse_frame(raw,1,tag,count)
            for changed in (fields[:-1],fields+(b'x',)):
                with self.assertRaises(p.ProtocolRejected):decoder(p.frame(1,tag,changed))
        checkpoint=q.decode_checkpoint(FIRST)
        for kwargs in ({'revision':0},{'event_sequence':0}):
            with self.assertRaises(p.ProtocolRejected):replace(checkpoint,**kwargs)

    def test_exact_byte_identity_not_hash_only(self):
        candidate=self.candidate()
        with self.assertRaises(s.TimeRejected):replace(candidate,exact_bytes=b'other')
        changed=replace(candidate,exact_bytes=b'other',sha256=sha256(b'other').digest())
        with self.assertRaises((p.ProtocolRejected,s.TimeRejected)):
            q.validate_candidate(changed,*self.material(),keys=())

    def test_state_claims_must_equal_ack_keys(self):
        material=self.material()
        key=c.frame_conflict(c.ConflictFamily.FIXTURE_SET,(b'target',b'set'))
        claim=p.ClaimRow(key,'r',0,'a')
        material[3]=replace(material[3],claims=(claim,))
        material[5]=replace(material[5],state_digest=p.state_digest(material[3],material[4]))
        with self.assertRaises(p.ProtocolRejected):self.candidate(material)

    def test_checkpoint_utf8_and_field_boundaries(self):
        fields=list(p.parse_frame(FIRST,1,7,11))
        for raw in (b'\xff',b'',b' '*2,b'x'*256):
            changed=fields.copy();changed[0]=raw
            with self.assertRaises(p.ProtocolRejected):q.decode_checkpoint(p.frame(1,7,changed))
        # Decoder consumes the frozen per-field bound; a forged length is not normalized.
        forged=p.PREFIX+b'\x01\x07'+p.u32(11)+p.u32(65536)+b'x'*65536
        with self.assertRaises(p.ProtocolRejected):q.decode_checkpoint(forged)

    def test_utc_codec_signed_endpoints(self):
        value=q.decode_checkpoint(FIRST)
        for utc in (-(1<<63),p.MAX_UINT):
            changed=replace(value,utc_us=utc)
            self.assertEqual(q.decode_checkpoint(q.checkpoint_bytes(changed)),changed)
        for utc in (-(1<<63)-1,p.MAX_UINT+1):
            with self.assertRaises(p.ProtocolRejected):replace(value,utc_us=utc)

    def directed_material(self, kind=c.Command.RECORD_EXECUTION, execution=p.ExecutionState.STARTED):
        material=self.material();command=p.decode_record(D,p.CommandPayload)
        primary=command.parameters.primary_evidence_reference
        if kind==c.Command.RELEASE:primary=replace(primary,artifact_type=c.ArtifactType.RELEASE_EVIDENCE)
        if kind==c.Command.RECOVER:primary=replace(primary,artifact_type=c.ArtifactType.RECOVERY_EVIDENCE)
        reason=p.QuarantineReason.EVIDENCE_MISMATCH if kind==c.Command.QUARANTINE else None
        parameters=replace(command.parameters,execution_state=execution if kind==c.Command.RECORD_EXECUTION else None,
            quarantine_reason=reason,primary_evidence_reference=primary,supporting_refs=(primary,))
        command=replace(command,command_kind=kind,parameters=parameters,evidence_references=(primary,))
        raw=p.command_bytes(command);prior=material[0].predecessor.event_digest;events=[]
        for sequence,event_type in enumerate(p.event_order(kind),4):
            event=replace(material[2][0],event_sequence=sequence,event_type=event_type,prior_digest=prior)
            events.append(event);prior=p.event_digest(event)
        ack=replace(p.decode_record(ACK,p.AckPayload),command_payload_sha256=sha256(raw).digest(),
            evidence_references=(primary,),final_event_sequence=events[-1].event_sequence,
            event_count=len(events),final_event_digest=prior)
        row=replace(material[1],command_kind=kind,canonical_payload_bytes=raw,canonical_payload_hash=sha256(raw).digest(),
                    durable_ack_bytes=p.ack_bytes(ack),transition_event_sequence=events[-1].event_sequence)
        envelope=material[0];required=kind in (c.Command.RELEASE,c.Command.RECOVER)
        material[0]=replace(envelope,canonical_command_bytes=raw,
            context=replace(envelope.context,command=kind,payload_sha256=sha256(raw).digest()),
            approval_applicability=s.ApprovalApplicability.REQUIRED if required else s.ApprovalApplicability.NOT_APPLICABLE,
            approval=s.EvidenceReference('approval',command.approval_record_hash) if required else None)
        reservation=material[3].reservations[0]
        if kind==c.Command.RECORD_EXECUTION:reservation=replace(reservation,execution_state=execution)
        if kind==c.Command.QUARANTINE:reservation=replace(reservation,lease_status=c.LeaseStatus.QUARANTINED,quarantine_reason=reason)
        if kind==c.Command.RELEASE:reservation=replace(reservation,lease_status=c.LeaseStatus.RELEASED,release_evidence_artifact_id=primary.artifact_id)
        if kind==c.Command.RECOVER:reservation=replace(reservation,lease_status=c.LeaseStatus.RELEASED,recovery_evidence_artifact_id=primary.artifact_id)
        material[1]=row;material[2]=tuple(events)
        material[3]=replace(material[3],reservations=(reservation,),commands=(material[3].commands[0],row))
        material[5]=q.CommittedHead(ack.final_event_sequence,prior,p.state_digest(material[3],material[4]))
        return material

    def assert_direct_mismatch(self,material,**changes):
        row=replace(material[3].reservations[0],**changes)
        material[3]=replace(material[3],reservations=(row,))
        material[5]=replace(material[5],state_digest=p.state_digest(material[3],material[4]))
        # Prove frozen completion passes, and rejection originates at the new
        # equality check on a valid, fully rehashed STATE target.
        with patch.object(q,'_command_result_coherent',wraps=q._command_result_coherent) as probe:
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)
            probe.assert_called_once()
            self.assertEqual(probe.call_args.args[1],row)

    def test_il5b01_started_unknown_recomputed_reviewer_case(self):
        material=self.material()
        self.assert_direct_mismatch(material,execution_state=p.ExecutionState.UNKNOWN)
        self.assertEqual(material[5].state_digest,p.state_digest(material[3],material[4]))

    def test_execution_directed_positive_states(self):
        for execution in p.ExecutionState:
            self.assertEqual(self.candidate(self.directed_material(execution=execution)).fixed_utc_us,1)

    def test_execution_directed_negative_states_rehashed(self):
        for expected,actual in ((p.ExecutionState.STARTED,p.ExecutionState.STOPPED_KNOWN),
                               (p.ExecutionState.STOPPED_KNOWN,p.ExecutionState.STARTED)):
            self.assert_direct_mismatch(self.directed_material(execution=expected),execution_state=actual)

    def test_authorization_reference_directed_result(self):
        self.candidate(self.material())
        self.assert_direct_mismatch(self.material(),authorization_ref='other')

    def test_acquire_owner_directed_result(self):
        material=self.acquire_material();self.candidate(material)
        # Change both ACK owner and STATE owner: existing ACK/STATE owner equality
        # still holds, so only direct command principal equality rejects.
        material=self.acquire_material();ack=p.decode_record(material[1].durable_ack_bytes,p.AckPayload)
        material[1]=replace(material[1],durable_ack_bytes=p.ack_bytes(replace(ack,owner='other')))
        projection=material[3];row=replace(projection.reservations[1],owner='other')
        material[3]=replace(projection,reservations=(projection.reservations[0],row),commands=(projection.commands[0],material[1]))
        material[5]=replace(material[5],state_digest=p.state_digest(material[3],material[4]))
        with patch.object(q,'_command_result_coherent',wraps=q._command_result_coherent) as probe:
            with self.assertRaises(p.ProtocolRejected):self.candidate(material)
            probe.assert_called_once();self.assertEqual(probe.call_args.args[1],row)

    def test_quarantine_reason_directed_result(self):
        material=self.directed_material(c.Command.QUARANTINE);self.candidate(material)
        self.assert_direct_mismatch(self.directed_material(c.Command.QUARANTINE),
                                    quarantine_reason=p.QuarantineReason.CLOCK_UNCERTAIN)

    def test_release_evidence_directed_result(self):
        self.candidate(self.directed_material(c.Command.RELEASE))
        self.assert_direct_mismatch(self.directed_material(c.Command.RELEASE),release_evidence_artifact_id='other')

    def test_recovery_evidence_directed_result(self):
        self.candidate(self.directed_material(c.Command.RECOVER))
        self.assert_direct_mismatch(self.directed_material(c.Command.RECOVER),recovery_evidence_artifact_id='other')


if __name__ == '__main__':unittest.main(verbosity=2)
