# macOS build and release gate

No CI workflow is enabled or paid service invoked by this project. These are instructions for a separately approved Mac build machine or existing authorised self-hosted runner.

1. Use macOS 26 and the selected Xcode command-line tools. Install the official Rust toolchain and this project's pinned Tauri CLI under the machine's normal software policy.
2. Install the web and desktop dependencies; generate and review lockfiles. Subsequent verified builds should use `npm ci` and locked Cargo dependencies.
3. Run `npm test` in `apps/desktop`, then `cargo test --manifest-path src-tauri/Cargo.toml`. The latter needs the native toolchain and remains unrun here.
4. Start the local API and React Vite server using the repository instructions. Run `npm run dev` and exercise the same review, split, goal and undo journeys used for the web build.
5. Set the approved HTTPS application/API addresses and run `npm run build`. Verify the generated `.app` and `.dmg` on a fresh Mac, not only on the build machine. Use the intended Apple Silicon/Intel target matrix explicitly; do not assume a single-target artifact is universal.
6. Distribution signing and notarisation require the owner's approved Apple developer setup and secure credential injection. Keep secrets outside this repository and frontend. Do not disable Gatekeeper or strip quarantine as a substitute for distribution validation.
7. Record build SHA, dependency locks, native SDK/toolchain, backend release and model configuration alongside test results. Pin the compatible web/API deployment for the release.

The initial icon set, native menus/keyboard integration and install artwork still need a release pass. None is claimed complete by a successful JavaScript test run.

Official build packaging: [macOS application bundle](https://v2.tauri.app/distribute/macos-application-bundle/). Official signing steps: [macOS code signing](https://v2.tauri.app/distribute/sign/macos/).
