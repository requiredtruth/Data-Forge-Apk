#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
MOBILE="$ROOT/mobile"
mkdir -p "$MOBILE"
if [ ! -f "$MOBILE/node_modules/nitron/dist/cli.js" ] || [ ! -f "$MOBILE/node_modules/nitronplus/template/base.apk" ] || [ ! -f "$MOBILE/node_modules/sql.js/js/sql.js" ]; then
  npm --cache /tmp/dataforge-npm-cache --prefix "$MOBILE" install --no-audit --no-fund
fi
cp "$MOBILE/node_modules/sql.js/js/sql.js" "$MOBILE/sql.js"
# Nitron 1.2 provides the SDK-free binary-manifest builder. Nitronplus provides
# its newer WebView shell with Android's system file chooser.
cp "$MOBILE/node_modules/nitronplus/template/base.apk" "$MOBILE/node_modules/nitron/template/base.apk"
# Nitron requires its config to be named app.js. Preserve the actual UI logic.
mv "$MOBILE/app.js" "$MOBILE/main.js"
cp "$ROOT/android_app_config.mjs" "$MOBILE/app.js"
trap 'mv -f "$MOBILE/main.js" "$MOBILE/app.js"' EXIT
sed -i 's#<script src="app.js"></script>#<script src="main.js"></script>#' "$MOBILE/index.html"
trap 'sed -i '\''s#<script src="main.js"></script>#<script src="app.js"></script>#'\'' "$MOBILE/index.html"; mv -f "$MOBILE/main.js" "$MOBILE/app.js"' EXIT
(cd "$MOBILE" && node node_modules/nitron/dist/cli.js build)
mkdir -p "$ROOT/releases"
cp "$MOBILE/dist/app.apk" "$ROOT/releases/DataForge-1.0.3.apk"
sha256sum "$ROOT/releases/DataForge-1.0.3.apk" > "$ROOT/releases/DataForge-1.0.3.apk.sha256"
echo "Built $ROOT/releases/DataForge-1.0.3.apk"
