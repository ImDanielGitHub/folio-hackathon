/** Exact synthetic finance domain. No external service or model performs arithmetic. */
export class DomainError extends Error { constructor(message,status=422){super(message);this.status=status} }
export const categories=['Eating out','Power','Transport','Groceries','Everything else','Not sorted yet'];
const base={'2026-07':[58800,12500,36000,82000,104500,15000],'2026-08':[46410,10320,35260,87150,122470,0],'2026-09':[71240,16420,40890,88420,103900,20410]};
const counts={'2026-07':102,'2026-08':112,'2026-09':127};
const merchants=[['Riverside Cafe','Garden Table','Dinner Delivery'],['Demo Energy'],['City Transit','Fuel Stop'],['Market Lane','Fresh Basket'],['Fictional Mobile','Design Software','Home Store'],['Unclear merchant','Mixed purchase']];
export function initialState(){
 const transactions=[];
 for(const [month,totals] of Object.entries(base))for(let c=0;c<6;c++){
  const n=Math.floor(counts[month]/6)+(c<counts[month]%6?1:0);
  for(let i=0;i<n;i++){const id=`demo-${month}-${c}-${String(i).padStart(2,'0')}`,amount=Math.floor(totals[c]/n)+(i<totals[c]%n?1:0);
   transactions.push({id,date:`${month}-${String((i*2+c)%28+1).padStart(2,'0')}`,merchant:merchants[c][i%merchants[c].length],description:`SYNTHETIC SAMPLE ${categories[c]} ${i+1}`,amountMinor:-amount,currency:'NZD',category:categories[c],purpose:'personal',businessPercent:0,status:c===5&&amount?'needs_review':'example_label',accountId:'demo-everyday',sourceId:`source-${id}`,recurring:c===1,version:1});
  }
 }
 return {id:crypto.randomUUID(),kind:'demo',displayName:'Sam Rivera',currency:'NZD',timezone:'Pacific/Auckland',asOf:'2026-10-04T00:00:00Z',version:1,transactions,annotations:{},goals:[],memory:[],activities:[],history:[],messages:[],model:{state:'unconfigured',provider:'nebius',model:'nvidia/nemotron-3-super-120b-a12b'}};
}
export function splitAmount(amount,pct){if(!Number.isSafeInteger(amount)||!Number.isInteger(pct)||pct<0||pct>100)throw new DomainError('Use an integer percentage from 0 to 100.');const work=Math.sign(amount)*Math.floor(Math.abs(amount)*pct/100);return [work,amount-work]}
export function scopedAmount(row,scope){if(!['personal','business','everything'].includes(scope))throw new DomainError('Unknown scope.');if(scope==='everything')return row.amountMinor;const [work,personal]=splitAmount(row.amountMinor,row.businessPercent??(row.purpose==='business'?100:0));return scope==='business'?work:personal}
export const effectiveTransactions=state=>state.transactions.map(t=>({...t,...state.annotations[t.id]}));
export function posted(row){return !['pending','removed','deleted'].includes(row.status)&&row.type!=='transfer'&&row.type!=='income'}
export function compareMonths(state,scope,previous='2026-08',current='2026-09',currency='NZD'){
 scopedAmount({amountMinor:0,businessPercent:0},scope);
 const rows=effectiveTransactions(state), all=rows.filter(t=>t.currency===currency&&[previous,current].includes(t.date.slice(0,7))), selected=all.filter(posted);
 const totals=Object.fromEntries([previous,current].map(month=>[month,all.some(t=>t.date.startsWith(month))?-selected.filter(t=>t.date.startsWith(month)).reduce((s,t)=>s+scopedAmount(t,scope),0):null]));
 const detail=[...new Set(selected.map(t=>t.category))].map(category=>{const matches=selected.filter(t=>t.category===category),a=-matches.filter(t=>t.date.startsWith(previous)).reduce((s,t)=>s+scopedAmount(t,scope),0),b=-matches.filter(t=>t.date.startsWith(current)).reduce((s,t)=>s+scopedAmount(t,scope),0);return {category,previousMinor:a,currentMinor:b,differenceMinor:b-a,transactionIds:matches.map(t=>t.id)}}).sort((a,b)=>b.differenceMinor-a.differenceMinor);
 return {type:'PeriodComparison',schemaVersion:1,calculationId:`compare:${state.id}:${state.version}:${scope}:${currency}:${previous}:${current}`,currency,scope,previousPeriod:previous,currentPeriod:current,previousMinor:totals[previous],currentMinor:totals[current],differenceMinor:totals[previous]===null||totals[current]===null?null:totals[current]-totals[previous],rows:detail,sourceIds:selected.map(t=>t.sourceId)};
}
export function goalBaseline(state,scope='personal'){
 const values=Object.keys(base).map(month=>({month,amountMinor:-effectiveTransactions(state).filter(t=>posted(t)&&t.currency==='NZD'&&t.category==='Eating out'&&t.date.startsWith(month)).reduce((sum,t)=>sum+scopedAmount(t,scope),0)}));
 return {months:values,baselineMinor:Math.floor(values.reduce((sum,x)=>sum+x.amountMinor,0)/values.length)};
}
export function publicState(state,enabled=false){const {history,annotations,...rest}=state;return {...rest,transactions:effectiveTransactions(state),goalBaseline:goalBaseline(state),model:{...rest.model,state:enabled?'configured_unverified':'unconfigured'}}}
export function applyAction(state,type,payload){
 const value=structuredClone(state),before={annotations:structuredClone(state.annotations),goals:structuredClone(state.goals),memory:structuredClone(state.memory),capacityScenario:structuredClone(state.capacityScenario??null)},ids=new Set(state.transactions.map(t=>t.id));let label='';
 const integerAmount=amount=>{if(!Number.isSafeInteger(amount)||amount<1||amount>100000000)throw new DomainError('Enter a positive supported amount.');return amount};
 if(type==='reset'){const result=initialState();return {...result,id:state.id,version:state.version+1}}
 if(type==='undo'){const prior=value.history.pop();if(!prior)throw new DomainError('There is no reversible action.');Object.assign(value,prior.before);label=`Undid: ${prior.label}`}
 else if(type==='classify'){
  const {ids:chosen,purpose}=payload;if(!Array.isArray(chosen)||chosen.length<1||chosen.length>50||new Set(chosen).size!==chosen.length||chosen.some(id=>!ids.has(id)))throw new DomainError('Choose 1–50 transactions in this workspace.');
  if(!['personal','business'].includes(purpose))throw new DomainError('Choose personal or business.');
  for(const id of chosen)value.annotations[id]={...value.annotations[id],purpose,businessPercent:purpose==='business'?100:0,status:'confirmed'};
  label=`Confirmed ${chosen.length} transactions as ${purpose}`;
  if(payload.remember===true)value.memory.push({id:crypto.randomUUID(),text:`These ${chosen.length} selected purchases were ${purpose}.`,scope:chosen,status:'confirmed',source:'Your correction',createdAt:new Date().toISOString()});
 }else if(type==='split'){
  const row=state.transactions.find(t=>t.id===payload.id);if(!row)throw new DomainError('Transaction not found in this workspace.');splitAmount(row.amountMinor,payload.businessPercent);
  value.annotations[row.id]={...value.annotations[row.id],purpose:'split',businessPercent:payload.businessPercent,status:'confirmed'};label=`Split one transaction ${payload.businessPercent}/${100-payload.businessPercent}`;
 }else if(type==='save_capacity_scenario'){value.capacityScenario=capacitySettings(state,payload);label='Saved a hypothetical capacity scenario';
 }else if(type==='save_goal'){
  value.goals.push({id:crypto.randomUUID(),title:'Eating out',limitMinor:integerAmount(payload.limitMinor),currency:'NZD',scope:'personal',period:'month',startsOn:'2026-10-01',status:'active',version:1,spentMinor:null,progressNote:'No October transactions imported yet. Progress is unknown.',...goalBaseline(state)});label='Saved an eating-out goal';
 }else if(['pause_goal','edit_goal','archive_goal'].includes(type)){
  const goal=value.goals.find(g=>g.id===payload.id);if(!goal)throw new DomainError('Goal not found in this workspace.');
  if(type==='edit_goal'){goal.limitMinor=integerAmount(payload.limitMinor);label='Updated goal'}else{goal.status=type==='archive_goal'?'archived':goal.status==='paused'?'active':'paused';label=`${goal.status} goal`}goal.version++;
 }else if(type==='forget_memory'){
  if(!value.memory.some(m=>m.id===payload.id))throw new DomainError('Memory not found.');value.memory=value.memory.filter(m=>m.id!==payload.id);label='Forgot a scoped example';
 }else throw new DomainError('This action is not supported. No changes were made.');
 if(type!=='undo')value.history.push({before,label});value.version++;
 value.activities.unshift({id:crypto.randomUUID(),label,status:'completed',createdAt:new Date().toISOString(),source:'You confirmed',undoable:type!=='undo',affectedIds:payload.ids??(payload.id?[payload.id]:[])});
 return value;
}
export const capacityFields=['regularIncomeMinor','variableIncomeMinor','committedCostsMinor','livingCostsMinor','savingsReserveMinor','availableBalanceMinor','protectedBalanceMinor','oneOffCostMinor'];
export function capacitySettings(state,payload){
 const allowed=new Set([...capacityFields,'scope','currency','includeVariableIncome']);if(!payload||typeof payload!=='object'||Array.isArray(payload)||Object.keys(payload).some(k=>!allowed.has(k)))throw new DomainError('Unsupported capacity assumption.');
 const scope=payload.scope===undefined?'personal':payload.scope;scopedAmount({amountMinor:0,businessPercent:0},scope);const currency=payload.currency===undefined?state.currency:payload.currency;if(currency!==state.currency)throw new DomainError('The scenario must use the workspace currency; no conversion is assumed.');
 const includeVariableIncome=payload.includeVariableIncome===undefined?false:payload.includeVariableIncome;if(typeof includeVariableIncome!=='boolean')throw new DomainError('Choose whether to include variable income.');const result={scope,currency,includeVariableIncome};
 for(const key of capacityFields){const value=payload[key]??null;if(value!==null&&(!Number.isSafeInteger(value)||value<0||value>100000000))throw new DomainError('Scenario money must be nonnegative integer minor units or unknown.');result[key]=value}return result;
}
export function calculateCapacity(state,scope='personal'){
 scopedAmount({amountMinor:0,businessPercent:0},scope);const saved=state.capacityScenario;
 if(!saved||saved.scope!==scope)return {type:'CapacityScenario',schemaVersion:1,status:'needs_input',scope,currency:state.currency,monthlyCapacityMinor:null,cashHeadroomAfterPurchaseMinor:null,guaranteedIncome:false,question:'Add your fictional income, costs and reserve assumptions in Capacity. No income or balance is inferred from spending records.'};
 const values=capacitySettings(state,saved),required=['regularIncomeMinor','committedCostsMinor','livingCostsMinor','savingsReserveMinor'];if(values.includeVariableIncome)required.push('variableIncomeMinor');const missing=required.filter(k=>values[k]===null);
 const income=values.regularIncomeMinor===null||(values.includeVariableIncome&&values.variableIncomeMinor===null)?null:values.regularIncomeMinor+(values.includeVariableIncome?values.variableIncomeMinor:0),costKeys=required.slice(1,4),costs=costKeys.some(k=>values[k]===null)?null:costKeys.reduce((sum,k)=>sum+values[k],0),capacity=income===null||costs===null?null:income-costs;
 const cashKeys=['availableBalanceMinor','protectedBalanceMinor','oneOffCostMinor'],cashMissing=cashKeys.filter(k=>values[k]===null),cash=cashMissing.length?null:values.availableBalanceMinor-values.protectedBalanceMinor-values.oneOffCostMinor;
 const parts=new Intl.DateTimeFormat('en-NZ',{timeZone:state.timezone??'Pacific/Auckland',year:'numeric',month:'2-digit'}).formatToParts(new Date(state.asOf??Date.now()));const part=type=>parts.find(p=>p.type===type).value;
 return {type:'CapacityScenario',schemaVersion:1,status:missing.length?'needs_input':'completed',scope,currency:values.currency,inputs:values,period:`${part('year')}-${part('month')}`,timezone:state.timezone??'Pacific/Auckland',calculationId:`capacity:${state.id}:${state.version}:${scope}`,incomeMinor:income,monthlyOutgoingsMinor:costs,monthlyCapacityMinor:capacity,cashHeadroomAfterPurchaseMinor:cash,missingInputs:missing,missingCashInputs:cashMissing,guaranteedIncome:false,dataBasis:'user_entered_hypothetical_assumptions',assumptions:['Inputs are fictional, user-entered assumptions, not verified bank evidence.',values.includeVariableIncome?'Variable income is included as an uncertain scenario assumption.':'Variable income is excluded.','Monthly cash flow and current balance are shown separately, never added together.','Costs must not be counted in both commitments and day-to-day spending.','A positive estimate is not a guarantee of affordability.']};
}
