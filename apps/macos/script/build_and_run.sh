#!/usr/bin/env bash
set -euo pipefail
MODE="${1:-run}"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_NAME="Folio"
BUNDLE_ID="app.folio.hackathon"
APP_BUNDLE="$ROOT_DIR/dist/$APP_NAME.app"
cd "$ROOT_DIR"
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "Folio's SwiftUI build requires macOS 26 with Xcode 26 or newer. This host cannot compile or run it." >&2
  exit 1
fi
case "$MODE" in run|--debug|--logs|--telemetry|--verify|--build-only|--test) ;; *) echo "usage: $0 [--debug|--logs|--telemetry|--verify|--build-only|--test]" >&2; exit 2 ;; esac
command -v swift >/dev/null || { echo 'Install Xcode and select its command-line tools.' >&2; exit 1; }
if [[ "$MODE" == "--test" ]]; then exec swift test; fi
pkill -x "$APP_NAME" >/dev/null 2>&1 || true
swift build --product "$APP_NAME"
BIN_PATH="$(swift build --show-bin-path)"
rm -rf "$APP_BUNDLE"
mkdir -p "$APP_BUNDLE/Contents/MacOS" "$APP_BUNDLE/Contents/Resources"
cp "$BIN_PATH/$APP_NAME" "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
chmod +x "$APP_BUNDLE/Contents/MacOS/$APP_NAME"
# SwiftPM resource accessor location differs between compiler releases.
for resource in "$BIN_PATH"/*.bundle; do
  [[ -d "$resource" ]] || continue
  cp -R "$resource" "$APP_BUNDLE/Contents/Resources/"
  cp -R "$resource" "$APP_BUNDLE/"
done
cat > "$APP_BUNDLE/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>Folio</string>
<key>CFBundleIdentifier</key><string>$BUNDLE_ID</string>
<key>CFBundleName</key><string>Folio</string>
<key>CFBundleDisplayName</key><string>Folio</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>0.1.0</string>
<key>CFBundleVersion</key><string>1</string>
<key>LSMinimumSystemVersion</key><string>26.0</string>
<key>NSPrincipalClass</key><string>NSApplication</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict></plist>
PLIST
/usr/bin/plutil -lint "$APP_BUNDLE/Contents/Info.plist"
# Development-only ad hoc signature. This is NOT distribution signing or notarisation.
/usr/bin/codesign --force --sign - "$APP_BUNDLE"
case "$MODE" in
  --build-only) printf '%s\n' "$APP_BUNDLE" ;;
  --debug) lldb -- "$APP_BUNDLE/Contents/MacOS/$APP_NAME" ;;
  --logs) /usr/bin/open -n "$APP_BUNDLE"; /usr/bin/log stream --info --style compact --predicate 'process == "Folio"' ;;
  --telemetry) /usr/bin/open -n "$APP_BUNDLE"; /usr/bin/log stream --info --style compact --predicate "subsystem == \"$BUNDLE_ID\"" ;;
  --verify) /usr/bin/open -n "$APP_BUNDLE"; sleep 2; pgrep -x "$APP_NAME" >/dev/null ;;
  run) /usr/bin/open -n "$APP_BUNDLE" ;;
esac
