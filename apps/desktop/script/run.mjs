import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {preflight} from './preflight.mjs';
import {resolveDeployment} from './deployment.mjs';
import {prepareRelease} from './prepare-release.mjs';

const mode = process.argv[2];
if (!['dev','build'].includes(mode)) { console.error('Use npm run dev or npm run build.'); process.exit(2); }
const missing = preflight();
if (missing.length) { console.error(`Desktop build blocked:\n${missing.map(v=>`- ${v}`).join('\n')}`); process.exit(1); }
const root = fileURLToPath(new URL('../', import.meta.url));
const config = mode === 'build' ? prepareRelease() : resolveDeployment({}, {development:true});
const env = {...process.env, FOLIO_DESKTOP_APP_URL:config.appURL, FOLIO_DESKTOP_API_BASE_URL:config.apiBaseURL};
if (mode === 'build') {
  const web = spawnSync('npm',['--prefix','../web-demo','run','build'], {cwd:root, env, stdio:'inherit'});
  if (web.status !== 0) process.exit(web.status ?? 1);
}
const cli = fileURLToPath(new URL('../node_modules/@tauri-apps/cli/tauri.js', import.meta.url));
const args = [cli,mode];
if (mode === 'build') args.push('--config',config.configPath,'--bundles', process.platform === 'darwin' ? 'app,dmg' : 'deb,appimage');
const result = spawnSync(process.execPath,args,{cwd:root,env,stdio:'inherit'});
process.exit(result.status ?? 1);
