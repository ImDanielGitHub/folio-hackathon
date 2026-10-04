export class APIError extends Error {constructor(public status:number,message:string){super(message)}}
export async function api<T>(path:string,body?:unknown,signal?:AbortSignal):Promise<T>{
 const response=await fetch(path,{method:body===undefined?'GET':'POST',credentials:'same-origin',headers:body===undefined?{Accept:'application/json'}:{Accept:'application/json','Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal});
 let data;try{data=await response.json()}catch{throw new APIError(response.status,'The service returned an unreadable response. Your draft is still here.')}
 if(!response.ok)throw new APIError(response.status,typeof data.detail==='string'?data.detail:'The request could not be completed. Please check your choices and try again.');return data as T;
}
