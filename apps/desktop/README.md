# Folio desktop: React + Tauri

This is the new Mac/Linux shell for the shared React interface in `../web-demo`. The preserved SwiftUI source is superseded. Web delivery remains first.

**Status:** wrapper source and deployment guard tests exist. Native compilation, desktop launch, session persistence across restarts and distributable packages have not been verified. No paid runner, deployment or system package installation was started.

## Deliberate web-first transport

Development loads `http://127.0.0.1:5176`, the existing React Vite app. Its `/v1` and `/health` proxy reaches the local Folio API. Start both separately before `npm run dev`.

Release builds load an explicitly selected HTTPS deployment of that same React app. UI and API must share one origin. This preserves the existing `credentials: 'same-origin'` request behaviour and the server's HttpOnly cookie without exposing session tokens to JavaScript or introducing a broad native HTTP bridge. The deployment must serve the matching shared React build and API together.

Set these public build variables (the scripts do not automatically load `.env`):

```sh
export FOLIO_DESKTOP_APP_URL='https://YOUR_APPROVED_DOMAIN/'
export FOLIO_DESKTOP_API_BASE_URL='https://YOUR_APPROVED_DOMAIN'
```

No credentials, query strings, fragments, loopback or `.invalid` placeholders are accepted for a release. `/v1` and `/health` must resolve on this exact origin; API path prefixes and cross-origin API hosts are rejected. Tauri officially supports remote `frontendDist` URLs; the generated release configuration uses that route. This version needs the hosted service and does **not** provide a bundled offline financial workspace. [Configuration reference](https://v2.tauri.app/reference/config/)

## Build and test

After the official prerequisites and project dependencies are installed on an approved development machine:

```sh
npm install
npm test
npm run check
npm run dev
# With the approved HTTPS variables exported:
npm run build
```

The build command validates endpoints, builds the shared React project, then runs the local Tauri CLI. It does not deploy the web app. Mac output targets `.app` and `.dmg`; Linux targets `.deb` and AppImage. The shell keeps the currently agreed macOS 26 baseline. Generate and review `package-lock.json` and `src-tauri/Cargo.lock` on the first toolchain-enabled build, then use locked dependencies for release verification.

The preflight only detects tools; it never installs them. On this Linux workspace it reports missing Rust, Cargo, WebKitGTK 4.1 and GTK 3 development packages, and the local Tauri CLI. Platform setup is documented by [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/).

## Security and session boundary

- No command handlers, filesystem/shell/process plugins or general-purpose HTTP proxy.
- No global Tauri JavaScript API; the only capability has zero permissions and no remote grants. [Tauri capabilities](https://v2.tauri.app/security/capabilities/)
- Top-level navigation is restricted to the exact compiled origin. Pop-ups, downloads and new device-permission requests are denied.
- Normal persistent webview storage is enabled. Linux uses an app-local directory; Mac uses a stable WKWebView data-store ID. Development and release stores are separated. Persistence is designed but must be tested on both systems. [Webview builder API](https://docs.rs/tauri/latest/tauri/webview/struct.WebviewWindowBuilder.html)
- The hosted app must supply its own CSP and Permissions-Policy headers. Tauri's local-asset CSP is not claimed to govern remote HTTP responses.
- Adding bank sign-in, external browser links, file import/export or other native features requires explicit narrowly scoped implementation and tests. They are intentionally absent from this wrapper.

See [Mac build/release checks](docs/mac-build.md) and [deployment/session acceptance](docs/deployment.md).
