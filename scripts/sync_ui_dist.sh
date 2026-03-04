#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="$ROOT_DIR/frontend/dist"
TARGET_DIR="$ROOT_DIR/attractor/ui_dist"

if [[ ! -f "$SOURCE_DIR/index.html" ]]; then
  echo "Missing frontend build output at $SOURCE_DIR/index.html" >&2
  echo "Run 'npm --prefix frontend run build' first." >&2
  exit 1
fi

rm -rf "$TARGET_DIR"
mkdir -p "$TARGET_DIR"
cp -R "$SOURCE_DIR"/. "$TARGET_DIR"/

echo "Synced UI bundle to $TARGET_DIR"
