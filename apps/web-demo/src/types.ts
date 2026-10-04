export type Scope='personal'|'business'|'everything';
export interface Transaction {id:string;date:string;merchant:string;description:string;amountMinor:number;currency:string;category:string;purpose:string;businessPercent:number;status:string;accountId:string;sourceId:string;recurring:boolean;version:number}
export interface Goal {id:string;title:string;limitMinor:number;currency:string;scope:Scope;period:string;status:string;spentMinor:number|null;progressNote:string;version:number}
export interface Memory {id:string;text:string;status:string;scope:string[];source:string;createdAt:string}
export interface Activity {id:string;label:string;status:string;createdAt:string;source:string;undoable:boolean;affectedIds:string[]}
export interface Workspace {id:string;kind:'demo';displayName:string;currency:string;timezone:string;version:number;goalBaseline?:{baselineMinor:number|null;months:{month:string;amountMinor:number|null}[]};transactions:Transaction[];goals:Goal[];memory:Memory[];activities:Activity[];messages:Message[];model:{state:string;provider:string;model:string}}
export interface Message {role:'user'|'assistant';text:string;runId?:string}
export interface RunSnapshot {executionMode?:'client_steps'|'durable_worker';runId:string;status:string;question:string;scope:Scope;events:{sequence:number;type:string}[];result?:{text:string;actualInference:boolean;toolResults?:Comparison[]}|null}
export interface Comparison {type:'PeriodComparison';schemaVersion:1;calculationId:string;currency:string;scope:Scope;previousPeriod:string;currentPeriod:string;previousMinor:number|null;currentMinor:number|null;differenceMinor:number|null;rows:{category:string;previousMinor:number;currentMinor:number;differenceMinor:number;transactionIds:string[]}[];sourceIds:string[]}
