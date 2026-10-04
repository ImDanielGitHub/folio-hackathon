import os
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from folio_api.app import create_app

class DemoAPITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.app=create_app('sqlite:///'+str(Path(self.tmp.name)/'test.db'),testing=True)
        self.client=TestClient(self.app); self.headers={'Origin':'http://testserver'}
    def tearDown(self): self.tmp.cleanup()
    def session(self,client=None): return (client or self.client).post('/v1/demo/session',json={},headers=self.headers).json()
    def test_no_session_no_data(self): self.assertEqual(self.client.get('/v1/demo/workspace').status_code,401)
    def test_sessions_isolated(self):
        a=self.session(); b=self.session(TestClient(self.app)); self.assertNotEqual(a['id'],b['id'])
        self.assertNotIn('history',a)
    def test_origin_required(self): self.assertEqual(self.client.post('/v1/demo/session',json={}).status_code,403)
    def test_foreign_origin_denied(self): self.assertEqual(self.client.post('/v1/demo/session',json={},headers={'Origin':'https://evil.example'}).status_code,403)
    def test_idempotency_and_reload(self):
        state=self.session(); command={'operationId':str(uuid4()),'expectedVersion':1,'type':'save_goal','payload':{'limitMinor':50000}}
        a=self.client.post('/v1/demo/actions',json=command,headers=self.headers)
        b=self.client.post('/v1/demo/actions',json=command,headers=self.headers)
        self.assertEqual(a.status_code,200,a.text); self.assertEqual(a.json(),b.json())
        self.assertEqual(len(self.client.get('/v1/demo/workspace').json()['goals']),1)
    def test_stale_write_rejected(self):
        self.session()
        for expected in (200,409):
            r=self.client.post('/v1/demo/actions',json={'operationId':str(uuid4()),'expectedVersion':1,'type':'save_goal','payload':{'limitMinor':50000}},headers=self.headers)
            self.assertEqual(r.status_code,expected,r.text)
    def test_foreign_transaction_rejected(self):
        self.session();r=self.client.post('/v1/demo/actions',json={'operationId':str(uuid4()),'expectedVersion':1,'type':'split','payload':{'id':'foreign','businessPercent':60}},headers=self.headers)
        self.assertEqual(r.status_code,422)
    def test_real_bank_route_absent(self):
        self.session(); self.assertEqual(self.client.post('/v1/demo/connections',json={},headers=self.headers).status_code,404)
    def test_missing_model_honest(self):
        self.session(); r=self.client.post('/v1/demo/ask',json={'operationId':str(uuid4()),'expectedVersion':1,'question':'Why was September different?','scope':'personal'},headers=self.headers)
        self.assertEqual(r.status_code,503); self.assertNotIn('396.70',r.text)
    def test_cookie_security(self):
        r=self.client.post('/v1/demo/session',json={},headers=self.headers)
        self.assertIn('HttpOnly',r.headers['set-cookie']);self.assertIn('SameSite=lax',r.headers['set-cookie'])
    def test_idempotency_key_payload_conflict(self):
        self.session(); key=str(uuid4()); command={'operationId':key,'expectedVersion':1,'type':'save_goal','payload':{'limitMinor':50000}}
        self.client.post('/v1/demo/actions',json=command,headers=self.headers); command['payload']['limitMinor']=40000
        self.assertEqual(self.client.post('/v1/demo/actions',json=command,headers=self.headers).status_code,409)
    def test_session_restore(self):
        a=self.session();b=self.session();self.assertEqual(a['id'],b['id'])
    def test_security_headers(self):
        response=self.client.get('/health');self.assertEqual(response.headers['X-Content-Type-Options'],'nosniff');self.assertEqual(response.headers['Cache-Control'],'no-store')
