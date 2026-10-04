# Deployment and session acceptance

## Required topology

The approved HTTPS app origin serves the compiled `apps/web-demo` assets and reverse-proxies `/v1` and `/health` to Folio's API. Include only that exact origin in `FOLIO_ALLOWED_ORIGINS`. Keep production cookies Secure, HttpOnly and SameSite=Lax. Do not add wildcard CORS or relax cookies to make a custom-protocol frontend appear to work.

`FOLIO_DESKTOP_APP_URL` pins the page to load. `FOLIO_DESKTOP_API_BASE_URL` must equal its root origin. Rust repeats the origin validation at launch. The generated Tauri release configuration is ignored by git; it contains public endpoints only. No provisioned endpoint is assumed or hard-coded.

The shared web build must deliver a restrictive response CSP, including self-hosted scripts, `object-src 'none'`, `base-uri 'none'`, and `frame-ancestors 'none'`; account for any current inline style requirements. Also send a Permissions-Policy that disables unneeded device features. Verify response headers at the actual reverse proxy, not only in source configuration. Local Tauri CSP does not replace these server headers.

## Test on both Linux and Mac before claiming session support

1. Fresh launch creates an isolated synthetic session and sets the HttpOnly cookie on the approved origin.
2. Correct a selected item, save a goal, close the entire desktop process, then reopen it. The same workspace and server-backed changes must return until session expiry.
3. Confirm JavaScript cannot read the HttpOnly session cookie. Do not log or export it for diagnostics.
4. Reset demo and verify the expected server-backed reset. Test expiry/revocation and confirm a clear path to a new synthetic workspace.
5. Deny cross-origin navigation, `window.open`, downloads and a fresh geolocation/camera/microphone permission request. Confirm the UI cannot invoke native filesystem, process or shell commands.
6. Disconnect networking. Verify the displayed error is truthful and no operation is reported complete without a server receipt. This thin shell has no offline mutation queue or durable financial cache.
7. Test 1024×720, light/dark, keyboard-only navigation, screen-reader labels and text selection in the actual system webview. Browser screenshots alone do not prove native behaviour.
8. Confirm state-changing requests carry the deployment Origin accepted by the backend, and failed expected-version checks do not duplicate effects.

Current verification is limited to Node deployment/configuration tests and host prerequisite detection. Native Rust tests, cookie restart tests and desktop screenshots remain blocked by the missing toolchain.
