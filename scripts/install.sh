#!/usr/bin/env bash
#
# install.sh — put what the conversion needs on this machine.
#
#   bash scripts/install.sh            print what would happen, change nothing
#   bash scripts/install.sh --yes      do it
#   bash scripts/install.sh --help     usage
#
# The compatibility line in SKILL.md is a list of homework, and a list of
# homework is not a working machine. This installs the missing half: PHP with
# sqlite3 and gd, WP-CLI, the three Python packages and the Chromium that
# Playwright needs separately from its own package, plus node, rsync and
# unzip when they are absent.
#
# Dry run by default, always. Every command that changes anything goes through
# run(), which prints it instead when --yes was not given — that is what makes
# the preview trustworthy rather than a promise.
#
# It installs nothing it cannot see a use for: each step checks first and says
# so. Running it twice is harmless.
set -uo pipefail

APPLY=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) APPLY=1 ;;
    --help|-h) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown argument: $arg (try --help)" >&2; exit 2 ;;
  esac
done

if [ -t 1 ]; then
  B=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; R=$'\033[0m'
else
  B=''; DIM=''; GREEN=''; YELLOW=''; RED=''; R=''
fi
step()  { printf '\n%s==>%s %s%s%s\n' "$B" "$R" "$B" "$1" "$R"; }
ok()    { printf '    %s✓%s %s\n' "$GREEN" "$R" "$1"; }
warn()  { printf '    %s!%s %s\n' "$YELLOW" "$R" "$1"; }
fail()  { printf '    %s✗%s %s\n' "$RED" "$R" "$1"; }
note()  { printf '    %s%s%s\n' "$DIM" "$1" "$R"; }
run() {
  if [ "$APPLY" -eq 1 ]; then printf '    %s$ %s%s\n' "$DIM" "$*" "$R"; "$@"
  else printf '    %swould run:%s %s\n' "$DIM" "$R" "$*"; return 0; fi
}
have() { command -v "$1" >/dev/null 2>&1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FAILED=0

# ------------------------------------------------------------- Homebrew ----
step "Checking this machine"
if [ "$(uname -s)" != "Darwin" ]; then
  warn "$(uname -s), not macOS — the brew commands below will not apply; install the same things your way"
fi
if have brew; then
  ok "Homebrew $(brew --version 2>/dev/null | head -1 | awk '{print $2}')"
else
  fail "Homebrew is not installed, and every step below uses it"
  note "install it from https://brew.sh, then run this again"
  note "this script will not install a package manager behind your back"
  exit 1
fi

# ------------------------------------------------------------------ PHP ----
step "PHP, WP-CLI — the sandbox"
if have php; then
  ok "php $(php -r 'echo PHP_VERSION;' 2>/dev/null)"
  # Homebrew's PHP carries sqlite3 and gd. A system PHP may not, and there is
  # nothing to install for it — the fix is to use Homebrew's.
  for ext in sqlite3 gd; do
    if php -m 2>/dev/null | grep -qix "$ext"; then ok "php has $ext"
    else
      warn "php has no $ext"
      note "this php build does not carry it: $(command -v php)"
      note "macOS's own php never has gd — put Homebrew's first on PATH; a Homebrew php that still lacks it wants brew reinstall php"
    fi
  done
else
  run brew install php || FAILED=1
fi
have wp && ok "wp-cli $(wp --version 2>/dev/null | head -1)" || run brew install wp-cli || FAILED=1

# --------------------------------------------------------------- Python ----
step "Python, Playwright, Chromium — the visual gates"
PY=""
for c in python3 python; do have "$c" && { PY="$c"; break; }; done
if [ -z "$PY" ]; then
  run brew install python || FAILED=1
  PY=python3
else
  ok "python $("$PY" -c 'import sys;print(".".join(map(str,sys.version_info[:3])))' 2>/dev/null)"
fi

if "$PY" -c 'import playwright, numpy, PIL' >/dev/null 2>&1; then
  ok "playwright, numpy and Pillow are already importable"
else
  # --user keeps this out of a system site-packages that macOS protects; a
  # virtualenv the caller already activated takes it anyway.
  run "$PY" -m pip install --user -r "$HERE/requirements.txt" || FAILED=1
fi

# The package and the browser are two downloads. `import playwright` passing
# says nothing about whether there is a Chromium to drive.
if "$PY" -c 'import playwright' >/dev/null 2>&1 && "$PY" - <<'PYCHECK' >/dev/null 2>&1
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    p.chromium.launch().close()
PYCHECK
then
  ok "Chromium is already downloaded"
else
  run "$PY" -m playwright install chromium || FAILED=1
fi

# ------------------------------------------------------------- the rest ----
step "node, rsync, unzip, curl"
for tool in node rsync unzip curl; do
  if have "$tool"; then ok "$tool"
  else run brew install "$tool" || FAILED=1; fi
done

# ------------------------------------------------------------------ end ----
if [ "$APPLY" -eq 0 ]; then
  printf '\n%sThis was a dry run. Nothing changed.%s\n' "$B" "$R"
  printf 'Run it again with %s--yes%s to apply, or %sbash %s/doctor.sh%s to see what is actually missing first.\n\n' \
    "$B" "$R" "$B" "${HERE/#$HOME/\~}" "$R"
  exit 0
fi

step "Verifying"
if bash "$HERE/doctor.sh"; then
  printf '%sDone.%s The conversion can start.\n\n' "$GREEN$B" "$R"
  exit 0
fi
printf '%sFinished with problems.%s The doctor lines above say what is still missing.\n\n' "$YELLOW$B" "$R"
exit 1
