import {mkdirSync, writeFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolveDeployment} from './deployment.mjs';

export function prepareRelease(env = process.env) {
  const deployment = resolveDeployment(env);
  const directory = new URL('../.generated/', import.meta.url);
  mkdirSync(directory, {recursive:true});
  const config = new URL('tauri.release.json', directory);
  writeFileSync(config, JSON.stringify({build:{frontendDist:deployment.appURL}}, null, 2)+'\n');
  return {...deployment, configPath:fileURLToPath(config)};
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  try { const config = prepareRelease(); console.log(`Release configuration prepared for ${config.origin}. No build or deployment was run.`); }
  catch(error) { console.error(error.message); process.exitCode = 1; }
}
