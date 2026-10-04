export const bankCategories=['Eating out','Groceries','Transport','Shopping','Utilities','Software','Other'];
export type BankReviewDraft={purpose?:string;category?:string;type?:string};
type ReviewRow={id:string;status:string;amountMinor:number;currency:string};
export function bankReviewChoice(row:ReviewRow,draft:BankReviewDraft):Record<string,string>|null {
 const {purpose,category,type}=draft;
 if(row.status!=='staged'||!Number.isSafeInteger(row.amountMinor)||row.amountMinor===0)return null;
 if(!purpose||!['personal','business'].includes(purpose)||!category||!bankCategories.includes(category)||!type||!['expense','refund','income','transfer'].includes(type))return null;
 if(type==='expense'&&row.amountMinor>=0)return null;
 if(['refund','income'].includes(type)&&row.amountMinor<=0)return null;
 if(['income','transfer'].includes(type)&&category!=='Other')return null;
 return {id:row.id,purpose,category,type};
}
export function bankSpendingEffect(row:ReviewRow,type:string):number|null {
 if(!Number.isSafeInteger(row.amountMinor)||!['expense','refund','income','transfer'].includes(type))return null;
 return type==='income'||type==='transfer'?0:-row.amountMinor;
}
export function bankImportCounts(rows:{status:string}[]){return {staged:rows.filter(r=>r.status==='staged').length,imported:rows.filter(r=>r.status==='imported').length,blocked:rows.filter(r=>['pending','quarantined'].includes(r.status)).length}}
