# Scripts

Every script in `scripts/`, with its usage line, what it is for, an example, and its own header — the comment block at the top of the file, reproduced here so this page cannot drift from the code. The exit status convention is the same everywhere: **0** pass, **1** findings, **2** usage error or nothing to check. A wrong path or an empty directory is never a green run; the two PHP tools exit 2 without their variables.

Python dependencies: `pip install -r scripts/requirements.txt && python3 -m playwright install chromium`. The sandbox needs PHP with `sqlite3` and `gd`, plus curl, unzip and rsync. See [installation.md](installation.md).

| Script | Serves |
|---|---|
| [`lint-delimiters.py`](#lint-delimiterspy) | Tier 1 |
| [`lint-html.py`](#lint-htmlpy) | Tier 1 |
| [`raise-specificity.py`](#raise-specificitypy) | Step 4 |
| [`apply-style-classes.py`](#apply-style-classespy) | Step 7 |
| [`render-original.py`](#render-originalpy) | Tier 2 baseline |
| [`visual-diff.py`](#visual-diffpy) | Criterion 1 |
| [`measure-diff.py`](#measure-diffpy) | Criterion 1, debugging |
| [`editor-validity.py`](#editor-validitypy) | Criterion 2 |
| [`wp-sandbox/setup.sh`](#setupsh) | Tier 2 |
| [`wp-sandbox/sync.sh`](#syncsh) | Tier 2 |
| [`wp-sandbox/install.php`](#installphp) | Tier 2, called by setup.sh |
| [`wp-sandbox/import.php`](#importphp) | Tier 2, called by setup.sh |

## lint-delimiters.py

```
lint-delimiters.py [<theme-dir>] [--fix]
```

**Serves:** Tier 1.

Checks every block delimiter in `content/`, `parts/`, `templates/` and `patterns/` against the grammar WordPress parses with, then checks that openers and closers pair up. `--fix` rewrites delimiter whitespace in place. Run it on `content/` too: the wp-block-theme-converter doctor never looks there.

```bash
python3 scripts/lint-delimiters.py ~/themes/my-blocks
```

<details><summary>The script's own header</summary>

```text
Check every block delimiter against WordPress's own grammar, then check
that the delimiters pair up.

WP_Block_Parser matches a delimiter with, in essence:

    <!--\\s+(/)?wp:(namespace/)?name(\\s+{attrs}\\s+)?(/)?-->

The whitespace is not decoration. `<!-- wp:paragraph {"className":"lead"}-->`
— no space before the arrow — is not a block delimiter at all. WordPress reads
the paragraph as freeform HTML, the matching `<!-- /wp:paragraph -->` then
closes the wrong thing, and every block after it nests one level too deep. On
the guide page that swallowed the whole document into a sticky form panel and
made it 4,794px too tall.

Nothing else catches this: the comments still balance, the HTML in the file
still balances, and the fault only appears once WordPress parses it.

The second pass walks the delimiters WordPress *would* accept with a stack,
the way WP_Block_Parser does: a closer pops whatever is open, by position and
not by name, and anything still open at the end of the file is closed there
with everything after it nested inside. A closer with nothing to close, a
closer for the wrong block, and an opener that is never closed are all
reported with their line numbers. Counting block names cannot see any of
these — a swallowed closer keeps every name and every count and only changes
the depth (pitfall #16).

    python3 lint-delimiters.py <theme-dir>          # report
    python3 lint-delimiters.py <theme-dir> --fix    # insert the missing whitespace

Exit status: 0 clean, 1 problems found, 2 nothing to check (bad path, no files).
```

</details>

## lint-html.py

```
lint-html.py [<theme-dir>]
```

**Serves:** Tier 1.

Checks that the HTML between the delimiters is balanced — an unclosed wrapper swallows every following section, and WordPress will not say so because it serialises from the comments.

```bash
python3 scripts/lint-html.py ~/themes/my-blocks
```

<details><summary>The script's own header</summary>

```text
Check that the HTML inside the block markup is balanced.

Block comments and HTML tags are two separate things that both have to line up.
A file can have every <!-- wp:x --> matched by its <!-- /wp:x --> and still be
broken, because the markup a block *saves* between those comments is ordinary
HTML: leave a <div> unclosed and the browser adopts every following section into
it. WordPress will not complain — it serialises from the comments — so the page
only looks wrong once it is rendered.

That is exactly the fault this caught on the guide page, where one unclosed
wrapper swallowed the rest of the document and made it 4,794px too tall.

    python3 lint-html.py <theme-dir>       # exits non-zero if anything is off

Exit status: 0 clean, 1 problems found, 2 nothing to check (bad path, no files).
```

</details>

## raise-specificity.py

```
raise-specificity.py <stylesheet.css> [--write]
```

**Serves:** Step 4.

Prefixes every selector with `:root ` so the design consistently outranks core layout rules (pitfall #3). Idempotent: a stylesheet already raised comes back unchanged. Without `--write` it reports and writes nothing.

```bash
python3 scripts/raise-specificity.py ~/themes/my-blocks/assets/css/site.css --write
```

<details><summary>The script's own header</summary>

```text
Prefix every selector in a stylesheet with :root (pitfall #3).

WordPress emits its layout rules as

    :root :where(.is-layout-flow) > *            { margin-block: 0 }
    :root :where(.is-layout-flow) > :first-child { margin-block-start: 0 }

The :where() contributes nothing, but :root and :first-child each count as a
class, so those rules carry the weight of one and two classes respectively.
Most of a design is written as one or two classes too, so the cascade comes
down to source order — and core's global stylesheet is printed before the
theme's on some requests and after it on others, depending on what else is
enqueued. Margins disappear unpredictably.

Prefixing every selector with :root adds exactly one class-worth of weight to
all of them at once. The design's internal cascade is untouched, because every
rule moves by the same amount; what changes is that it now sits a step above
core's layout resets instead of level with them.

Skipped: :root and html selectors, which the prefix would break; the interior
of @keyframes, whose "from"/"to" are not selectors; and rules already prefixed,
so the script can be run twice without doubling up. A comment that sits on its
own before a selector is flushed first, or the prefix would land on it.

    python3 raise-specificity.py <theme>/assets/css/site.css            # report
    python3 raise-specificity.py <theme>/assets/css/site.css --write    # apply

Exit status: 0 done, 2 usage.
```

</details>

## apply-style-classes.py

```
apply-style-classes.py --sources <dir> --pages <dir> --map <json> [--ignore cls,cls] [--write]
apply-style-classes.py --example
```

**Serves:** Step 7.

Carries the inline styles of the html2wp sources across to the converted pages as utility classes, matching elements by class set and ordinal rather than first match (pitfall #6). `--map` is the project's own declaration → class table; `--example` prints one to start from; `--ignore` names classes to leave out of the matching key. Without `--write` it reports and writes nothing.

```bash
python3 scripts/apply-style-classes.py --sources ~/themes/my-html2wp/clara-content/sources --pages ~/themes/my-blocks/content/pages --map style-map.json
```

<details><summary>The script's own header</summary>

```text
Carry the source's inline styles across as utility classes (pitfall #6).

The static build wrote one-off declarations straight onto elements. Block
markup cannot hold a style attribute, so each declaration gets a class in the
theme's stylesheet instead, and this puts that class on the element that used
to carry the style.

Matching is by class set and ordinal: the third element in the original whose
classes are exactly {h-lg} is the third block in the converted page whose own
classes are exactly {h-lg}. Matching on "contains h-lg" instead drifts the
moment an unstyled sibling shares the class — 19 misplacements on the
reference.

The pass reconciles rather than appends — it removes utility classes that do
not belong as well as adding the ones that do, so it can be run repeatedly and
always leaves the same result. Styled elements that carry no class at all are
invisible to it and must be listed by hand.

    python3 apply-style-classes.py --sources <old>/clara-content/sources \\
        --pages <theme>/content/pages --map style-classes.json            # report
    python3 apply-style-classes.py ... --write                            # apply
    python3 apply-style-classes.py --example > style-classes.json         # starter map

The map is the project's own inline-style census — every distinct `style=`
declaration in the sources, verbatim, and the class (or classes) that replace
it. An empty string means "handled elsewhere": listed so nothing reads as
unmapped, applied nowhere.

Exit status: 0 done (unmapped declarations are reported, not fatal), 2 usage.
```

</details>

## render-original.py

```
render-original.py --config <file.json> [page ...]
render-original.py --example
```

**Serves:** Tier 2 baseline.

Composes the html2wp source fragments into standalone pages the way the old runtime did — head, stylesheet, script, header and footer parts, the card template for the listing — so there is an original to diff against. `--example` prints a config to fill in.

```bash
python3 scripts/render-original.py --config render-original.json
```

<details><summary>The script's own header</summary>

```text
Render the ORIGINAL html2wp site to standalone HTML, for comparison.

The source pages in the input theme's bundle are fragments: no head, no
header, no footer, and a handful of tokens the old runtime resolved at request
time. This composes them the way that runtime did, so the result can be
screenshotted next to the converted pages (visual-diff.py) and measured
against them (measure-diff.py).

Everything project-specific lives in a JSON config, not in this file:

    python3 render-original.py --example > render-original.json   # starter config
    python3 render-original.py --config render-original.json      # every page
    python3 render-original.py --config render-original.json about contact

Keys (paths are absolute or relative to the config file):

    old_theme        the html2wp theme directory (required)
    out              where the rendered pages go (required)
    sources          bundle pages, relative to old_theme     [clara-content/sources]
    stylesheet       relative to old_theme                   [assets/css/site.css]
    script           relative to old_theme                   [assets/js/site.js]
    header_part      relative to old_theme                   [parts/header.html]
    footer_part      relative to old_theme                   [parts/footer.html]
    header_open      wrapper the old runtime put round the header part
    header_open_hero same, on pages listed in hero_pages (transparent nav)
    hero_pages       page keys that get header_open_hero
    footer_open, footer_close, footer_strip
                     wrapper round the footer part, and strings removed from
                     the part first so it is not wrapped twice
    skip             page keys not to render (became templates, 404, …)
    posts_json       the CONVERTED theme's content/posts.json, so [wp-posts]
                     tokens expand to the same entries the live loop shows
    card_template    markup for one such entry; placeholders {image}
                     {category} {datetime} {date} {title} {excerpt} {url}
    date_format      strftime format for {date}               [%-d %b %Y]
    category_labels  slug → label for {category}
    url_map          [regex, replacement] pairs applied to every page, with
                     {assets} and {old} expanded to the old theme relative to out
    strip_patterns   regexes removed from every page (the skip link that moved
                     into the header part, for instance)
    extra_head       raw HTML inlined into <head> — @font-face rules, usually,
                     since the page's own <link> tags are dropped
    extra_head_file  a file whose contents are inlined the same way
    lang             html lang attribute                       [en]

Exit status: 0 rendered, 2 usage or config error.
```

</details>

## visual-diff.py

```
visual-diff.py --original <dir> (--live <url> | --preview <dir>) [--out <dir>] [--width N] [--threshold PCT] [--path key=/route/ ...] [page ...]
```

**Serves:** Criterion 1.

Screenshots every rendered original and the same page on the live sandbox (or a static preview), diffs them, writes the diff images to `--out`, prints the differing-pixel percentage per page and fails any page above `--threshold`. `--path` maps a page key to a route that differs on the live site; run it at `--width 1440` and `--width 390`.

```bash
python3 scripts/visual-diff.py --original preview-original --live http://127.0.0.1:8899 --out preview-diff --width 1440
```

<details><summary>The script's own header</summary>

```text
Screenshot the original and converted pages side by side and diff them.

This is the check that matches what the conversion actually promised: not that
the markup matches, but that the rendered page does. Both sides are loaded with
reduced motion on, so every scroll reveal resolves immediately and no animation
frame can land differently between two runs (pitfall #11).

    python3 visual-diff.py --original <dir> --live http://127.0.0.1:8899
    python3 visual-diff.py --original <dir> --live http://127.0.0.1:8899 --width 390
    python3 visual-diff.py --original <dir> --live http://127.0.0.1:8899 about contact

--original is the directory render-original.py wrote: one <key>.html per page.
--live is a running WordPress with the converted theme active — the version
that matters, the only one where core's own block styles, the global
stylesheet theme.json generates and the real query loops are in play. A
static preview (--preview <dir> of <key>.html files) can agree with the
original for reasons production would not repeat; the reference's did, at
0.56% against a real 26%.

Each page maps to <live>/<key>/; --path key=/route/ overrides that, and
front-page=/ is the default override.

Writes <out>/<key>-{original,converted,diff}.png and prints a per-page
difference percentage. Exit 1 when any page is at or above --threshold
(default 1.0%) or has no original to compare against.
```

</details>

## measure-diff.py

```
measure-diff.py --original <dir> (--live <url> | --preview <dir>) --css <site.css> [--width N] [--limit N] [--marker TEXT] [--path key=/route/ ...] [page ...]
```

**Serves:** Criterion 1, debugging.

When the diff says a page is wrong, this says where: for every design class in `--css` it compares the element's box on the original and the converted page and lists the ones that moved, largest first (`--limit`).

```bash
python3 scripts/measure-diff.py --original preview-original --live http://127.0.0.1:8899 --css ~/themes/my-blocks/assets/css/site.css guide
```

<details><summary>The script's own header</summary>

```text
Compare the geometry of the original and converted pages, element by element.

A screenshot diff says a page is wrong. This says where. For every design class
that appears in both documents it reads the browser's own layout box and
reports the ones that moved, which is usually enough to name the rule that
needs fixing. The pixel diff is the alarm; this is the debugging tool.

    python3 measure-diff.py --original <dir> --live http://127.0.0.1:8899 \\
        --css <theme>/assets/css/site.css privacy
    python3 measure-diff.py --original <dir> --live ... --css ...    # every page, worst offenders

--css is the design's stylesheet: every class it defines is measured. Classes
after the --marker line (default "BLOCK BRIDGE") are skipped — they exist only
on the converted side. --path key=/route/ maps a page to its live address,
front-page=/ by default.

Exit status: 0 measured, 2 usage.
```

</details>

## editor-validity.py

```
editor-validity.py --site <url> --user <u> --password <p> [--types page,post] [--ids 1,2] [--timeout SECONDS]
```

**Serves:** Criterion 2.

Logs in, opens every page and post in the block editor and reads the invalid blocks out of `wp.data.select('core/block-editor')` — the acceptance test the whole conversion is arranged around. Prints one row per post and a summary line; fails on any invalid block or any editor that did not load.

```bash
python3 scripts/editor-validity.py --site http://127.0.0.1:8899 --user admin --password admin-password
```

<details><summary>The script's own header</summary>

```text
Open every page and post in the block editor and count invalid blocks.

This is the acceptance test the whole conversion is arranged around, and only
Gutenberg can answer it: validity is decided by re-running each block's save()
and comparing byte for byte, which no PHP can do. So a real browser logs in,
opens each post in the editor, waits on the editor's data store — not on the
canvas, which is an iframe — and walks every block recursively for
`isValid === false` (verification.md, criterion 2).

    python3 editor-validity.py --site http://127.0.0.1:8899 --user admin --password admin-password
    python3 editor-validity.py --site ... --types page            # pages only
    python3 editor-validity.py --site ... --ids 12,40             # named posts

Run it over every page AND every post, not a sample: invalid blocks cluster by
block type, so one page of the wrong kind hides fifty faults. Run it twice on
the pages holding a form — once with Visual Edit Lite absent and once with it
active (criterion 7).

Serve the sandbox with PHP_CLI_SERVER_WORKERS=8 or the editor's parallel
requests queue into timeouts; an initial load that still times out is retried
once (pitfall #17).

Exit status: 0 all valid, 1 invalid blocks or a post that would not load,
2 usage or login failure.
```

</details>

## setup.sh

```
bash setup.sh <theme-dir> [sandbox-dir]
```

**Serves:** Tier 2.

Builds a throwaway WordPress on SQLite beside the theme — never inside it (pitfall #11) — installs it, copies the theme in, activates it and runs the theme's synchronous import if `IMPORT_FUNCTION` names it. Environment variables: `PORT` (default 8899), `SITE_TITLE`, `ADMIN_PASSWORD` (the user is always `admin`), `IMPORT_FUNCTION` (`<slug>_run_import`), `IMPORT_USER` (default 1, because a request with no user cannot `unfiltered_html` and kses strips every form control — pitfall #5d).

```bash
IMPORT_FUNCTION=my_blocks_run_import bash scripts/wp-sandbox/setup.sh ~/themes/my-blocks ~/themes/my-blocks-sandbox
```

<details><summary>The script's own header</summary>

```text
Build a throwaway WordPress with a theme installed, on SQLite, no server
software required beyond PHP. Everything lands in the sandbox directory,
which is created BESIDE the theme, never inside it — a WordPress inside the
theme directory makes every theme linter walk core (pitfall #11).

  bash setup.sh <theme-dir> [sandbox-dir]

  PORT=8899                        the address baked into wp-config
  SITE_TITLE="Sandbox"             what wp_install() names the site
  ADMIN_PASSWORD=admin-password    user is always "admin"
  IMPORT_FUNCTION=<slug>_run_import
                                   the theme's synchronous whole-import
                                   function (SKILL.md step 8); left unset,
                                   the import is skipped and said so.
                                   It runs as user 1 (IMPORT_USER to change):
                                   without a user, kses strips every form
                                   control out of post_content (pitfall #5d)

Afterwards:
  PHP_CLI_SERVER_WORKERS=8 php -S 127.0.0.1:$PORT -t <sandbox>/wordpress
  bash sync.sh <theme-dir> <sandbox-dir>      # push theme changes in again
  python3 ../editor-validity.py --site http://127.0.0.1:$PORT --user admin --password $ADMIN_PASSWORD
  python3 ../visual-diff.py --original <rendered originals> --live http://127.0.0.1:$PORT
```

</details>

## sync.sh

```
bash sync.sh <theme-dir> <sandbox-dir>
```

**Serves:** Tier 2.

Copies the theme into the sandbox again after a change. A copy, not a symlink: WordPress resolves theme paths in ways a symlinked theme breaks. **The sandbox theme is named after the source directory's basename**, so the theme directory must be named exactly the theme slug — a clone named anything else lands under a second theme name and every later test runs against the stale copy.

```bash
bash scripts/wp-sandbox/sync.sh ~/themes/my-blocks ~/themes/my-blocks-sandbox
```

<details><summary>The script's own header</summary>

```text
Copy the theme into the sandbox. A copy rather than a symlink: WordPress
resolves theme paths in ways that make a symlinked theme unreliable.

  bash sync.sh <theme-dir> <sandbox-dir>
```

</details>

## install.php

```
WP_ROOT=<sandbox>/wordpress THEME_SLUG=<slug> [SITE_TITLE=…] [ADMIN_PASSWORD=…] php install.php
```

**Serves:** Tier 2, called by setup.sh.

Runs `wp_install()` and switches to the theme, from the command line, without a web server. Exits 2 without its variables.

```bash
WP_ROOT=~/themes/my-blocks-sandbox/wordpress THEME_SLUG=my-blocks php scripts/wp-sandbox/install.php
```

<details><summary>The script's own header</summary>

```text
Developer tool, not part of any theme. Run from the command line by setup.sh:
  WP_ROOT=<sandbox>/wordpress THEME_SLUG=<slug> [SITE_TITLE=…] [ADMIN_PASSWORD=…] php install.php
```

</details>

## import.php

```
WP_ROOT=<sandbox>/wordpress IMPORT_FUNCTION=<slug>_run_import [IMPORT_USER=1] php import.php
```

**Serves:** Tier 2, called by setup.sh.

Runs the theme's synchronous whole-import function — the CLI path of SKILL.md step 8 — as the administrator, and prints what the site holds afterwards. Refuses to run as a user who cannot `unfiltered_html`. The sliced admin-ajax path is exercised over HTTP, not here.

```bash
WP_ROOT=~/themes/my-blocks-sandbox/wordpress IMPORT_FUNCTION=my_blocks_run_import php scripts/wp-sandbox/import.php
```

<details><summary>The script's own header</summary>

```text
Developer tool, not part of any theme. Runs the theme's synchronous
whole-import function (SKILL.md step 8) — the CLI path — and prints what
the site holds afterwards. The sliced admin-ajax path is exercised over
HTTP, not here (verification.md, criterion 5b).
  WP_ROOT=<sandbox>/wordpress IMPORT_FUNCTION=<slug>_run_import php import.php
```

</details>
