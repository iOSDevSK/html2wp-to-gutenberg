---
name: html2wp-to-gutenberg
description: >
  Convert an html2wp-generated WordPress theme (raw HTML inside wp:html
  blocks, clara-content/ bundle, Visual Edit contract, [wp-posts]/[wp-form]
  tokens) into a fully NATIVE Gutenberg block theme, visually 1:1 including
  every animation, with all page and post content as core block markup in
  post_content — editable in the standard block editor with no plugin.
  This is the method proven on the Amanda Rose conversion
  (github.com/iOSDevSK/amanda-rose-guttenberg): final result 15 pages within
  0.4% pixel diff of the original against a REAL WordPress, 1,303 blocks /
  0 invalid in the editor. Trigger when the user asks to "preklop tému do
  Gutenbergu", "convert my html2wp theme to native blocks", "make the theme
  editable without Visual Edit", "gutenberg verzia témy", "1:1 like amanda
  rose", or names this skill. Do NOT use for plain static HTML folders
  (that's wp-block-theme-converter or html2wp-sub) — this skill's input is
  specifically a theme the html2wp converter already produced.
license: GPL-2.0-or-later
compatibility: >
  WordPress 6.6+ (theme.json v3) and PHP 7.4+ for the theme it produces. On the converting machine: PHP CLI with sqlite3 and gd, Python 3 with playwright, numpy and Pillow (scripts/requirements.txt) plus Chromium, node for the wp-block-theme-converter doctor, rsync, curl, unzip. Visual Edit Lite 1.27+ for the two-sided form and SEO gates.
---

# html2wp theme → native Gutenberg block theme, 1:1

The input theme is a block theme in name only: `theme.json`, `templates/`,
`parts/` exist, but the content is raw HTML wrapped in `wp:html` blocks, pages
live in `clara-content/sources/*.html`, dynamics run through `[wp-posts]`/
`[wp-form]`/`[wp-article]` tokens, and editing requires the Visual Edit
plugin. The output is a **new sibling theme** where every page is core block
markup in `post_content`, the design and animations are untouched, and the
old runtime (~3,600 lines) is replaced by core WordPress.

**Read `references/pitfalls.md` before writing any code.** Every entry there
cost real debugging time on the reference conversion; several are invisible
to linters and only appear inside a running WordPress. **Forms and search
metadata have their own file** — `references/forms-and-seo.md` — because the
reference got both wrong in the same way: the markup rendered, and the client
could not edit it.

## What "1:1" means (set expectations first)

- **Visually 1:1** — yes, the acceptance criterion, verified by screenshot
  diff against a real WordPress (target: every page ≤ ~1% differing pixels,
  the residue being text anti-aliasing).
- **Byte-identical HTML** — no; core blocks add `wp-block-*` classes and
  wrapper elements. The *block bridge* CSS layer absorbs this.
- **Same editing experience** — no, and that is the point: the client edits
  in Gutenberg instead of Visual Edit.

## The one rule of content conversion

**Every original class survives, in the same nesting order, on the same kind
of element.** Blocks are the vehicle; the classes are the design. The
original `site.css` is carried over almost verbatim and remains the source of
truth for appearance. Full mapping rules: `references/conversion-rules.md`.

## Inputs required

- **The html2wp theme directory** — `clara-content/` with `sources/`,
  `posts.json`, `terms.json`, `redirects.json`; `parts/`, `templates/`,
  `theme.json`, `inc/`, `assets/`. No `clara-content/` means this is not an
  html2wp theme and the wrong skill (see the description).
- **The new theme's slug and text domain**, and where the sibling directory
  goes. The slug is the directory name; the sandbox, the importer's flag and
  the shortcode namespace all derive from it.
- **What the original looked like.** The html2wp theme's own `site.css`,
  `site.js` and sources are what `scripts/render-original.py` composes into
  the comparison baseline; a live URL of the old site, if one exists, settles
  arguments the render cannot.
- **Which plugins the source site used.** Contact Form 7 changes the form
  path (pitfall #10). Visual Edit Lite 1.27+ has to be at hand for the
  two-sided form and SEO gates (verification.md, criteria 7–8), and its
  `includes/class-form-blocks.php` is what the theme carries a copy of.
- **Tooling** — do not take this on trust, ask the machine:

  ```bash
  bash scripts/doctor.sh          # reads only; exit 0 means it can start
  bash scripts/install.sh         # shows what it would install
  bash scripts/install.sh --yes   # installs it
  ```

  Run the doctor BEFORE step 1, not when something fails. Without Playwright
  there is no tier 2, and without tier 2 there is no acceptance (step 9) — a
  run that finds this out at step 9 has done eight steps of work it cannot
  close. The doctor checks PHP with sqlite3 and gd, WP-CLI, the three Python
  packages in `scripts/requirements.txt`, the Chromium that Playwright
  downloads separately from itself, node, rsync, curl, unzip, and Visual Edit
  Lite. `install.sh` is a dry run until `--yes`, installs nothing already
  present, and is harmless to run twice.
- **A dump of any database the gates will reuse.** The cleanup gate deletes
  content; a sandbox somebody is using for other work is not a fixture.

## Workflow

### 1. Audit (fan out Explore agents; do not skip)

Two parallel inventories: (a) `clara-content/` — every source page's section
list, all `data-*` attributes with counts, forms with fields, `[wp-*]` token
usage, posts.json tag census, menus/terms/redirects/settings; (b) the theme —
CSS custom properties, every JS behaviour with its selectors, every `inc/`
file's role, and **dead code** (the reference had a whole client-side search
whose anchor element existed nowhere, plus an unused scroll-video runtime).
Record what you will deliberately NOT port, with reasons — it is the
difference between "dead code removed" and "feature lost".

### 2. Scaffold + theme.json

New directory, new slug, version 2.0.0. `theme.json` v3 mirrors the design's
`:root` tokens as palette/fonts/spacing presets — **with
`defaultSpacingSizes:false` and `defaultFontSizes:false`** (pitfall #2),
`defaultPalette:false`, `appearanceTools:true`, `customTemplates` for the
page variants (visible in the editor — the old per-slug `page-*.html` files
were invisible). Disable core's image lightbox if the design ships its own.

### 3. Fonts: self-host

Fetch the exact Google Fonts css2 URL the theme used (browser UA to get
woff2), download latin + latin-ext subsets, declare all cuts in `fontFace`
with their `unicodeRange`, preload the two above-the-fold cuts via
`wp_preload_resources`. Same files as the CDN served → identical rendering.

### 4. CSS: verbatim + alias layer + block bridge

- Copy `site.css`. Point its `:root` variables at the theme.json presets
  (`--bg: var(--wp--preset--color--bg)`) so tokens are defined once.
- Append a **block bridge** section: rules that make core wrappers behave
  like the bare markup (figure around images taking the frame's box, linked
  images `a{display:block;height:100%}`, button styles matching `.btn`
  variants as registered block styles, query-loop `<li>` passing the grid
  track to the card, stretched-link whole-card click). No new visual
  decisions live there.
- Inline styles from the source become **utility classes marked
  `!important`** — the only `!important` in the file, justified: they replace
  style attributes, which outranked everything by definition (pitfall #6).
- Run `scripts/raise-specificity.py <site.css> --write` (`:root ` prefix on
  every selector, idempotent) so the design consistently beats core's
  `:root :where(.is-layout-flow)` layout resets (pitfall #3).
- `editor.css` = load `site.css` itself into the editor plus a short
  corrections file (unfix the nav, unhide overlays, cap viewport-height
  sections). Reveal animations gated on `html.js` are inert in the canvas —
  correct behaviour, content shows while editing.

### 5. JS: keep it classic, rekey what render-time filters used to fix

Keep the site JS as one deferred classic script (the nav/menu/lightbox state
machine is coordinated; Interactivity API rewrite risks parity). Mandatory
changes — each silently breaks otherwise:

- `getElementById('nav')` → `querySelector('.nav')` — template parts emit
  tagName+className, never an id, and the old theme injected ids at render
  time through runtime filters that no longer exist.
- Lightbox: `[data-lb]` → real image links (`core/image` with
  `linkDestination:"media"`); JS intercepts clicks on `.gal a[href]` etc.
  Bonus: keyboard access and no-JS fallback for free — and in the reference,
  the data-lb paths were relative and 404'd on every permalink, so this was
  a bug fix.
- Marquee/wordstrip loops: author the content ONCE, clone the track's
  children at runtime for the infinite loop — skip cloning under
  `prefers-reduced-motion` (the animation is off; a clone would visibly
  repeat).
- Keep the one-line `html.js` class setter as a head, non-deferred script —
  without it every `.reveal` element is `opacity:0` forever.
- `data-d="N"` stagger attributes → `dN` classes (core blocks drop unknown
  attributes).

### 6. Parts, templates, patterns

- Collapse duplicate parts (the reference's header/header-2 were
  byte-identical; footer-2 = footer + lightbox → one of each, lightbox
  always present, inert without triggers).
- Menus: `core/navigation` with `overlayMenu:"never"` everywhere; decorative
  numbering/indicators via CSS counters and pseudo-elements, never spans in
  RichText (they die on first edit). Mixed link+text columns are `core/list`,
  not navigation. `aria-current` for custom-URL links via a `render_block`
  path-comparison filter (port `amanda_rose_blocks_mark_current_link`).
- **The links do not live in the part.** A navigation block with inline links
  renders fine and is not a menu: it never appears in the Site Editor's
  Navigation screen, which instead shows the menu WordPress invents from the
  page list — attached to nothing. Model menus (the links) apart from
  placements (where one appears + the classes the design needs there), have
  the importer create one `wp_navigation` post per menu, and resolve `{"ref":N}`
  through a **pattern registered in code** — a static `.html` cannot carry an
  ID, and a pattern *file* would cache the pre-import branch for ever (#13).
  One menu, two placements, is how the header panel and the footer column stop
  drifting apart. And **delete `register_nav_menus()`**: it calls
  `add_theme_support('menus')`, which is the single line that puts Appearance →
  Menus back — a working editor for menus a block theme renders nowhere.
  Replace it with a link to `site-editor.php?p=%2Fnavigation`. Pitfall #12b.
- Dialog semantics (`role`/`aria-modal`) that group blocks cannot carry: add
  at render time with `WP_HTML_Tag_Processor`, keyed on the block's anchor.
- **Forms are blocks, not a shortcode**, and the theme registers the
  `clara-ve/*` family itself when Visual Edit Lite is not installed, so the
  labels, placeholders, choices and button text are editable either way; the
  theme also delivers the submission. `references/forms-and-seo.md` §2.
- **`inc/seo.php` reads `_clara_ve_seo`**, the record the editor's SEO panel
  writes, never a theme-prefixed key — and keeps
  `add_theme_support('html2wp-runtime', ['schema' => 1])`, which is what stops
  the plugin printing a second set of tags. Same file, §1.
- Templates are thin shells (`header part + post-content + footer part`).
  The blog listing becomes the real posts page; static topic pages become
  category archives **at their original URLs** via one rewrite rule +
  a `term_link` filter (both directions, or the archive exists at two URLs).
- Patterns only for genuine repetition (journal card, journal loop, CTA);
  content lives in `post_content`, not patterns — patterns don't save back
  to files and the client edits pages, not the Site Editor.
- **Theme-shipped images inside a part or template must be a PHP pattern.**
  A static `.html` cannot call `get_template_directory_uri()`, so a token
  swapped by a `render_block` filter is the obvious move — and it breaks in
  the block editor (renders in the browser, filter never runs) and in
  `wp_head` (JSON-LD shipping `__THEME_URI__/...` to search engines). A PHP
  pattern resolves at registration, so both get real markup. Bump the theme
  `Version:` after adding one or WordPress serves a cached pattern list.
  Pitfalls #12, #13.
- Dynamic one-offs (topic chips with live counts) = one small
  server-rendered block; per-post derived values (reading time) = a block
  binding, so the value sits in an ordinary editable paragraph.

### 7. Content conversion (the bulk — fan out agents)

Write a per-project `CONVERSION-GUIDE.md` from
`references/conversion-rules.md`, then fan out parallel agents by page
family (editorial / forms / galleries / utility / posts). Each agent reports
an ordered section list and `UNMAPPED STYLE:` lines for any inline style not
in the mapping table — collect those into utility classes in ONE pass
afterwards with `scripts/apply-style-classes.py`, fed the project's own
style→class map — a **reconciling matcher keyed on class-set + ordinal**
(first-match placement drifts; the reference caught 19 misplacements that
way). Forms become the `clara-ve/*` block family — a field per field, so the
client can rename a label or add a choice without touching markup; the rules
and the saved-markup contract are in `references/forms-and-seo.md`.

### 8. Importer + setup screen

One admin page, one idempotent import: media (**slug-namespace the
attachments**, pitfall #4), categories with the topic pages' intros as
descriptions, pages (claim-slug guard, template assignment, SEO meta into
`_clara_ve_seo` and only when it is empty), posts, redirect map, reading
settings (**`$wp_rewrite->set_permalink_structure()`, not `update_option`**,
pitfall #5), trash untouched sample content (pitfall #8). `bind_media()` rewrites image URLs to attachments
and injects the `id` attr + `wp-image-N` class — and nothing else
(pitfall #1c). Everything handed to `wp_insert_post()` goes through
`wp_slash()` first, or the `\u0026` a serialized attribute carries loses its
backslash and the block opens invalid (pitfall #1e).

**The import must not be one request, and it must be visible.** Resizing
sixty-five photographs takes minutes on real hosting; every host kills the
request first, and an importer that saves its record only at the end of a loop
throws away everything it just did — which is why the reference site arrived
with all fifteen pages and an empty media library. Non-negotiable, all five,
and pitfall **#5b** has the measurements:

- **A server-owned state machine** — `media → rebind → terms → pages → posts →
  settings` — driven one slice per `wp_ajax_` request. The client sends only
  "carry on"; the server reads its own record and decides what that means.
  Each call takes a time budget (~5s), does at least one item, and returns
  `{stage, label, done, total, percent, finished, errors}`.
- **The record is written after every item**, never after a stage. An
  interrupted slice must cost one photograph.
- **Identity from the database, not the record** — look up `photo-{base}` +
  the import flag before creating anything, so a lost record adopts what is
  there instead of making `-1` copies. Flag first, resize second.
- **Per-item failures are recorded and counted as done**, or one bad file
  wedges the bar at 64/65 for ever.
- **Zero is never success.** Show the reasons; render "finished with 0 of 65
  photographs" as an error, not a green tick.

Keep the synchronous whole-import function: it is the CLI path and the no-JS
fallback, and the slices wrap the same stage functions rather than forking
them. It must not depend on who calls it: kses strips every form control out
of `post_content` for a caller without `unfiltered_html`, and the command
line has no user — wrap the inserts in `kses_remove_filters()` or refuse to
run (pitfall #5d). **A `rebind` stage is part of the machine, not an extra** (pitfall #5c):
without it, fixing the importer fixes future conversions and does nothing for
the site that reported the bug.

The screen has to say three things, because the client is watching it for
minutes: that it has started, where it is (stage + climbing count + bar), and
that it has finished, with what it imported. A spinner ending in a blank page
is what this replaced.

The importer must **flag everything it creates** — one post meta key, on
pages, posts AND attachments — and **snapshot the site options it is about to
claim**, once, before claiming them:

```php
const THEME_IMPORT_FLAG = '_<slug>_imported';
update_post_meta( $id, THEME_IMPORT_FLAG, 1 );   // every page, post, attachment

// Written ONCE and never rewritten: a second import would otherwise capture
// the theme's OWN values as "before" and turn the restore into a no-op.
if ( ! isset( $state['site_options_before'] ) ) {
    $state['site_options_before'] = array(
        'show_on_front' => get_option( 'show_on_front' ),
        'page_on_front' => get_option( 'page_on_front' ),
        'page_for_posts' => get_option( 'page_for_posts' ),
        'date_format' => get_option( 'date_format' ),
        'permalink_structure' => get_option( 'permalink_structure' ),
    );
}
```

Both exist for step 8b, which cannot be added later: a theme that did not
flag what it made can never tell its own pages from the owner's.

### 8b. The other direction — removing the imported content

An import installs a whole site. An owner who tries the theme and decides
against it is left with forty pages and no way to tell which arrived with the
design. So every generated theme ships `inc/content-clean.php` beside its
importer, and a section at the foot of the setup screen.

**It reads the flags back. It never guesses.** A page goes because it carries
the import flag, never because its title or slug looked familiar — an owner's
own page called "About" must survive, and the test says so.

Two things it must not take:

- **A photograph the owner's own content still uses.** Check surviving posts
  for both spellings — the `wp-image-{id}` class and the file's basename —
  plus `_thumbnail_id`. Whoever uploaded it, it is theirs now.
- **A category anything is still filed under.** Delete only the empty ones.

**Order matters once.** Put the front-page options back BEFORE deleting the
page they name. WordPress turns the home page into a lookup of one post id
and its status gate has no capability check, so deleting that post underneath
the option 404s the entire site for everyone, administrator included.

**Say which of two things is about to happen.** With a snapshot, the reading
options are restored. Without one — every site installed before the theme
started recording it — they can only reset to WordPress's defaults, and the
screen must say that rather than claiming to restore.

**Three rails, all of them.** Never automatic and never part of switching
themes (switching stays reversible — that is the whole contract). A dry-run
listing shown BEFORE the destructive step, with the count of pages edited
since the import stated plainly, because those edits go too. And a typed
confirmation, WordPress's own uninstall idiom.

If the Visual Edit plugin may be present, drop its history rows for the pages
being deleted (`page_key = 'block__page-{id}'`), guarded by a `SHOW TABLES`
check — orphaned restore points for a post that no longer exists are the same
leak as orphaned responsive rules.

**The regression that proves it: clean, then import again onto the emptied
site.** Assert the pages come back at their own addresses rather than as
`-2` versions of them. A cleanup that left one page behind — holding a slug
`wp_unique_post_slug()` will not reuse — shows up there and nowhere else.

### 9. Verify — files first, then a REAL WordPress (non-negotiable)

File gates: `scripts/lint-delimiters.py` (grammar **and pairing** of every
delimiter, `content/` included — the doctor never looks there),
`scripts/lint-html.py`, the wp-block-theme-converter doctor, `php -l`.
**Then build the sandbox** (`scripts/wp-sandbox/setup.sh`) — static
harnesses agreed with the original at 0.56% while the real thing was 26%
out; every fault that mattered was found only in WordPress. The harness is
in `scripts/`; the recipe and the acceptance criteria are in
`references/verification.md`.

Acceptance: every page ≤ ~1% pixel diff against the original at 1440px and
390px; **0 invalid blocks** when every page and post is opened in the block
editor (`scripts/editor-validity.py` walks
`wp.data.select('core/block-editor')`; don't eyeball) — and
again with Visual Edit Lite activated, which registers the same form blocks;
every form sends and every field is editable in the editor; a description
typed into the editor's SEO panel reaches the page source, once; all original
URLs answer 200 or intentional 301; `debug.log` clean; no `__THEME_URI__`
surviving in `parts/`, `templates/` or any rendered page.

**Then open the editor and look at it.** Appearance → Editor → Templates:
the thumbnails must be distinguishable from one another, with no broken
images and no overlay panel covering the canvas. Nothing in the automated
tiers examines the screen the client will actually work in, and on the
reference two real defects lived there — every template previewing as the
same expanded menu, and nine broken images — while every check above was
green.

## Escalation — when to stop and ask

- **The input is not an html2wp theme** — no `clara-content/`, a different
  token family, no `[wp-*]` tokens. Say so and route to
  wp-block-theme-converter or html2wp-sub; do not improvise a converter.
- **A page stays above the visual threshold** after `scripts/measure-diff.py`
  has named the element and two rounds of bridge CSS. Show the diff images
  and the moved boxes; do not "fix" it by changing the design's own rules —
  the design is the specification.
- **Something the source does that core blocks cannot hold** without a
  `style` attribute, a span inside RichText or markup the editor would strip.
  Report it as `UNMAPPED` (conversion-rules.md); a custom block is a decision
  the owner makes, not a default.
- **Visual Edit Lite is unavailable or older than 1.27.** Criteria 7 and 8
  cannot run; say which gates were skipped instead of marking them passed.
- **A failure that reproduces only in the SQLite sandbox.** Try the MariaDB
  container in verification.md before concluding anything; if it reproduces
  there too, it is real.
- **Anything destructive on a site you did not just install** — the cleanup
  of step 8b, trashing sample content, permalink changes. Those need the
  owner's typed confirmation, not an agent's.

## Reference implementation

`github.com/iOSDevSK/amanda-rose-guttenberg` (private) — the complete worked
example: `steps/` is the conversion record (16 notes); `tools/` is where
this skill's `scripts/` came from, with the Amanda Rose values filled in;
`tests/` holds the regression files verification.md asks every theme to
ship. When in doubt, read how that repo did it.
Forms and search metadata are the part to read at version **2.4.1 or later** —
`inc/form-blocks.php`, `inc/seo.php` and `steps/14-forms-blocks-seo.md` are the
worked example of `references/forms-and-seo.md`. Everything it shipped before
that (a shortcode nobody can edit, a static form that never sends, and
`_amanda_rose_description`, which the editor's SEO panel never writes) is the
counter-example, and `steps/11-forms-cf7.md` still describes it.
