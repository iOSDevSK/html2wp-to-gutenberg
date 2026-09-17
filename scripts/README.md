# Scripts

The file gates and the tier-2 harness, vendored from the reference conversion
(`github.com/iOSDevSK/amanda-rose-guttenberg`, `tools/`) with every
project-specific value turned into an argument or a config key. Which step or
gate each one serves is in `SKILL.md` and `references/verification.md`.

## Before anything else

| | |
|---|---|
| `doctor.sh` | Can this machine run the conversion? Reads only. Exit 0 means yes. |
| `install.sh` | Installs what the doctor found missing. Dry run until `--yes`. |

The `compatibility` line in SKILL.md names what the conversion needs; these
two check it and fix it. Run the doctor before step 1 — a run that finds out
at step 9 that Playwright is absent has done eight steps it cannot close.

## The gates and the harness

| Script | Serves | Needs |
|---|---|---|
| `lint-delimiters.py <theme> [--fix]` | tier 1 — block grammar and delimiter pairing, `content/` included | python3 |
| `lint-html.py <theme>` | tier 1 — tag balance inside block markup | python3 |
| `raise-specificity.py <site.css> [--write]` | step 4 — `:root ` prefix on every selector (pitfall #3) | python3 |
| `apply-style-classes.py --sources … --pages … --map … [--write]` | step 7 — inline styles → utility classes, reconciled by class-set + ordinal (pitfall #6) | python3 |
| `wp-sandbox/setup.sh <theme> [sandbox]` | tier 2 — WordPress on SQLite beside the theme, installed, imported | php (sqlite3, gd), curl, unzip, rsync |
| `wp-sandbox/sync.sh <theme> <sandbox>` | tier 2 — push theme changes in again | rsync |
| `render-original.py --config …` | tier 2 baseline — the html2wp sources composed the way the old runtime did | python3 |
| `visual-diff.py --original … --live …` | criterion 1 — pixel diff of every page against the original | playwright, numpy, Pillow |
| `measure-diff.py --original … --live … --css …` | criterion 1 debugging — which element moved | playwright |
| `editor-validity.py --site … --user … --password …` | criterion 2 — invalid blocks across every page and post | playwright |

Python dependencies: `bash install.sh --yes`, or by hand with
`pip install -r requirements.txt && python3 -m playwright install chromium`.

Exit status, every script: **0** pass, **1** findings, **2** usage error or
nothing to check. A wrong path or an empty directory is never a green run.
