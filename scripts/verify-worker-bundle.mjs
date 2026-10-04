// Exercise the exact Worker artifact with an in-memory D1 contract adapter.
// This sends no network requests and uses only the server-owned fictional fixture.
import assert from 'node:assert/strict';
import worker from '../dist/server/index.js';
import {D1} from '../apps/edge/test/d1-adapter.mjs';
const origin='https://folio-bundle-test.invalid', env={DB:new D1()};
const call=(path,body,cookie)=>worker.fetch(new Request(origin+path,{method:body===undefined?'GET':'POST',headers:{...(body===undefined?{}:{Origin:origin,'Content-Type':'application/json'}),...(cookie?{Cookie:cookie}:{})},body:body===undefined?undefined:JSON.stringify(body)}),env);
const opened=await call('/v1/demo/session',{});assert.equal(opened.status,200);const cookie=opened.headers.get('set-cookie').split(';')[0],first=await opened.json();
const loaded=await call('/v1/demo/actions',{operationId:crypto.randomUUID(),expectedVersion:first.version,type:'load_bank_fixture',payload:{fixtureId:'nz-original-v1'}},cookie);assert.equal(loaded.status,200);const staged=await loaded.json();assert.equal(staged.transactions.length,341);assert.equal(staged.bankImport.apiConnected,false);
const confirmed=await call('/v1/demo/actions',{operationId:crypto.randomUUID(),expectedVersion:staged.version,type:'confirm_bank_fixture',payload:{id:'bank-fixture-nz-v1-coffee',purpose:'personal',category:'Eating out',type:'expense'}},cookie);assert.equal(confirmed.status,200);assert.equal((await confirmed.json()).transactions.length,342);
const comparison=await call('/v1/demo/comparison?scope=personal',undefined,cookie);assert.equal((await comparison.json()).differenceMinor,41545);
console.log('Verified built Worker: isolated fixture staging, explicit review, exact totals.');
