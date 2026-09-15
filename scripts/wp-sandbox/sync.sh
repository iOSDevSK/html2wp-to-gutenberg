#!/bin/bash
# Copy the theme into the sandbox. A copy rather than a symlink: WordPress
# resolves theme paths in ways that make a symlinked theme unreliable.
#
#   bash sync.sh <theme-dir> <sandbox-dir>
set -euo pipefail
if [ $# -ne 2 ] || [ ! -d "$1" ] || [ ! -d "$2/wordpress" ]; then
  echo "usage: bash sync.sh <theme-dir> <sandbox-dir>   (sandbox-dir must hold wordpress/)" >&2
  exit 2
fi
THEME="$(cd "$1" && pwd)"
SLUG="$(basename "$THEME")"
DEST="$(cd "$2" && pwd)/wordpress/wp-content/themes/$SLUG/"
mkdir -p "$DEST"
rsync -a --delete \
  --exclude 'preview' --exclude 'preview-original' --exclude 'preview-diff' \
  --exclude 'tools' --exclude 'steps' --exclude 'dist' --exclude 'node_modules' \
  --exclude '.git' --exclude '.DS_Store' \
  "$THEME/" "$DEST"
echo "synced $SLUG → $DEST"
