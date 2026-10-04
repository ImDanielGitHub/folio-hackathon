import {useState} from 'react';
import {money} from './format';
import {bankCategories,bankReviewChoice,bankSpendingEffect,bankImportCounts} from './bankReview';
import type {BankReviewDraft} from './bankReview';
import type {BankFixtureImport,BankFixtureTransaction} from './types';

type Props={data?:BankFixtureImport|null;busy:boolean;onCommand:(type:string,payload?:Record<string,unknown>)=>Promise<boolean|undefined>;onTransactions:()=>void;onActivity:()=>void};
function FixtureReviewRow({row,busy,onConfirm}:{row:BankFixtureTransaction;busy:boolean;onConfirm:(payload:Record<string,string>)=>Promise<boolean|undefined>}){
 const [draft,setDraft]=useState<BankReviewDraft>({});
 const choice=bankReviewChoice(row,draft),effect=bankSpendingEffect(row,draft.type??'');
 const set=(field:keyof BankReviewDraft,value:string)=>setDraft(current=>({...current,[field]:value,...(field==='type'&&['income','transfer'].includes(value)?{category:'Other'}:{})}));
 return <article className="bank-review-item" aria-label={`${row.merchant} import review`}>
  <div className="bank-row-heading"><div><h3>{row.merchant}</h3><p className="small muted">{row.date} · original fictional record</p></div><strong>{money(row.amountMinor,row.currency)}</strong></div>
  {row.status==='staged'?<form onSubmit={e=>{e.preventDefault();if(choice)void onConfirm(choice)}}>
   <div className="bank-review-fields"><label>What kind of entry?<select aria-label={`${row.merchant} entry type`} value={draft.type??''} onChange={e=>set('type',e.target.value)} required disabled={busy}><option value="">Choose a type</option>{row.amountMinor<0?<option value="expense">Spending</option>:<><option value="refund">Refund</option><option value="income">Income</option></>}<option value="transfer">Transfer between accounts</option></select></label>
   <label>Whose money?<select aria-label={`${row.merchant} purpose`} value={draft.purpose??''} onChange={e=>set('purpose',e.target.value)} required disabled={busy}><option value="">Choose a purpose</option><option value="personal">Personal</option><option value="business">Business</option></select></label>
   <label>Category<select aria-label={`${row.merchant} category`} value={draft.category??''} onChange={e=>set('category',e.target.value)} required disabled={busy||['income','transfer'].includes(draft.type??'')}><option value="">Choose a category</option>{bankCategories.map(c=><option key={c}>{c}</option>)}</select></label></div>
   <p className="bank-effect">{choice&&effect!==null?(effect===0?'This will enter the transaction list, but will not count as spending.':`This will ${effect>0?'add':'subtract'} ${money(Math.abs(effect),row.currency)} ${effect>0?'to':'from'} ${draft.purpose} September spending.`):'Nothing counts toward spending until you choose and confirm.'}</p>
   <button className="primary" type="submit" disabled={busy||!choice}>Confirm import of {row.merchant}</button>
  </form>:row.status==='imported'?<p className="bank-status imported">Imported · {row.confirmation?.purpose} · {row.confirmation?.category} · {row.confirmation?.type}. Your choice is recorded in Activity.</p>:<p className="bank-status blocked">{row.status==='pending'?'Pending · excluded until it posts.':'Needs a stable source ID · kept out of the ledger.'} {row.reason?.replaceAll('_',' ')}</p>}
  <details><summary>Source and provenance</summary><p>{row.description}</p><p className="small muted">Source ID: {row.sourceId??'Unavailable; no replacement ID has been invented.'}</p><p className="small muted">Original fictional fixture. No bank supplied this record. Original amount: {money(row.amountMinor,row.currency)}.</p></details>
 </article>
}
export function ConnectionsView({data,busy,onCommand,onTransactions,onActivity}:Props){
 const counts=bankImportCounts(data?.transactions??[]);
 return <section className="page-section bank-connections"><p className="label muted">Data connections</p><h1>A clear way in.</h1><p className="muted">Bring records into a review queue before they become part of your money picture.</p>
  <div className="bank-connection-status"><span className="status-dot"/><div><h2>Direct NZ bank API · not connected</h2><p>No live or sandbox bank has been authorised. Provider access and consent are still required.</p></div></div>
  <div className="bank-fixture-intro"><div><p className="label muted">Original test fixture · NZD</p><h2>Try the import and review flow.</h2><p>Load two fictional accounts and seven test entries. They were written for Folio, not downloaded from a bank. This public demo does not accept files, credentials or real financial information.</p></div><button className="primary" disabled={busy||!!data} onClick={()=>void onCommand('load_bank_fixture',{fixtureId:'nz-original-v1'})}>{data?'Test fixture loaded':'Load fictional NZ records'}</button></div>
  {data&&<><div className="bank-import-summary" role="status"><span><b>{counts.staged}</b> waiting for review</span><span><b>{counts.imported}</b> explicitly imported</span><span><b>{counts.blocked}</b> excluded</span></div>
   <div className="bank-accounts">{data.accounts.map(account=><article key={account.id}><p className="label muted">Fictional account</p><h2>{account.name}</h2><dl><div><dt>Booked balance</dt><dd>{money(account.currentBalanceMinor,account.currency)}</dd></div><div><dt>Available funds</dt><dd>{money(account.availableBalanceMinor,account.currency)}</dd></div></dl><p className="small muted">{account.availableIncludesCredit===true?'Available funds include a credit facility.':account.availableIncludesCredit===false?'No credit facility is included in available funds.':'Credit-facility inclusion is unknown.'} The two balances are not added together.</p><p className="small muted">Fixture snapshot · {new Date(account.asOf).toLocaleString('en-NZ',{timeZone:'Pacific/Auckland'})} NZ time</p></article>)}</div>
   <div className="bank-review-title"><div><h2>Review each source entry</h2><p>Confirmation affects only that entry. Pending and unidentified records stay separate.</p></div><button onClick={onActivity}>Activity & undo →</button></div>
   <div>{data.transactions.map(row=><FixtureReviewRow key={row.id} row={row} busy={busy} onConfirm={payload=>onCommand('confirm_bank_fixture',payload)}/>)}</div>
   <div className="bank-import-footer"><button onClick={onTransactions}>Open the transaction list →</button><p className="small muted">Fixture nz-original-v1 · API calls: none · Full bank-history coverage: not established.</p></div>
  </>}
 </section>
}
