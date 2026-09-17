#!/usr/bin/env bash
#
# doctor.sh — is this machine able to run the conversion? Changes nothing.
#
#   bash scripts/doctor.sh
#
# The `compatibility` line in SKILL.md names what the conversion needs. Naming
# it is not the same as having it: a run that starts without Playwright gets
# through the audit, through the rewrite, and stops at tier 2 with the work
# half done and the reason four steps behind it. This asks every question up
# front, in the order the workflow will ask them.
#
# Every line is a question with a yes or a no, and a no says what to run.
# Exit 0 means the conversion can start; 1 means something needed is missing.
set -uo pipefail

if [ -t 1 ]; then
  B=$'\033[1m'; DIM=$'\033[2m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; R=$'\033[0m'
else
  B=''; DIM=''; GREEN=''; YELLOW=''; RED=''; R=''
fi

MISSING=0
row() {  # row <ok|no|warn> <label> <detail>
  case "$1" in
    ok)   printf '  %s✓%s  %-24s %s\n' "$GREEN" "$R" "$2" "$3" ;;
    no)   printf '  %s✗%s  %-24s %s\n' "$RED" "$R" "$2" "$3"; MISSING=1 ;;
    warn) printf '  %s!%s  %-24s %s\n' "$YELLOW" "$R" "$2" "$3" ;;
  esac
}
hint() { printf '     %s%s%s\n' "$DIM" "$1" "$R"; }
have() { command -v "$1" >/dev/null 2>&1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

printf '\n%shtml2wp → Gutenberg%s\n\n' "$B" "$R"

# ------------------------------------------------------------------ PHP ----
# PHP runs the sandbox and lints every template the conversion writes. sqlite3
# is what lets the sandbox exist without a database server; gd is what lets it
# generate the thumbnails the visual diff compares.
printf '%sPHP%s\n' "$B" "$R"
if have php; then
  row ok "php" "$(php -r 'echo PHP_VERSION;' 2>/dev/null || echo '?')"
  for ext in sqlite3 gd; do
    if php -m 2>/dev/null | grep -qix "$ext"; then
      row ok "php ext $ext" "loaded"
    else
      row no "php ext $ext" "not loaded"
      hint "this php build does not carry it: $(command -v php)"
      hint "macOS's own php never has gd; a Homebrew php that lacks it wants brew reinstall php"
    fi
  done
else
  row no "php" "not on PATH"
  hint "brew install php"
  row no "php ext sqlite3" "cannot check without php"
  row no "php ext gd" "cannot check without php"
fi

if have wp; then
  row ok "wp-cli" "$(wp --version 2>/dev/null | head -1 || echo installed)"
else
  row no "wp-cli" "not on PATH"
  hint "brew install wp-cli — scripts/wp-sandbox/setup.sh calls it throughout"
fi

# --------------------------------------------------------------- Python ----
# Tier 2 is the pixel comparison, and step 9 accepts nothing without it.
printf '\n%sPython and the visual gates%s\n' "$B" "$R"
PY=""
for c in python3 python; do have "$c" && { PY="$c"; break; }; done
if [ -n "$PY" ]; then
  row ok "python" "$("$PY" -c 'import sys;print(".".join(map(str,sys.version_info[:3])))' 2>/dev/null)"
  for mod in playwright numpy PIL; do
    label=$([ "$mod" = PIL ] && echo Pillow || echo "$mod")
    if "$PY" -c "import $mod" >/dev/null 2>&1; then
      row ok "python $label" "importable"
    else
      row no "python $label" "not installed"
      hint "$PY -m pip install -r $HERE/requirements.txt"
    fi
  done
  # The browser is a separate download from the package, and forgetting it is
  # the commonest way a machine passes `import playwright` and still cannot
  # take a screenshot.
  if "$PY" -c "import playwright" >/dev/null 2>&1; then
    if "$PY" - <<'PYCHECK' >/dev/null 2>&1
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    p.chromium.launch().close()
PYCHECK
    then row ok "chromium" "playwright can launch it"
    else
      row no "chromium" "playwright has no browser to launch"
      hint "$PY -m playwright install chromium"
    fi
  fi
else
  row no "python" "not on PATH"
  hint "brew install python"
fi

# ----------------------------------------------------------- the rest ------
printf '\n%sEverything else the workflow shells out to%s\n' "$B" "$R"
for tool in node rsync curl unzip; do
  if have "$tool"; then row ok "$tool" "$(command -v "$tool")"
  else row no "$tool" "not on PATH"; hint "brew install $tool"; fi
done

# Named in compatibility, and only two of the eight acceptance criteria need
# it — so it is a warning, not a stop. A conversion without it is finishable;
# it just cannot close criteria 7 and 8.
printf '\n%sVisual Edit Lite%s\n' "$B" "$R"
VEL=""
for guess in "$HOME/Developer/visual-edit-lite" "$HOME/Developer/visual-edit" \
             "$(dirname "$HERE")/../visual-edit-lite"; do
  [ -f "$guess/includes/class-form-blocks.php" ] && { VEL="$guess"; break; }
done
if [ -n "$VEL" ]; then
  row ok "visual-edit-lite" "${VEL/#$HOME/\~}"
else
  row warn "visual-edit-lite" "not found in the usual places"
  hint "needed only for the two-sided form and SEO gates (verification.md, criteria 7-8)"
fi

# ------------------------------------------------------------------ end ----
printf '\n'
if [ "$MISSING" -eq 0 ]; then
  printf '%sThis machine can run the conversion.%s\n\n' "$GREEN$B" "$R"
  exit 0
fi
printf '%sSomething needed is missing.%s The lines marked ✗ say what.\n' "$YELLOW$B" "$R"
printf 'To install them: %sbash %s/install.sh%s (shows the plan), then %s--yes%s.\n\n' \
  "$B" "${HERE/#$HOME/\~}" "$R" "$B" "$R"
exit 1
