import {readFile,mkdir,cp,writeFile,rm} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
execFileSync('npm',['--prefix','apps/web-demo','run','build'],{stdio:'inherit'});
await mkdir('dist/server',{recursive:true});await mkdir('dist/.openai',{recursive:true});
await rm('dist/client',{recursive:true,force:true});
await cp('apps/web-demo/dist','dist/client',{recursive:true});
const parts=[`const nzBankFixtureData=${await readFile('services/api/folio_api/data/nz_bank_fixture.json','utf8')};`,`const phoneOffersData=${await readFile('services/api/folio_api/data/phone_offers.json','utf8')};`];for(const file of ['domain','bank-fixture','offer-costs','phone-offers','store','agent','index']){
 const source=await readFile(`apps/edge/${file}.mjs`,'utf8');parts.push(source.replace(/^import .*;\n/gm,'').replace(/\bexport (?=(?:const|class|function|async function))/g,''));
}
await writeFile('dist/server/index.js',parts.join('\n'));
await cp('.openai/hosting.json','dist/.openai/hosting.json');
await cp('drizzle','dist/.openai/drizzle',{recursive:true});
execFileSync('node',['--check','dist/server/index.js'],{stdio:'inherit'});
execFileSync('node',['scripts/verify-worker-bundle.mjs'],{stdio:'inherit'});
console.log('Built shared React client and dependency-free Worker.');
