"""Policy-bound RFC3161 verification and the unchanged IL6 monotonic bridge.

No default endpoint, wall clock, certificate store, credential chain or I/O at
import/construction. Approved policy/status/bootstrap material is supplied via
the existing independent evidence-verifier boundary. No TSA retransmission.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from fractions import Fraction
from hashlib import sha256
import re
from threading import Lock

from . import fixture_lease_authority_evidence as e
from . import fixture_lease_authority_providers as p


@dataclass(frozen=True, repr=False)
class TsaPolicy:
    service: p.s.EvidenceReference
    policy_oid: str
    signer_der_sha256: str
    chain_der: tuple
    policy_accuracy_us: int
    allowed_signature_algorithms: tuple
    entitlement: p.s.EvidenceReference
    bootstrap: p.s.EvidenceReference
    status: tuple
    qualification: p.s.EvidenceReference


def _ceil(value):
    return -((-value.numerator) // value.denominator)


def _floor(value):
    return value.numerator // value.denominator


def conservative_interval(g_us, accuracy_us, elapsed_ns, measurement_error_ns, extra_error_ns=0):
    """All errors occur once; elapsed is never halved or centered."""
    e.need(type(g_us) in (int, Fraction), "AUTHENTICATED_GENTIME_REQUIRED")
    for value in (accuracy_us, elapsed_ns, measurement_error_ns, extra_error_ns):
        e.uint(value)
    g = Fraction(g_us)
    duration = Fraction(elapsed_ns + measurement_error_ns, 1000)
    extra = Fraction(extra_error_ns, 1000)
    return p.s.UtcInterval(_floor(g - accuracy_us - extra),
                           _ceil(g + accuracy_us + duration + extra))


def _der(cls, raw):
    e.need(type(raw) is bytes, "EXACT_DER_BYTES")
    try:
        parsed = cls.load(raw, strict=True)
        e.need(parsed.dump(force=True) == raw, "NON_DER_ENCODING")
        return parsed
    except (ValueError, TypeError, KeyError):
        raise e.EvidenceFailure("MALFORMED_DER") from None


def request_der(*, context_bytes, nonce, policy):
    from asn1crypto import tsp
    e.need(type(context_bytes) is bytes, "SAMPLE_CONTEXT_BYTES")
    e.need(type(nonce) is bytes and 16 <= len(nonce) <= 32 and any(nonce), "UNPREDICTABLE_NONCE_REQUIRED")
    e.need(type(policy) is TsaPolicy, "QUALIFIED_TSA_POLICY")
    # The explicit entropy carrier must independently establish freshness and
    # unpredictability. A caller-supplied integer is not accepted as entropy.
    return tsp.TimeStampReq({"version": "v1", "message_imprint": {
        "hash_algorithm": {"algorithm": "sha256"}, "hashed_message": sha256(context_bytes).digest()},
        "req_policy": policy.policy_oid, "nonce": int.from_bytes(nonce, "big"), "cert_req": True}).dump()


def _utc_fraction(value):
    e.need(value.tzinfo is not None and value.utcoffset().total_seconds() == 0, "UTC_GENTIME")
    difference = value - datetime(1970, 1, 1, tzinfo=timezone.utc)
    return Fraction((difference.days * 86400 + difference.seconds) * 1000000 + difference.microseconds)


def _gen_time(raw):
    """Preserve arbitrary DER fractional precision before outward rounding."""
    matched = re.fullmatch(rb"([0-9]{14})(?:\.([0-9]+))?Z", raw)
    e.need(matched is not None, "DER_UTC_GENTIME_REQUIRED")
    whole = datetime.strptime(matched[1].decode("ascii"), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    fraction = matched[2]
    return _utc_fraction(whole) + (Fraction(int(fraction), 10 ** len(fraction)) * 1000000 if fraction else 0)


@e.closed_boundary("TSA_RESPONSE_NOT_QUALIFIED")
def validate_response(*, request_raw, response_raw, context_bytes, policy, authority):
    """CMS authenticity plus separately qualified path/status/bootstrap policy.

    authority is the selected independent qualification client, rooted through
    approved evidence. It authenticates entitlement, exact permitted certificate
    path, revocation and bootstrap-time validity, without OS time/network lookup.
    Commodity ASN.1 and cryptography perform parsing and mathematical signatures.
    """
    from asn1crypto import tsp
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding, rsa, ec
    from cryptography.x509.oid import ExtendedKeyUsageOID

    req = _der(tsp.TimeStampReq, request_raw)
    response = _der(tsp.TimeStampResp, response_raw)
    e.need(response["status"]["status"].native in ("granted", "granted_with_mods"), "TSA_STATUS")
    e.need(req["version"].native == "v1" and req["req_policy"].native == policy.policy_oid
           and req["nonce"].native is not None, "EXACT_TSA_REQUEST")
    expected_imprint = sha256(context_bytes).digest()
    e.need(req["message_imprint"]["hash_algorithm"]["algorithm"].native == "sha256"
           and req["message_imprint"]["hashed_message"].native == expected_imprint, "REQUEST_IMPRINT")
    token = response["time_stamp_token"]
    e.need(token["content_type"].native == "signed_data", "CMS_SIGNED_DATA_REQUIRED")
    cms = token["content"]
    content = cms["encap_content_info"]
    e.need(content["content_type"].native == "tst_info", "TSTINFO_REQUIRED")
    info_raw = content["content"].contents
    info = _der(tsp.TSTInfo, info_raw)
    e.need(info["version"].native == "v1" and info["policy"].native == policy.policy_oid
           and info["nonce"].native == req["nonce"].native, "TSA_POLICY_NONCE")
    e.need(info["message_imprint"].dump() == req["message_imprint"].dump(), "RESPONSE_IMPRINT")
    e.need(len(cms["signer_infos"]) == 1, "AMBIGUOUS_TSA_SIGNER")
    signer = cms["signer_infos"][0]
    e.need(signer["digest_algorithm"]["algorithm"].native == "sha256", "TSA_DIGEST_ALGORITHM")
    e.need(signer["signature_algorithm"]["algorithm"].native in policy.allowed_signature_algorithms,
           "UNAPPROVED_TSA_SIGNATURE_ALGORITHM")
    candidates = [c.chosen for c in cms["certificates"] if c.name == "certificate"]
    candidates = [c for c in candidates if sha256(c.dump()).hexdigest() == policy.signer_der_sha256]
    e.need(len(candidates) == 1, "EXACT_APPROVED_TSA_CERTIFICATE")
    certificate = candidates[0]
    sid = signer["sid"]
    e.need(sid.name == "issuer_and_serial_number"
           and sid.chosen["serial_number"].native == certificate.serial_number
           and sid.chosen["issuer"].dump() == certificate.issuer.dump(), "CMS_SIGNER_IDENTITY")
    attributes = signer["signed_attrs"]
    attrs = {}
    for attr in attributes:
        name = attr["type"].native
        e.need(name not in attrs and len(attr["values"]) == 1, "AMBIGUOUS_CMS_ATTRIBUTE")
        attrs[name] = attr["values"][0]
    e.need("content_type" in attrs and attrs["content_type"].native == "tst_info"
           and "message_digest" in attrs
           and attrs["message_digest"].native == sha256(info_raw).digest(), "CMS_CONTENT_BINDING")
    if "signing_certificate_v2" in attrs:
        certid = attrs["signing_certificate_v2"]["certs"][0]
        e.need(certid["hash_algorithm"]["algorithm"].native == "sha256"
               and certid["cert_hash"].native == sha256(certificate.dump()).digest(), "ESS_CERT_BINDING")
    elif "signing_certificate" in attrs:
        from hashlib import sha1
        certid = attrs["signing_certificate"]["certs"][0]
        e.need(certid["cert_hash"].native == sha1(certificate.dump()).digest(), "ESS_CERT_BINDING")
    else:
        e.need(False, "ESS_SIGNER_CERTIFICATE_BINDING_REQUIRED")
    leaf = x509.load_der_x509_certificate(certificate.dump())
    usage = leaf.extensions.get_extension_for_class(x509.ExtendedKeyUsage)
    e.need(usage.critical and list(usage.value) == [ExtendedKeyUsageOID.TIME_STAMPING], "TIMESTAMP_ONLY_EKU")
    key = leaf.public_key()
    signed = attributes.untag().dump()
    signature = signer["signature"].native
    algorithm = signer["signature_algorithm"]["algorithm"].native
    try:
        if algorithm in ("rsassa_pkcs1v15", "sha256_rsa"):
            e.need(isinstance(key, rsa.RSAPublicKey) and key.key_size >= 2048, "TSA_RSA_SIZE")
            key.verify(signature, signed, padding.PKCS1v15(), hashes.SHA256())
        elif algorithm == "sha256_ecdsa":
            e.need(isinstance(key, ec.EllipticCurvePublicKey) and key.key_size >= 256, "TSA_EC_SIZE")
            key.verify(signature, signed, ec.ECDSA(hashes.SHA256()))
        elif algorithm == "rsassa_pss":
            parameters = signer["signature_algorithm"]["parameters"]
            e.need(isinstance(key, rsa.RSAPublicKey) and key.key_size >= 2048
                   and parameters["hash_algorithm"]["algorithm"].native == "sha256"
                   and parameters["mask_gen_algorithm"]["algorithm"].native == "mgf1"
                   and parameters["mask_gen_algorithm"]["parameters"]["algorithm"].native == "sha256"
                   and parameters["trailer_field"].native == "trailer_field_bc", "TSA_PSS_PARAMETERS")
            salt = parameters["salt_length"].native
            e.uint(salt)
            key.verify(signature, signed, padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=salt), hashes.SHA256())
        else:
            e.need(False, "UNSUPPORTED_TSA_ALGORITHM")
    except Exception:
        raise e.EvidenceFailure("TSA_SIGNATURE_REJECTED") from None
    e.need(type(policy.chain_der) is tuple and len(policy.chain_der) >= 2
           and policy.chain_der[0] == certificate.dump(), "PINNED_TSA_PATH")
    path = tuple(x509.load_der_x509_certificate(raw) for raw in policy.chain_der)
    for child, issuer in zip(path, path[1:]):
        child.verify_directly_issued_by(issuer)
    # Full X.509 path policies, constraints, critical extensions, name constraints,
    # allowed algorithms, revocation and certificate validity are independently
    # qualified against precisely this retained path and authenticated token.
    # Mathematical path verification above alone never establishes adoption.
    authority.validate_tsa_path(policy, policy.chain_der, request_raw, response_raw, info_raw)
    gen = _gen_time(info["gen_time"].contents)
    accuracy = info["accuracy"]
    token_accuracy = 0
    if accuracy.native is not None:
        seconds = accuracy["seconds"].native or 0
        millis = accuracy["millis"].native or 0
        micros = accuracy["micros"].native or 0
        e.need(type(seconds) is int and seconds >= 0 and type(millis) is int and 0 <= millis <= 999
               and type(micros) is int and 0 <= micros <= 999
               and (accuracy["millis"].native is None or millis >= 1)
               and (accuracy["micros"].native is None or micros >= 1), "TSA_ACCURACY")
        token_accuracy = seconds * 1000000 + millis * 1000 + micros
    e.uint(policy.policy_accuracy_us)
    return gen, max(token_accuracy, policy.policy_accuracy_us)


class Rfc3161Bridge:
    def __init__(self, *, policy, profile, authority, evidence, transport, monotonic, entropy):
        self.policy, self.profile, self.authority = policy, profile, authority
        self.evidence, self.transport = evidence, transport
        self.monotonic, self.entropy = monotonic, entropy
        self._state = None
        self._epoch = 0
        self._state_lock = Lock()
        self._refresh_lock = Lock()
        self._requests = set()
        self._request_lock = Lock()

    @e.closed_boundary("TSA_SAMPLE_UNAVAILABLE_NO_RETRANSMISSION")
    def sample(self, *, request_id, context_record):
        with self._refresh_lock:
            with self._state_lock:
                epoch = self._epoch
                profile = self.profile
            try:
                return self._refresh(request_id=request_id, context_record=context_record, epoch=epoch, profile=profile)
            except BaseException:
                with self._state_lock:
                    if self._epoch == epoch:
                        self._epoch += 1
                        self._state = None
            raise e.EvidenceFailure("TSA_SAMPLE_UNAVAILABLE_NO_RETRANSMISSION")

    def _refresh(self, *, request_id, context_record, epoch, profile):
        e.identifier(request_id)
        with self._request_lock:
            e.need(request_id not in self._requests, "TSA_REQUEST_ALREADY_ENTERED")
            # Includes uncertainty while retaining the original DER request:
            # the same request identity never gets a replacement nonce/body.
            self._requests.add(request_id)
        e.need(type(context_record) is p.RetainedEvidence
               and sha256(context_record.raw).digest() == context_record.reference.sha256, "SAMPLE_CONTEXT")
        self.authority.authorize_sample(self.policy, profile, request_id, context_record)
        nonce = self.entropy.fresh_nonce(request_id)
        request = request_der(context_bytes=context_record.raw, nonce=nonce, policy=self.policy)
        request_record = p.RetainedEvidence(p.s.EvidenceReference(request_id, sha256(request).digest()), request)
        self.evidence.retain(request_record)
        send = self.monotonic.observe()
        # A timeout consumes this request. No automatic TSA retransmission.
        try:
            response = self.transport.timestamp(request)
            receive = self.monotonic.observe()
            e.need(type(send) is p.s.MonotonicPoint and type(receive) is p.s.MonotonicPoint
                   and (send.process_id, send.domain_id) == (receive.process_id, receive.domain_id)
                   and receive.ticks_ns >= send.ticks_ns, "QUALIFIED_MONOTONIC_CONTINUITY")
            response_record = self.authority.response_record(request_record, response, send, receive)
            self.evidence.retain(response_record)
            gen, accuracy = validate_response(request_raw=request, response_raw=response,
                context_bytes=context_record.raw, policy=self.policy, authority=self.authority)
            anchor = self.monotonic.observe()
            measured_error, validation_error = self.authority.elapsed_errors(send, receive, anchor, profile)
            e.need((anchor.process_id, anchor.domain_id) == (send.process_id, send.domain_id)
                   and anchor.ticks_ns >= receive.ticks_ns, "SAMPLE_ANCHOR_CONTINUITY")
            interval = conservative_interval(gen, accuracy, anchor.ticks_ns - send.ticks_ns,
                                             measured_error, validation_error)
            validation = self.authority.retain_validation(request_record, response_record, interval, anchor)
            sample = p.s.QualifiedSample(response_record.reference, profile.source,
                                          profile.profile, validation, interval, anchor)
            self._publish(sample, epoch, profile)
            return sample
        except Exception:
            with self._state_lock:
                if self._epoch == epoch:
                    self._epoch += 1
                    self._state = None
            raise e.EvidenceFailure("TSA_SAMPLE_UNAVAILABLE_NO_RETRANSMISSION") from None

    def _publish(self, sample, epoch, profile=None):
        # Publication is a single immutable state transition. An invalidation
        # during an in-flight refresh wins; that refresh cannot restore a root.
        with self._state_lock:
            if profile is None:
                profile = self.profile
            e.need(epoch == self._epoch and self.profile is profile, "INVALIDATED_REFRESH")
            self._epoch += 1
            self._state = (sample, (sample.anchor.process_id, sample.anchor.domain_id), profile, self._epoch)

    @e.closed_boundary("UNKNOWN_TRUSTED_TIME_UNAVAILABLE")
    def current(self):
        with self._state_lock:
            state = self._state
            profile = self.profile
        e.need(state is not None, "QUALIFIED_STARTUP_SAMPLE_REQUIRED")
        sample, domain, profile, epoch = state
        try:
            return self._current_snapshot(state, sample, domain, profile, epoch)
        except BaseException:
            with self._state_lock:
                if self._state is state:
                    self._epoch += 1
                    self._state = None
        raise e.EvidenceFailure("UNKNOWN_TRUSTED_TIME_UNAVAILABLE")

    def _current_snapshot(self, state, sample, domain, profile, epoch):
        current = self.monotonic.observe()
        e.need((current.process_id, current.domain_id) == domain, "RESTART_INVALIDATES_ANCHOR")
        error = self.authority.propagation(sample, profile, current)
        p.s.evaluate_time(sample, profile, current, error)
        binding = p.a.TimeBinding(profile, sample, current, error)
        with self._state_lock:
            e.need(self._state is state and self._epoch == epoch and self.profile is profile,
                   "TIME_STATE_CHANGED_DURING_OBSERVATION")
            return binding

    def invalidate(self):
        with self._state_lock:
            self._epoch += 1
            self._state = None
