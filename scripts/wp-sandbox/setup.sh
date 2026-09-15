#!/bin/bash
# SPDX-License-Identifier: GPL-2.0-or-later
# Build a throwaway WordPress with a theme installed, on SQLite, no server
# software required beyond PHP. Everything lands in the sandbox directory,
# which is created BESIDE the theme, never inside it — a WordPress inside the
# theme directory makes every theme linter walk core (pitfall #11).
#
#   bash setup.sh <theme-dir> [sandbox-dir]
#
#   PORT=8899                        the address baked into wp-config
#   SITE_TITLE="Sandbox"             what wp_install() names the site
#   ADMIN_PASSWORD=admin-password    user is always "admin"
#   IMPORT_FUNCTION=<slug>_run_import
#                                    the theme's synchronous whole-import
#                                    function (SKILL.md step 8); left unset,
#                                    the import is skipped and said so.
#                                    It runs as user 1 (IMPORT_USER to change):
#                                    without a user, kses strips every form
#                                    control out of post_content (pitfall #5d)
#
# Afterwards:
#   PHP_CLI_SERVER_WORKERS=8 php -S 127.0.0.1:$PORT -t <sandbox>/wordpress
#   bash sync.sh <theme-dir> <sandbox-dir>      # push theme changes in again
#   python3 ../editor-validity.py --site http://127.0.0.1:$PORT --user admin --password $ADMIN_PASSWORD
#   python3 ../visual-diff.py --original <rendered originals> --live http://127.0.0.1:$PORT
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
if [ $# -lt 1 ] || [ ! -d "$1" ]; then
  echo "usage: bash setup.sh <theme-dir> [sandbox-dir]" >&2
  exit 2
fi
THEME="$(cd "$1" && pwd)"
SLUG="$(basename "$THEME")"
SANDBOX="${2:-$(dirname "$THEME")/$SLUG-sandbox}"
PORT="${PORT:-8899}"
SITE_TITLE="${SITE_TITLE:-Sandbox}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-admin-password}"

if [ ! -f "$THEME/style.css" ] || [ ! -f "$THEME/theme.json" ]; then
  echo "error: $THEME has no style.css/theme.json — not a block theme" >&2
  exit 2
fi
case "$SANDBOX" in "$THEME"/*) echo "error: sandbox must not be inside the theme" >&2; exit 2;; esac

mkdir -p "$SANDBOX" && cd "$SANDBOX"
SANDBOX="$(pwd)"

if [ ! -d wordpress ]; then
  echo "downloading WordPress…"
  curl -sSL -o wp.tar.gz https://wordpress.org/latest.tar.gz
  tar xzf wp.tar.gz && rm wp.tar.gz
fi

# SQLite drop-in, so there is no database server to install.
if [ ! -d wordpress/wp-content/plugins/sqlite-database-integration ]; then
  echo "downloading the SQLite drop-in…"
  curl -sSL -o sqlite.zip https://downloads.wordpress.org/plugin/sqlite-database-integration.zip
  unzip -q sqlite.zip -d wordpress/wp-content/plugins/ && rm sqlite.zip
fi
python3 - "$SANDBOX" <<'PY'
import pathlib, sys
base = pathlib.Path(sys.argv[1]) / "wordpress/wp-content"
src = (base / "plugins/sqlite-database-integration/db.copy").read_text()
# The placeholders sit inside single quotes, so they take plain strings —
# not PHP expressions (pitfall #11).
src = src.replace("{SQLITE_IMPLEMENTATION_FOLDER_PATH}", str(base / "plugins/sqlite-database-integration"))
src = src.replace("{SQLITE_PLUGIN}", "sqlite-database-integration/load.php")
(base / "db.php").write_text(src)
PY

cat > wordpress/wp-config.php <<CONF
<?php
define( 'DB_NAME', 'wordpress' ); define( 'DB_USER', '' );
define( 'DB_PASSWORD', '' );     define( 'DB_HOST', 'localhost' );
define( 'DB_CHARSET', 'utf8' );  define( 'DB_COLLATE', '' );
define( 'AUTH_KEY','a' ); define( 'SECURE_AUTH_KEY','b' ); define( 'LOGGED_IN_KEY','c' );
define( 'NONCE_KEY','d' ); define( 'AUTH_SALT','e' ); define( 'SECURE_AUTH_SALT','f' );
define( 'LOGGED_IN_SALT','g' ); define( 'NONCE_SALT','h' );
\$table_prefix = 'wp_';
define( 'DISABLE_WP_CRON', true );   // it tries to fetch every URL it finds (pitfall #11)
define( 'WP_DEBUG', true ); define( 'WP_DEBUG_LOG', true ); define( 'WP_DEBUG_DISPLAY', false );
define( 'WP_HOME', 'http://127.0.0.1:$PORT' );
define( 'WP_SITEURL', 'http://127.0.0.1:$PORT' );
if ( ! defined( 'ABSPATH' ) ) { define( 'ABSPATH', __DIR__ . '/' ); }
require_once ABSPATH . 'wp-settings.php';
CONF

bash "$HERE/sync.sh" "$THEME" "$SANDBOX"
WP_ROOT="$SANDBOX/wordpress" THEME_SLUG="$SLUG" SITE_TITLE="$SITE_TITLE" ADMIN_PASSWORD="$ADMIN_PASSWORD" \
  php "$HERE/install.php"
if [ -n "${IMPORT_FUNCTION:-}" ]; then
  WP_ROOT="$SANDBOX/wordpress" IMPORT_FUNCTION="$IMPORT_FUNCTION" php "$HERE/import.php"
else
  echo "import skipped: set IMPORT_FUNCTION=<the theme's whole-import function> to run it"
fi

echo
echo "Serve it with:"
echo "  PHP_CLI_SERVER_WORKERS=8 php -S 127.0.0.1:$PORT -t $SANDBOX/wordpress"
echo "Admin: http://127.0.0.1:$PORT/wp-admin  (admin / $ADMIN_PASSWORD)"
echo "debug.log: $SANDBOX/wordpress/wp-content/debug.log"
