import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {existsSync} from 'node:fs';

export function preflight() {
  const missing = [];
  const available = (command, args=[]) => spawnSync(command,args,{stdio:'ignore'}).status === 0;
  for (const command of ['rustc','cargo']) if (!available(command,['--version'])) missing.push(command);
  if (process.platform === 'linux') {
    for (const library of ['webkit2gtk-4.1','gtk+-3.0']) if (!available('pkg-config',['--exists',library])) missing.push(`${library} development package`);
  } else if (process.platform === 'darwin') {
    if (!available('xcrun',['--find','clang'])) missing.push('Xcode command-line tools');
  } else missing.push('supported build host (macOS or Linux)');
  const cli = fileURLToPath(new URL('../node_modules/@tauri-apps/cli/tauri.js', import.meta.url));
  if (!existsSync(cli)) missing.push('project-local @tauri-apps/cli (npm install has not been run)');
  return missing;
}
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const missing = preflight();
  if (missing.length) { console.error(`Desktop build blocked:\n${missing.map(v=>`- ${v}`).join('\n')}\nNo packages or system settings were changed.`); process.exitCode = 1; }
  else console.log('Desktop build prerequisites found. Runtime and packaging are not yet verified.');
}
