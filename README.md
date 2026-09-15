# html2wp-to-gutenberg

An [Agent Skill](https://agentskills.io) that turns a WordPress theme produced by
the html2wp converter into a **native Gutenberg block theme**. Every page and
journal entry becomes core block markup in `post_content`, editable in the
standard block editor with no plugin, and the front end stays visually 1:1 with
the original — verified by pixel diff against a real WordPress, not a static
harness.

It is the method that produced [Amanda Rose Blocks](#reference-implementation),
written down so the next conversion does not pay again for what that one
learned. The procedure is for an AI coding agent — Claude Code first, then any
host that reads the [Agent Skills specification](https://agentskills.io/specification).
The rules, the numbered pitfalls and the verification harness are what make the
procedure trustworthy.

## Why

An html2wp theme is a block theme in name only. `theme.json`, `templates/` and
`parts/` are there, but the content is raw HTML wrapped in `wp:html` blocks,
the pages live in `clara-content/sources/*.html`, dynamics run through
`[wp-posts]`, `[wp-form]` and `[wp-article]` tokens, and editing anything needs
the Visual Edit plugin. Take the plugin away and the owner cannot change a
heading.

## What you get

A new sibling theme in which:

- every page and post is core block markup that opens in the block editor with
  **0 invalid blocks**;
- the design's own CSS and JS are carried over, with a small *block bridge*
  layer absorbing the wrappers core adds, so every page is within about 1 % of
  the original at 1440 px and 390 px;
- forms are editable blocks the theme registers and delivers itself, and search
  metadata comes from the editor's own SEO panel;
- a setup screen imports the content in resumable slices, reports what it did,
  and can take the imported content back off the site without touching the
  owner's own;
- the old runtime (about 3,600 lines) is replaced by core WordPress.

What it does **not** promise: byte-identical HTML (core blocks add `wp-block-*`
classes and wrappers) or the same editing experience (the point is Gutenberg
instead of Visual Edit). [SKILL.md](SKILL.md#what-11-means-set-expectations-first)
sets those expectations before anything else.

## Requirements

From the skill's `compatibility` line, which is the authority:

> WordPress 6.6+ (theme.json v3) and PHP 7.4+ for the theme it produces. On the
> converting machine: PHP CLI with sqlite3 and gd, Python 3 with playwright,
> numpy and Pillow (scripts/requirements.txt) plus Chromium, node for the
> wp-block-theme-converter doctor, rsync, curl, unzip. Visual Edit Lite 1.27+
> for the two-sided form and SEO gates.

## Installation

Global, for Claude Code — every project sees it:

```bash
git clone https://github.com/iOSDevSK/html2wp-to-gutenberg.git ~/Developer/html2wp-to-gutenberg
mkdir -p ~/.claude/skills
ln -s ~/Developer/html2wp-to-gutenberg ~/.claude/skills/html2wp-to-gutenberg
```

Project scope: clone or copy the repository to
`<project>/.claude/skills/html2wp-to-gutenberg`. Any other host that reads the
Agent Skills specification: point it at the directory. `SKILL.md`,
`references/` and `scripts/` are the whole skill.

The Python side of the harness, in a virtual environment outside the
repository:

```bash
python3 -m venv ~/.venvs/html2wp && source ~/.venvs/html2wp/bin/activate
pip install -r scripts/requirements.txt
python3 -m playwright install chromium
```

Details — the PHP extensions, the other tools, how to validate the install and
how to update — are in [docs/installation.md](docs/installation.md).

## Using it

Ask the agent in its own words: "convert my html2wp theme to native blocks",
"make the theme editable without Visual Edit", "preklop tému do Gutenbergu",
"gutenberg verzia témy", or name the skill. It refuses plain static HTML
folders — those belong to wp-block-theme-converter or html2wp-sub — and says
so.

Have ready what [Inputs required](SKILL.md#inputs-required) lists: the html2wp
theme directory with its `clara-content/`, the new theme's slug, what the
original looked like, which plugins the old site used, and the tooling above.

The agent then works through nine steps, each closed by a gate:

1. [Audit](SKILL.md#1-audit-fan-out-explore-agents-do-not-skip) the bundle and the theme, recording what will deliberately not be ported.
2. [Scaffold + theme.json](SKILL.md#2-scaffold--themejson) — v3, presets mirroring the design's tokens, core's own defaults off.
3. [Fonts](SKILL.md#3-fonts-self-host) — self-hosted, the same cuts the CDN served.
4. [CSS](SKILL.md#4-css-verbatim--alias-layer--block-bridge) — verbatim, aliased to the presets, plus the block bridge and the specificity raise.
5. [JS](SKILL.md#5-js-keep-it-classic-rekey-what-render-time-filters-used-to-fix) — classic and deferred, rekeyed where render-time filters used to inject ids.
6. [Parts, templates, patterns](SKILL.md#6-parts-templates-patterns) — real menus, thin templates, PHP patterns wherever a theme URL is needed.
7. [Content conversion](SKILL.md#7-content-conversion-the-bulk--fan-out-agents) — one agent per page family, inline styles reconciled in one pass.
8. [Importer + setup screen](SKILL.md#8-importer--setup-screen), and [its reverse](SKILL.md#8b-the-other-direction--removing-the-imported-content), the cleanup.
9. [Verify](SKILL.md#9-verify--files-first-then-a-real-wordpress-non-negotiable) — files first, then a real WordPress.

Where it stops and asks instead of guessing is
[Escalation](SKILL.md#escalation--when-to-stop-and-ask). A human-paced walk
through the same steps, with what each one produces and what you will be asked
for, is [docs/workflow.md](docs/workflow.md).

## Scripts

The file gates and the tier-2 harness, vendored from the reference conversion
with every project-specific value turned into an argument.

| Script | What it closes |
|---|---|
| `lint-delimiters.py`, `lint-html.py` | tier 1 — block grammar and pairing, tag balance |
| `raise-specificity.py`, `apply-style-classes.py` | steps 4 and 7 — the specificity raise, inline styles to utility classes |
| `wp-sandbox/setup.sh`, `sync.sh`, `install.php`, `import.php` | tier 2 — a WordPress on SQLite beside the theme, installed and imported |
| `render-original.py`, `visual-diff.py`, `measure-diff.py` | criterion 1 — the pixel diff against the original, and which element moved |
| `editor-validity.py` | criterion 2 — invalid blocks across every page and post |

Every script exits 0 on pass, 1 on findings and 2 on a usage error or nothing to
check, so a wrong path is never a green run. Usage at a glance is in
[scripts/README.md](scripts/README.md); every flag, variable and example is in
[docs/scripts.md](docs/scripts.md).

## Verification and acceptance

Two tiers, and only the second counts. Tier 1 is files: the two linters, the
wp-block-theme-converter doctor, `php -l`. Tier 2 is a throwaway WordPress
built by `setup.sh`, because a static harness agreed with the original at
0.56 % while the real thing was 26 % out.

A conversion is accepted when every page is within about 1 % of the original at
1440 px and 390 px; every page and post opens in the block editor with 0 invalid
blocks, with and without Visual Edit Lite active; every form sends and every
field is editable; a description typed into the SEO panel reaches the page
source once; every original URL answers 200 or an intentional 301; `debug.log`
is clean; and no `__THEME_URI__` survives anywhere. Then the editor is opened
and looked at. The full list is
[references/verification.md](references/verification.md); how to read the
harness's numbers is [docs/verification.md](docs/verification.md).

## Reference implementation

[`iOSDevSK/amanda-rose-guttenberg`](https://github.com/iOSDevSK/amanda-rose-guttenberg)
(private) is the complete worked example, at version 2.4.3 as this is written:
a fine-art wedding photography site converted with this method, with `steps/`
as the conversion record, `tools/` as the origin of `scripts/`, and `tests/` as
the regression files every generated theme is asked to ship. Measured against a
real WordPress 7.1 installed from its release ZIP: 1,303 blocks, 0 invalid;
every page within 0.40 % of the original at 1440 px and 0.89 % at 390 px.
[docs/reference-conversion.md](docs/reference-conversion.md) says what it proves
and what it got wrong first.

## Repository layout

```
SKILL.md                 the procedure the agent follows
references/              what the agent reads on demand
  conversion-rules.md    HTML → block mapping, instantiated per project
  forms-and-seo.md       the form block family and the SEO record
  pitfalls.md            what the reference paid for, numbered
  verification.md        the two tiers and the acceptance criteria
scripts/                 the file gates and the tier-2 harness
  wp-sandbox/            a WordPress on SQLite beside the theme
docs/                    documentation for people
CHANGELOG.md             what changed, by commit
CONTRIBUTING.md          how to change the skill without breaking it
LICENSE                  GPL-2.0-or-later
```

## Documentation

Two audiences, kept apart on purpose. `SKILL.md` and `references/` are read by
the agent and written as procedure; `docs/` is read by people and explains.
Nothing in `SKILL.md` links into `docs/`, so the agent never mistakes an
explanation for an instruction.

- [docs/installation.md](docs/installation.md) — install, dependencies, validating and updating the skill
- [docs/workflow.md](docs/workflow.md) — what happens at each step, what it produces, what you are asked for
- [docs/scripts.md](docs/scripts.md) — every script, flag, variable and exit code
- [docs/verification.md](docs/verification.md) — how to read the harness's output, and what passes
- [docs/troubleshooting.md](docs/troubleshooting.md) — symptom → pitfall
- [docs/reference-conversion.md](docs/reference-conversion.md) — the worked example
- [CHANGELOG.md](CHANGELOG.md)

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md): validate with `skills-ref`, keep `SKILL.md`
procedural and short, put the reasoning in `references/`, number the pitfalls,
and never ship a script that exits 0 on nothing.

## License

Copyright (C) 2026 Filip Dvoran.

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version — **GPL-2.0-or-later**, the licence WordPress itself uses. The PHP this
skill carries — the importer's shape, the cleanup, the form blocks — lands
inside the themes it generates, and a GPL-compatible licence is what keeps
those themes distributable, on WordPress.org or anywhere else. It is
distributed without any warranty; see the full text in [LICENSE](LICENSE).
