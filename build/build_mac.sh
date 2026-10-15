#!/bin/sh
# Builds the macOS app -> dist/EuroJackpotApp-mac-<arm64|intel>.zip (+ .sha256). Run on a Mac (or in GitHub Actions: .github/workflows/mac.yml).
# Usage (project root):  sh build/build_mac.sh
set -e
cd "$(dirname "$0")/.."
PY=${PYTHON:-python3}
[ -d .venv ] || { "$PY" -m venv .venv; .venv/bin/pip install -r requirements.txt; }
NAME="EuroJackpot Analyzer"
VERSION=$(.venv/bin/python -c "from app.version import __version__ as v; print(v)")
.venv/bin/python -m PyInstaller --noconfirm --clean --windowed --name "$NAME" \
    --icon build/icon.icns --osx-bundle-identifier io.github.vezrevoulis.eurojackpot-analyzer \
    --distpath dist --workpath build/work --specpath build/work \
    --add-data "$PWD/app/ui:app/ui" --add-data "$PWD/app/locales:app/locales" --add-data "$PWD/app/seed:app/seed" \
    --collect-submodules webview --paths "$PWD" run.py
APP="dist/$NAME.app"
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $VERSION" -c "Set :CFBundleVersion $VERSION" "$APP/Contents/Info.plist"
# ad-hoc signature (required to run on Apple Silicon; not a paid Developer ID, so Gatekeeper still asks on first launch)
codesign --force --deep --sign - "$APP"
"$APP/Contents/MacOS/$NAME" --selftest
ARCH=intel; [ "$(uname -m)" = arm64 ] && ARCH=arm64
ZIP="dist/EuroJackpotApp-mac-$ARCH.zip"
rm -f "$ZIP"
ditto -c -k --keepParent "$APP" "$ZIP"
(cd dist && shasum -a 256 "$(basename "$ZIP")" > "$(basename "$ZIP").sha256")
echo "Done: $ZIP"
