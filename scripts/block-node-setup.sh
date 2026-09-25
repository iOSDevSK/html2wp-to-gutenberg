#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-2.0-or-later
# The node packages block-roundtrip.cjs needs, as ONE WordPress release ships
# them:
#
#   bash block-node-setup.sh <dir> [wp-7.0]
#   NODE_PATH=<dir>/node_modules node block-roundtrip.cjs …
#
# Installing @wordpress/blocks and @wordpress/block-library at their wp-X.Y
# dist-tags is not enough: block-library depends on ~57 other @wordpress/*
# packages by range, npm resolves those to today's latest, and a second copy of
# @wordpress/blocks ends up registering the core blocks where validateBlock
# does not look (every block "invalid", or a crash on the first parse). So
# every @wordpress/* package in the tree is pinned to the same dist-tag
# through npm overrides, and the install is done twice: once to learn the
# tree, once pinned.
#
# Exit 0 installed; 1 npm failed; 2 usage.
set -euo pipefail
DIR="${1:-}"; TAG="${2:-wp-7.0}"
[ -n "$DIR" ] || { echo "usage: bash block-node-setup.sh <dir> [wp-X.Y]" >&2; exit 2; }
command -v npm >/dev/null || { echo "error: npm is not installed" >&2; exit 2; }
mkdir -p "$DIR"
cd "$DIR"
[ -f package.json ] || echo '{"private":true}' > package.json
npm install --no-audit --no-fund --silent "@wordpress/blocks@$TAG" "@wordpress/block-library@$TAG" jsdom@24 || exit 1
python3 - "$TAG" <<'EOF'
import json, subprocess, sys
from pathlib import Path
tag = sys.argv[1]
names = sorted({p.parent.name if p.parent.parent.name == "@wordpress" else None
                for p in Path("node_modules").rglob("@wordpress/*/package.json")} - {None})
overrides = {}
for name in names:
    out = subprocess.run(["npm", "view", f"@wordpress/{name}", "dist-tags", "--json"],
                         capture_output=True, text=True).stdout
    try:
        version = json.loads(out or "{}").get(tag)
    except ValueError:
        version = None
    if version:
        overrides[f"@wordpress/{name}"] = version
pkg = json.loads(Path("package.json").read_text())
pkg["overrides"] = overrides
for dep in ("@wordpress/blocks", "@wordpress/block-library"):
    if dep in overrides:
        pkg.setdefault("dependencies", {})[dep] = overrides[dep]
Path("package.json").write_text(json.dumps(pkg, indent=2) + "\n")
print(f"pinned {len(overrides)} @wordpress packages to {tag}")
EOF
rm -rf node_modules package-lock.json
npm install --no-audit --no-fund --silent || exit 1
echo "ok: NODE_PATH=$PWD/node_modules node block-roundtrip.cjs …"
