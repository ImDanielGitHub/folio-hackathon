/** Closed original fictional data. No bank API, consent, credentials or uploads. */
import nzBankFixtureData from '../../services/api/folio_api/data/nz_bank_fixture.json' with {type:'json'};
import {DomainError} from './domain.mjs';

export const importCategories=['Eating out','Groceries','Transport','Shopping','Utilities','Software','Other'];
function exactPayload(payload,keys){
 if(!payload||typeof payload!=='object'||Array.isArray(payload)||Object.keys(payload).length!==keys.length||keys.some(key=>!Object.hasOwn(payload,key)))throw new DomainError('Only the required review fields are accepted; fixture data is server-owned.');
}
export function loadBankFixture(current,payload){
 exactPayload(payload,['fixtureId']);
 if(payload.fixtureId!==nzBankFixtureData.fixtureId)throw new DomainError('Choose the original fictional NZ fixture.');
 if(current!==null&&current!==undefined){if(current.fixtureId!==nzBankFixtureData.fixtureId)throw new DomainError('Another import is already staged; no fixture was replaced.');return structuredClone(current)}
 return {...structuredClone(nzBankFixtureData),loadedAt:new Date().toISOString()};
}
export function confirmBankFixture(current,payload){
 exactPayload(payload,['id','purpose','category','type']);
 if(!current||current.fixtureId!==nzBankFixtureData.fixtureId||current.provenance!=='original_fictional_fixture'||current.apiConnected!==false)throw new DomainError('Load the original fictional fixture before reviewing a transaction.');
 const source=nzBankFixtureData.transactions.find(row=>row.id===payload.id),row=current.transactions.find(row=>row.id===payload.id);
 if(!source||!row)throw new DomainError("Choose a staged transaction in this workspace's fixture.");
 if(row.status==='imported')throw new DomainError('This fixture transaction is already imported.');
 if(row.status!=='staged'||source.status!=='staged'||!row.sourceId)throw new DomainError('Only posted staged transactions with a source ID can be imported.');
 if(Object.entries(source).some(([key,value])=>row[key]!==value))throw new DomainError('Fixture source evidence must remain unchanged.');
 const {purpose,category,type}=payload;
 if(!['personal','business'].includes(purpose))throw new DomainError('Choose personal or business before importing.');
 if(!importCategories.includes(category))throw new DomainError('Choose a supported import category.');
 if(!['expense','refund','income','transfer'].includes(type))throw new DomainError('Choose expense, refund, income or transfer.');
 const amount=source.amountMinor;if(amount===0||(type==='expense'&&amount>=0)||(['refund','income'].includes(type)&&amount<=0))throw new DomainError('The transaction type must match the original signed amount.');
 if(['income','transfer'].includes(type)&&category!=='Other')throw new DomainError('Use Other for income and transfers; these do not count as spending.');
 const result=structuredClone(current),reviewed=result.transactions.find(row=>row.id===payload.id);
 Object.assign(reviewed,{status:'imported',confirmation:{purpose,category,type},confirmedAt:new Date().toISOString()});return result;
}
export function confirmedFixtureTransactions(bankImport){
 if(!bankImport)return [];
 return bankImport.transactions.filter(row=>row.status==='imported'&&row.confirmation).map(source=>{
  const {confirmation,...row}=structuredClone(source);
  return {...row,...confirmation,status:'confirmed',businessPercent:confirmation.purpose==='business'?100:0,provenance:bankImport.provenance,fixtureId:bankImport.fixtureId,recurring:false,version:1};
 });
}
