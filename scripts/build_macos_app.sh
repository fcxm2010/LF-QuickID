#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-./.venv/bin/python}"
PYINSTALLER_CONFIG_DIR="${PYINSTALLER_CONFIG_DIR:-/private/tmp/lf-quickid-pyinstaller-config}"
SPEC_DIR="${SPEC_DIR:-/private/tmp/lf-quickid-pyinstaller-spec}"
WORK_DIR="${WORK_DIR:-/private/tmp/lf-quickid-pyinstaller-build}"
DIST_DIR="${DIST_DIR:-dist}"
APP_PATH="$DIST_DIR/LF QuickID.app"

rm -rf "$PYINSTALLER_CONFIG_DIR" "$SPEC_DIR" "$WORK_DIR" "$APP_PATH"
mkdir -p "$PYINSTALLER_CONFIG_DIR" "$SPEC_DIR" "$WORK_DIR" "$DIST_DIR"
export PYINSTALLER_CONFIG_DIR

"$PYTHON_BIN" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "LF QuickID" \
  --osx-bundle-identifier "com.lf.quickid" \
  --paths src \
  --collect-all cv2 \
  --collect-all insightface \
  --collect-all onnxruntime \
  --collect-all rembg \
  --collect-all pymatting \
  --collect-all sklearn \
  --hidden-import rembg.sessions.u2net \
  --hidden-import rembg.sessions.dis_general_use \
  --hidden-import rembg.sessions.birefnet_general \
  --hidden-import rembg.sessions.birefnet_portrait \
  --hidden-import sklearn.cluster._dbscan_inner \
  --specpath "$SPEC_DIR" \
  --workpath "$WORK_DIR" \
  --distpath "$DIST_DIR" \
  src/lf_quickid/main.py

codesign --force --deep --sign - "$APP_PATH"
codesign --verify --deep --strict "$APP_PATH"

echo "$APP_PATH"
