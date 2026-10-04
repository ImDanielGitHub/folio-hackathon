"""PostgreSQL-authoritative workspace snapshots and idempotent operations.

SQLite is allowed only for local development/testing. Production schema changes are
run explicitly with the migration command, never during request handling.
"""
from __future__ import annotations
import hashlib
import json
import secrets
import time
from copy import deepcopy
from sqlalchemy import Column,Integer,MetaData,String,Table,Text,create_engine,select,update
from folio_api.demo_domain import initial_state,apply_action,DomainError

metadata=MetaData()
workspaces=Table('demo_workspaces',metadata,Column('id',String(36),primary_key=True),Column('version',Integer,nullable=False),Column('state',Text,nullable=False))
sessions=Table('demo_sessions',metadata,Column('digest',String(64),primary_key=True),Column('workspace_id',String(36),nullable=False),Column('expires',Integer,nullable=False))
operations=Table('demo_operations',metadata,Column('id',String(80),primary_key=True),Column('request_hash',String(64),nullable=False),Column('response',Text,nullable=False))

class StoreError(RuntimeError):
    def __init__(self,message,status=409): self.status=status;super().__init__(message)

def digest(value): return hashlib.sha256(value.encode()).hexdigest()

class Store:
    def __init__(self,url,*,testing=False):
        if not url: raise ValueError('DATABASE_URL is required.')
        self.engine=create_engine(url,connect_args={'check_same_thread':False} if url.startswith('sqlite') else {},pool_pre_ping=True)
        if testing: metadata.create_all(self.engine)
    def migrate(self): metadata.create_all(self.engine)
    def create_session(self):
        state=initial_state(); token=secrets.token_urlsafe(32)
        with self.engine.begin() as con:
            con.execute(workspaces.insert().values(id=state['id'],version=state['version'],state=json.dumps(state)))
            con.execute(sessions.insert().values(digest=digest(token),workspace_id=state['id'],expires=int(time.time())+86400*7))
        return token,state
    def load(self,token):
        if not token: raise StoreError('Open your own demo workspace to continue.',401)
        with self.engine.connect() as con:
            sid=con.execute(select(sessions.c.workspace_id).where(sessions.c.digest==digest(token),sessions.c.expires>int(time.time()))).scalar_one_or_none()
            if not sid: raise StoreError('Your demo session expired. Open a new one.',401)
            raw=con.execute(select(workspaces.c.state).where(workspaces.c.id==sid)).scalar_one()
            return json.loads(raw)
    def command(self,token,command):
        state=self.load(token); operation_id=state['id']+':'+command['operationId']; fingerprint=digest(json.dumps(command,sort_keys=True))
        with self.engine.begin() as con:
            prior=con.execute(select(operations).where(operations.c.id==operation_id)).mappings().one_or_none()
            if prior:
                if prior['request_hash']!=fingerprint: raise StoreError('Operation ID was already used for different data.')
                return json.loads(prior['response'])
            current=con.execute(select(workspaces.c.state).where(workspaces.c.id==state['id'])).scalar_one();state=json.loads(current)
            if state['version']!=command['expectedVersion']: raise StoreError('This workspace changed. Refresh before applying this choice.')
            if command['type']=='reset':
                result=initial_state();result['id']=state['id'];result['version']=state['version']+1
            else: result=apply_action(state,command['type'],command['payload'])
            changed=con.execute(update(workspaces).where(workspaces.c.id==state['id'],workspaces.c.version==state['version']).values(version=result['version'],state=json.dumps(result)))
            if changed.rowcount!=1: raise StoreError('Another change arrived. Refresh and review again.')
            con.execute(operations.insert().values(id=operation_id,request_hash=fingerprint,response=json.dumps(result)))
            return result

    def load_workspace_for_job(self,workspace_id):
        with self.engine.connect() as con:
            raw=con.execute(select(workspaces.c.state).where(workspaces.c.id==workspace_id)).scalar_one_or_none()
            if raw is None: raise StoreError('Workspace no longer exists.',404)
            return json.loads(raw)

    def revoke_session(self,token):
        if token:
            with self.engine.begin() as con:
                con.execute(sessions.delete().where(sessions.c.digest==digest(token)))
