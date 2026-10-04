"""Isolated synthetic judge API. No private accounts or bank connections exist here."""
from __future__ import annotations
import os
from collections import defaultdict,deque
from time import monotonic
from uuid import UUID
from pathlib import Path
from sqlalchemy.engine import make_url
from sqlalchemy import text
from folio_api.jobs import JobQueue,JobError
from fastapi import FastAPI,Request,HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel,ConfigDict,Field
from folio_api.demo_domain import DomainError,compare_months,effective_transactions,refresh_goal_progress,goal_baseline,goal_settings
from folio_api.store import Store,StoreError

class Command(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    operationId:str
    expectedVersion:int=Field(ge=1)
    type:str=Field(min_length=1,max_length=40)
    payload:dict=Field(default_factory=dict)
class Question(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    operationId:str
    expectedVersion:int=Field(ge=1)
    question:str=Field(min_length=1,max_length=2000)
    scope:str

def public_state(state):
    state=refresh_goal_progress(state)
    return {**{k:v for k,v in state.items() if k not in ('history','annotations')},'transactions':effective_transactions(state),'goalBaseline':{'baselineMinor':goal_baseline(state,goal_settings(state,{'limitMinor':50000,'scope':'personal'}))['baselineMinor'],'months':goal_baseline(state,goal_settings(state,{'limitMinor':50000,'scope':'personal'}))['baselineMonths']}}

def create_app(database_url=None,*,testing=False):
    production=os.getenv('FOLIO_ENV')=='production' and not testing
    url=database_url or os.getenv('DATABASE_URL')
    if production:
        if not url or not url.startswith('postgresql+psycopg://'):
            raise ValueError('Production requires Managed PostgreSQL with psycopg.')
        parsed=make_url(url)
        ca=parsed.query.get('sslrootcert') or os.getenv('PGSSLROOTCERT','')
        if parsed.query.get('sslmode')!='verify-full' or not ca or not Path(ca).is_file():
            raise ValueError('Production requires verify-full TLS and a readable trusted CA.')
    store=Store(url or 'sqlite:////tmp/folio-hackathon-dev.sqlite3',testing=testing)
    app=FastAPI(title='Folio synthetic companion',version='1.0.0',docs_url=None if production else '/docs')
    app.state.store=store
    jobs=JobQueue(store.engine)
    if testing: jobs.migrate()
    app.state.jobs=jobs
    app.state.inference_enabled=(os.getenv('FOLIO_LIVE_INFERENCE_ENABLED')=='true'
                                 and bool(os.getenv('NEBIUS_API_KEY','').strip()))
    allowed={v.strip().rstrip('/') for v in os.getenv('FOLIO_ALLOWED_ORIGINS','http://127.0.0.1:5176,http://localhost:5176,folio://macos').split(',') if v.strip()}
    if testing: allowed.add('http://testserver')
    # Per-process anonymous session burst protection; provider quota is separately durable.
    bursts=defaultdict(deque)
    @app.middleware('http')
    async def guard(request,call_next):
        if request.method in ('POST','PUT','PATCH','DELETE'):
            if request.headers.get('origin','').rstrip('/') not in allowed: return JSONResponse({'detail':'Request origin is not permitted.'},403)
            if not request.headers.get('content-type','').startswith('application/json'): return JSONResponse({'detail':'JSON is required.'},415)
            raw=await request.body()
            if len(raw)>16384: return JSONResponse({'detail':'Request too large.'},413)
        response=await call_next(request)
        response.headers['Cache-Control']='no-store';response.headers['X-Content-Type-Options']='nosniff';response.headers['Referrer-Policy']='same-origin'
        return response
    @app.exception_handler(JobError)
    async def job_error(_,exc): return JSONResponse({'detail':str(exc)},exc.status)
    @app.exception_handler(StoreError)
    async def store_error(_,exc): return JSONResponse({'detail':str(exc)},exc.status)
    @app.exception_handler(DomainError)
    async def domain_error(_,exc): return JSONResponse({'detail':str(exc)},422)
    def token(request): return request.cookies.get('folio_demo')
    def check_id(value):
        try: UUID(value)
        except (ValueError,TypeError): raise HTTPException(422,'operationId must be a UUID.')
    def view(state):
        result=public_state(state)
        result['model']={**result['model'], 'state':'configured_unverified' if app.state.inference_enabled else 'unconfigured'}
        return result
    @app.get('/ready')
    def ready():
        try:
            with store.engine.connect() as con: con.execute(text('SELECT 1 FROM demo_workspaces LIMIT 1'))
        except Exception: raise HTTPException(503,'Database schema is not ready.')
        return {'status':'ready','inferenceEnabled':app.state.inference_enabled}
    @app.get('/health')
    def health(): return {'status':'ok','product':'Folio','mode':'synthetic-only','version':1}
    @app.post('/v1/demo/session')
    def session(request:Request):
        try: return view(store.load(token(request)))
        except StoreError: pass
        ip=request.client.host if request.client else 'unknown';now=monotonic();queue=bursts[ip]
        while queue and queue[0]<now-3600:queue.popleft()
        if len(queue)>=20 and not testing: raise HTTPException(429,'Please wait before opening another demo.')
        queue.append(now);key,state=store.create_session();response=JSONResponse(view(state))
        response.set_cookie('folio_demo',key,max_age=604800,httponly=True,secure=production,samesite='lax',path='/')
        return response
    @app.get('/v1/demo/workspace')
    def workspace(request:Request):return view(store.load(token(request)))
    @app.get('/v1/demo/comparison')
    def comparison(request:Request,scope:str='personal'):return compare_months(store.load(token(request)),scope)
    @app.post('/v1/demo/actions')
    def action(request:Request,command:Command):
        check_id(command.operationId)
        return view(store.command(token(request),command.model_dump()))
    @app.post('/v1/demo/ask')
    async def ask(request:Request,question:Question):
        check_id(question.operationId); state=store.load(token(request))
        if question.scope not in ('personal','business','everything'):raise HTTPException(422,'Unknown scope.')
        if state['version']!=question.expectedVersion:raise HTTPException(409,'Workspace changed. Refresh and try again.')
        if not app.state.inference_enabled:
            raise HTTPException(503,'Live Nemotron is not enabled yet. Your data is unchanged. You can still explore the calculation and manual review tools.')
        return JSONResponse(jobs.enqueue(workspace_id=state['id'],operation_id=question.operationId,
            question=question.question.strip(),scope=question.scope,expected_version=question.expectedVersion),202)
    @app.get('/v1/demo/runs')
    def recent_runs(request:Request,limit:int=20):
        state=store.load(token(request))
        return {'runs':jobs.list(state['id'],limit=limit)}
    @app.get('/v1/demo/runs/{run_id}')
    def run_status(request:Request,run_id:str,after:int=0):
        if after<0: raise HTTPException(422,'Event cursor must be nonnegative.')
        state=store.load(token(request))
        return jobs.get(state['id'],run_id,after_sequence=after)
    @app.post('/v1/demo/runs/{run_id}/cancel')
    def cancel_run(request:Request,run_id:str):
        state=store.load(token(request))
        return jobs.cancel(state['id'],run_id)
    @app.post('/v1/demo/signout')
    def signout(request:Request):
        store.revoke_session(token(request))
        response=JSONResponse({'status':'signed_out'})
        response.delete_cookie('folio_demo',path='/',secure=production,httponly=True,samesite='lax')
        return response
    return app

app=create_app()
