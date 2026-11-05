"""IL6 capability implementation; importing this module establishes no authority.

Bound to implementation contract 92f591b26d2e0b37c34448bc724a4ed4988f6fea
and serialization profile 63dbed6ae575797da27d6a4ee3be03bb184256c3.
External qualification/authentication remains external. Default capabilities deny.
No CLI, startup hook, provider, credential selection or operational configuration.
"""
from dataclasses import dataclass, fields, make_dataclass, replace
from enum import StrEnum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import threading

from . import fixture_lease_protocol as protocol
from . import fixture_lease_service as service
from . import fixture_lease_store as store
from . import fixture_lease_commands as commands

IMPLEMENTATION_CONTRACT = "92f591b26d2e0b37c34448bc724a4ed4988f6fea"
SERIALIZATION_PROFILE = "63dbed6ae575797da27d6a4ee3be03bb184256c3"
_AUTHORITY_SHA256 = (
    ("serialization_profile", "244af712477959ba0d2c4a6d106829ab8a31a3ae82d9247ecd85b620d349a875"),
    ("il6_contract", "d687f86997b371ceebe3c84b504e1a7582b4a2cade4b657c7625c18844eff429"),
    ("genesis_reference_amendment", "2787bb6fed551f29b756a7fa915feea5d1b509f133f380427366f3c10786574f"),
    ("bootstrap_amendment", "eb6fe7d8ae02daa4c409c166b2bbc2d9b0940017f418676bb7ee3836aaec3cf6"),
    ("provisioning_contract", "a36b527fe2c6d9fa16b4debf9e4fb9fea3c2a725611a457569ec96a5d220dab8"),
)


class ActivationRejected(ValueError):
    """Finite rejection. Does not assert an attempted effect did not occur."""


def require(condition, reason="IL6_REJECTED"):
    if not condition:
        raise ActivationRejected(reason)


def _native_identity_numbers(value):
    require(type(value) is tuple and len(value) == 2 and
            all(type(item) is int and item >= 0 for item in value), "NATIVE_IDENTITY_TYPE")


def _external_numbers(value):
    """Check existing typed-view domains before Python equality/arithmetic.

    This inspects in-memory claims only, never opaque evidence bytes, and defines
    no serialization. Frozen canonical/store/time validators retain their domains.
    Native OS identifiers remain nonnegative integers without an invented size cap.
    """
    cls = type(value)
    try:
        if cls in _SCHEMAS:
            _mapping(value)
            return
        if cls is protocol.MetadataRow:
            protocol.encode_record(value)
            return
        if cls is store.MetadataRow:
            store._validate_row(value)
            return
        if cls in (service.QualifiedClockProfile, service.QualifiedSample, service.UtcInterval,
                   service.MonotonicPoint, service.QualifiedPropagationError):
            cls.__post_init__(value)
        for name, domain in _EXTERNAL_NUMERIC_FIELDS.get(cls, ()):
            number = getattr(value, name)
            if domain == "utc":
                protocol.utc(number)
            elif domain in ("uint", "one"):
                protocol.uint(number)
                if domain == "one":
                    require(number == 1, "GENERATION_DOMAIN")
            elif domain == "native":
                _native_identity_numbers(number)
            else:
                require(type(number) is int and number >= 0, "NATIVE_IDENTIFIER_TYPE")
        if type(value) is tuple:
            for item in value:
                _external_numbers(item)
        elif hasattr(cls, "__dataclass_fields__"):
            for field in fields(value):
                _external_numbers(getattr(value, field.name))
    except (protocol.ProtocolRejected, service.TimeRejected, store.StorageRejected) as error:
        raise ActivationRejected("EXTERNAL_NUMERIC_CLAIM") from error


def _capture(value):
    """In-memory mutation guard, NOT an authority serialization or digest."""
    if type(value) in (str, bytes, int, bool, type(None)) or isinstance(value, StrEnum):
        return (type(value), value)
    if isinstance(value, Path):
        return (type(value), str(value))
    if type(value) is tuple:
        return tuple(_capture(item) for item in value)
    if hasattr(type(value), "__dataclass_fields__"):
        return (type(value), tuple((field.name, _capture(getattr(value, field.name))) for field in fields(value)))
    # Native ownership and attempt guards intentionally have mutable resource state.
    require(isinstance(value, (NativeStorage, GenesisAttempt)))
    return (type(value), id(value))


def _invoke(callback, *arguments):
    before = _capture(arguments)
    try:
        result = callback(*arguments)
    except BaseException as error:
        if _capture(arguments) != before:
            error.add_note("IL6 input mutation detected during failed callback")
        raise
    require(_capture(arguments) == before, "CALLBACK_INPUT_MUTATION")
    return result


# Closed schemas are literal frozen-profile tables, not caller-supplied maps.
# Generated frozen records retain named, exact fields and reject extension bags.
_SCHEMAS = {}


def _validate_record_instance(value):
    try:
        _mapping(value)
    except (ValueError, TypeError, UnicodeError, protocol.ProtocolRejected) as error:
        raise ActivationRejected("TYPED_RECORD_REJECTED") from error


def _record(name, specification):
    schema = tuple(tuple(item.split(":")) for item in specification.split())
    scalar_types = {"ID": str, "H": str, "T": int, "ONE": int, "ZERO": int, "TRUE": bool, "FALSE": bool}
    cls = make_dataclass(name, [(key, str if kind.startswith("=") else
                               scalar_types.get(kind, globals().get(kind))) for key, kind in schema],
                         frozen=True, slots=True, namespace={"__module__": __name__,
                                                           "__post_init__": _validate_record_instance})
    _SCHEMAS[cls] = schema
    globals()[name] = cls
    return cls


_record("Reference", "identity:ID sha256:H")
_record("SchemaBinding", "version:ONE reference:Reference")
_record("HostBinding", "identity:ID qualification:Reference")
_record("StorageBinding", "identity:ID location:Reference ownership:Reference exclusion:Reference qualification:Reference")
_record("ScopeBinding", "environment:ID project_scope:ID qualification:Reference")
_record("ActorBinding", "genesis_operator:ID preparation_operator:ID issuer:ID opener:ID process:ID authorization:Reference fencing:Reference qualification:Reference")
_record("RepresentationBinding", "identity:ID authority:Reference")
_record("ClockBinding", "profile:Reference source:ID qualification:Reference sample:Reference monotonic_domain:ID")
_record("StorageProfile", "journal_mode:=DELETE synchronous:=EXTRA foreign_keys:TRUE busy_timeout:ZERO locking_mode:=NORMAL read_uncommitted:FALSE")
_record("SoftwareBinding", "python_build:ID driver_build:ID sqlite_version:ID sqlite_source_id:ID package:Reference qualification:Reference storage_profile:StorageProfile")
_record("ProtectedAuthorities", "activation:Reference checkpoint:Reference absence_requirements:Reference history_retention:Reference readback_requirements:Reference result_verification_requirements:Reference")
_record("Requirements", "durability:Reference backup_restore:Reference evidence_retention:Reference initial_state_verification:Reference approval_applicability:Reference")
_record("Authorization", "reference:Reference valid_from_us:T valid_until_us:T")
_record("ExpectedCounts", "metadata:ONE artifacts:ZERO reservations:ZERO claims:ZERO commands:ZERO events:ZERO")
_record("AuthorityBindings", " ".join(name + ":Reference" for name in (
    "fixture_plan", "bootstrap_amendment", "provisioning_contract", "implementation_design",
    "il6_contract", "genesis_reference_amendment", "serialization_profile", "il4_protocol",
    "state_framing", "il5_normal_checkpoint", "replacement_generation", "design_adoption_evidence")))
_record("CeremonyEvidence", "object_type:=JOUS.CORE.1A.IL6.E profile_version:ONE purpose:=GENESIS_V1 register_id:ID schema:SchemaBinding issuer_generation:ONE activation_id:ID host:HostBinding storage:StorageBinding scope:ScopeBinding actors:ActorBinding authorities:AuthorityBindings representation:RepresentationBinding creation_evidence:Reference clock:ClockBinding creation_utc_us:T initial_state:Reference event_sequence:ZERO event_digest:H predecessor_generation:ZERO predecessor_checkpoint_digest:H activation_command_id:ID approval_id:ID")
_record("ActivationPackage", "object_type:=JOUS.CORE.1A.IL6.P profile_version:ONE purpose:=GENESIS register_id:ID issuer_generation:ONE activation_id:ID ceremony_evidence:Reference creation_evidence:Reference initial_state:Reference checkpoint:Reference activation_command_id:ID approval_id:ID software:SoftwareBinding protected_authorities:ProtectedAuthorities requirements:Requirements authorization:Authorization expected_counts:ExpectedCounts recovery_required:FALSE")
_record("ActivationPayload", "object_type:=JOUS.CORE.1A.IL6.ACTIVATION_PAYLOAD profile_version:ONE purpose:=ABSENT_TO_GENERATION_ONE activation_command_id:ID expected_presence:=AUTHORITATIVE_ABSENT predecessor_generation:ZERO register_id:ID issuer_generation:ONE activation_id:ID host_identity:ID package:Reference checkpoint:Reference approval:Reference")


def _scalar(value, kind):
    if kind == "ID":
        require(type(value) is str)
        protocol.identifier(value)
    elif kind == "H":
        require(type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None)
    elif kind == "T":
        protocol.utc(value)
    elif kind in ("ONE", "ZERO"):
        require(type(value) is int and value == (1 if kind == "ONE" else 0))
    elif kind in ("TRUE", "FALSE"):
        require(type(value) is bool and value is (kind == "TRUE"))
    else:
        require(kind.startswith("=") and type(value) is str and value == kind[1:])
    return value


def _mapping(value):
    require(type(value) in _SCHEMAS)
    result = {}
    for name, kind in _SCHEMAS[type(value)]:
        item = getattr(value, name)
        if kind in globals() and globals()[kind] in _SCHEMAS:
            require(type(item) is globals()[kind])
            result[name] = _mapping(item)
        else:
            result[name] = _scalar(item, kind)
    if type(value) is Authorization:
        require(value.valid_from_us <= value.valid_until_us)
    if type(value) is CeremonyEvidence:
        require(value.event_digest == protocol.GENESIS_EVENT_DIGEST.hex())
        require(value.predecessor_checkpoint_digest == "0" * 64)
    return result


def canonical_bytes(value):
    """Only the three frozen new objects have independent canonical bytes."""
    require(type(value) in (CeremonyEvidence, ActivationPackage, ActivationPayload))
    try:
        return json.dumps(_mapping(value), ensure_ascii=True, separators=(",", ":"),
                          allow_nan=False).encode("ascii")
    except (ValueError, TypeError, UnicodeError, protocol.ProtocolRejected) as error:
        raise ActivationRejected("SERIALIZATION_REJECTED") from error


def _pairs(items):
    require(len({key for key, _ in items}) == len(items), "DUPLICATE_FIELD")
    return dict(items)


def _from_mapping(cls, value):
    require(type(value) is dict and tuple(value) == tuple(key for key, _ in _SCHEMAS[cls]))
    values = []
    for name, kind in _SCHEMAS[cls]:
        item = value[name]
        nested = globals().get(kind)
        values.append(_from_mapping(nested, item) if nested in _SCHEMAS else _scalar(item, kind))
    result = cls(*values)
    _mapping(result)
    return result


def decode_canonical(raw, cls):
    require(type(raw) is bytes and cls in (CeremonyEvidence, ActivationPackage, ActivationPayload))
    try:
        value = json.loads(raw.decode("ascii"), object_pairs_hook=_pairs,
                           parse_constant=lambda _: require(False))
        result = _from_mapping(cls, value)
        require(canonical_bytes(result) == raw, "NONCANONICAL_BYTES")
        return result
    except (ValueError, TypeError, UnicodeError, protocol.ProtocolRejected) as error:
        raise ActivationRejected("SERIALIZATION_REJECTED") from error


def content_reference(value):
    raw = canonical_bytes(value)
    prefix = {CeremonyEvidence: "genesis-ceremony", ActivationPackage: "il6-package",
              ActivationPayload: "il6-activation-payload"}[type(value)]
    digest = sha256(raw).hexdigest()
    return Reference(prefix + ":sha256:" + digest, digest)


def validate_ceremony_reference(reference, evidence):
    require(type(reference) is Reference and reference == content_reference(evidence))
    _mapping(reference)
    return reference


def _reference_bytes(reference, raw):
    require(type(reference) is Reference and type(raw) is bytes)
    _mapping(reference)
    require(sha256(raw).hexdigest() == reference.sha256, "EVIDENCE_DIGEST")


def initial_projection(evidence):
    """Existing STATE-2 only, with its unchanged metadata projection exclusions."""
    _mapping(evidence)
    require(type(evidence) is CeremonyEvidence and evidence.representation.identity == protocol.STATE_2)
    require(evidence.representation.authority == evidence.authorities.state_framing)
    pins = tuple(bytes.fromhex(getattr(evidence.authorities, name).sha256) for name in (
        "fixture_plan", "bootstrap_amendment", "provisioning_contract", "implementation_design"))
    metadata = protocol.MetadataRow(1, 1, evidence.register_id, 1, evidence.activation_id,
                                    *pins, evidence.creation_utc_us, 0)
    context = protocol.StateContext(protocol.STATE_2, evidence.register_id, 1, evidence.activation_id)
    return protocol.StateProjection(metadata, (), (), ()), context


def genesis_checkpoint(evidence):
    """Pure frozen genesis specialization, never the normal checkpoint codec."""
    projection, context = initial_projection(evidence)
    state = protocol.state_bytes(projection, context)
    _reference_bytes(evidence.initial_state, state)
    ceremony = content_reference(evidence)
    require(len({ceremony.identity, evidence.creation_evidence.identity,
                 evidence.activation_command_id, evidence.approval_id}) == 4)
    return protocol.frame(1, 7, (
        protocol.identifier(evidence.register_id), protocol.uint(1),
        protocol.identifier(evidence.activation_id), protocol.uint(0), protocol.uint(0),
        protocol.GENESIS_EVENT_DIGEST, sha256(state).digest(), protocol.utc(evidence.creation_utc_us),
        bytes(32), protocol.identifier(ceremony.identity), b"\x01" + protocol.identifier(evidence.approval_id)))


@dataclass(frozen=True)
class PackageSnapshot:
    ceremony: bytes
    package: bytes
    state: bytes
    checkpoint: bytes


@dataclass(frozen=True)
class ValidatedPackage:
    snapshot: PackageSnapshot
    evidence: CeremonyEvidence
    package: ActivationPackage
    qualification: "QualifiedPackageBindings | None" = None


def _validate_snapshot(snapshot):
    require(type(snapshot) is PackageSnapshot and all(type(getattr(snapshot, f.name)) is bytes
                                                    for f in fields(snapshot)))
    e = decode_canonical(snapshot.ceremony, CeremonyEvidence)
    p = decode_canonical(snapshot.package, ActivationPackage)
    for role, digest in _AUTHORITY_SHA256:
        require(getattr(e.authorities, role).sha256 == digest, "FROZEN_AUTHORITY_MISMATCH")
    for name in ("register_id", "issuer_generation", "activation_id", "creation_evidence",
                 "initial_state", "activation_command_id", "approval_id"):
        require(getattr(e, name) == getattr(p, name), "PACKAGE_BINDING")
    validate_ceremony_reference(p.ceremony_evidence, e)
    projection, context = initial_projection(e)
    require(protocol.state_bytes(projection, context) == snapshot.state)
    require(genesis_checkpoint(e) == snapshot.checkpoint)
    _reference_bytes(p.checkpoint, snapshot.checkpoint)
    return ValidatedPackage(snapshot, e, p)


def _references(value, path=""):
    if type(value) is Reference:
        return ((path, value),)
    require(type(value) in _SCHEMAS)
    return tuple(item for field in fields(value) if type(getattr(value, field.name)) in _SCHEMAS
                 for item in _references(getattr(value, field.name), path + "." + field.name))


@dataclass(frozen=True)
class OpaqueEvidence:
    """Raw retained bytes, NEVER parsed/reserialized as C, Q or another opaque role."""
    role: str
    reference: Reference
    raw: bytes
    qualification: service.EvidenceReference


@dataclass(frozen=True)
class CreationClaims:
    reference: Reference
    purpose: str
    register_id: str
    schema: SchemaBinding
    generation: int
    activation_id: str
    host: HostBinding
    storage: StorageBinding
    scope: ScopeBinding
    preparation_operator: str
    authorization: service.EvidenceReference
    fixed_utc: int
    clock: ClockBinding
    metadata: protocol.MetadataRow
    native_identity: tuple[int, int]
    state: str
    dependency_stage: str


@dataclass(frozen=True)
class StorageClaims:
    binding: StorageBinding
    location: "StorageLocation"
    native_identity: tuple[int, int]
    account: str
    effective_access: service.EvidenceReference
    issuer: str
    process: str
    host: str
    continuity: service.EvidenceReference
    locking_atomicity_flush_vfs: service.EvidenceReference
    durability: service.EvidenceReference
    filesystem: str
    state: str


@dataclass(frozen=True)
class AuthorityClaims:
    role: str
    reference: Reference
    version: str
    adoption: service.EvidenceReference
    scope: ScopeBinding


@dataclass(frozen=True)
class PackageClaims:
    """Closed authenticated views of profile section 7, supplied by the adapter.

    Named nested records bind exact values; qualification references are proofs
    from the separately qualified authorities, never self-issued permission flags.
    No raw external record is parsed to construct these views in this module.
    """
    creation: CreationClaims
    schema: SchemaBinding
    host: HostBinding
    host_authentication: service.EvidenceReference
    storage: StorageClaims
    scope: ScopeBinding
    governance_target: service.EvidenceReference
    scope_justification: service.EvidenceReference
    actors: ActorBinding
    actor_role_action_validity: service.EvidenceReference
    clock: ClockBinding
    authorities: tuple[AuthorityClaims, ...]
    representation: RepresentationBinding
    generation_selection: service.EvidenceReference
    software: SoftwareBinding
    host_vfs_compatibility: service.EvidenceReference
    protected_authorities: ProtectedAuthorities
    protected_trust_scope: service.EvidenceReference
    absence: str
    linearizable_cas: service.EvidenceReference
    history_tombstones: service.EvidenceReference
    original_command_outcomes: service.EvidenceReference
    requirements: Requirements
    requirement_applicability: service.EvidenceReference
    authorization: Authorization
    authorization_register_id: str
    authorization_activation_id: str
    authorization_command_id: str
    authorization_host: str
    authorization_operator: str
    authorization_action: str
    upstream_dependency_stage: str


@dataclass(frozen=True)
class QualifiedPackageBindings:
    """Authenticated adapter output, not self-authenticating input.

    The qualified adapter is responsible for the profile section 7 closed views
    and transitive upstream-stage restrictions. Exact role/reference/raw coverage
    and the complete context are rechecked locally; a boolean is never sufficient.
    """
    snapshot: PackageSnapshot
    opaque: tuple[OpaqueEvidence, ...]
    schema_bytes: bytes
    profile: service.QualifiedClockProfile
    creation_sample: service.QualifiedSample
    provenance: service.EvidenceReference
    claims: PackageClaims


@dataclass(frozen=True)
class QualifiedCreation:
    evidence: OpaqueEvidence
    claims: CreationClaims
    provenance: service.EvidenceReference


class QualificationAdapter:
    """Trusted composition seam; default has no authentication provider or I/O."""
    def package(self, snapshot):
        raise ActivationRejected("UNQUALIFIED_PACKAGE")

    def preparation(self, request):
        raise ActivationRejected("UNQUALIFIED_PREPARATION")

    def creation(self, request, native_identity, state, database_sha256):
        raise ActivationRejected("UNQUALIFIED_CREATION_EVIDENCE")

    def execution(self, request):
        raise ActivationRejected("UNQUALIFIED_EXECUTION")

    def opening(self, request):
        raise ActivationRejected("UNQUALIFIED_OPEN")

    def approval(self, accepted, approval, clock):
        raise ActivationRejected("UNQUALIFIED_APPROVAL")


def validate_genesis_package(snapshot, qualification=None):
    """Pure validation of already-qualified immutable in-memory views; no callback.

    A validated value is not operational authority. Effectful entry points obtain
    these views from their separately qualified trusted composition seam.
    """
    accepted = _validate_snapshot(snapshot)
    q = qualification
    require(type(q) is QualifiedPackageBindings)
    _external_numbers(q)
    require(q.snapshot == snapshot)
    require(type(q.provenance) is service.EvidenceReference)
    require(type(q.opaque) is tuple)
    e, p = accepted.evidence, accepted.package
    # These three are existing/new canonical objects, not opaque records.
    canonical_roles = {"E.initial_state", "P.initial_state", "P.ceremony_evidence", "P.checkpoint"}
    expected = tuple((role, ref) for root, value in (("E", e), ("P", p))
                     for role, ref in _references(value, root) if role not in canonical_roles)
    require(len(q.opaque) == len(expected))
    require(tuple((item.role, item.reference) for item in q.opaque) == expected, "OPAQUE_ROLE_COVERAGE")
    identities = {}
    for item in q.opaque:
        require(type(item) is OpaqueEvidence and type(item.qualification) is service.EvidenceReference)
        _reference_bytes(item.reference, item.raw)
        prior = identities.setdefault(item.reference.identity, (item.reference.sha256, item.raw))
        require(prior == (item.reference.sha256, item.raw), "IDENTITY_COLLISION")
    require(q.schema_bytes == store.SCHEMA_SQL.encode("utf-8"))
    _reference_bytes(e.schema.reference, q.schema_bytes)
    require(type(q.profile) is service.QualifiedClockProfile and type(q.creation_sample) is service.QualifiedSample)
    require((q.profile.profile.identity, q.profile.profile.sha256.hex()) ==
            (e.clock.profile.identity, e.clock.profile.sha256))
    require(q.profile.source == e.clock.source == q.creation_sample.source)
    require((q.profile.qualification.identity, q.profile.qualification.sha256.hex()) ==
            (e.clock.qualification.identity, e.clock.qualification.sha256))
    require(q.creation_sample.profile == q.profile.profile)
    require((q.creation_sample.sample.identity, q.creation_sample.sample.sha256.hex()) ==
            (e.clock.sample.identity, e.clock.sample.sha256))
    require(q.creation_sample.anchor.domain_id == e.clock.monotonic_domain)
    require(q.creation_sample.anchor.process_id == e.actors.process)
    require(q.creation_sample.utc.lower_us == e.creation_utc_us)
    require(q.creation_sample.utc.upper_us - q.creation_sample.utc.lower_us <= q.profile.max_command_uncertainty_us)
    _package_claims(q.claims, accepted)
    return replace(accepted, qualification=q)


def _qualified_package(snapshot, adapter):
    require(isinstance(adapter, QualificationAdapter), "UNQUALIFIED_PACKAGE")
    return validate_genesis_package(snapshot, _invoke(adapter.package, snapshot))


def _package_claims(claims, accepted):
    require(type(claims) is PackageClaims)
    _external_numbers(claims)
    e, p = accepted.evidence, accepted.package
    for name in ("schema", "host", "scope", "actors", "clock", "representation"):
        require(getattr(claims, name) == getattr(e, name), "QUALIFIED_CONTEXT_MISMATCH")
    for name in ("software", "protected_authorities", "requirements", "authorization"):
        require(getattr(claims, name) == getattr(p, name), "QUALIFIED_CONTEXT_MISMATCH")
    _evidence_fields(claims, ("host_authentication", "governance_target", "scope_justification",
        "actor_role_action_validity", "generation_selection", "host_vfs_compatibility", "protected_trust_scope",
        "linearizable_cas", "history_tombstones", "original_command_outcomes", "requirement_applicability"))
    require(claims.absence == "AUTHORITATIVE_ABSENT" and claims.upstream_dependency_stage == "UPSTREAM_ONLY")
    require((claims.authorization_register_id, claims.authorization_activation_id, claims.authorization_command_id,
             claims.authorization_host, claims.authorization_operator, claims.authorization_action) ==
            (e.register_id, e.activation_id, e.activation_command_id, e.host.identity,
             e.actors.genesis_operator, "GENESIS"))
    require(type(claims.authorities) is tuple and len(claims.authorities) == len(fields(e.authorities)))
    for field, authority in zip(fields(e.authorities), claims.authorities):
        require(type(authority) is AuthorityClaims and authority.role == field.name)
        require(authority.reference == getattr(e.authorities, field.name) and authority.scope == e.scope)
        protocol.identifier(authority.version)
        _evidence_fields(authority, ("adoption",))
    c, storage = claims.creation, claims.storage
    require(type(c) is CreationClaims and type(storage) is StorageClaims)
    require((c.reference, c.purpose, c.register_id, c.schema, c.generation, c.activation_id,
             c.host, c.storage, c.scope, c.preparation_operator, c.fixed_utc, c.clock) ==
            (e.creation_evidence, "GENESIS_V1", e.register_id, e.schema, 1, e.activation_id,
             e.host, e.storage, e.scope, e.actors.preparation_operator, e.creation_utc_us, e.clock))
    require(c.state == "PREPARED_NON_AUTHORITATIVE" and c.dependency_stage == "UPSTREAM_ONLY")
    require(c.metadata == initial_projection(e)[0].metadata)
    _evidence_fields(c, ("authorization",))
    require(type(storage.location) is StorageLocation and storage.binding == e.storage)
    require((storage.host, storage.issuer, storage.process) == (e.host.identity, e.actors.issuer, e.actors.process))
    require((storage.location.host_identity, storage.location.storage_identity) == (e.host.identity, e.storage.identity))
    require(storage.native_identity == c.native_identity and type(c.native_identity) is tuple and
            len(c.native_identity) == 2 and all(type(x) is int and x >= 0 for x in c.native_identity))
    protocol.identifier(storage.account)
    require(storage.filesystem == "QUALIFIED_DURABLE_LOCAL" and storage.state == "EXCLUSIVE_IDENTITY_CONTINUITY")
    _evidence_fields(storage, ("effective_access", "continuity", "locking_atomicity_flush_vfs", "durability"))


class Reached(StrEnum):
    REJECTED = "REJECTED"
    PREPARATION_ATTEMPTED = "PREPARATION_ATTEMPTED"
    PREPARED_NON_AUTHORITATIVE = "PREPARED_NON_AUTHORITATIVE"
    FILE_PUBLICATION_ATTEMPTED = "FILE_PUBLICATION_ATTEMPTED"
    FILE_PUBLISHED_NON_AUTHORITATIVE = "FILE_PUBLISHED_NON_AUTHORITATIVE"
    CHECKPOINT_ATTEMPTED = "CHECKPOINT_ATTEMPTED"
    CHECKPOINT_CONFIRMED = "CHECKPOINT_CONFIRMED"
    CAS_ATTEMPTED = "CAS_ATTEMPTED"
    CAS_CONFIRMED_VERIFICATION_PENDING = "CAS_CONFIRMED_VERIFICATION_PENDING"
    READBACK_CONFIRMED_VERIFICATION_PENDING = "READBACK_CONFIRMED_VERIFICATION_PENDING"
    OPEN_VALIDATED = "OPEN_VALIDATED"


@dataclass(frozen=True)
class OperationResult:
    reached: Reached
    recovery_only: bool
    evidence: tuple
    cause: BaseException | None
    receipt: object = None


@dataclass(frozen=True)
class StorageLocation:
    final: Path
    staging: Path
    parent_device: int
    parent_inode: int
    host_identity: str
    storage_identity: str
    exclusion_identity: str


@dataclass(frozen=True)
class TimeBinding:
    profile: service.QualifiedClockProfile
    sample: service.QualifiedSample
    current: service.MonotonicPoint
    error: service.QualifiedPropagationError


def _time(binding, *, not_before, valid_from, valid_until):
    require(type(binding) is TimeBinding)
    _external_numbers(binding)
    for timestamp in (not_before, valid_from, valid_until):
        protocol.utc(timestamp)
    require(valid_from <= valid_until, "INVALID_VALIDITY_INTERVAL")
    evaluation = service.evaluate_time(binding.sample, binding.profile, binding.current, binding.error)
    require(evaluation.interval.lower_us >= not_before, "BACKWARD_TIME")
    require(service.valid_from_satisfied(evaluation.interval, valid_from), "NOT_YET_VALID")
    require(service.inclusive_bound(evaluation.interval, service.InclusiveDeadline(valid_until))
            is service.TimingBound.SATISFIED, "EXPIRED_OR_UNCERTAIN")
    return evaluation


@dataclass(frozen=True)
class PreparationRequest:
    register_id: str
    activation_id: str
    activation_command_id: str
    approval_id: str
    metadata: store.MetadataRow
    context: protocol.StateContext
    location: StorageLocation
    clock: TimeBinding
    authorization: service.EvidenceReference


@dataclass(frozen=True)
class QualifiedPreparation:
    request: PreparationRequest
    absence_history: service.EvidenceReference
    storage: service.EvidenceReference
    actor: service.EvidenceReference
    authorization: service.EvidenceReference
    valid_from_us: int
    valid_until_us: int
    provenance: service.EvidenceReference
    operator: str
    process: str
    issuer: str
    action: str
    presence: str
    original_history: str


@dataclass(frozen=True)
class PreparedReceipt:
    request: PreparationRequest
    native_identity: tuple[int, int]
    state: bytes
    database_sha256: bytes
    qualification: QualifiedPreparation
    storage: "NativeStorage"
    attempt: "GenesisAttempt"
    creation: QualifiedCreation


@dataclass(frozen=True)
class ApprovalView:
    """Already authenticated closed Q claims; raw Q is never decoded locally."""
    evidence: OpaqueEvidence
    package: Reference
    checkpoint: Reference
    register_id: str
    generation: int
    activation_id: str
    host_identity: str
    activation_command_id: str
    approver: str
    requester: str
    issuer: str
    independence: service.EvidenceReference
    authority: service.EvidenceReference
    authorization: service.EvidenceReference
    not_revoked: service.EvidenceReference
    validity_observation: service.EvidenceReference
    valid_from_us: int
    valid_until_us: int
    status: str


@dataclass(frozen=True)
class ExecutionRequest:
    snapshot: PackageSnapshot
    prepared: PreparedReceipt
    approval: ApprovalView
    authorization: service.EvidenceReference
    clock: TimeBinding


@dataclass(frozen=True)
class QualifiedExecution:
    request: ExecutionRequest
    absence_history: service.EvidenceReference
    storage: service.EvidenceReference
    actor: service.EvidenceReference
    authorization: service.EvidenceReference
    valid_from_us: int
    valid_until_us: int
    provenance: service.EvidenceReference
    clock: TimeBinding
    operator: str
    process: str
    issuer: str
    action: str
    presence: str
    original_history: str


@dataclass(frozen=True)
class CheckpointResult:
    operation: str
    checkpoint: Reference
    package: Reference
    approval: Reference
    host_identity: str
    status: str
    evidence: service.EvidenceReference


@dataclass(frozen=True)
class ActivationResult:
    command_id: str
    payload_sha256: bytes
    package: Reference
    checkpoint: Reference
    approval: Reference
    register_id: str
    generation: int
    activation_id: str
    host_identity: str
    status: str
    evidence: service.EvidenceReference


class ProtectedGenesis:
    """No production authority provider. No implicit lookup/retry or generic CAS."""
    def publish_checkpoint(self, snapshot, approval, authorization):
        raise ActivationRejected("NO_PROTECTED_CHECKPOINT_CAPABILITY")

    def activate_absent(self, payload, publication, absence_history, authorization):
        raise ActivationRejected("NO_GENESIS_CAS_CAPABILITY")

    def readback(self, result):
        raise ActivationRejected("NO_READBACK_CAPABILITY")


def _evidence_fields(value, names):
    for name in names:
        reference = getattr(value, name)
        require(type(reference) is service.EvidenceReference, "UNQUALIFIED_EVIDENCE")
        service.EvidenceReference(reference.identity, reference.sha256)


def _approval(view, accepted, clock):
    require(type(view) is ApprovalView and type(view.evidence) is OpaqueEvidence)
    _external_numbers(view)
    e, p = accepted.evidence, accepted.package
    require(view.evidence.role == "Q" and view.evidence.reference.identity == e.approval_id)
    require(type(view.evidence.qualification) is service.EvidenceReference)
    _reference_bytes(view.evidence.reference, view.evidence.raw)
    require(view.status == "APPROVED_GENESIS")
    require(view.package == content_reference(p) and view.checkpoint == p.checkpoint)
    require((view.register_id, view.generation, view.activation_id, view.host_identity,
             view.activation_command_id) == (e.register_id, 1, e.activation_id,
                                              e.host.identity, e.activation_command_id))
    for identity in (view.approver, view.requester, view.issuer):
        protocol.identifier(identity)
    require(view.requester == e.actors.genesis_operator and view.issuer == e.actors.issuer)
    require(view.approver not in (view.requester, view.issuer, e.actors.preparation_operator))
    _evidence_fields(view, ("independence", "authority", "authorization", "not_revoked", "validity_observation"))
    _time(clock, not_before=e.creation_utc_us, valid_from=view.valid_from_us, valid_until=view.valid_until_us)


def activation_payload(accepted, approval, clock, qualification=None):
    # Authentication must be re-established for the complete execution request by
    # execute_genesis. This pure constructor accepts only a qualified approval
    # delivered by a trusted adapter, never opaque bytes parsed as an approval.
    require(type(accepted) is ValidatedPackage)
    accepted = validate_genesis_package(accepted.snapshot, accepted.qualification)
    require(isinstance(qualification, QualificationAdapter), "UNQUALIFIED_APPROVAL")
    qualified = _invoke(qualification.approval, accepted, approval, clock)
    require(type(qualified) is ApprovalView and qualified == approval, "UNQUALIFIED_APPROVAL")
    _approval(approval, accepted, clock)
    return _bound_payload(accepted, approval)


def _bound_payload(accepted, approval):
    e, p = accepted.evidence, accepted.package
    return ActivationPayload("JOUS.CORE.1A.IL6.ACTIVATION_PAYLOAD", 1,
        "ABSENT_TO_GENERATION_ONE", e.activation_command_id, "AUTHORITATIVE_ABSENT", 0,
        e.register_id, 1, e.activation_id, e.host.identity, content_reference(p),
        p.checkpoint, approval.evidence.reference)


class NativeStorage:
    """Explicit native primitives, never selected or invoked by import/open.

    Linux: flock on the approved parent, renameat2(RENAME_NOREPLACE), fsync.
    Windows: named mutex, MoveFileExW(no REPLACE_EXISTING, WRITE_THROUGH),
    FlushFileBuffers on the approved directory handle and os.fsync on the file.
    Unsupported native guarantees reject; there is no overwrite/flush fallback.
    These primitives do NOT qualify ACLs, hardware, VFS, host or durability.
    An independently qualified storage/OS adapter must establish those boundaries.
    """
    def __init__(self):
        self._location = None
        self._lock = None

        self._attempted = False
        self._mutex = threading.Lock()
        self._parent_fd = None
        self._directory_handle = None
        self._owns_mutex = False
        self._original_attempt = None

    @staticmethod
    def _identity(path):
        info = os.stat(path, follow_symlinks=False)
        return info.st_dev, info.st_ino

    @staticmethod
    def _plain(path):
        require(type(path) is Path or isinstance(path, Path))
        require(path.is_absolute() and path == path.resolve(strict=False), "NONCANONICAL_PATH")
        for component in (path, *path.parents):
            try:
                info = os.lstat(component)
            except FileNotFoundError:
                require(component == path, "MISSING_PARENT")
                continue
            require(not os.path.islink(component) and not
                    (getattr(info, "st_file_attributes", 0) & 0x400), "PATH_REDIRECTION")

    @staticmethod
    def _absent(path):
        try:
            os.lstat(path)
        except FileNotFoundError:
            return
        raise ActivationRejected("TARGET_EXISTS")

    def check(self, location, *, staging_exists):
        require(type(location) is StorageLocation)
        _external_numbers(location)
        require(self._location in (None, location), "STORAGE_SUBSTITUTION")
        for path in (location.final, location.staging):
            self._plain(path)
        require(location.final != location.staging and location.final.parent == location.staging.parent)
        require(location.final.parent.is_dir())
        require(self._identity(location.final.parent) == (location.parent_device, location.parent_inode))
        self._absent(location.final)
        if not staging_exists:
            self._absent(location.staging)
        for path in (location.final, location.staging):
            for suffix in ("-journal", "-wal", "-shm"):
                self._absent(Path(str(path) + suffix))

    def acquire(self, location):
        self._acquire(location)

    def acquire_existing(self, location, native_identity):
        """OS ownership only, never file/schema creation or authority adoption."""
        self._acquire(location, native_identity)

    def check_existing(self, location, native_identity):
        require(type(location) is StorageLocation)
        _external_numbers(location)
        _native_identity_numbers(native_identity)
        require(self._location in (None, location))
        self._plain(location.final)
        self._plain(location.staging)
        require(location.final != location.staging and location.final.parent == location.staging.parent)
        require(location.final.is_file() and self._identity(location.final) == native_identity)
        require(self._identity(location.final.parent) == (location.parent_device, location.parent_inode))
        self._absent(location.staging)
        for path in (location.final, location.staging):
            for suffix in ("-journal", "-wal", "-shm"):
                self._absent(Path(str(path) + suffix))

    def _acquire(self, location, native_identity=None):
        require(self._location is None and self._lock is None)
        if native_identity is None:
            self.check(location, staging_exists=False)
        else:
            self.check_existing(location, native_identity)
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateMutexW.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
            kernel.CreateMutexW.restype = wintypes.HANDLE
            kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
            kernel.WaitForSingleObject.restype = wintypes.DWORD
            name = "Global\\JOUS-IL6-" + sha256(location.exclusion_identity.encode("utf-8")).hexdigest()
            handle = kernel.CreateMutexW(None, False, name)
            require(bool(handle), "NATIVE_MUTEX")
            self._lock = (kernel, handle)
            wait = kernel.WaitForSingleObject(handle, 0)
            self._owns_mutex = wait in (0, 0x80)
            require(wait == 0, "EXCLUSION_UNAVAILABLE_OR_ABANDONED")
            kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                          ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
            kernel.CreateFileW.restype = wintypes.HANDLE
            self._directory_handle = kernel.CreateFileW(str(location.final.parent),
                0x80000000 | 0x40000000, 1 | 2, None, 3, 0x02000000 | 0x00200000, None)
            if self._directory_handle in (None, ctypes.c_void_p(-1).value):
                self._directory_handle = None
                raise ActivationRejected("DIRECTORY_HANDLE")
        elif os.name == "posix" and __import__("sys").platform == "linux":
            import ctypes
            import fcntl
            require(getattr(ctypes.CDLL(None, use_errno=True), "renameat2", None) is not None,
                    "NO_REPLACE_UNSUPPORTED")
            self._parent_fd = os.open(location.final.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            fcntl.flock(self._parent_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock = self._parent_fd
        else:
            raise ActivationRejected("UNSUPPORTED_NATIVE_PLATFORM")
        self._location = location
        if native_identity is None:
            self.check(location, staging_exists=False)
        else:
            self.check_existing(location, native_identity)
        # Establish support before creating any staging bytes.
        self.flush_directory()

    def flush_directory(self):
        require(self._lock is not None)
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel, _ = self._lock
            kernel.FlushFileBuffers.argtypes = (wintypes.HANDLE,)
            kernel.FlushFileBuffers.restype = wintypes.BOOL
            require(bool(kernel.FlushFileBuffers(self._directory_handle)), "DIRECTORY_FLUSH_UNSUPPORTED")
        else:
            os.fsync(self._parent_fd)

    def create(self, request):
        with self._mutex:
            require(not self._attempted, "PREPARATION_ALREADY_ATTEMPTED")
            self._attempted = True
        self.acquire(request.location)
        self.check(request.location, staging_exists=False)
        flags = os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0)
        descriptor = os.open(request.location.staging, flags, 0o600)
        try:
            identity = self._identity(request.location.staging)
            require(identity == (os.fstat(descriptor).st_dev, os.fstat(descriptor).st_ino))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return identity

    def readback(self, request, identity, *, final=False):
        require(self._location == request.location and self._lock is not None)
        path = request.location.final if final else request.location.staging
        self._plain(path)
        require(self._identity(path) == identity, "NATIVE_IDENTITY_MISMATCH")
        require(self._identity(path.parent) == (request.location.parent_device, request.location.parent_inode))
        # Windows _commit requires a writable descriptor even when no bytes are
        # changed. This is an existing-file open under qualified exclusion.
        with path.open("r+b") as file:
            require((os.fstat(file.fileno()).st_dev, os.fstat(file.fileno()).st_ino) == identity)
            raw = file.read()
            os.fsync(file.fileno())
        self.flush_directory()
        return sha256(raw).digest()

    def publish(self, receipt):
        location = receipt.request.location
        self.check(location, staging_exists=True)
        require(self.readback(receipt.request, receipt.native_identity) == receipt.database_sha256)
        self._no_replace(location, self._parent_fd)
        self.flush_directory()
        require(self.readback(receipt.request, receipt.native_identity, final=True) == receipt.database_sha256)

    @staticmethod
    def _no_replace(location, parent_fd):
        """Private native primitive; public execution still requires all gates."""
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.MoveFileExW.argtypes = (wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD)
            kernel.MoveFileExW.restype = wintypes.BOOL
            require(bool(kernel.MoveFileExW(str(location.staging), str(location.final), 8)), "NO_REPLACE_PUBLICATION")
        else:
            import ctypes
            libc = ctypes.CDLL(None, use_errno=True)
            rename = getattr(libc, "renameat2", None)
            require(rename is not None, "NO_REPLACE_UNSUPPORTED")
            rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
            rename.restype = ctypes.c_int
            require(rename(parent_fd, os.fsencode(location.staging.name), parent_fd,
                           os.fsencode(location.final.name), 1) == 0, "NO_REPLACE_PUBLICATION")

    def close(self):
        # Closing exclusion is never recovery or permission to repeat an attempt.
        if os.name == "nt" and self._lock is not None:
            import ctypes
            from ctypes import wintypes
            kernel, handle = self._lock
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel.CloseHandle.restype = wintypes.BOOL
            kernel.ReleaseMutex.argtypes = (wintypes.HANDLE,)
            kernel.ReleaseMutex.restype = wintypes.BOOL
            if self._directory_handle is not None:
                require(bool(kernel.CloseHandle(self._directory_handle)), "DIRECTORY_CLOSE")
                self._directory_handle = None
            if self._owns_mutex:
                require(bool(kernel.ReleaseMutex(handle)), "MUTEX_RELEASE")
                self._owns_mutex = False
            require(bool(kernel.CloseHandle(handle)), "MUTEX_CLOSE")
        elif self._parent_fd is not None:
            os.close(self._parent_fd)
            self._parent_fd = None
        self._lock = None


def _initial_metadata(request):
    require(type(request) is PreparationRequest and type(request.metadata) is store.MetadataRow)
    _external_numbers(request)
    metadata = request.metadata
    store._validate_row(metadata)
    require(type(request.context) is protocol.StateContext and request.context.representation == protocol.STATE_2)
    require((metadata.register_id, metadata.issuer_generation, metadata.activation_id) ==
            (request.register_id, 1, request.activation_id))
    require((request.context.register_id, request.context.issuer_generation, request.context.activation_id) ==
            (request.register_id, 1, request.activation_id))
    require(metadata.last_event_sequence == 0 and metadata.last_event_digest == protocol.GENESIS_EVENT_DIGEST
            and metadata.recovery_required == 0)
    protocol.identifier(request.activation_command_id)
    protocol.identifier(request.approval_id)
    require(request.activation_command_id != request.approval_id)
    projection = protocol.StateProjection(commands._adapt(metadata, protocol.MetadataRow), (), (), ())
    raw = protocol.state_bytes(projection, request.context)
    require(sha256(raw).digest() == metadata.state_digest)
    return raw


def _initial_readback(request, *, final=False):
    path = request.location.final if final else request.location.staging
    NativeStorage._plain(path)
    for suffix in ("-journal", "-wal", "-shm"):
        NativeStorage._absent(Path(str(path) + suffix))
    handle = store.LeaseStore(path, request.register_id)
    try:
        require(handle.read_rows(store.MetadataRow) == (request.metadata,))
        for row in (store.ArtifactRow, store.ReservationRow, store.ClaimRow, store.CommandRow, store.EventRow):
            require(handle.read_rows(row) == ())
    finally:
        handle.close()


def prepare_register(request, *, qualification=None, storage=None):
    reached, evidence = Reached.REJECTED, ()
    try:
        state = _initial_metadata(request)
        require(type(request.authorization) is service.EvidenceReference)
        require(isinstance(storage, NativeStorage) and isinstance(qualification, QualificationAdapter),
                "UNQUALIFIED_PREPARATION")
        q = _invoke(qualification.preparation, request)
        require(type(q) is QualifiedPreparation)
        _external_numbers(q)
        require(q.request == request and q.authorization == request.authorization)
        _evidence_fields(q, ("absence_history", "storage", "actor", "authorization", "provenance"))
        for identity in (q.operator, q.process, q.issuer):
            protocol.identifier(identity)
        require(q.process == request.clock.current.process_id)
        require(request.clock.sample.utc.lower_us == request.metadata.last_valid_utc,
                "FIXED_CREATION_TIME_MISMATCH")
        require((q.action, q.presence, q.original_history) ==
                ("PREPARE_GENESIS", "AUTHORITATIVE_ABSENT", "NO_PRIOR_OR_INFLIGHT_ATTEMPT"))
        _time(request.clock, not_before=request.metadata.last_valid_utc,
              valid_from=q.valid_from_us, valid_until=q.valid_until_us)
        # Claim no non-occurrence once dispatch to native preparation is possible.
        reached = Reached.PREPARATION_ATTEMPTED
        evidence = (request, storage)
        identity = _invoke(storage.create, request)
        evidence += (identity,)
        _native_identity_numbers(identity)
        path = request.location.staging
        require(storage._identity(path) == identity)
        connection = None
        primary = None
        try:
            store._runtime()
            connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True,
                                         isolation_level=None, timeout=0)
            connection.enable_load_extension(False)
            store._profile(connection)
            connection.execute("BEGIN IMMEDIATE").close()
            for sql in store.TABLE_SQL.values():
                connection.execute(sql).close()
            values = store._values(request.metadata)
            connection.execute("INSERT INTO REGISTER_METADATA VALUES (" + ",".join("?" for _ in values) + ")", values).close()
            store._validate_register(connection, request.register_id)
            connection.execute("COMMIT").close()
        except BaseException as error:
            primary = error
        finally:
            if connection is not None:
                try:
                    connection.close()
                except BaseException as cleanup:
                    if primary is None:
                        primary = cleanup
                    else:
                        primary.add_note("SQLite close also failed: " + type(cleanup).__name__)
        if primary is not None:
            raise primary
        _initial_readback(request)
        digest = storage.readback(request, identity)
        require(type(digest) is bytes and len(digest) == 32)
        reached = Reached.PREPARED_NON_AUTHORITATIVE
        evidence += (state, digest)
        creation = _invoke(qualification.creation, request, identity, state, digest)
        require(type(creation) is QualifiedCreation and type(creation.evidence) is OpaqueEvidence
                and type(creation.claims) is CreationClaims)
        _external_numbers(creation)
        _evidence_fields(creation, ("provenance",))
        c = creation.claims
        require(creation.evidence.role == "C" and creation.evidence.reference == c.reference)
        _evidence_fields(creation.evidence, ("qualification",))
        _reference_bytes(c.reference, creation.evidence.raw)
        require((c.purpose, c.register_id, c.generation, c.activation_id, c.native_identity, c.metadata,
                 c.authorization, c.preparation_operator, c.fixed_utc, c.state, c.dependency_stage) ==
                ("GENESIS_V1", request.register_id, 1, request.activation_id, identity,
                 commands._adapt(request.metadata, protocol.MetadataRow), request.authorization, q.operator,
                 request.metadata.last_valid_utc, "PREPARED_NON_AUTHORITATIVE", "UPSTREAM_ONLY"))
        require(type(c.schema) is SchemaBinding and c.schema.version == 1)
        _reference_bytes(c.schema.reference, store.SCHEMA_SQL.encode("utf-8"))
        require(type(c.host) is HostBinding and type(c.storage) is StorageBinding and type(c.scope) is ScopeBinding)
        require((c.host.identity, c.storage.identity) == (request.location.host_identity, request.location.storage_identity))
        require(type(c.clock) is ClockBinding)
        require((c.clock.profile.identity, c.clock.profile.sha256) ==
                (request.clock.profile.profile.identity, request.clock.profile.profile.sha256.hex()))
        require((c.clock.source, c.clock.sample.identity, c.clock.sample.sha256, c.clock.monotonic_domain) ==
                (request.clock.sample.source, request.clock.sample.sample.identity,
                 request.clock.sample.sample.sha256.hex(), request.clock.sample.anchor.domain_id))
        receipt = PreparedReceipt(request, identity, state, digest, q, storage, GenesisAttempt(), creation)
        require(storage._original_attempt is None, "PREPARATION_RECEIPT_ALREADY_BOUND")
        storage._original_attempt = receipt.attempt
        return OperationResult(Reached.PREPARED_NON_AUTHORITATIVE, False, evidence, None, receipt)
    except BaseException as error:
        return OperationResult(reached, reached is not Reached.REJECTED, evidence, error)


class GenesisAttempt:
    """Local one-dispatch guard; does not replace protected durable K/history."""
    def __init__(self):
        self._lock = threading.Lock()
        self._used = False

    def claim(self):
        with self._lock:
            require(not self._used, "GENESIS_ALREADY_ATTEMPTED")
            self._used = True


def _execution_bindings(request, accepted):
    require(type(request) is ExecutionRequest and type(request.prepared) is PreparedReceipt)
    _external_numbers(request)
    receipt = request.prepared
    e, p = accepted.evidence, accepted.package
    initial = receipt.request
    require(initial.location == accepted.qualification.claims.storage.location)
    require(receipt.native_identity == accepted.qualification.claims.creation.native_identity)
    require(receipt.creation.claims == accepted.qualification.claims.creation)
    require(receipt.creation.evidence.reference == accepted.evidence.creation_evidence)
    _reference_bytes(receipt.creation.evidence.reference, receipt.creation.evidence.raw)
    require(receipt.creation.evidence.raw == next(item.raw for item in accepted.qualification.opaque
                                                 if item.role == "E.creation_evidence"))
    require(initial.authorization == accepted.qualification.claims.creation.authorization)
    require((receipt.qualification.operator, receipt.qualification.process, receipt.qualification.issuer) ==
            (e.actors.preparation_operator, e.actors.process, e.actors.issuer))
    require((initial.register_id, initial.activation_id, initial.activation_command_id, initial.approval_id) ==
            (e.register_id, e.activation_id, e.activation_command_id, e.approval_id))
    require(initial.location.host_identity == e.host.identity and initial.location.storage_identity == e.storage.identity)
    require(receipt.state == accepted.snapshot.state and _initial_metadata(initial) == receipt.state)
    require(initial.metadata.last_valid_utc == e.creation_utc_us)
    require(request.clock.profile == initial.clock.profile)
    require(request.clock.profile == accepted.qualification.profile)
    require(initial.clock.sample == accepted.qualification.creation_sample,
            "CREATION_SAMPLE_BINDING")
    require(request.clock.current.process_id == e.actors.process and
            request.clock.current.domain_id == e.clock.monotonic_domain)
    _approval(request.approval, accepted, request.clock)
    _time(request.clock, not_before=e.creation_utc_us, valid_from=p.authorization.valid_from_us,
          valid_until=p.authorization.valid_until_us)


def _qualified_execution(request, accepted, qualification):
    q = _invoke(qualification.execution, request)
    require(type(q) is QualifiedExecution)
    _external_numbers(q)
    require(q.request == request and q.authorization == request.authorization)
    _evidence_fields(q, ("absence_history", "storage", "actor", "authorization", "provenance"))
    e, p = accepted.evidence, accepted.package
    require((q.operator, q.process, q.issuer, q.action, q.presence, q.original_history) ==
            (e.actors.genesis_operator, e.actors.process, e.actors.issuer, "EXECUTE_ORIGINAL_GENESIS",
             "AUTHORITATIVE_ABSENT", "ORIGINAL_UNATTEMPTED_K"))
    require(q.clock.profile == accepted.qualification.profile)
    require((q.clock.current.process_id, q.clock.current.domain_id) == (e.actors.process, e.clock.monotonic_domain))
    _time(q.clock, not_before=e.creation_utc_us, valid_from=q.valid_from_us, valid_until=q.valid_until_us)
    _time(q.clock, not_before=e.creation_utc_us, valid_from=p.authorization.valid_from_us,
          valid_until=p.authorization.valid_until_us)
    _approval(request.approval, accepted, q.clock)
    return q


def execute_genesis(request, *, qualification=None, protected=None, attempt=None):
    reached, evidence = Reached.REJECTED, ()
    try:
        require(type(request) is ExecutionRequest and isinstance(qualification, QualificationAdapter)
                and isinstance(protected, ProtectedGenesis))
        require(type(attempt) is GenesisAttempt)
        accepted = _qualified_package(request.snapshot, qualification)
        _execution_bindings(request, accepted)
        require(attempt is request.prepared.attempt, "ORIGINAL_ATTEMPT_REQUIRED")
        require(attempt is request.prepared.storage._original_attempt, "ORIGINAL_PREPARATION_REQUIRED")
        q = _qualified_execution(request, accepted, qualification)
        e, p = accepted.evidence, accepted.package
        payload = _bound_payload(accepted, request.approval)
        raw_payload = canonical_bytes(payload)
        attempt.claim()
        receipt = request.prepared
        reached = Reached.FILE_PUBLICATION_ATTEMPTED
        evidence = (request,)
        _invoke(receipt.storage.publish, receipt)
        reached = Reached.FILE_PUBLISHED_NON_AUTHORITATIVE
        _initial_readback(receipt.request, final=True)
        require(receipt.storage.readback(receipt.request, receipt.native_identity, final=True) == receipt.database_sha256)
        _qualified_execution(request, accepted, qualification)
        reached = Reached.CHECKPOINT_ATTEMPTED
        publication = _invoke(protected.publish_checkpoint, request.snapshot, request.approval, request.authorization)
        evidence += (publication,)
        require(type(publication) is CheckpointResult and publication.status == "CONFIRMED")
        require((publication.checkpoint, publication.package, publication.approval, publication.host_identity) ==
                (p.checkpoint, content_reference(p), request.approval.evidence.reference, e.host.identity))
        protocol.identifier(publication.operation)
        _evidence_fields(publication, ("evidence",))
        reached = Reached.CHECKPOINT_CONFIRMED
        # Fresh time/absence/exclusion qualification after external publication.
        fresh = _qualified_execution(request, accepted, qualification)
        require(receipt.storage.readback(receipt.request, receipt.native_identity, final=True) == receipt.database_sha256)
        reached = Reached.CAS_ATTEMPTED
        result = _invoke(protected.activate_absent, raw_payload, publication, fresh.absence_history, request.authorization)
        evidence += (result,)
        _activation_result(result, accepted, request.approval.evidence.reference, sha256(raw_payload).digest())
        reached = Reached.CAS_CONFIRMED_VERIFICATION_PENDING
        readback = _invoke(protected.readback, result)
        evidence += (readback,)
        _activation_result(readback, accepted, request.approval.evidence.reference, sha256(raw_payload).digest())
        require(readback == result or readback.evidence != result.evidence)
        return OperationResult(Reached.READBACK_CONFIRMED_VERIFICATION_PENDING, True, evidence, None)
    except BaseException as error:
        return OperationResult(reached, reached is not Reached.REJECTED, evidence, error)


def _activation_result(result, accepted, approval, payload_hash):
    require(type(result) is ActivationResult and result.status == "CONFIRMED")
    _external_numbers(result)
    e, p = accepted.evidence, accepted.package
    require((result.command_id, result.payload_sha256, result.package, result.checkpoint, result.approval,
             result.register_id, result.generation, result.activation_id, result.host_identity) ==
            (e.activation_command_id, payload_hash, content_reference(p), p.checkpoint, approval,
             e.register_id, 1, e.activation_id, e.host.identity))
    _evidence_fields(result, ("evidence",))


@dataclass(frozen=True)
class OpenRequest:
    snapshot: PackageSnapshot
    location: StorageLocation
    native_identity: tuple[int, int]
    approval: ApprovalView
    original_result: ActivationResult
    independent_result_verification: OpaqueEvidence
    clock: TimeBinding
    opener: str
    issuer: str


@dataclass(frozen=True)
class QualifiedOpen:
    request: OpenRequest
    activation: ActivationResult
    checkpoint_state_sha256: bytes
    event_sequence: int
    event_digest: bytes
    current_checkpoint: service.EvidenceReference
    history: service.EvidenceReference
    storage: service.EvidenceReference
    actor: service.EvidenceReference
    result_verification: service.EvidenceReference
    clock: service.EvidenceReference
    provenance: service.EvidenceReference
    fresh_time: TimeBinding
    opener: str
    issuer: str
    process: str
    state: str


class _ReadSnapshot:
    """Fixed immutable read adapter for existing frozen consistency validators."""
    def __init__(self, handle):
        self.rows = {cls: handle.read_rows(cls) for cls in store.SPECS}

    def iter_rows(self, cls):
        return iter(self.rows[cls])

    def lookup(self, cls, key):
        return next((row for row in self.rows[cls] if getattr(row, fields(cls)[0].name) == key), None)

    def event_interval(self, first, final):
        return (row for row in self.rows[store.EventRow] if first <= row.event_sequence <= final)

    def claims_for(self, reservation_id):
        return (row for row in self.rows[store.ClaimRow] if row.reservation_id == reservation_id)


class AuthoritativeHandle:
    """Scoped read handle only; never a normal permit or generic SQL capability."""
    def __init__(self, handle, ownership, request, qualification):
        self._handle = handle
        self._ownership = ownership
        self._request = request
        self._qualification = qualification
        self._fenced = False

    def read_rows(self, row_type):
        """Typed reads requalify current authority; no SQL or operation permission."""
        require(not self._fenced and row_type in store.SPECS)
        result = open_authoritative_register(self._request, qualification=self._qualification,
                                             storage=self._ownership)
        if result.cause is not None:
            self._fenced = True
            raise ActivationRejected("HANDLE_FENCED") from result.cause
        replacement = result.receipt
        try:
            self._handle.close()
            self._handle = replacement._handle
            return self._handle.read_rows(row_type)
        except BaseException:
            self._fenced = True
            raise

    def close(self):
        self._fenced = True
        primary = None
        try:
            self._handle.close()
        except BaseException as error:
            primary = error
        try:
            self._ownership.close()
        except BaseException as error:
            if primary is None:
                primary = error
            else:
                primary.add_note("Ownership close also failed: " + type(error).__name__)
        if primary is not None:
            raise primary


def open_authoritative_register(request, *, qualification=None, storage=None):
    handle = None
    ownership_acquired_here = False
    try:
        require(type(request) is OpenRequest and isinstance(qualification, QualificationAdapter)
                and isinstance(storage, NativeStorage))
        _external_numbers(request)
        accepted = _qualified_package(request.snapshot, qualification)
        e = accepted.evidence
        require((request.opener, request.issuer) == (e.actors.opener, e.actors.issuer))
        require((request.location.host_identity, request.location.storage_identity) == (e.host.identity, e.storage.identity))
        _approval(request.approval, accepted, request.clock)
        require(type(request.independent_result_verification) is OpaqueEvidence and
                request.independent_result_verification.role == "INDEPENDENT_RESULT_VERIFICATION")
        _reference_bytes(request.independent_result_verification.reference, request.independent_result_verification.raw)
        q = _invoke(qualification.opening, request)
        require(type(q) is QualifiedOpen)
        _external_numbers(q)
        require(q.request == request)
        require((q.opener, q.issuer, q.process, q.state) ==
                (e.actors.opener, e.actors.issuer, e.actors.process, "VERIFIED_CURRENT_NO_UNRESOLVED_OUTCOME"))
        _evidence_fields(q, ("current_checkpoint", "history", "storage", "actor", "result_verification", "clock", "provenance"))
        # Current approval applicability follows the authenticated opening sample,
        # including every read that re-enters this path. Request time is not enough.
        require(type(q.fresh_time) is TimeBinding, "QUALIFIED_OPENING_TIME_REQUIRED")
        require(q.fresh_time.profile == accepted.qualification.profile)
        require(q.fresh_time.sample.anchor.process_id == e.actors.process and
                q.fresh_time.sample.anchor.domain_id == e.clock.monotonic_domain)
        _approval(request.approval, accepted, q.fresh_time)
        require(type(request.independent_result_verification.qualification) is service.EvidenceReference)
        payload_hash = sha256(canonical_bytes(_bound_payload(accepted, request.approval))).digest()
        _activation_result(request.original_result, accepted, request.approval.evidence.reference, payload_hash)
        _activation_result(q.activation, accepted, request.approval.evidence.reference,
                           payload_hash)
        # Ownership is independently qualified; open cannot acquire genesis authority.
        require(request.location == accepted.qualification.claims.storage.location)
        require(request.native_identity == accepted.qualification.claims.creation.native_identity)
        if storage._lock is None:
            require(q.fresh_time.sample.sample != accepted.qualification.creation_sample.sample,
                    "FRESH_STARTUP_SAMPLE_REQUIRED")
            ownership_acquired_here = True
            _invoke(storage.acquire_existing, request.location, request.native_identity)
        require(storage._location == request.location and storage._lock is not None)
        storage.check_existing(request.location, request.native_identity)
        storage._plain(request.location.final)
        require(storage._identity(request.location.final) == request.native_identity)
        require(storage._identity(request.location.final.parent) == (request.location.parent_device, request.location.parent_inode))
        handle = store.LeaseStore(request.location.final, e.register_id)
        rows = _ReadSnapshot(handle)
        metadata = rows.lookup(store.MetadataRow, 1)
        require(metadata is not None and metadata.recovery_required == 0)
        projection, context = initial_projection(e)
        initial = projection.metadata
        for name in ("singleton", "schema_version", "register_id", "issuer_generation", "activation_id",
                     "fixture_plan_sha256", "bootstrap_amendment_sha256", "provisioning_contract_sha256", "design_sha256"):
            require(getattr(metadata, name) == getattr(initial, name), "METADATA_BINDING")
        _time(q.fresh_time, not_before=metadata.last_valid_utc,
              valid_from=accepted.package.authorization.valid_from_us,
              valid_until=accepted.package.authorization.valid_until_us)
        require(q.fresh_time.profile == accepted.qualification.profile)
        require(q.fresh_time.sample.anchor.process_id == e.actors.process and
                q.fresh_time.sample.anchor.domain_id == e.clock.monotonic_domain)
        commands._snapshot(rows, metadata, context)
        for reservation in rows.iter_rows(store.ReservationRow):
            commands._structural_projection(rows, reservation, tuple(rows.claims_for(reservation.reservation_id)))
        require((metadata.state_digest, metadata.last_event_sequence, metadata.last_event_digest) ==
                (q.checkpoint_state_sha256, q.event_sequence, q.event_digest))
        if metadata.last_event_sequence == 0:
            require(all(not rows.rows[cls] for cls in store.SPECS if cls is not store.MetadataRow))
            require(metadata.state_digest.hex() == e.initial_state.sha256)
        scoped = AuthoritativeHandle(handle, storage, request, qualification)
        return OperationResult(Reached.OPEN_VALIDATED, False, (q,), None, scoped)
    except BaseException as error:
        if handle is not None:
            try:
                handle.close()
            except BaseException as cleanup:
                error.add_note("Open cleanup also failed: " + type(cleanup).__name__)
        if ownership_acquired_here:
            try:
                storage.close()
            except BaseException as cleanup:
                error.add_note("Open ownership cleanup also failed: " + type(cleanup).__name__)
        return OperationResult(Reached.REJECTED, True, (), error)


# Exhaustive numeric fields on IL6 external views. Other external numeric values
# are covered by _SCHEMAS or the unchanged protocol/store/service validators above.
_EXTERNAL_NUMERIC_FIELDS = {
    CreationClaims: (("generation", "one"), ("fixed_utc", "utc"), ("native_identity", "native")),
    StorageClaims: (("native_identity", "native"),),
    StorageLocation: (("parent_device", "native_scalar"), ("parent_inode", "native_scalar")),
    QualifiedPreparation: (("valid_from_us", "utc"), ("valid_until_us", "utc")),
    PreparedReceipt: (("native_identity", "native"),),
    ApprovalView: (("generation", "one"), ("valid_from_us", "utc"), ("valid_until_us", "utc")),
    QualifiedExecution: (("valid_from_us", "utc"), ("valid_until_us", "utc")),
    ActivationResult: (("generation", "one"),),
    OpenRequest: (("native_identity", "native"),),
    QualifiedOpen: (("event_sequence", "uint"),),
    protocol.StateContext: (("issuer_generation", "uint"),),
}
