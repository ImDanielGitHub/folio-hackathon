from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from folio_api.app import create_app

@pytest.fixture
def clients(tmp_path):
    app=create_app(f'sqlite:///{tmp_path / "api.db"}',testing=True)
    one,two=TestClient(app),TestClient(app)
    for client in (one,two):
        client.headers.update({'Origin':'http://testserver'})
        client.post('/v1/demo/session',json={})
    return app,one,two

def question():
    return {'operationId':str(uuid4()),'expectedVersion':1,'question':'Compare my months','scope':'personal'}

def test_explicit_inference_gate(clients):
    app,one,_=clients
    assert one.post('/v1/demo/ask',json=question()).status_code==503
    app.state.inference_enabled=True
    assert one.post('/v1/demo/ask',json=question()).status_code==202

def test_run_idempotency_and_isolation(clients):
    app,one,two=clients; app.state.inference_enabled=True
    body=question()
    first=one.post('/v1/demo/ask',json=body).json()
    second=one.post('/v1/demo/ask',json=body).json()
    assert first['runId']==second['runId']
    path=f'/v1/demo/runs/{first["runId"]}'
    assert one.get(path).status_code==200
    assert two.get(path).status_code==404
    assert two.post(path+'/cancel',json={}).status_code==404
    assert one.post(path+'/cancel',json={}).json()['status']=='cancelled'

def test_reconnect_and_cursor_validation(clients):
    app,one,_=clients; app.state.inference_enabled=True
    run=one.post('/v1/demo/ask',json=question()).json()
    path=f'/v1/demo/runs/{run["runId"]}'
    snapshot=one.get(path).json()
    last=snapshot['events'][-1]['sequence']
    assert one.get(path+f'?after={last}').json()['events']==[]
    assert one.get(path+'?after=-1').status_code==422

def test_signout_invalidates_copied_cookie(clients):
    app,one,_=clients; cookie=one.cookies.get('folio_demo')
    assert one.post('/v1/demo/signout',json={}).status_code==200
    with TestClient(app) as old:
        old.cookies.set('folio_demo',cookie)
        assert old.get('/v1/demo/workspace').status_code==401

def test_ready_checks_schema(clients):
    _,one,_=clients
    assert one.get('/ready').json()['status']=='ready'
