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

## 17. Small but real

- `wp:pattern` referencing shared card markup keeps the front-page teaser
  and the archive loop from drifting apart.
- Entity fidelity: avoid DOM parsers on content (`&mdash;` etc. get
  re-serialised to literals); string-level processing only.
- `.distignore` must NOT exclude the content bundle if the importer reads it
  from the theme.
- The old theme's `style.css:` check for stray syntax (the reference had a
  dead `a@media` typo rule) — don't port bugs faithfully.
