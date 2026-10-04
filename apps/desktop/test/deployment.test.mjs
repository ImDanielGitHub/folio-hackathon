import test from 'node:test';
import assert from 'node:assert/strict';
import {resolveDeployment} from '../script/deployment.mjs';

test('release pins a HTTPS application and same-origin API', () => {
  const config = resolveDeployment({FOLIO_DESKTOP_APP_URL:'https://folio.example/demo',FOLIO_DESKTOP_API_BASE_URL:'https://folio.example/'});
  assert.equal(config.appURL, 'https://folio.example/demo');
  assert.equal(config.origin, 'https://folio.example');
  assert.equal(config.apiBaseURL, 'https://folio.example');
});
test('release cannot silently select localhost or a placeholder host', () => {
  for (const value of [undefined,'http://folio.example','http://127.0.0.1:5176','https://localhost','https://127.0.0.1','https://127.0.0.2','https://your-approved-folio-domain.invalid/']) {
    assert.throws(() => resolveDeployment({FOLIO_DESKTOP_APP_URL:value}));
  }
});
test('cross-origin and prefixed API paths are rejected', () => {
  for (const value of ['https://api.folio.example','https://folio.example/api','https://folio.example:8443']) {
    assert.throws(() => resolveDeployment({FOLIO_DESKTOP_APP_URL:'https://folio.example',FOLIO_DESKTOP_API_BASE_URL:value}));
  }
});
test('credentials, token queries, fragments and control characters are rejected', () => {
  for (const value of ['https://user:secret@folio.example','https://folio.example/?key=secret','https://folio.example/#token','https://folio.exam\nple']) {
    assert.throws(() => resolveDeployment({FOLIO_DESKTOP_APP_URL:value}));
  }
});
test('same origin uses default port normalization', () => {
  const config = resolveDeployment({FOLIO_DESKTOP_APP_URL:'https://folio.example:443/demo',FOLIO_DESKTOP_API_BASE_URL:'https://folio.example'});
  assert.equal(config.origin, 'https://folio.example');
});
test('development is fixed to the shared React Vite origin', () => {
  const config = resolveDeployment({}, {development:true});
  assert.equal(config.appURL, 'http://127.0.0.1:5176/');
  assert.equal(config.apiBaseURL, 'http://127.0.0.1:5176');
});
