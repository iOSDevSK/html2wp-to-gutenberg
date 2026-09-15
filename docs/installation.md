# Installation

The skill is one directory — `SKILL.md`, `references/`, `scripts/` — and the
harness in `scripts/` has dependencies on the machine that runs a conversion.
Installing means putting the directory where the agent looks and putting those
dependencies in place.

## The skill directory

**Claude Code, global** — available in every project:

```bash
git clone https://github.com/iOSDevSK/html2wp-to-gutenberg.git ~/Developer/html2wp-to-gutenberg
mkdir -p ~/.claude/skills
ln -s ~/Developer/html2wp-to-gutenberg ~/.claude/skills/html2wp-to-gutenberg
```

A symlink rather than a copy, so `git pull` in the clone is the whole update.

**Claude Code, one project** — clone or copy the repository to
`<project>/.claude/skills/html2wp-to-gutenberg`. A git submodule works too.

**Other hosts** — the directory follows the
[Agent Skills specification](https://agentskills.io/specification): a
`SKILL.md` with frontmatter, `references/` the agent reads on demand,
`scripts/` it runs. Put it where the host looks for skills.

## Dependencies

| Needed for | What | Check |
|---|---|---|
| every `.py` | Python 3.10 or newer | `python3 --version` |
| `visual-diff.py`, `measure-diff.py`, `editor-validity.py` | playwright with Chromium; numpy and Pillow for the diff | `pip install -r scripts/requirements.txt && python3 -m playwright install chromium` |
| `wp-sandbox/` | PHP CLI 7.4 or newer with the `sqlite3` extension (the drop-in database) and `gd` (the importer resizes photographs) | `php -m` lists `sqlite3` and `gd` |
| `wp-sandbox/setup.sh` | curl and unzip to fetch WordPress and the SQLite drop-in; rsync to copy the theme in | `which curl unzip rsync` |
| tier 1 | node, for the wp-block-theme-converter doctor | `node --version` |
| criteria 7 and 8 | Visual Edit Lite 1.27 or newer, the plugin the theme's form blocks are checked against | its ZIP at hand |
| the worked example | access to the private reference repository, if you want to read how it did something | ask the owner |

Keep the virtual environment outside the skill directory, or under `.venv/`,
which `.gitignore` already covers. A directory the agent's host scans as part of
the skill should hold the skill, not a copy of Chromium.

```bash
python3 -m venv ~/.venvs/html2wp && source ~/.venvs/html2wp/bin/activate
pip install -r scripts/requirements.txt
python3 -m playwright install chromium
```

## Validating the install

The Agent Skills reference implementation ships a validator. In any virtual
environment:

```bash
pip install skills-ref
skills-ref validate ~/Developer/html2wp-to-gutenberg
```

It checks the frontmatter (`name`, `description`, `license`, `compatibility`)
against the specification. Then a smoke test of the harness — every script must
refuse to run with no arguments, and refuse loudly:

```bash
cd ~/Developer/html2wp-to-gutenberg/scripts
for f in *.py wp-sandbox/*.sh wp-sandbox/*.php; do
  case "$f" in *.py) python3 "$f" ;; *.sh) bash "$f" ;; *.php) php "$f" ;; esac >/dev/null 2>&1
  echo "$f exit=$?"
done
```

Every line should end in `exit=2`. An exit of 0 here would mean a gate that can
pass on nothing, and that is the one thing the harness is built not to do.

## Updating

```bash
git -C ~/Developer/html2wp-to-gutenberg pull
```

The symlink follows. [CHANGELOG.md](../CHANGELOG.md) says what changed; the
entries that add a pitfall are the ones worth reading before the next
conversion, because a pitfall is a thing that already went wrong once.

## Removing

Delete the symlink (or the project copy). The clone and the virtual environment
are yours to keep or drop.
