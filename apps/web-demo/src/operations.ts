export interface PendingOperation {key:string;command:{operationId:string;expectedVersion:number;type:string;payload:Record<string,unknown>}}
export function prepareOperation(pending:PendingOperation|null,workspaceId:string,version:number,type:string,payload:Record<string,unknown>):PendingOperation{
 const key=JSON.stringify([workspaceId,type,payload]);
 if(pending?.key===key)return pending;
 return {key,command:{operationId:crypto.randomUUID(),expectedVersion:version,type,payload}};
}
export function allocationPreview(amount:number,percentage:number):[number,number]|null{
 if(!Number.isSafeInteger(amount)||!Number.isInteger(percentage)||percentage<0||percentage>100)return null;
 const work=Math.sign(amount)*Math.floor(Math.abs(amount)*percentage/100);return [work,amount-work];
}
