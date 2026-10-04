import {phoneComparison} from './phone-offers.mjs';
import {DomainError,publicState,compareMonths,calculateCapacity} from './domain.mjs';
import {Store} from './store.mjs';
import {advance} from './agent.mjs';
const json=(value,status=200,extra={})=>new Response(JSON.stringify(value),{status,headers:{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin',...extra}});
const uuid=value=>typeof value==='string'&&/^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(value);
export async function handle(request,env){
 const url=new URL(request.url),path=url.pathname,enabled=env.FOLIO_LIVE_INFERENCE_ENABLED==='true'&&!!env.NEBIUS_API_KEY;
 if(path==='/health')return json({status:'ok',product:'Folio',mode:'synthetic-only',runtime:'sites',backgroundWhileClosed:false});
 if(!path.startsWith('/v1/')&&path!=='/ready')return env.ASSETS?env.ASSETS.fetch(request):new Response('Folio assets are unavailable.',{status:503});
 try{
  let body;
  if(request.method==='POST'){
   if(request.headers.get('origin')!==url.origin)throw new DomainError('Request origin is not permitted.',403);
   if(!request.headers.get('content-type')?.startsWith('application/json'))throw new DomainError('JSON is required.',415);
   if(Number(request.headers.get('content-length')??0)>16384)throw new DomainError('Request too large.',413);
   const raw=await request.text();if(raw.length>16384)throw new DomainError('Request too large.',413);try{body=JSON.parse(raw)}catch{throw new DomainError('Invalid JSON.')}
   if(!body||typeof body!=='object'||Array.isArray(body))throw new DomainError('A JSON object is required.');
  }else if(request.method!=='GET')throw new DomainError('Method not allowed.',405);
  const store=new Store(env.DB),token=request.headers.get('cookie')?.split(';').map(x=>x.trim()).find(x=>x.startsWith('folio_demo='))?.slice(11);
  if(path==='/ready'){await env.DB.prepare('SELECT id FROM workspaces LIMIT 1').first();return json({status:'ready',inferenceEnabled:enabled,backgroundWhileClosed:false})}
  if(path==='/v1/demo/signout'&&request.method==='POST'){await store.revoke(token);return json({status:'signed_out'},200,{'Set-Cookie':'folio_demo=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0'})}
  if(path==='/v1/demo/session'&&request.method==='POST'){
   try{return json(publicState(await store.load(token),enabled))}catch(e){if(e.status!==401)throw e}
   const sessions=await env.DB.prepare('SELECT COUNT(*) AS count FROM sessions WHERE expires>?').bind(Math.floor(Date.now()/1000)).first();if(sessions.count>=500)throw new DomainError('Demo capacity is reached. Please try later.',429);
   const {state,token:newToken}=await store.createSession();return json(publicState(state,enabled),200,{'Set-Cookie':`folio_demo=${newToken}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=604800`})
  }
  const state=await store.load(token);
  if(path==='/v1/demo/workspace'&&request.method==='GET')return json(publicState(state,enabled));
  if(path==='/v1/demo/comparison'&&request.method==='GET')return json(compareMonths(state,url.searchParams.get('scope')??'personal'));
  if(path==='/v1/demo/capacity'&&request.method==='GET')return json(calculateCapacity(state,url.searchParams.get('scope')??'personal'));
  if(path==='/v1/demo/phone-comparison'&&request.method==='GET')return json(phoneComparison(state,url.searchParams.get('scope')??'personal'));
  if(path==='/v1/demo/actions'&&request.method==='POST'){
   if(Object.keys(body).some(k=>!['operationId','expectedVersion','type','payload'].includes(k))||!uuid(body.operationId)||!Number.isInteger(body.expectedVersion)||typeof body.type!=='string'||!body.payload||Array.isArray(body.payload)||typeof body.payload!=='object')throw new DomainError('Invalid action request.');
   return json(publicState(await store.command(state,body),enabled));
  }
  if(path==='/v1/demo/ask'&&request.method==='POST'){
   if(!enabled)throw new DomainError('Live Nemotron is not enabled yet. Your data is unchanged. You can still explore calculations and manual review.',503);
   if(Object.keys(body).some(k=>!['operationId','expectedVersion','question','scope'].includes(k))||!uuid(body.operationId)||!Number.isInteger(body.expectedVersion)||typeof body.question!=='string'||!body.question.trim()||body.question.length>2000||!['personal','business','everything'].includes(body.scope))throw new DomainError('Invalid question request.');
   return json(await store.enqueue(state,{...body,question:body.question.trim()}),202);
  }
  if(path==='/v1/demo/runs'&&request.method==='GET'){const limit=Number(url.searchParams.get('limit')??20);if(!Number.isInteger(limit)||limit<1||limit>100)throw new DomainError('Invalid run limit.');return json({runs:await store.list(state.id,limit)})}
  const match=path.match(/^\/v1\/demo\/runs\/([0-9a-f-]+)(?:\/(cancel|advance))?$/i);
  if(match){
   if(match[2]==='cancel'&&request.method==='POST')return json(await store.cancel(state.id,match[1]));
   if(match[2]==='advance'&&request.method==='POST'){
    if(!enabled)throw new DomainError('Live inference is paused. Your run is preserved.',503);
    const row=await store.claim(state.id,match[1]);return json(row?await advance(store,row,state,env):await store.get(state.id,match[1]));
   }
   if(!match[2]&&request.method==='GET'){const after=Number(url.searchParams.get('after')??0);if(!Number.isSafeInteger(after)||after<0)throw new DomainError('Invalid event cursor.');return json(await store.get(state.id,match[1],after))}
  }
  throw new DomainError('Not found.',404);
 }catch(error){if(error instanceof DomainError)return json({detail:error.message},error.status);console.error('Folio request failed',{name:error?.name??'Error'});return json({detail:'The service is temporarily unavailable. Your draft is preserved.'},503)}
}
export default {fetch:handle};
