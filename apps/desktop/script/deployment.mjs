/** Compile-time endpoints only. Never pass provider keys to the webview. */
export function resolveDeployment(env = process.env, {development = false} = {}) {
  if (development) return {appURL:'http://127.0.0.1:5176/', apiBaseURL:'http://127.0.0.1:5176', origin:'http://127.0.0.1:5176'};
  const parse = (raw, label) => {
    if (!raw || /\s/.test(raw)) throw new Error(`${label} must be an explicit URL without whitespace.`);
    let url;
    try { url = new URL(raw); } catch { throw new Error(`${label} is not a valid URL.`); }
    if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash)
      throw new Error(`${label} must use HTTPS with no credentials, query or fragment.`);
    if (['localhost','127.0.0.1','[::1]'].includes(url.hostname) || url.hostname.endsWith('.localhost') || url.hostname.startsWith('127.') || url.hostname.endsWith('.invalid'))
      throw new Error(`${label} must point to the deployed service, not loopback.`);
    return url;
  };
  const app = parse(env.FOLIO_DESKTOP_APP_URL, 'FOLIO_DESKTOP_APP_URL');
  const api = parse(env.FOLIO_DESKTOP_API_BASE_URL || app.origin, 'FOLIO_DESKTOP_API_BASE_URL');
  if (app.origin !== api.origin || api.pathname !== '/')
    throw new Error('The shared React client requires /v1 and /health on the exact application origin.');
  return {appURL:app.href, apiBaseURL:api.origin, origin:app.origin};
}
