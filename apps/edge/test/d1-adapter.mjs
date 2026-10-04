import {DatabaseSync} from 'node:sqlite';
import {readFileSync,readdirSync} from 'node:fs';
export class D1 {
 constructor(){this.sqlite=new DatabaseSync(':memory:');for(const file of readdirSync('drizzle').filter(x=>x.endsWith('.sql')).sort())this.sqlite.exec(readFileSync(`drizzle/${file}`,'utf8'))}
 prepare(sql){const db=this.sqlite;return {values:[],bind(...values){this.values=values;return this},async first(){return db.prepare(sql).get(...this.values)??null},async all(){return {results:db.prepare(sql).all(...this.values)}},async run(){const result=db.prepare(sql).run(...this.values);return {success:true,meta:{changes:Number(result.changes)}}},execute(){const result=db.prepare(sql).run(...this.values);return {success:true,meta:{changes:Number(result.changes)}}}}}
 async batch(statements){this.sqlite.exec('BEGIN');try{const results=statements.map(s=>s.execute());this.sqlite.exec('COMMIT');return results}catch(error){this.sqlite.exec('ROLLBACK');throw error}}
}
