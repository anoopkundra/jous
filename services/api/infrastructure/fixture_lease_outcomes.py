"""IL.5C pure outcome knowledge and in-memory recovery handoff descriptions.

Inputs come from separately qualified sources. Construction does not qualify
evidence or prove retention. No action is performed or operationally authorized.
Later refined knowledge cannot clear a fence or replace IL.7 resumption authority.
"""
from dataclasses import dataclass
from enum import StrEnum

from . import fixture_lease_service as service


class LocalCommitState(StrEnum):
    CONFIRMED = 'CONFIRMED'
    UNKNOWN = 'UNKNOWN'
    NOT_COMMITTED = 'NOT_COMMITTED'


class Stage(StrEnum):
    PUBLICATION = 'PUBLICATION'
    COMPLETION = 'COMPLETION'


class RequiredGate(StrEnum):
    ORIGINAL_COMPLETION = 'ORIGINAL_COMPLETION'
    CURRENT_DELIVERY_QUALIFICATION = 'CURRENT_DELIVERY_QUALIFICATION'
    RECOVERY_HANDOFF = 'RECOVERY_HANDOFF'


class Reason(StrEnum):
    NEXT_GATE = 'NEXT_GATE'
    DEFINITELY_REJECTED = 'DEFINITELY_REJECTED'
    UNKNOWN = 'UNKNOWN'
    MISSING = 'MISSING'
    MALFORMED = 'MALFORMED'
    BINDING_MISMATCH = 'BINDING_MISMATCH'
    UNQUALIFIED = 'UNQUALIFIED'
    PUBLICATION_NOT_CONFIRMED = 'PUBLICATION_NOT_CONFIRMED'
    LOCAL_COMMIT_NOT_CONFIRMED = 'LOCAL_COMMIT_NOT_CONFIRMED'
    PRIOR_FENCE = 'PRIOR_FENCE'


@dataclass(frozen=True, repr=False)
class RecoveryHandoff:
    """In-memory description only; not durable evidence or an executed fence.

    Candidate includes exact predecessor/envelope/context/operation identities.
    Evaluated well-formed results can disagree with that original candidate;
    they are preserved as observations, never silently adopted as its outcome.
    """
    candidate: service.CheckpointCandidate
    operation: service.OriginalOperation
    reason: Reason
    publication: service.PublicationResult | None
    completion: service.CompletionResult | None

    def __post_init__(self):
        service.require(type(self.candidate) is service.CheckpointCandidate)
        service.require(type(self.operation) is service.OriginalOperation)
        service.require(type(self.reason) is Reason and self.reason is not Reason.NEXT_GATE)
        service.CheckpointCandidate.__post_init__(self.candidate)
        service.OriginalOperation.__post_init__(self.operation)
        service.require(self.operation in (_operation(self.candidate, Stage.PUBLICATION),
                                           _operation(self.candidate, Stage.COMPLETION)))
        service.require(self.publication is None or type(self.publication) is service.PublicationResult)
        service.require(self.completion is None or type(self.completion) is service.CompletionResult)
        for observed, cls in ((self.publication, service.PublicationResult),
                              (self.completion, service.CompletionResult)):
            if observed is not None:
                _, problem = _observe(observed, cls)
                service.require(problem is None)


@dataclass(frozen=True, repr=False)
class Disposition:
    """Knowledge and outstanding gates, never permission to execute a next step."""
    stage: Stage
    candidate: service.CheckpointCandidate
    operation: service.OriginalOperation
    local_commit: LocalCommitState
    outcome: service.ExternalOutcome | None
    reason: Reason
    required_gate: RequiredGate
    publication: service.PublicationResult | None
    completion: service.CompletionResult | None
    recovery: RecoveryHandoff | None
    prior_recovery: RecoveryHandoff | None
    publication_qualification: service.EvidenceValidity = service.EvidenceValidity.UNKNOWN
    completion_qualification: service.EvidenceValidity = service.EvidenceValidity.UNKNOWN
    publication_problem: Reason | None = None
    completion_problem: Reason | None = None

    def __post_init__(self):
        service.require(type(self.stage) is Stage and type(self.local_commit) is LocalCommitState)
        service.require(type(self.candidate) is service.CheckpointCandidate
                        and type(self.operation) is service.OriginalOperation)
        service.require(self.operation == _operation(self.candidate, self.stage))
        service.require(self.outcome is None or type(self.outcome) is service.ExternalOutcome)
        service.require(type(self.reason) is Reason and type(self.required_gate) is RequiredGate)
        service.require(self.publication is None or type(self.publication) is service.PublicationResult)
        service.require(self.completion is None or type(self.completion) is service.CompletionResult)
        service.require(self.prior_recovery is None or type(self.prior_recovery) is RecoveryHandoff)
        service.CheckpointCandidate.__post_init__(self.candidate)
        _history(self.candidate, self.prior_recovery)
        service.require(type(self.publication_qualification) is service.EvidenceValidity
                        and type(self.completion_qualification) is service.EvidenceValidity)
        outcome, reason = _knowledge(self.stage, self.candidate, self.publication, self.completion,
            self.publication_qualification, self.completion_qualification,
            self.publication_problem, self.completion_problem)
        reason, gate = _required(self.stage, reason, self.local_commit, self.prior_recovery)
        service.require(self.outcome is outcome and self.reason is reason and self.required_gate is gate)
        service.require((self.required_gate is RequiredGate.RECOVERY_HANDOFF) == (self.recovery is not None))
        if self.recovery is not None:
            _history(self.candidate, self.recovery)
            service.require(type(self.recovery) is RecoveryHandoff and
                (self.recovery.candidate, self.recovery.operation, self.recovery.reason,
                 self.recovery.publication, self.recovery.completion) ==
                (self.candidate, self.operation, self.reason, self.publication, self.completion))

    @property
    def ack_delivery_authorized(self): return False

    @property
    def runtime_active_authorized(self): return False

    @property
    def automatic_publication_retry_authorized(self): return False

    @property
    def automatic_completion_retry_authorized(self): return False

    @property
    def fence_clearance_authorized(self): return False

    @property
    def completion_required(self):
        """Outstanding original completion gate, not permission to invoke/retry it."""
        pub_outcome, _ = _publication_knowledge(self.candidate, self.publication,
            self.publication_qualification, self.publication_problem)
        return (self.local_commit is LocalCommitState.CONFIRMED
                and pub_outcome is service.ExternalOutcome.CONFIRMED
                and not (self.stage is Stage.COMPLETION and self.outcome is service.ExternalOutcome.CONFIRMED))

    @property
    def delivery_qualification_required(self):
        """Still required even when historical recovery blocks operational progression."""
        return (self.local_commit is LocalCommitState.CONFIRMED and self.stage is Stage.COMPLETION
                and self.outcome is service.ExternalOutcome.CONFIRMED)


def _operation(candidate, stage):
    return candidate.operation if stage is Stage.PUBLICATION else service.OriginalOperation(
        candidate.operation.permit, service.OperationKind.PERMIT_COMPLETION)


def _history(candidate, handoff):
    if handoff is not None:
        service.require(type(handoff) is RecoveryHandoff)
        RecoveryHandoff.__post_init__(handoff)
        service.verify_candidate_association(candidate, handoff.candidate)
        # Both closed operation keys are derived from the same exact permit and
        # candidate namespace. Earlier publication history can accompany completion.
        service.require(handoff.operation in (_operation(candidate, Stage.PUBLICATION),
                                               _operation(candidate, Stage.COMPLETION)))


def _original(candidate, local_commit, prior):
    # With no valid original identity there is no safe handoff identity to invent.
    service.require(type(candidate) is service.CheckpointCandidate)
    service.CheckpointCandidate.__post_init__(candidate)
    service.verify_candidate_association(candidate, candidate)
    service.require(type(local_commit) is LocalCommitState)
    if prior is not None:
        service.require(type(prior) is Disposition)
        Disposition.__post_init__(prior)
        service.verify_candidate_association(candidate, prior.candidate)
        return prior.recovery or prior.prior_recovery
    return None


def _observe(result, cls):
    """Retain only well-formed typed observations; never inspect arbitrary objects."""
    if result is None: return None, Reason.MISSING
    if type(result) is not cls: return None, Reason.MALFORMED
    try:
        cls.__post_init__(result)
    except (ValueError, TypeError, AttributeError):
        return None, Reason.MALFORMED
    return result, None


def _publication_knowledge(candidate, publication, qualification, problem):
    service.require(problem is None or (problem is Reason.MALFORMED and publication is None))
    if problem is not None: return None, problem
    observed, reason = _observe(publication, service.PublicationResult)
    if reason is not None: return None, reason
    try:
        service.verify_publication_result(candidate, observed)
    except (ValueError, TypeError, AttributeError):
        return None, Reason.BINDING_MISMATCH
    return _qualified_outcome(observed.outcome, qualification)


def _qualified_outcome(outcome, qualification):
    if outcome is service.ExternalOutcome.UNKNOWN:
        return outcome, Reason.UNKNOWN
    if qualification is not service.EvidenceValidity.VALID:
        return None, Reason.UNQUALIFIED
    return outcome, (Reason.NEXT_GATE if outcome is service.ExternalOutcome.CONFIRMED
                     else Reason.DEFINITELY_REJECTED)


def _knowledge(stage, candidate, publication, completion, pub_qualification, completion_qualification,
               pub_problem, completion_problem):
    pub_outcome, reason = _publication_knowledge(candidate, publication, pub_qualification, pub_problem)
    if stage is Stage.PUBLICATION:
        service.require(completion is None and completion_problem is None
                        and completion_qualification is service.EvidenceValidity.UNKNOWN)
        return pub_outcome, reason
    service.require(completion_problem is None or
                    (completion_problem is Reason.MALFORMED and completion is None))
    if pub_outcome is not service.ExternalOutcome.CONFIRMED:
        return None, Reason.PUBLICATION_NOT_CONFIRMED
    if completion_problem is not None: return None, completion_problem
    observed, reason = _observe(completion, service.CompletionResult)
    if reason is not None: return None, reason
    try:
        service.verify_completion_result(_operation(candidate, Stage.COMPLETION), publication, observed)
    except (ValueError, TypeError, AttributeError):
        return None, Reason.BINDING_MISMATCH
    return _qualified_outcome(observed.outcome, completion_qualification)


def _required(stage, reason, local_commit, prior_recovery):
    if local_commit is not LocalCommitState.CONFIRMED:
        reason = Reason.LOCAL_COMMIT_NOT_CONFIRMED
    elif prior_recovery is not None and reason is Reason.NEXT_GATE:
        reason = Reason.PRIOR_FENCE
    if reason is Reason.NEXT_GATE:
        gate = (RequiredGate.ORIGINAL_COMPLETION if stage is Stage.PUBLICATION
                else RequiredGate.CURRENT_DELIVERY_QUALIFICATION)
    else:
        gate = RequiredGate.RECOVERY_HANDOFF
    return reason, gate


def _finish(stage, candidate, local_commit, publication, completion, prior_recovery,
            pub_qualification, completion_qualification, pub_problem=None, completion_problem=None):
    outcome, reason = _knowledge(stage, candidate, publication, completion,
        pub_qualification, completion_qualification, pub_problem, completion_problem)
    reason, gate = _required(stage, reason, local_commit, prior_recovery)
    operation = _operation(candidate, stage)
    recovery = (RecoveryHandoff(candidate, operation, reason, publication, completion)
                if gate is RequiredGate.RECOVERY_HANDOFF else None)
    return Disposition(stage, candidate, operation, local_commit, outcome, reason, gate,
                       publication, completion, recovery, prior_recovery, pub_qualification,
                       completion_qualification, pub_problem, completion_problem)


def publication_disposition(candidate: service.CheckpointCandidate, result=None, *,
                            local_commit=LocalCommitState.UNKNOWN,
                            qualification=service.EvidenceValidity.UNKNOWN,
                            prior: Disposition | None = None) -> Disposition:
    """Consume already-qualified evidence; unavailable qualification fails closed.

    qualification records an upstream supplied fact, never establishes it here.
    None/invalid evidence is not a definitive external rejection or absence.
    """
    prior_recovery = _original(candidate, local_commit, prior)
    publication, problem = _observe(result, service.PublicationResult)
    qualification = (qualification if type(qualification) is service.EvidenceValidity
                     else service.EvidenceValidity.UNKNOWN)
    return _finish(Stage.PUBLICATION, candidate, local_commit, publication, None, prior_recovery,
                   qualification, service.EvidenceValidity.UNKNOWN,
                   Reason.MALFORMED if problem is Reason.MALFORMED else None)


def completion_disposition(candidate: service.CheckpointCandidate, publication=None, result=None, *,
                           local_commit=LocalCommitState.UNKNOWN,
                           publication_qualification=service.EvidenceValidity.UNKNOWN,
                           completion_qualification=service.EvidenceValidity.UNKNOWN,
                           prior: Disposition | None = None) -> Disposition:
    """Exact confirmed publication precedes completion knowledge; ACK is never granted."""
    prior_recovery = _original(candidate, local_commit, prior)
    publication, pub_problem = _observe(publication, service.PublicationResult)
    completion, completion_problem = _observe(result, service.CompletionResult)
    publication_qualification = (publication_qualification if type(publication_qualification)
        is service.EvidenceValidity else service.EvidenceValidity.UNKNOWN)
    completion_qualification = (completion_qualification if type(completion_qualification)
        is service.EvidenceValidity else service.EvidenceValidity.UNKNOWN)
    return _finish(Stage.COMPLETION, candidate, local_commit, publication, completion, prior_recovery,
        publication_qualification, completion_qualification,
        Reason.MALFORMED if pub_problem is Reason.MALFORMED else None,
        Reason.MALFORMED if completion_problem is Reason.MALFORMED else None)
