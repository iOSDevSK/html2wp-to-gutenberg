# Scripts

Every script in `scripts/`, with its usage line, what it is for, an example, and its own header — the comment block at the top of the file, reproduced here so this page cannot drift from the code. The exit status convention is the same everywhere: **0** pass, **1** findings, **2** usage error or nothing to check. A wrong path or an empty directory is never a green run; the two PHP tools exit 2 without their variables.

Python dependencies: `pip install -r scripts/requirements.txt && python3 -m playwright install chromium`. The sandbox needs PHP with `sqlite3` and `gd`, plus curl, unzip and rsync. See [installation.md](installation.md).

| Script | Serves |
|---|---|
| [`lint-delimiters.py`](#lint-delimiterspy) | Tier 1 |
| [`lint-html.py`](#lint-htmlpy) | Tier 1 |
| [`raise-specificity.py`](#raise-specificitypy) | Step 4 |
| [`apply-style-classes.py`](#apply-style-classespy) | Step 7 |
| [`extract-tokens.py`](#extract-tokenspy) | Step 2 |
| [`scaffold-theme.py`](#scaffold-themepy) | Steps 2, 4, 6 and 7 |
| [`convert-source.py`](#convert-sourcepy) | Step 7 |
| [`block-metrics.py`](#block-metricspy) | The quality report |
| [`block-roundtrip.cjs`](#block-roundtripcjs) | Criterion 2, before WordPress |
| [`block-node-setup.sh`](#block-node-setupsh) | Criterion 2, the node packages |
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

## extract-tokens.py

```
extract-tokens.py <old-theme> --css <file> [--css …] --out tokens.json [--sources dir …] [--theme-json theme.json]
```

**Serves:** Step 2 — the presets.

Reads the design's stylesheet and the classes the pages use, and writes `tokens.json`: the theme.json presets (palette, font families, font sizes, spacing steps — only what a used class reads, named after the design's own variables), the class → block-attribute map `convert-source.py` applies, the properties every class sets (variants included, so a responsive twin keeps a class a class), the `contentSize` of the design's own container, and the variable each preset came from, so `scaffold-theme.py` can point the design's `:root` at the preset.

```bash
python3 scripts/extract-tokens.py ../mara-vidal --css assets/styles.css --out tokens.json
```

<details><summary>The script's own header</summary>

```text
The design's tokens, as theme.json presets and a class → block-attribute map.

An official block theme keeps its design in theme.json — a palette, font
families, a type scale, a spacing scale — and its blocks use those presets.
An html2wp theme's design is a stylesheet whose rules read custom properties
(`:root{--ember:…}` and `.text-ember{color:var(--ember)}`): the tokens are
already there, named by the designer. This reads them out of the stylesheet
and the classes the pages actually use; it invents nothing.

    python3 extract-tokens.py <old-theme> --css assets/site.css --out tokens.json
    python3 extract-tokens.py <old-theme> --css … --out tokens.json --theme-json theme.json

tokens.json:

  presets    palette, fontFamilies, fontSizes, spacingSizes — only what a used
             class reads, slugs from the design's own variable names
             (--ember → "ember", --text-2xl → "2-xl", calc(var(--spacing)*5)
             → "5"), values resolved to literals
  classes    for every used class whose rule is one token: the block
             attribute that says the same (textColor, backgroundColor,
             borderColor, fontFamily, fontSize (+ the line height it carried),
             lineHeight, padding/margin sides, blockGap, and the layout
             properties convert-source.py reads)
  properties the CSS properties every class sets, variants included
             (md:px-10 → padding-inline): a class converts only when no other
             class on the element touches the same property
  layout     contentSize: the most used centred max width less its widest
             padding (what core's constrained layout measures)
  aliases    for every variable a preset came from, the preset variable it
             now reads (--ember → var(--wp--preset--color--ember)):
             scaffold-theme.py points the design's own :root at theme.json,
             so a colour changed in Styles reaches the classes that stayed
             classes too, and the token is defined once

--theme-json merges the presets into a theme.json (settings.color.palette,
typography.fontFamilies/fontSizes, spacing.spacingSizes, with core's defaults
off) and prints it or writes it there.

Exit 0; 2 = usage.
```

</details>

## scaffold-theme.py

```
scaffold-theme.py --old <html2wp-theme> --tokens tokens.json --out <dir> --slug <slug> --name <name> --css <file> [--js <file>] [--fonts-url URL] [--media-url URL] [--presets on|off] [--layout on|off] [--author NAME] [--chrome key]
```

**Serves:** Steps 2, 4, 6 and 7.

Writes the sibling block theme: theme.json v3 from the tokens, the design's stylesheet unlayered and raised with its `:root` variables reading the presets, the block bridge, header and footer parts from the source's own chrome, thin templates, and every page as block markup in `content/` (via `convert-source.py`). `--presets off` is the old every-class-survives rule, kept so a conversion's before and after come from the same code.

```bash
python3 scripts/scaffold-theme.py --old ../mara-vidal --tokens tokens.json --out ../mara-vidal-blocks --slug mara-vidal-blocks --name "Mara Vidal Blocks" --css assets/styles.css --js assets/spa-runtime.js
```

<details><summary>The script's own header</summary>

```text
The sibling block theme, scaffolded the way an official one is laid out.

    python3 scaffold-theme.py --old <html2wp-theme> --tokens tokens.json \
        --out <new-theme> --slug mara-vidal-blocks --name "Mara Vidal Blocks" \
        --css assets/styles.css [--js assets/spa-runtime.js] [--fonts-url URL] \
        [--media-url __THEME_URI__/assets/images] [--presets on|off] [--layout on|off] \
        [--author NAME] [--version 2.0.0] [--chrome front-page]

What it writes (SKILL.md steps 2, 4, 6; convert-source.py does the pages):

  theme.json     v3, the design tokens as presets (extract-tokens.py): palette,
                 font families, font sizes, spacing scale — core's own
                 defaults off — contentSize/wideSize from the design's centred
                 width, and a root block gap of 0 with blockGap on, so every
                 gap is a block's own preset and nothing is implied
  templates/     Twenty Twenty-Five's set in the design's page shell (a group
                 with its own classes) around the header part, a <main> group
                 and the footer part: page and front-page hold the post
                 content; index, home, archive, search, single and 404 are
                 built from the presets and the design's content rail
  parts/         header and footer, converted from the source's own chrome:
                 menus as core/navigation placements, the site's name as
                 core/site-title (content/menus.json, placements.json,
                 site.json; inc/navigation.php; editor-navigation.css)
  content/       every page source as block markup (convert-source.py), and
                 pages.json: each page's key, address and title
  inc/import.php the importer: an admin notice with one button (and a
                 function wp eval can call) that creates the pages — images
                 resolved from the __THEME_URI__ token, the front page and
                 pretty permalinks set, every page flagged so a re-import
                 updates its own and never an owner's
  <out>.reports/ beside the theme, not in it: convert-source.py's per-page
                 report (every class kept, and why)
  assets/        the design's stylesheet UNLAYERED and raised by one :root
                 (pitfall #3: core's layout rules are unlayered, so a layered
                 utility loses to them whatever its specificity), its :root
                 variables pointed at the presets they became, its scripts,
                 its images, and bridge.css — only what core's own wrappers
                 need (the <figure> an image gains, a background's padding)
  functions.php  enqueues all of it, the editor included; style.css and
                 readme.txt with the headers Theme Check requires (carried from
                 the source; an author it lacks comes from --author or stays out)

Exit 0; 2 = usage.
```

</details>

## convert-source.py

```
convert-source.py <source.html> --tokens tokens.json --out <page.html> [--presets on|off] [--layout on|off] [--fragment] [--media-url URL] [--keep path …]
```

**Serves:** Step 7.

One html2wp page source as core block markup: groups, headings, paragraphs, images, lists; forms, buttons, svg and runtime-driven elements stay `core/html`. Classes that are one token become preset attributes, layout classes become core layout, and everything else stays in `className`; `<out>.report.json` lists every class kept and why. `--keep` reverts named elements to their classes — the pixel gate's escape hatch, one element at a time.

```bash
python3 scripts/convert-source.py ../mara-vidal/clara-content/sources/about.html --tokens tokens.json --out content/about.html
```

<details><summary>The script's own header</summary>

```text
An html2wp page source as core block markup — the way official themes build.

    python3 convert-source.py <source.html> --tokens tokens.json --out page.html
    python3 convert-source.py <source.html> --tokens tokens.json --out page.html --presets off
    python3 convert-source.py <part.html> --tokens … --out … --fragment

Two modes, one mapper, so a conversion's "before" and "after" come from the
same code:

--presets off   the skill's original rule: every class survives on a block of
                the same kind (a <div class="X"> is a group with className X)
--presets on    (default) a class whose rule is one design token becomes the
                block attribute official themes use — textColor,
                backgroundColor, borderColor, fontSize (with the line height it
                carried), fontFamily, lineHeight, padding/margin/blockGap as
                var:preset|spacing|N — and a group's wrapper classes become
                core layout: flex (orientation, justification, alignment,
                wrap), grid (columnCount) and constrained (contentSize).
                A class converts only when no other class on the element
                touches the same property (a responsive md:text-4xl or a
                hover: keeps text-2xl a class: core layout and presets have
                no breakpoints), and only on a block that supports the
                attribute. Everything else stays in className — the residue
                the report counts.

Blocks: group (div, section, article, aside, header, footer, main, nav),
heading, paragraph (text, a standalone link, any inline-only element),
image, list/list-item. Anything a block cannot hold without losing
behaviour — a form, a button, an svg, an iframe, an element the old runtime
drives (data-spa-*), a link wrapping blocks — stays as core/html, verbatim.

In a part (scaffold-theme.py converts the header and footer this way), two
more: a row of links that is a menu becomes a core/navigation placement (a
registered pattern resolving the menu's wp_navigation post), and the home
link that names the site becomes core/site-title + core/site-tagline.

--media-url rewrites the bundle's image tokens (__CLARA_UPLOADS_URI__…/<file>
and __CLARA_THEME_URI__/assets/<file>) to <url>/<file>. --keep lists element
paths (1.2.0 …, from the report) whose classes stay classes: the pixel gate's
revert, one element at a time.

Writes the markup and <out>.report.json (every class kept, and why).
Exit 0; 2 = usage.
```

</details>

## block-metrics.py

```
block-metrics.py <theme-dir> [--json out.json] | block-metrics.py file.html …
```

**Serves:** The quality report.

Counts how official a theme's content is: blocks, how many are `core/html`, the share of blocks using a theme.json preset, the share with core layout (overall and among groups), custom classes per block, style variations, pattern references, and what theme.json declares. Run it before and after a change; the numbers are the claim.

```bash
python3 scripts/block-metrics.py ../mara-vidal-blocks --json metrics.json
```

<details><summary>The script's own header</summary>

```text
How "official" a block theme's content is — the numbers behind the claim.

An official WordPress block theme (Twenty Twenty-Five, the Create Block Theme
output) keeps its design in theme.json and has its blocks USE it: a heading
says fontSize "x-large" and textColor "contrast", a section says
layout constrained and padding var:preset|spacing|50. A converted theme that
carries every original class on nested groups renders the same page and
edits like raw HTML. This counts which of the two a theme is, per page and in
total, so a conversion's progress is a number rather than an opinion:

    python3 block-metrics.py <theme-dir>                 every block file the theme ships
    python3 block-metrics.py <theme-dir> --json out.json the same, as data
    python3 block-metrics.py page.html other.html        named block files

What it counts, per block (core/html counted apart: it is not a block
anybody edits as one):

  presets      the block uses a theme.json preset: textColor, backgroundColor,
               fontSize, fontFamily, gradient, borderColor, or any
               var:preset|… in its style
  layout       layout.type flex, grid or constrained (core layout, not a
               wrapper class)
  classes      custom class names in className (is-style-* variations apart)
  styleVars    is-style-* block style variations
and per theme: templates, parts, patterns (patterns/*.php), pattern
references (wp:pattern), the presets theme.json declares, and the chrome —
the block types the parts are made of, the menus the theme ships as
wp_navigation posts and where they are placed (content/menus.json,
content/placements.json), and whether the site's name is core/site-title.

Exit 0; 2 = usage.
```

</details>

## block-roundtrip.cjs

```
node block-roundtrip.cjs [--canonical] file.html …
```

**Serves:** Criterion 2, before WordPress.

Gutenberg's own `validateBlock` on every block and the byte round trip `serialize(parse(x)) === x`, in node, without a browser. `--canonical` rewrites a file whose blocks are ALL valid into the serializer's bytes — never a repair; it does not call `createBlock`. The editor check (`editor-validity.py`) still decides; this one finds the failure in a second instead of a sandbox.

```bash
NODE_PATH=.blocks-node/node_modules node scripts/block-roundtrip.cjs content/*.html parts/*.html templates/*.html
```

<details><summary>The script's own header</summary>

```text
Two gates Gutenberg itself decides, without a browser:

  valid       every block's stored markup is what its save() produces
              (wp.blocks.validateBlock — the check behind "This block
              contains unexpected or invalid content")
  round trip  serialize(parse(x)) === x, byte for byte: the file is exactly
              what the editor would write back, so opening and saving a
              page changes nothing

  node block-roundtrip.cjs file.html [more.html …]
  node block-roundtrip.cjs --canonical file.html      rewrite a file whose
       blocks are ALL valid into the serializer's own bytes (attribute
       order, whitespace between blocks). Never a repair: one invalid block
       and the file is left alone. Nothing here calls createBlock.

The packages are the ones one WordPress release ships — every @wordpress/*
package in the tree pinned to its wp-X.Y dist-tag, or a second copy of
@wordpress/blocks registers the blocks where validateBlock does not look:
  bash block-node-setup.sh <dir> wp-7.0
  NODE_PATH=<dir>/node_modules node block-roundtrip.cjs …

Exit 0 all valid and byte-stable; 1 an invalid block or a round-trip
difference; 2 usage.
```

</details>

## block-node-setup.sh

```
block-node-setup.sh <dir> [wp-X.Y]
```

**Serves:** Criterion 2, the node packages.

Installs the packages `block-roundtrip.cjs` loads, every `@wordpress/*` one pinned to the same WordPress release through npm overrides.

```bash
bash scripts/block-node-setup.sh .blocks-node wp-7.0
```

<details><summary>The script's own header</summary>

```text
The node packages block-roundtrip.cjs needs, as ONE WordPress release ships
them:

  bash block-node-setup.sh <dir> [wp-7.0]
  NODE_PATH=<dir>/node_modules node block-roundtrip.cjs …

Installing @wordpress/blocks and @wordpress/block-library at their wp-X.Y
dist-tags is not enough: block-library depends on ~57 other @wordpress/*
packages by range, npm resolves those to today's latest, and a second copy of
@wordpress/blocks ends up registering the core blocks where validateBlock
does not look (every block "invalid", or a crash on the first parse). So
every @wordpress/* package in the tree is pinned to the same dist-tag
through npm overrides, and the install is done twice: once to learn the
tree, once pinned.

Exit 0 installed; 1 npm failed; 2 usage.
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
visual-diff.py --original <dir|url> (--live <url> | --preview <dir>) [--out <dir>] [--width N] [--threshold PCT] [--path key=/route/ ...] [page ...]
```

**Serves:** Criterion 1.

Screenshots every rendered original and the same page on the live sandbox (or a static preview), diffs them, writes the diff images to `--out`, prints the differing-pixel percentage per page and fails any page above `--threshold`. `--original` may also be the original site itself, live (the html2wp theme in a WordPress of its own), with the page keys named. `--path` maps a page key to a route that differs on the live site; run it at `--width 1440` and `--width 390`.

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

--original is the directory render-original.py wrote: one <key>.html per page
— or the ORIGINAL SITE ITSELF, live (http://…: the html2wp theme installed in a
WordPress of its own), with the page keys named on the command line; each
maps to the same route on both sides.
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
