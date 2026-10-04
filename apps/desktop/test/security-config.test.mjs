import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
const readJSON = path => JSON.parse(readFileSync(new URL(path, import.meta.url), 'utf8'));

test('frontend has no exposed native API and an explicit empty capability', () => {
  const config = readJSON('../src-tauri/tauri.conf.json');
  const capability = readJSON('../src-tauri/capabilities/no-native-ipc.json');
  assert.equal(config.app.withGlobalTauri, false);
  assert.deepEqual(config.app.security.capabilities, ['no-native-ipc']);
  assert.deepEqual(capability.permissions, []);
  assert.equal(capability.remote, undefined);
  assert.deepEqual(capability.windows, ['main']);
});
test('local asset policy prohibits remote scripts and nested frames', () => {
  const policy = readJSON('../src-tauri/tauri.conf.json').app.security.csp;
  assert.match(policy, /script-src 'self';/);
  assert.match(policy, /frame-src 'none'/);
  assert.match(policy, /object-src 'none'/);
  assert.ok(!policy.includes('unsafe-eval'));
});
test('app declares no auto-created window that could evade the Rust navigation guard', () => {
  assert.deepEqual(readJSON('../src-tauri/tauri.conf.json').app.windows, []);
});
