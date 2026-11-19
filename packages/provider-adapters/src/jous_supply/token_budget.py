"""Offline provisional counting only. Never proves hosted input eligibility."""
import hashlib
import json
from pathlib import Path
from tokenizers import Tokenizer

ROOT = Path(__file__).parent / 'model_assets' / 'qwen3_32b'
REVISION = '9216db5781bf21249d130ec9da846c4624c16137'
HASHES = {'tokenizer.json': 'aeb13307a71acd8fe81861d94ad54ab689df773318809eed3cbe794b4492dae4',
          'tokenizer_config.json': 'd5d09f07b48c3086c508b30d1c9114bd1189145b74e982a265350c923acd8101'}
BRANCH = 'system-user-no-tools-nonthinking-v1'
MANIFEST_SHA256 = '6c0cd4149b4dc1adff8245807dcda3be8f8f6c15d22ca18dff6f8aec0dd50d04'


def count(system: str, user: str, *, root=ROOT, branch=BRANCH):
    if branch != BRANCH: raise ValueError('Unsupported template branch')
    try:
        assets = {name: (root / name).read_bytes() for name in HASHES}
        if any(hashlib.sha256(assets[n]).hexdigest() != h for n, h in HASHES.items()):
            raise ValueError('Tokenizer integrity failure')
        manifest_bytes = (root / 'manifest.json').read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
            raise ValueError('Tokenizer manifest integrity failure')
        manifest = json.loads(manifest_bytes)
        if manifest['upstream_revision'] != REVISION or manifest['asset_hashes'] != HASHES or manifest['template_branch'] != BRANCH:
            raise ValueError('Tokenizer integrity failure')
        # Literal specialization of the hashed authoritative template: exactly
        # system/user string messages, no tools, add_generation_prompt=True,
        # enable_thinking=False. No general template evaluation or Hub calls.
        rendered = ('<|im_start|>system\n' + system + '<|im_end|>\n'
                    '<|im_start|>user\n' + user + '<|im_end|>\n'
                    '<|im_start|>assistant\n<think>\n\n</think>\n\n')
        tokenizer = Tokenizer.from_buffer(assets['tokenizer.json'])
        n = len(tokenizer.encode(rendered, add_special_tokens=False).ids)
        if n > 28467 or n + 1024 + 3277 > 32768: raise ValueError('Local token limit exceeded')
        evidence = {'schema_version': 1, 'asset_revision': REVISION, 'asset_hashes': HASHES,
                    'method': 'LOCAL_PROVISIONAL', 'template_branch': BRANCH,
                    'input_token_upper_bound': n, 'context_capacity': 32768,
                    'output_allowance': 1024, 'safety_margin': 3277,
                    'hosted_authority_state': 'HOSTED_TOKEN_TEMPLATE_AUTHORITY_UNRESOLVED'}
        return n, evidence, hashlib.sha256(manifest_bytes).digest()
    except (OSError, KeyError, TypeError, json.JSONDecodeError):
        raise ValueError('Tokenizer unavailable') from None
