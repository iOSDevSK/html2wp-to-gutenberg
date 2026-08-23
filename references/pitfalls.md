# Pitfalls — every one of these bit the reference conversion

Ordered by cost. The first five are invisible to file linting and surface
only inside a running WordPress or the block editor.

## 1. Block markup that WordPress silently rejects

### 1a. Delimiter whitespace is grammar, not style
`<!-- wp:paragraph {"className":"lead"}-->` — no space before `-->` — **is
not a block delimiter**. WP_Block_Parser requires `\s+` before the closing
arrow. The block becomes freeform HTML, its closer then closes the wrong
thing, and every following block nests one level deeper. Symptom on the
reference: a page quietly wrapped its entire remaining document inside a
sticky form panel and rendered 4,794px too tall — while every comment-balance
and HTML-balance check stayed green. LLM agents writing block markup produced
19 of these across 15 pages (~1.5% of delimiters). **Run
`scripts/lint-delimiters.py` on everything generated; it also `--fix`es.**

### 1b. HTML comments inside block containers
A plain `<!-- explanatory note -->` between a group's opener and its inner
blocks becomes a freeform block of its own and invalidates the parent.
Explanations go outside block boundaries or nowhere.

### 1c. Attributes core/image does not serialize
`width`, `height`, `loading`, `decoding`, `fetchpriority` on the `<img>` make
the saved HTML disagree with what the block type would serialize → "This
block contains unexpected or invalid content" on first open — 50 blocks on
the reference. WordPress adds loading/decoding at render time itself; sizing
is owned by the design's aspect-ratio frames. Same reason: never inject
`sizeSlug` at import without also writing the matching `size-{slug}` class.

### 1d. Spans inside RichText don't survive
`<span class="ind">+</span>` in a summary, numbering spans in nav labels —
gone on first edit. Decorative glyphs move to CSS (`::after`, counters).

## 2. theme.json v3: core generates competing presets

Without `settings.spacing.defaultSpacingSizes: false` and
`settings.typography.defaultFontSizes: false`, WordPress generates its own
1.5× scale **under the same numeric slugs** (`--wp--preset--spacing--80` =
5.06rem instead of your clamp) and it wins. Symptom: every section ~30–100px
short; the reference's live diff read 26% before this, near-zero after.
`spacingScale:{steps:0}` does NOT work — the merged data keeps core's scale.
Also: theme.json is cached — `wp_clean_theme_json_cache()` after changes.

## 3. Core's layout CSS ties your specificity

`:root :where(.is-layout-flow) > * { margin-block-start: 0 }` (+ first/last
child variants) weighs one–two classes — the same as most design selectors —
and print order varies. Margins vanish unpredictably (the reference lost the
article sheet's top margin, card figure margins, signup margins). Two-part
fix: enqueue the design CSS with `array('wp-block-library','global-styles')`
as deps, AND prefix every selector with `:root ` (scripted; skip `:root`/
`html` selectors and `@keyframes` bodies; flush standalone comments before
prefixing or the prefix lands on them).

## 4. Attachments steal page slugs

Attachments share the slug pool. `about.webp` imported before the About page
claims `/about/`; the page lands on `/about-2/`. Namespace attachment slugs
(`photo-{name}`) in the importer.

## 5. Permalinks: `update_option` is not enough

A `%postname%`-leading structure needs verbose page rules, decided when
WP_Rewrite initialises. Writing the option leaves rules generated for the old
structure and **every post 404s** (page rules match first). Use
`$wp_rewrite->set_permalink_structure('/%postname%/')` then flush. Recent WP
installs default to date-based, so set it unconditionally, don't fill-if-empty.

## 5b. An import that must finish inside one request will not

**The single most expensive bug in the reference conversion**, because it
looked like a feature working. The importer copies the theme's photographs
into the media library, and WordPress resizes each one into every registered
size. Sixty-five photographs is ~12s on an M-series laptop and **minutes** on
the shared hosting a client's site actually lives on. Every host kills the
request first — PHP `max_execution_time`, or the proxy in front of it.

Three properties, and it takes all three. Any two still lose the images:

**(a) Write the record after every item, not after the loop.** The reference
saved its file-name → attachment-ID map once, at the end of the media loop.
Kill the process at 4 seconds and the DB has 20 attachments, 96 files on disk,
and *nothing at all* in the option. Measured, not supposed. The next attempt
therefore starts from zero, dies in the same place, and no site ever finishes.

**(b) Identity comes from the database, not from the record.** Because the
record was the only memory, retrying re-copied files that were already there —
`wp_unique_filename()` turns them into `about-1.webp`, `about-2.webp`, and the
library grows on every attempt. Before creating anything, look it up: you
already namespace attachment slugs (#4), so `photo-{base}` + your import flag
identifies your own copy exactly. Write the flag **immediately after the
insert, before the slow resize** — reversed, an interruption between the two
leaves an attachment that neither the importer nor the cleanup (#8b) can ever
recognise.

**(c) Hand the work out in slices, and show them.** One server-owned state
machine — `media → rebind → terms → pages → posts → settings` — behind a
`wp_ajax_` endpoint. The client sends no stage and no counter, only "carry
on"; the server reads its own record and decides. Each call takes a **time
budget** (~5s), always does at least one item, then stops and reports
`{stage, label, done, total, percent, finished, errors}`. Keep the synchronous
whole-import function for CLI and as the no-JS fallback — the slices should
wrap the same stage functions, not fork them.

> Printing that script: **`admin_footer` does not pass the hook suffix.** It
> fires as `do_action('admin_footer', '')`. A callback that guards on its
> argument — which is what every other admin hook trains you to write —
> returns early on every request, the progress script is never printed, and
> the form silently falls back to the one blocking POST you just spent a
> release removing. It is invisible in `php -l`, in the DOM (the markup and
> the `<style>` are both there), and in `debug.log`. Register against the
> suffix `add_theme_page()` returned:
> `add_action( 'admin_print_footer_scripts-' . $hook, … )`. Caught only by
> fetching the real admin page over HTTP and grepping for the script.

Two more, both of which turn a bug into a lie:

- **A stage needs a way to be finished with an item it cannot do.** Record
  per-item failures and count them as dealt with, or one unreadable file makes
  the bar sit at 64/65 and the loop never ends.
- **Never render zero as success.** `copy()` failing 65 times because the
  uploads folder is unwritable produced *"Imported 0 images, 15 pages and 10
  journal entries"* in a **green** notice. Collect the reasons, show them, and
  make "finished with 0 of 65 photographs" an error.

### 5c. The repair stage: importing the media later does not fix the pages

Content is bound to the media library **as each page is created**, so a run
whose media stage came back empty leaves pages whose every image still reads
`__THEME_URI__/…`. They render — the theme resolves the token at display time
(#12) — which is exactly why nobody notices: the site looks right and nothing
in it is a library item, so the editor offers no replace, no alt text, no size,
and the media library is empty.

Fixing the importer does not heal those sites. The pages already exist and an
idempotent importer will not touch a page twice. So ship a stage that finds
flagged posts whose content still contains the placeholder and re-runs
`bind_media()` on them. Two constraints:

- **Flag, never shape** — the same rule as #8b. An owner's own page carrying
  the same placeholder is theirs.
- **Put `post_modified` back** where it was. A repair is not an edit, and the
  cleanup screen counts a moved modified date as work the owner is about to
  lose.

This is the difference between "fixed in the next conversion" and "fixed on
the site that reported it".

## 6. Inline styles → utility classes need `!important`

A style attribute outranks every stylesheet rule by definition. Its
replacement class does not — container rules like `.split .txt > * + *` win
on specificity and the element silently loses its spacing. Mark the utility
classes (and only them) `!important`, with a comment saying why.

Placement needs a **reconciling matcher keyed on exact class-set + ordinal**
("the 3rd element whose classes are exactly {h-lg}"), run repeatedly to a
fixed point. Contains-matching drifted 19 placements on the reference.
Elements styled but class-less in the source are invisible to the matcher —
they must be listed and handled by hand.

## 7. Wrapper-induced layout drift (the block bridge's job)

- `core/image`'s `<figure>` sizes to the photo, not to the frame — page-hero
  bands crop wrong until the figure takes the band's box (`position:absolute;
  inset:0` inside positioned media containers, `height:100%` in aspect
  frames).
- A `core/buttons` div among block siblings opens a line box taller than its
  inline-flex anchor (+8–13px), and **margins collapse** through it where the
  original inline element's margin sat in a line box and never collapsed.
  Where the link stood alone in a centred row, the line box was part of the
  spacing — fix per placement, not globally.
- Generic element rules catch new paragraphs: `.card p{flex:1}` grabbed
  `p.numeral` (was a span) and blew the row open → `:not(.numeral)`.
- Scoping: `.nav .wp-block-navigation` matched the overlay menu *inside* the
  header part too → child combinator.

## 8. WordPress's own sample content pollutes dynamic sections

"Hello world!" is a post: it takes the newest slot in every Query Loop —
no image, category "Uncategorized". The reference misread the resulting 26px
as a harness artifact until real data proved otherwise. Importer trashes
untouched `hello-world`/`sample-page` (modified≠created check; trash, not
delete).

## 9. Redirect maps imported from the old site contain self-references

Old bundles map `/journal-x/` → the post that now lives at `/journal-x/`.
Harmless while it resolves; an infinite 301 the moment it 404s. Guard **at
redirect time** (target path == request path → don't redirect), not while
building the map — then the entries double as slug-change safety nets.

## 10. Contact Form 7 layout deltas (only visible with the plugin active)

- `wpcf7_autop_or_not` → false, or every control gets a `<p>` wrapper and
  grids collapse.
- Textareas default to 10 rows → `[textarea name 40x2]`; let the design's
  min-height govern.
- `.wpcf7-form-control-wrap` is a block span around an inline-block control
  → descender gap on every field; set it `display:flex`.
- The submit spinner is an extra flex item; on phones it wraps to its own
  line (+33–53px). Hide it — CF7 still sets `aria-busy` and disables the
  button.
- Never gate theme activation on CF7 (`Requires Plugins`): render the
  design's own static form as fallback + an admin notice that nothing is
  delivered.

## 11. Verification traps

- **Static harnesses lie.** The reference's file-based preview agreed at
  0.56% while real WordPress was 26% out (pitfalls 2, 3, 5 are invisible
  without core CSS and the block parser). Screenshots must come from a
  running WP.
- Lazy images make full-page screenshots nondeterministic — force
  `loading=eager` + `img.decode()` + `document.fonts.ready` before capture.
- Strip `srcset`/`sizes` on BOTH sides when diffing — WP serves its own
  responsive sizes and a 433px rendition of the same photo reads as a
  100%-different region.
- Force `reduced_motion` in the browser context so reveals resolve and no
  animation frame differs between runs.
- Editor validity is checked by walking
  `wp.data.select('core/block-editor').getBlocks()` recursively for
  `isValid===false` — the canvas renders inside an iframe, so DOM selectors
  for the canvas time out; wait on the data store instead.
- The editor loads block markup pages fine but `PHP_CLI_SERVER_WORKERS=8`
  is needed or `php -S` serialises the editor's parallel requests into
  timeouts.
- Keep the sandbox WordPress OUTSIDE the theme directory or every theme
  linter starts scanning WP core.
- SQLite drop-in: `db.copy`'s `{SQLITE_IMPLEMENTATION_FOLDER_PATH}` sits
  inside single quotes — replace with a plain path string, not PHP code.
  `DISABLE_WP_CRON` in the sandbox, or cron fetches every URL in imported
  content and floods debug.log.

## 12. Theme-shipped images in static template files

A `parts/*.html` or `templates/*.html` file cannot call
`get_template_directory_uri()`, so the obvious move is a token
(`__THEME_URI__/assets/images/x.webp`) swapped by a `render_block` /
`the_content` filter. That filter is **server-side**, and two places never
run it:

- **The block editor.** It renders markup in the browser, so the token stays
  literal and every image in that part is broken — on every screen that
  previews it. The reference had six broken images in the footer, one in the
  journal hero and three on the 404 page, visible in all nine template
  thumbnails.
- **`wp_head`.** Structured data, `og:image`, canonical URLs — none of it
  passes through the content filters. The reference shipped JSON-LD telling
  search engines to fetch `__THEME_URI__/assets/images/about.webp`. Silent,
  and the one place it does real damage.

**Fix: put theme-shipped imagery in a PHP pattern** (`patterns/*.php`) and
reference it from the template with
`<!-- wp:pattern {"slug":"theme/name"} /-->`. PHP patterns are registered by
PHP, so the URL is real before anything asks for the content — front end and
editor receive identical resolved markup, and the shipped theme file carries
no install-specific path at all.

For metadata, resolve **at import time**, where the real addresses are known.
Never at render: structured data pointing at a token is worse than none.

Audit with `grep -rn '__THEME_URI__' parts/ templates/` (must be empty) and
`curl -s <url> | grep -c __THEME_URI__` on every page (must be 0) — the
second one is what catches the `wp_head` case.

## 12b. A `core/navigation` with inline links is not a menu

It renders perfectly, and it is seven lists of links wearing a menu's clothes.
Reported as **"I can't edit the menu — not in the Site Editor and not under
Appearance → Menus."** All three symptoms come from the same shape:

- **`register_nav_menus()` is what puts Appearance → Menus back.** It calls
  `add_theme_support('menus')`, and WordPress shows the classic screen for any
  theme that claims it — block theme or not. So the obvious place to look
  *works*: it edits `nav_menu` terms that a block theme renders **nowhere**. An
  owner can build a whole menu there, save it, and watch the site not change.
  The reference carried seven registered locations with a comment claiming the
  importer used them. Nothing ever did. **Delete the call** — a block theme has
  no use for it — and add an Appearance → Menus *link* pointing at
  `site-editor.php?p=%2Fnavigation`, because removing the signpost is not the
  same as fixing the road.
- **The Site Editor's Navigation screen lists `wp_navigation` posts.** A theme
  with none is not shown an empty list — it is shown the menu WordPress
  *invents* from the site's page list (`WP_Navigation_Fallback`). It looks
  exactly like the site's menu, is attached to nothing, and editing it does
  nothing. Worse than an empty screen.
- **Duplicated links drift.** Header bar and overlay panel were two unrelated
  blocks holding the same six links.

**The fix, and the one non-obvious part of it.** Model *menus* (the links)
separately from *placements* (where a menu appears + the attributes the design
needs there — the class names are load-bearing if JS keys on them). One menu
can then have two placements, which is the whole point: one edit, both places.
The importer creates one `wp_navigation` post per menu, flagged like everything
else it makes, and never rewrites one somebody has edited.

A static `parts/*.html` cannot carry `{"ref":N}` — the post ID does not exist
until the site does. **A pattern per placement resolves it**, the same idiom as
#12, branching:

```php
$id = $menus[ $placement['menu'] ] ?? 0;
return $id
    ? '<!-- wp:navigation ' . wp_json_encode( $attrs + array( 'ref' => $id ) ) . ' /-->'
    : '<!-- wp:navigation ' . wp_json_encode( $attrs ) . ' -->' . $inline_links . '<!-- /wp:navigation -->';
```

**Register these in code, never as files in `/patterns`.** Pattern files are
cached against the theme VERSION (#13), so the "no menus yet" branch would
freeze the header on the inline fallback for as long as the version string
held — which is for ever. This is the trap that makes the whole thing look
finished and silently not work after the import.

Two things to prove, because reasoning will not settle either: the rendered
`<nav>` must be **byte-identical** between the two branches (it was), and an
edit to a shared menu must reach **both** placements. Also refresh the menu
lookup cache at the end of the import stage, or the request that created the
menus spends the rest of its life still rendering the fallback.

## 13. WordPress caches a theme's pattern list against the theme VERSION

Add `patterns/new-thing.php`, reload, and it is not registered. Nothing is
wrong with the file. `WP_Theme::get_block_patterns()` caches the discovered
list in a site transient keyed on the theme and invalidated by its `Version:`
header.

Bump `Version:` in `style.css` (you are shipping a change anyway) or call
`wp_get_theme()->delete_pattern_cache()`. Cost one confused hour on the
reference.

## 14. The editor canvas is part of the deliverable

An overlay panel — the mobile menu, a search drawer, a lightbox — is
`position: fixed` and hidden until opened. In `editor.css` the reflex is to
force it visible so its contents can be reached. Do that and it becomes a
full screen of navigation sitting in the middle of **every** template: the
Templates screen renders N thumbnails that are all the same panel and nobody
can tell one template from another.

Fold it instead, and unfold it on selection — Gutenberg puts `.is-selected`
on a block's own element and `.has-child-selected` on its ancestors, so this
needs no JavaScript:

```css
.editor-styles-wrapper .menu{ max-height: 3.25rem; overflow: hidden; padding: 0; }
.editor-styles-wrapper .menu::before{ content: "Overlay menu — click to edit";
    position: absolute; inset: 0; z-index: 2; display: flex; align-items: center; }
.editor-styles-wrapper .menu.is-selected,
.editor-styles-wrapper .menu.has-child-selected{ max-height: none; overflow: visible; }
.editor-styles-wrapper .menu.is-selected::before,
.editor-styles-wrapper .menu.has-child-selected::before{ display: none; }
```

Clicking the band selects the group, which unfolds it — "click to edit" is
literally what happens. Measured on the reference: 52px folded, 614px open.

Every rule in `editor.css` must be scoped under `.editor-styles-wrapper`.
Verify: `awk '/^\./ && !/^\.editor-styles-wrapper/' assets/css/editor.css`
prints nothing.

### 14a. Putting things back into flow changes the parent's layout

This is the trap that follows from the fix above, and it does not announce
itself. A header is `display: grid; grid-template-columns: 1fr auto 1fr` and
holds exactly three things on the site — because the toggle and the overlay
panel are `position: fixed`, out of flow. `editor.css` puts both back into
flow so they can be edited, and now **five** children compete for three
columns: they wrap onto grid rows, one column takes 825px of a 1,480px
canvas, and the navigation folds into three lines.

The visible symptom is the navigation, so that is what you will try to fix.
It is not the cause. **Count the flow children in the editor before touching
anything**:

```js
[...document.querySelector('header.nav').children].map(c =>
    c.className.slice(0, 60) + ' ' + Math.round(c.getBoundingClientRect().width))
```

A container whose layout assumed N children needs an editor-side layout that
tolerates N+2. A wrapping flex row, with the restored panels given
`flex-basis: 100%`, is usually the whole fix.

### 14b. The editor's DOM is not the front end's DOM

Two that cost time on the reference, both the same shape — a `site.css`
selector that is correct on the site and matches nothing in the canvas:

- `core/navigation` renders `<ul class="wp-block-navigation__container">` on
  the front end and `<div class="…__container">` in the editor. Every rule
  written as `ul.nav-links > ul` silently stops applying; the links run
  together with `gap: 0`.
- Rich text carries `white-space: pre-wrap` from Gutenberg's own stylesheet,
  which outranks a theme selector — a one-word button breaks mid-word into
  "ENQ / UIRE" and reads as a fault. The editor rule has to name
  `.block-editor-rich-text__editable` itself.

Also: a state class that depends on the page behind it. The reference's
front-page header wears `.over` — transparent with white text, because it
sits on the hero. There is no hero in the canvas, so it was white on cream:
present, and invisible. Restore the ordinary state in `editor.css`.

### 14c. core/html previews are a THIRD document your editor.css can't reach

A `core/html` block does not render its markup into the canvas — it previews
it inside a **sandbox iframe** nested in the canvas. Two consequences:

- `document.querySelector` on the canvas frame finds nothing inside these
  blocks (they read as empty), so a probe that "confirms the element is
  missing" is probing the wrong document.
- Rules in `editor.css` do not reliably apply in the sandbox. On the
  reference, two attempts to restyle a skip link in there failed — the
  sandbox kept `site.css`'s styling both times — leaving the block a black
  sliver in the corner of the canvas.

So for raw-HTML islands that are pure control chrome (skip link, nav toggle,
close buttons): don't try to make them presentable inside the sandbox —
**hide their block at the canvas level**, where editor.css demonstrably
applies, same as an overlay dialog with no editable content:

```css
/* the skip link is, by definition, the header's first element */
.editor-styles-wrapper header.nav > .wp-block-html:first-child{ display: none; }
```

The canvas wrapper carries nothing of the block's content to key on, so the
selector has to be structural — say why in a comment, or the next person
"fixes" it. Bonus on the reference: with the sliver out of the flex flow the
header folded into a single row, matching the site.

### 14d. The post-content placeholder reads as damage in thumbnails

Content-framing templates are thin shells around `wp:post-content`, and
WordPress renders that block's placeholder as three bare paragraphs. In the
Templates grid every such template's thumbnail becomes torn text lines over a
dominant footer — the owner will ask whether it is broken (the reference's
owner asked three times).

Keep WordPress's wording — clients meet that exact sentence in every Gutenberg
tutorial — and dress only the slot:

```css
.editor-styles-wrapper .wp-block-post-content:not(:has([data-block])){
    border-block: 1px dashed var(--line); background: var(--surface);
    padding: var(--section-y-sm) var(--gutter);
}
.editor-styles-wrapper .wp-block-post-content:not(:has([data-block])) > p{
    font-size: .78rem; color: var(--muted); max-width: 640px;
}
```

`:has([data-block])` is the guard that matters: a template's placeholder is
plain `<p>` elements, while a page being edited fills the same container with
block wrappers that all carry `data-block`. Without it this rule restyles the
client's real content.

Do not reason about any of this from the markup. Read the computed values out
of the canvas iframe (`pg.frame(name="editor-canvas")`) and fix what the
numbers say — and when an element is inside a core/html block, remember the
numbers live in the sandbox, not the canvas.

## 15. Rewriting stored data: two ways to make it worse

**Never regex over `wp_json_encode()` output.** It escapes forward slashes,
so `#__THEME_URI__/assets/#` cannot match `__THEME_URI__\/assets\/` — the
pattern fails against its own encoder's output and the placeholder ships.
Operate on the **values** before encoding (`map_deep()` handles nesting), or
if you must touch stored text, capture the separator and write it back in the
same shape:

```php
'#__THEME_URI__(\\\\?/)assets\1images\1([^\s"\\\\]+\.webp)#'
```

**Never write what `preg_*` returned without checking it.** A mis-escaped
character class (`[^\s"\\]` written one backslash short) does not throw — the
pattern fails to compile, `preg_replace_callback` returns `null`, and a
migration that assigns that result **empties every record it touches**. Fifteen
structured-data records on the reference, in one pass. Guard it:

```php
if ( null === $fixed || '' === $fixed ) { continue; }
```

Two more, learned the same afternoon:

- Data written **only at creation** (SEO meta, per-page records) needs an
  explicit one-shot repair guarded by an option, or every already-imported
  site keeps the bug forever and a theme update fixes nothing.
- A repair should walk **postmeta**, not posts. `post_status => 'any'` skips
  custom statuses; the first version missed ten articles a plugin had parked.

## 16. Editing block markup from a script

The conversion does this constantly, and four things bite:

- **`parse_blocks()` is asymmetric.** It keeps the whitespace *between
  top-level blocks* as freeform entries, but `innerBlocks` does not. So
  top-level indexes step `0, 2, 4` while nested ones are dense `6-0, 8-0`.
- **A preset attribute renders through a class**, and for a static block the
  block's own `save()` baked that class into the stored HTML — nothing adds it
  at render. Writing `"textColor":"accent"` alone changes the database and not
  the screen; write `has-accent-color has-text-color` too. Class *order* does
  not matter: Gutenberg compares `class` as an unordered set.
- **Eating a closing delimiter does not remove a block.** The parser
  auto-closes at end of document, so everything after becomes that block's
  *child* — same names, same count, same order. A flat comparison of block
  names calls it unchanged; only a depth-aware one, or a token-level balance
  count, sees it. This is the fault that folded a whole page into a sticky
  panel 4,794px tall.
- **`'0'` is `empty()` in PHP.** A patch addressing the first block on a page
  is silently refused by `if ( empty( $patch['block'] ) )`. It survived four
  test files that all happened to address nested blocks.

### 16a. A container does not store its HTML as one string

This is the one that deletes a page. A group holding a paragraph stores:

```php
'innerHTML'    => '<div class="wp-block-group"></div>',   // NOT the real markup
'innerContent' => array( '<div class="wp-block-group">', null, '</div>' ),
```

`innerHTML` is only the concatenation of the non-null pieces, so it reads as
an element **already closed and empty**. The `null` is where
`serialize_blocks()` puts the child back.

So the usual leaf-block writer —

```php
$block['innerHTML'] = $html;
$block['innerContent'] = array( $html );   // fine for a paragraph
```

— **silently deletes every child** of a container. Padding a section empties
it, and nothing reports an error: the write succeeds, the block is valid, the
content is gone.

Read and write only the piece carrying the opening tag:

```php
foreach ( $content as $i => $piece ) {
    if ( null !== $piece ) { $content[ $i ] = $rewritten; break; }
}
$block['innerHTML'] = implode( '', array_filter( $content, fn( $p ) => null !== $p ) );
```

Affects group, columns, column, quote, list, details, cover — and `<summary>`
edits on details, which live in that first piece while the answer below is
child blocks.

### 16b. `isValid` is not proof: a deprecated save passes

Gutenberg reports a block valid if the markup matches the current save() **or
any of the block's deprecations**. A deprecation match is *worse* than invalid:
WordPress migrates the block on the next open and the attribute you wrote is
gone, with nothing warning anybody. Seen with `core/separator` +
`backgroundColor` — `isValid: true`, but the editor state showed
`backgroundColor: null` and the classes dumped into `className`.

So validity checks need a second assertion: **every attribute you set must
still be readable back from the editor's own state.**

```js
wp.data.select('core/block-editor').getBlocks()
  .some((b) => b.name === name && b.attributes[attr] === value)
```

### 16c. `wp.blocks.getSaveContent()` is the only authority on a fixture

A hand-written fixture that is *already invalid* makes every row of a test
fail for reasons that have nothing to do with the code. A `core/cover` fixture
missing `has-background-dim-100` produced 15 invalid blocks and looked like a
broken writer.

**Assert an UNEDITED fixture is valid before any edited one means anything**,
and take the markup from the editor itself:

```js
wp.blocks.getSaveContent(wp.blocks.getBlockType(b.name), b.attributes, b.innerBlocks)
```

### 16d. Which properties a block supports is not guessable — read the registry

Hand-written lists drift and the surprises are not intuitive:

| Block | Surprise |
|---|---|
| `core/column` | padding YES, margin **NO** |
| `core/spacer` | no colour, no typography; margin only. Height is an **attribute**, plus a hand-written `style="height:…"` in save() |
| `core/cover` | declares `color.background` **false** — its background is the overlay |
| `core/image` | `color.text` and `color.background` both explicitly false |
| `core/paragraph` | declares NEITHER `color.text` nor `color.background` — for colour, **absent means supported**; every other flag is off unless declared |
| `core/separator` | bespoke colour recipe (`has-text-color`, `has-{slug}-color`); the generic writer cannot express it |
| `core/quote` | `textAlign` is a top-level ATTRIBUTE; paragraph/heading/button declare `supports.typography.textAlign` instead |

Read `WP_Block_Type_Registry::get_instance()->get_registered( $name )->supports`
and let one function answer for the UI, the server and the tests — then a
control is never offered for something that would be refused.

**Do not treat `__experimentalSkipSerialization` as "don't write".**
`core/button` sets it on typography, colour AND spacing and is styled
perfectly well; it means "the block writes this itself, elsewhere" (for a
button, on its `<a>`). Blocks with a genuinely bespoke recipe are found by
testing, not by that flag.

Attribute defaults matter too: a `core/spacer` left at 100px stores **no**
height attribute — the value lives only in the markup, as the registered
default. Rewriting style from attributes alone deletes it. Fall back to
`$type->attributes[ $name ]['default']`.

### 16d-bis. A sanitiser allow-list is a second list that drifts

If the UI decides what to offer from one list (block supports) and the writer
decides what to accept from another (a validation allow-list), a property in
the first and missing from the second is **not refused — it is dropped**. The
control appears, takes a value, saves without complaint, and changes nothing.
That is a far worse bug than a refusal, because there is nothing to read.

`typography.fontFamily` was exactly that: choosing a typeface of one's own did
nothing, while the preset dropdown worked (it writes an *attribute*, a
different code path). Note the shape — **two spellings of one control failing
differently** is the signature.

The guard is a test that walks the offered list and asserts every entry both
stores and reaches the markup:

```php
$offered = array_keys( SUPPORT_FLAG ); $tried = array_keys( $representative );
sort( $offered ); sort( $tried );
assert( $offered === $tried );   // a property added to one list and not the
                                 // other stops being covered, silently
```

And when writing the pattern for a font family, remember what one is made of:
quotes, spaces and commas (`"Cormorant Garamond", Georgia, serif`). A slug
pattern rejects every real font stack.

### 16d-ter. A support may be STORED and never serialized

Some supports are real, applied at render, and written into the markup by
nobody. `getSaveContent()` returns markup identical to the plain block for:

| Property | Applied by |
|---|---|
| `spacing.blockGap` | layout support, via a generated container class |
| `style.position` (sticky) | render-time class |
| `core/cover` `dimensions.aspectRatio` | render-time |

And `wp_style_engine_get_styles()` **disagrees**: it happily returns
`aspect-ratio:16/9` for one of them. The engine is not the authority — the
block's `save()` is. Emitting a declaration the block would not produce is one
entry too many in the style map, which is an invalid block. Prune those paths
before the engine sees them, and store the attribute only.

Corollary: values that live only in attributes are invisible to a browser
reading the page. If an editor UI needs to show them, the server has to stamp
them onto the preview (a `data-` attribute), or the control opens blank on a
block that has the value set.

### 16d-quater. `className` belongs to the block's ROOT element

`useBlockProps` writes the owner's extra classes onto the block's root, which
is NOT always the element that carries its styling:

```
core/button:  <div class="wp-block-button cve-anim-fade-up">   ← className here
                <a class="… has-accent-color …">                ← every style here
core/image:   <figure class="wp-block-image has-custom-border"> ← className + marker
                <img class="has-border-color" style="border-…"> ← border + shadow
```

Writing both to one element makes that block — and only that block — invalid,
which is exactly how it presents: eleven block types pass and one fails.
Distinguish *root*, *styled* and *inner* elements.

Two traps while implementing this: a check like
`strtoupper($tags->get_tag()) === $wanted` **after** `next_tag(['tag_name' => $wanted])`
compares the answer with itself and is always true; and `className` stored in
attributes but never echoed into markup is its own invalid-block bug (removing
one needs the OLD value, which only the attribute writer still knows).

### 16e. Structural edits: the whitespace is the work

Because `parse_blocks()` keeps the blank lines between top-level blocks
(see 16 above), every structural operation has to step over them:

- **Move** must swap with the neighbouring *block*, walking past freeform
  entries. Swapping with the adjacent array element trades a section for a
  newline and nothing appears to happen.
- **Remove** must take its separator with it — the one after, or the one
  before when removing the last block. Otherwise blank lines accumulate and
  every address below drifts.
- **Insert** brings exactly one separator per join.
- **One structural operation per request**, then reload. They renumber the
  page, so a queued patch for block 4 sent alongside a removal of block 2
  lands on whatever slid into the gap.
- Nested addresses need `innerContent` null-placeholder accounting; refuse
  them rather than approximate.

### 16f. The stored value is not the rendered value (fluid typography)

With `settings.typography.fluid` on — which most generated theme.json files
have — WordPress rewrites a block's custom `font-size` into a `clamp()` at
render time:

```
stored:   style="font-size:28px"
rendered: style="font-size:clamp(17.9px, 1.119rem + ((1vw - 3.2px) * 0.814), 28px)"
```

So a browser check asserting `getComputedStyle(el).fontSize === '28px'` fails
against correct behaviour. Assert against the **stored** markup, or against
the clamp's ceiling. Gutenberg validates the stored value, so nothing is wrong
— but half an hour goes into proving it.

## 18. Adding what core blocks cannot store (responsive, animation)

Two ways to go beyond a block's own attributes, with very different costs.

**As a CSS class** (animation, hover, any curated effect): a class is a core
attribute every block understands, so the page stays valid, stays ordinary
WordPress content, and keeps working with the plugin off — it simply stops
doing the extra thing. Cost: zero. Prefer this whenever the feature can be
expressed as a fixed set of options.

- Ship the stylesheet/script **only when the content carries the class** (scan
  `post_content`). A page that uses none of it should download nothing.
- **Never hide anything from CSS alone.** Apply the hidden starting state from
  a class the SCRIPT adds to `<html>`, or a page whose JS fails shows nothing.
  Test with `java_script_enabled=False`.
- Honour `prefers-reduced-motion` by doing nothing at all.

**As data in post meta** (per-breakpoint values): unavoidable when the value
set is open-ended, and the one thing that will NOT survive deactivation. Say
so out loud before building it.

- Store **structured JSON, compile CSS on read.** Never store the CSS. (The
  cautionary tale: a well-known builder stores CSS and changes breakpoints by
  `str_replace` across every page's stored string.)
- Validate per property with the **same whitelist** the block writer uses, or
  the two drift.
- **`!important` is mandatory.** Block styling is an inline `style` attribute,
  which beats any selector however specific. Without it the override silently
  does nothing.
- Anchor with a generated class. Then: **duplicate must re-anchor recursively
  and copy the rules** (a plain array copy shares anchors, so tuning one tunes
  both), and **remove must prune** or the meta accumulates dead rules.
- **Version it with the page's history**, and remember a rules-only change
  leaves the markup byte-identical — a history that skips on a content hash
  alone will never record it.
- If the editor has a device preview, make its widths **agree with the
  breakpoints**. A "Tablet" preview at 820px showing nothing for rules that
  apply below 781px is indistinguishable from a broken feature.
- `wp_slash()` JSON on the way into postmeta.

## 17. Small but real

- A console listener catches `Failed to load resource` as well as real
  exceptions. On a converted site those are the site's OWN broken image paths
  — true, and nothing to do with the code under test. Filter them, and make
  test fixtures point at images that actually exist.
- Sandboxes on `php -S` have a handful of workers. An editor page that loads
  itself, a canvas iframe and REST calls at once can queue past a 30s wait
  under a full suite run. Retry the initial load rather than accepting a
  flaky gate.
- `wp:pattern` referencing shared card markup keeps the front-page teaser
  and the archive loop from drifting apart.
- Entity fidelity: avoid DOM parsers on content (`&mdash;` etc. get
  re-serialised to literals); string-level processing only.
- `.distignore` must NOT exclude the content bundle if the importer reads it
  from the theme.
- The old theme's `style.css:` check for stray syntax (the reference had a
  dead `a@media` typo rule) — don't port bugs faithfully.
