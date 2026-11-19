"""Source-owned admission. Environment, credentials and requests cannot activate it."""
import hashlib
import json
from dataclasses import asdict, dataclass
from .contracts import RouteUnavailable

REASON = 'HOSTED_TOKEN_TEMPLATE_AUTHORITY_UNRESOLVED'


@dataclass(frozen=True)
class Route:
    route_id: str = 'hf-qwen3-32b-deepinfra-v1'
    logical_model_id: str = 'jous.text.general.v1'
    supplier_id: str = 'hugging_face'
    supplier_native_model_id: str = 'Qwen/Qwen3-32B:deepinfra'
    underlying_provider: str = 'DeepInfra'
    admission_version: str = 'v1.2.offline.1'
    implemented: bool = True
    offline_testable: bool = True
    real_execution_eligible: bool = False
    ineligibility_reason: str = REASON


HF_ROUTE = Route()


def snapshot():
    return asdict(HF_ROUTE)


def catalog_digest():
    return hashlib.sha256(json.dumps(snapshot(), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def resolve(logical_model_id, route_id):
    if (logical_model_id, route_id) != (HF_ROUTE.logical_model_id, HF_ROUTE.route_id):
        raise RouteUnavailable('Route unavailable')
    return HF_ROUTE


def require_real_eligibility(route):
    # Deliberately source-owned denial, including forged/replaced Route objects.
    # A future reviewed admission-evidence code change is necessary here too.
    raise RouteUnavailable(REASON)
