import json
import unittest
from datetime import datetime,timedelta,timezone
from unittest.mock import patch
import httpx
from jous_supply.hugging_face import HuggingFaceAdapter,DESTINATION
from jous_supply.contracts import ExecutionRequest,RouteUnavailable


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    def request(self):return ExecutionRequest('Server instruction','Untrusted task',datetime.now(timezone.utc)+timedelta(seconds=5))
    def body(self,**extra):return dict(choices=[{'message':{'content':'Answer','reasoning_content':'NEVER RETAIN'},'finish_reason':'stop'}],model='Qwen/Qwen3-32B',id='response-1',**extra)
    async def run_body(self,body,status=200):
        calls=[]
        def handler(request):calls.append(request);return httpx.Response(status,json=body)
        result=await HuggingFaceAdapter().exercise_offline(self.request(),httpx.MockTransport(handler))
        return result,calls
    async def test_exact_request_and_safe_normalization(self):
        outcome,calls=await self.run_body(self.body(usage={'prompt_tokens':2,'completion_tokens':3,'total_tokens':5}))
        self.assertEqual(len(calls),1);self.assertEqual(str(calls[0].url),DESTINATION)
        wire=json.loads(calls[0].content);self.assertFalse(wire['stream']);self.assertEqual(wire['chat_template_kwargs'],{'enable_thinking':False})
        self.assertNotIn('authorization',calls[0].headers);self.assertEqual(outcome.usage['total_tokens'],5)
        self.assertNotIn('NEVER RETAIN',repr(outcome));self.assertFalse(hasattr(outcome,'raw'))
    async def test_partial_missing_usage_and_empty_success(self):
        for usage,expected in [(None,'unavailable'),({'prompt_tokens':0},'partial')]:
            body=self.body();body['choices'][0]['message']['content']=''
            if usage is not None:body['usage']=usage
            outcome,_=await self.run_body(body);self.assertEqual(outcome.usage_status,expected);self.assertEqual(outcome.response_text,'')
    async def test_refusal(self):
        body=self.body();body['choices'][0]['message']={'refusal':'Cannot help'}
        outcome,_=await self.run_body(body);self.assertEqual(outcome.status,'refused')
    async def test_errors_redirect_rate_limit_and_bounds(self):
        for body,status,code in [(self.body(),302,'supplier_rejected'),(self.body(),429,'rate_limited'),
             ({},200,'malformed_response'),({'choices':[None]},200,'malformed_response'),
             ({'choices':[{'message':'not an object'}]},200,'malformed_response'),
             (self.body(usage={'prompt_tokens':True}),200,'malformed_response')]:
            outcome,calls=await self.run_body(body,status);self.assertEqual(outcome.error_code,code);self.assertEqual(len(calls),1)
        body=self.body();body['choices'][0]['message']['content']='x'*65537
        self.assertEqual((await self.run_body(body))[0].error_code,'response_too_large')
        body=self.body();body['padding']='x'*1048576
        self.assertEqual((await self.run_body(body))[0].error_code,'response_too_large')
    async def test_metadata_and_inline_reasoning_rejected(self):
        for body in [self.body(model_override=True),self.body(usage={'prompt_tokens':2,'completion_tokens':3,'total_tokens':9})]:
            body['model']='different'
            self.assertEqual((await self.run_body(body))[0].error_code,'metadata_inconsistent')
        body=self.body();body['choices'][0]['message']['content']='<think>private</think>Answer'
        self.assertEqual((await self.run_body(body))[0].error_code,'metadata_inconsistent')
    async def test_timeout_no_retry(self):
        calls=[]
        def handler(request):calls.append(1);raise httpx.ReadTimeout('private upstream information')
        result=await HuggingFaceAdapter().exercise_offline(self.request(),httpx.MockTransport(handler))
        self.assertEqual(len(calls),1);self.assertEqual(result.status,'unknown');self.assertNotIn('private',repr(result))
    async def test_stalled_transport_cancelled_by_total_deadline(self):
        import asyncio
        cancelled=asyncio.Event();calls=[]
        async def stalled(request):
            calls.append(request)
            try:await asyncio.Event().wait()
            finally:cancelled.set()
        request=ExecutionRequest('s','u',datetime.now(timezone.utc)+timedelta(milliseconds=40))
        async with asyncio.timeout(2):
            outcome=await HuggingFaceAdapter().exercise_offline(request,httpx.MockTransport(stalled))
        self.assertTrue(cancelled.is_set());self.assertEqual(len(calls),1)
        self.assertEqual(outcome.error_code,'provider_timeout')
    async def test_live_denied_and_transport_restricted(self):
        with patch('socket.socket',side_effect=AssertionError('Network denied')):
            with self.assertRaises(RouteUnavailable):await HuggingFaceAdapter().execute(self.request())
        with self.assertRaises(ValueError):await HuggingFaceAdapter().exercise_offline(self.request(),object())

    async def test_usage_arithmetic_only_inconsistency(self):
        body=self.body(usage={'prompt_tokens':2,'completion_tokens':3,'total_tokens':9})
        outcome,_=await self.run_body(body)
        self.assertEqual(outcome.error_code,'metadata_inconsistent');self.assertIsNone(outcome.usage)
    async def test_reported_provider_independent_constraint(self):
        for provider,code in [('DeepInfra',None),('OtherProvider','metadata_inconsistent')]:
            outcome,_=await self.run_body(self.body(provider=provider))
            self.assertEqual(outcome.error_code,code)
