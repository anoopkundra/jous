import shutil
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
from jous_supply.token_budget import count,ROOT
from jous_supply.registry import require_real_eligibility,HF_ROUTE
from jous_supply.contracts import RouteUnavailable


class TokenTests(unittest.TestCase):
    def test_local_only_and_provisional(self):
        with patch('socket.socket',side_effect=AssertionError('External network denied')):
            n,e,h=count('System','Task')
        self.assertGreater(n,0);self.assertEqual(len(h),32)
        self.assertEqual(e['method'],'LOCAL_PROVISIONAL');self.assertEqual(e['context_capacity'],32768)
        self.assertEqual(e['hosted_authority_state'],'HOSTED_TOKEN_TEMPLATE_AUTHORITY_UNRESOLVED')
        with self.assertRaises(RouteUnavailable):require_real_eligibility(HF_ROUTE)
    def test_missing_modified_asset_and_branch_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            with self.assertRaises(ValueError):count('s','u',root=root)
            for file in ROOT.iterdir():shutil.copyfile(file,root/file.name)
            (root/'tokenizer.json').write_bytes(b'{}')
            with self.assertRaises(ValueError):count('s','u',root=root)
        with self.assertRaises(ValueError):count('s','u',branch='tools')
    def test_arithmetic_boundary(self):
        from types import SimpleNamespace
        for n,allowed in [(28467,True),(28468,False)]:
            fake=SimpleNamespace(encode=lambda *a,**k:SimpleNamespace(ids=range(n)))
            with patch('jous_supply.token_budget.Tokenizer') as cls:
                cls.from_buffer.return_value=fake
                if allowed:self.assertEqual(count('s','u')[0],n)
                else:
                    with self.assertRaises(ValueError):count('s','u')
