#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

python3 tests/test_engine.py
node --check mobile/app.js
python3 - <<'PY'
from html.parser import HTMLParser
from pathlib import Path

class Parser(HTMLParser):
    pass

root = Path.cwd()
html = (root / "mobile/index.html").read_text(encoding="utf-8")
Parser().feed(html)
assert '<script src="sql.js"></script><script src="app.js"></script>' in html
app = (root / "mobile/app.js").read_text(encoding="utf-8")
for marker in ("seedSampleData", "buildSQL", "importFile", "exportResult", "drawChart", "indexedDB.open('DataForge',1)"):
    assert marker in app, marker
config = (root / "android_app_config.mjs").read_text(encoding="utf-8")
assert "packageId: 'app.dataforge.mobile'" in config
assert "version: '1.0.3'" in config
PY

if [[ -f releases/DataForge-1.0.3.apk ]]; then
  unzip -tq releases/DataForge-1.0.3.apk >/dev/null
  listing="$(unzip -Z1 releases/DataForge-1.0.3.apk)"
  for entry in AndroidManifest.xml assets/index.html assets/main.js assets/sql.js assets/style.css classes.dex; do
    grep -Fxq "$entry" <<<"$listing"
  done
  sha256sum -c releases/DataForge-1.0.3.apk.sha256
fi

if rg -n -i --hidden \
  --glob '!mobile/sql.js' --glob '!test.sh' --glob '!SUPPORT.md' --glob '!.github/FUNDING.yml' \
  --glob '!.github/ISSUE_TEMPLATE/funded-direction.yml' \
  --glob '!.gitignore' \
  --glob '!releases/**' --glob '!mobile/node_modules/**' \
  'worldforge|everforge|igneos|alfred|com\.requiredtruth|BEGIN [A-Z ]*PRIVATE KEY|\.jks|\.keystore|seed phrase|private key' .; then
  echo "Private, signing, or excluded project material detected" >&2
  exit 1
fi

echo "DataForge checks: PASS"
