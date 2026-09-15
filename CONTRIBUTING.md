# Contributing

The skill is a procedure with evidence attached. A change is welcome when it
makes the next conversion cheaper than the last one, and it is safe when the
checks below still pass.

## Where things go

- **`SKILL.md`** is the procedure. Short, imperative, one idea per step, and
  every claim traceable to a pitfall number or a script. It links into
  `references/` and `scripts/`, never into `docs/`.
- **`references/`** is what the agent reads on demand: the mapping rules, the
  form and SEO contract, the pitfalls, the verification criteria. Reasoning
  lives here, not in `SKILL.md`.
- **`references/pitfalls.md`** is append-mostly and numbered. A new entry says
  what was seen, why WordPress does that, what fixed it, and how the harness
  now catches it. Sub-letters (`5b`, `16d-bis`) keep related traps together;
  do not renumber.
- **`scripts/`** are deterministic gates. Every script exits 0 on pass, 1 on
  findings, 2 on a usage error or nothing to check. A script that can exit 0
  on an empty directory is a bug.
- **`docs/`** is for people. It explains and links; it does not restate the
  procedure.

## Before you commit

```bash
# frontmatter and structure
pip install skills-ref && skills-ref validate .

# every script refuses to run on nothing
cd scripts && for f in *.py wp-sandbox/*.sh wp-sandbox/*.php; do
  case "$f" in *.py) python3 "$f" ;; *.sh) bash "$f" ;; *.php) php "$f" ;; esac >/dev/null 2>&1; echo "$f exit=$?"
done

# syntax
python3 -m py_compile scripts/*.py && bash -n scripts/wp-sandbox/*.sh && php -l scripts/wp-sandbox/install.php && php -l scripts/wp-sandbox/import.php
```

A change to a script is proven against the reference conversion when you have
access to it (`docs/reference-conversion.md`): the linters over its `content/`,
the sandbox built from it, the editor walk at 0 invalid. Without access, prove
it against your own converted theme and say so in the commit.

## Commit messages

The subject is a sentence that says what changed and why, in the voice of the
existing log — "An importer that must finish inside one request will not" —
not a category label. The body carries the evidence: what was measured, on
which WordPress, and which pitfall or criterion it adds or changes.

## Licence

Contributions are accepted under the repository's licence, GPL-2.0-or-later,
so that everything the skill carries into a generated theme stays compatible
with WordPress.
