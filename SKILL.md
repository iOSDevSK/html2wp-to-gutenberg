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
  0.4% pixel diff of the original against a REAL WordPress, 1,025 blocks /
  0 invalid in the editor. Trigger when the user asks to "preklop tému do
  Gutenbergu", "convert my html2wp theme to native blocks", "make the theme
  editable without Visual Edit", "gutenberg verzia témy", "1:1 like amanda
  rose", or names this skill. Do NOT use for plain static HTML folders
  (that's wp-block-theme-converter or html2wp-sub) — this skill's input is
  specifically a theme the html2wp converter already produced.
license: MIT
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
to linters and only appear inside a running WordPress.

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
- Run `raise-specificity` (`:root ` prefix on every selector; see the
  reference repo's `tools/raise-specificity.py`) so the design consistently
  beats core's `:root :where(.is-layout-flow)` layout resets (pitfall #3).
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
- Dialog semantics (`role`/`aria-modal`) that group blocks cannot carry: add
  at render time with `WP_HTML_Tag_Processor`, keyed on the block's anchor.
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
afterwards using a **reconciling matcher keyed on class-set + ordinal**
(first-match placement drifts; the reference caught 19 misplacements that
way). Forms become a shortcode the theme renders two ways (CF7 template when
the plugin is active, the design's own static markup otherwise).

### 8. Importer + setup screen

One admin page, one idempotent import: media (**slug-namespace the
attachments**, pitfall #4), categories with the topic pages' intros as
descriptions, pages (claim-slug guard, template assignment, SEO meta),
posts, redirect map, reading settings (**`$wp_rewrite->set_permalink_structure()`,
not `update_option`**, pitfall #5), trash untouched sample content
(pitfall #8), CF7 forms. `bind_media()` rewrites image URLs to attachments
and injects the `id` attr + `wp-image-N` class — and nothing else
(pitfall #1c).

### 9. Verify — files first, then a REAL WordPress (non-negotiable)

File gates: `scripts/lint-delimiters.py`, `scripts/lint-html.py`, the
wp-block-theme-converter doctor, `php -l`. **Then build the sandbox** —
static harnesses agreed with the original at 0.56% while the real thing was
26% out; every fault that mattered was found only in WordPress. Full recipe
and the acceptance criteria: `references/verification.md`.

Acceptance: every page ≤ ~1% pixel diff against the original at 1440px and
390px; **0 invalid blocks** when every page and post is opened in the block
editor (walk `wp.data.select('core/block-editor')`, don't eyeball); all
original URLs answer 200 or intentional 301; `debug.log` clean; no
`__THEME_URI__` surviving in `parts/`, `templates/` or any rendered page.

**Then open the editor and look at it.** Appearance → Editor → Templates:
the thumbnails must be distinguishable from one another, with no broken
images and no overlay panel covering the canvas. Nothing in the automated
tiers examines the screen the client will actually work in, and on the
reference two real defects lived there — every template previewing as the
same expanded menu, and nine broken images — while every check above was
green.

## Reference implementation

`github.com/iOSDevSK/amanda-rose-guttenberg` (private) — the complete worked
example: `steps/` is the conversion record (16 notes), `tools/` has the full
harness set (visual-diff, measure-diff, render harnesses, apply-style-classes,
raise-specificity, wp-sandbox). When in doubt, read how that repo did it.
