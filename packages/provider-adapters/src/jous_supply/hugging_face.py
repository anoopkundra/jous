"""Non-streaming HF wire implementation; live execution is admission-blocked."""
import asyncio
import json
from datetime import datetime, timezone
import httpx
from .contracts import ExecutionRequest, Outcome, USAGE_KEYS
from .registry import HF_ROUTE, require_real_eligibility

DESTINATION = 'https://router.huggingface.co/v1/chat/completions'


class HuggingFaceAdapter:
    async def execute(self, request: ExecutionRequest, credential=None):
        # No credential lookup or socket can occur before this mandatory gate.
        require_real_eligibility(HF_ROUTE)

    async def exercise_offline(self, request: ExecutionRequest, transport: httpx.MockTransport):
        """Explicit non-operational seam: accepts only in-memory HTTPX transport."""
        if type(transport) is not httpx.MockTransport:
            raise ValueError('In-memory transport required')
        return await self._exchange(request, transport)

    async def _exchange(self, request, transport):
        started = datetime.now(timezone.utc)
        remaining = (request.deadline - started).total_seconds()
        if remaining <= 0 or not 1 <= request.max_tokens <= 1024:
            return Outcome('known_error', error_code='not_dispatched')
        try:
            async with asyncio.timeout(min(remaining, 20)):
                async with httpx.AsyncClient(transport=transport, verify=True, trust_env=False,
                    follow_redirects=False, http2=False, timeout=min(remaining, 20),
                    limits=httpx.Limits(max_connections=2, max_keepalive_connections=0)) as client:
                    async with client.stream('POST', DESTINATION, headers={'Content-Type': 'application/json','Accept-Encoding':'identity'},
                        json={'model': HF_ROUTE.supplier_native_model_id,
                              'messages': [{'role': 'system', 'content': request.system},
                                           {'role': 'user', 'content': request.user}],
                              'max_tokens': request.max_tokens, 'temperature': 0.7,
                              'stream': False, 'chat_template_kwargs': {'enable_thinking': False}}) as response:
                        received = datetime.now(timezone.utc)
                        stamp = {'request_started_at': started, 'response_received_at': received}
                        if response.headers.get('content-encoding','identity') != 'identity':
                            return Outcome('known_error', error_code='malformed_response', **stamp)
                        if response.status_code == 429:
                            return Outcome('known_error', error_code='rate_limited', **stamp)
                        if response.status_code != 200:
                            return Outcome('known_error', error_code='supplier_rejected', **stamp)
                        raw = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            if len(raw) + len(chunk) > 1048576:
                                return Outcome('known_error', error_code='response_too_large', **stamp)
                            raw.extend(chunk)
                        return normalize(bytes(raw), started, datetime.now(timezone.utc))
        except (TimeoutError, httpx.TimeoutException):
            return Outcome('unknown', error_code='provider_timeout', request_started_at=started)
        except httpx.HTTPError:
            return Outcome('unknown', error_code='transport_ambiguous', request_started_at=started)


def normalize(raw, started, received):
    stamp = {'request_started_at': started, 'response_received_at': received}
    try:
        body = json.loads(raw)
        if not isinstance(body, dict): raise ValueError()
        choices = body['choices']
        if not isinstance(choices, list) or len(choices) != 1: raise ValueError()
        choice = choices[0]
        if not isinstance(choice, dict): raise ValueError()
        message = choice['message']
        if not isinstance(message, dict): raise ValueError()
        refusal = message.get('refusal')
        content = refusal if isinstance(refusal, str) else message.get('content')
        if content is not None and not isinstance(content, str): raise ValueError()
        # Never retain reasoning fields; ambiguous inline reasoning is rejected.
        if content is not None and ('<think>' in content or '</think>' in content):
            return Outcome('known_error', error_code='metadata_inconsistent', **stamp)
        if content is not None and len(content.encode('utf-8')) > 65536:
            return Outcome('known_error', error_code='response_too_large', **stamp)
        def identifier(value):
            if value is None: return None
            if not isinstance(value, str) or not value.strip() or len(value.encode()) > 255: raise ValueError()
            return value
        model = identifier(body.get('model'))
        if model is not None and model not in ('Qwen/Qwen3-32B', HF_ROUTE.supplier_native_model_id):
            return Outcome('known_error', error_code='metadata_inconsistent', **stamp)
        provider = identifier(body.get('provider'))
        if provider is not None and provider != HF_ROUTE.underlying_provider:
            return Outcome('known_error', error_code='metadata_inconsistent', **stamp)
        usage = {}
        supplied = body.get('usage')
        if supplied is not None:
            if not isinstance(supplied, dict): raise ValueError()
            for upstream, local in [('prompt_tokens','input_tokens'),('completion_tokens','output_tokens'),('total_tokens','total_tokens')]:
                if upstream in supplied:
                    v = supplied[upstream]
                    if type(v) is not int or v < 0: raise ValueError()
                    usage[local] = v
            for outer, inner, local in [('prompt_tokens_details','cached_tokens','cached_input_tokens'),
                                         ('completion_tokens_details','reasoning_tokens','reasoning_tokens')]:
                if outer in supplied and supplied[outer] is not None:
                    details = supplied[outer]
                    if not isinstance(details, dict): raise ValueError()
                    if inner in details:
                        v = details[inner]
                        if type(v) is not int or v < 0: raise ValueError()
                        usage[local] = v
        if len(json.dumps(usage).encode()) > 8192: raise ValueError()
        if {'input_tokens','output_tokens','total_tokens'} <= usage.keys() and usage['total_tokens'] != usage['input_tokens'] + usage['output_tokens']:
            return Outcome('known_error', error_code='metadata_inconsistent', **stamp)
        return Outcome('refused' if isinstance(refusal, str) else 'succeeded', response_text=content,
            reported_model_id=model, reported_provider_id=provider,
            provider_response_id=identifier(body.get('id')), finish_reason=identifier(choice.get('finish_reason')),
            usage=usage or None, usage_status=('available' if {'input_tokens','output_tokens','total_tokens'} <= usage.keys()
                                            else 'partial' if usage else 'unavailable'), **stamp)
    except (ValueError, KeyError, TypeError, UnicodeError):
        return Outcome('known_error', error_code='malformed_response', **stamp)
