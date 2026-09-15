# Page conversion rules (block mapping)

Generalized from the Amanda Rose conversion guide. When running a conversion,
instantiate a per-project copy of this file: fix the source-of-truth CSS path,
and REBUILD the inline-style table from the project's own census (grep every
style attribute across sources and posts first — the reference had 40 distinct
declarations; yours will differ). Everything else transfers as-is.

---

## The one rule

**Keep every original class, in the same nesting order, on the same kind of
element.** Blocks are the vehicle; the classes are the design. A `<div class="wrap">`
becomes a `core/group` whose `className` is `wrap`, and its rendered output is
`<div class="wp-block-group wrap">` — the extra `wp-block-group` is harmless,
the missing `wrap` would not be.

Never invent classes. Never drop one because it "looks unused".

---

## Block mapping

| Source | Block |
|---|---|
| `<section class="X">` | `<!-- wp:group {"tagName":"section","className":"X","layout":{"type":"default"}} -->` |
| `<div class="X">` | `<!-- wp:group {"className":"X","layout":{"type":"default"}} -->` |
| `<article class="X">` | `<!-- wp:group {"tagName":"article","className":"X",…} -->` |
| `<header class="X">` | `<!-- wp:group {"tagName":"header","className":"X",…} -->` |
| `<nav class="X">` | `<!-- wp:group {"tagName":"nav","className":"X",…} -->` |
| `<h1>`…`<h4>` | `<!-- wp:heading {"level":N,"className":"…"} -->` (omit `level` for h2) |
| `<p class="X">` | `<!-- wp:paragraph {"className":"X"} -->` |
| `<span class="eyebrow …">` | `<!-- wp:paragraph {"className":"eyebrow …"} -->` — it is a block-level kicker everywhere it appears |
| `<img>` | `<!-- wp:image {"className":"…"} -->` (see **Images**) |
| `<div class="fig …"><img></div>` | one `core/image` carrying **both** sets of classes: `{"className":"fig fig-3x4"}` |
| `<a class="btn">` | `core/button` (see **Buttons**) |
| `<a class="tlink">` | `core/button` with `is-style-tlink` (see **Buttons**) |
| `<ul>` / `<li>` | `core/list` / `core/list-item` |
| `<blockquote><p class="q">` | `core/quote` wrapping `core/paragraph {"className":"q"}` |
| `<details>` + `<summary>` | `core/details` (see **Accordions**) |
| `<form>` | `clara-ve/form` + one block per field (see **Forms**) |
| `<hr>` | `<!-- wp:separator {"className":"hr"} -->` |

`layout: {"type":"default"}` on every group is deliberate — it is flow layout,
which renders a plain `<div>` and lets the design's own CSS own the spacing. Do
not use `constrained`; it would add a max-width the design does not want.

---

## Images

Rewrite every `src` to the theme's flat asset folder, keeping only the file name:

```
__CLARA_UPLOADS_URI__/clara-ve-import/about/story.webp  →  __THEME_URI__/assets/images/story.webp
__CLARA_THEME_URI__/assets/j-5.webp                     →  __THEME_URI__/assets/images/j-5.webp
```

- **Keep** `alt`. Nothing else on the source `<img>` survives.
- **Drop** `width`, `height`, `loading`, `decoding` and `fetchpriority`
  (pitfall #1c — 50 invalid blocks on the reference). `width` and `height`
  are attributes `core/image` keeps in the delimiter JSON with no HTML
  source, so a bare `width="1024"` on the `<img>` matches no `save()` and the
  block opens as "unexpected or invalid content". WordPress adds `loading`
  and `decoding` itself at render time; the design's aspect-ratio frames own
  the sizing.
- **Drop** `srcset` and `sizes`. WordPress regenerates both from the media
  library after import; a hand-written srcset pointing at theme files would
  contradict it.
- The `<figure>` core adds is expected — `.fig` styles it directly.

Markup shape:

```html
<!-- wp:image {"className":"fig fig-3x4 curtain"} -->
<figure class="wp-block-image fig fig-3x4 curtain"><img src="__THEME_URI__/assets/images/detail.webp" alt="…"/></figure>
<!-- /wp:image -->
```

### Gallery images that open the lightbox

Any tile that carried `data-lb` in the source — every `button.gal-item` and
every `button.m` — becomes an image **linked to its own file**:

```html
<!-- wp:image {"linkDestination":"media","className":"gal-item fig fig-3x4"} -->
<figure class="wp-block-image gal-item fig fig-3x4"><a href="__THEME_URI__/assets/images/w-1.webp"><img src="__THEME_URI__/assets/images/w-1.webp" alt="…"/></a></figure>
<!-- /wp:image -->
```

`site.js` turns those links into the lightbox. Tiles that were plain `<div class="m">`
in the source (portfolio.html, 404.html) get **no** link — they were never
clickable and must stay that way.

---

## Buttons

| Source | Block |
|---|---|
| `<a class="btn">` | `<!-- wp:button -->` (no className — plain is the default look) |
| `<a class="btn btn-ghost">` | `<!-- wp:button {"className":"is-style-ghost"} -->` |
| `<a class="btn btn-ondark">` | `is-style-ondark` |
| `<a class="btn btn-ondark-ghost">` | `is-style-ondark-ghost` |
| `<a class="tlink">Label <span class="arw">→</span></a>` | `is-style-tlink`, label only — **the arrow is drawn by CSS, do not keep the span** |
| `<a class="tlink tlink-ondark">` | `is-style-tlink-ondark` |

Full shape:

```html
<!-- wp:buttons {"className":"act"} -->
<div class="wp-block-buttons act">
	<!-- wp:button {"className":"is-style-ghost"} -->
	<div class="wp-block-button is-style-ghost"><a class="wp-block-button__link wp-element-button" href="/contact/">Enquire</a></div>
	<!-- /wp:button -->
</div>
<!-- /wp:buttons -->
```

When the source had several buttons in one row, put them in **one** `core/buttons`
block and give that block the row's class (`act`, `acts`, `form-foot`, `row-actions`).
When a single `tlink` sits inside a `.txt` column, still wrap it in `core/buttons`
but give the wrapper no class.

---

## Accordions

```html
<!-- wp:details -->
<details class="wp-block-details"><summary>How many hours do we need?</summary>
	<!-- wp:group {"className":"ans","layout":{"type":"default"}} -->
	<div class="wp-block-group ans">
		<!-- wp:paragraph --><p>…</p><!-- /wp:paragraph -->
	</div>
	<!-- /wp:group -->
</details>
<!-- /wp:details -->
```

- Drop `<span class="ind">+</span>` — CSS draws the indicator now.
- `summary` is read from the `<summary>` element itself (`source:
  rich-text`), so it does not go in the delimiter JSON; neither does an empty
  `className`.
- The first item in each group had `open` in the source; that one only gets
  `{"showContent":true}` in the JSON **and** `open` on the element —
  `<details class="wp-block-details" open>` — because `save()` writes both
  from the same attribute and the markup has to agree with it.
- The `.faq` wrapper around the whole set stays a `core/group`.

---

## Separators

```html
<!-- wp:separator {"className":"hr"} -->
<hr class="wp-block-separator has-alpha-channel-opacity hr"/>
<!-- /wp:separator -->
```

`has-alpha-channel-opacity` is what the block's default `opacity` writes into
the markup. Leave it out and the `<hr>` matches, at best, a deprecated
`save()` — which passes `isValid` and is silently migrated on the next open
(pitfall #16b).

---

## Forms

Convert the `<form>` into the `clara-ve/*` block family, one block per field,
so every label, placeholder, choice and the button text stay editable in the
block editor. The mapping table, the saved-markup contract and how the theme
registers and delivers the form are in **`forms-and-seo.md`** — read it
before converting the first form.

```html
<!-- wp:clara-ve/form {"formId":"contact","formClass":"form","wrapperClass":"ar-form","redirect":"/form-submitted/"} -->
<div class="wp-block-clara-ve-form ar-form"><form class="form">…fields…</form></div>
<!-- /wp:clara-ve/form -->
```

The form's own class goes to `formClass`, its single wrapper's class to
`wrapperClass`, `data-redirect` to `redirect`, and the design's hidden "sent"
sentence to `message`. `data-demo` disappears with the static markup.

A shortcode block (`[<slug>_form id="contact"]`) is what earlier conversions
emitted. It renders and cannot be edited — keep the shortcode registered for
pages published before the conversion, emit blocks for everything new.

The journal search form is not a page form — it lives in the templates and is
already handled.

---

## Reveal delays

`data-d="1"` … `data-d="5"` become classes `d1` … `d5`, appended to the same
element's `className`:

```
<div class="txt reveal" data-d="2">   →   {"className":"txt reveal d2"}
```

---

## Inline styles

Block markup may not carry a `style` attribute. These are the classes that
already exist for the styles the source used — use them and add nothing new:

| Source style | Class |
|---|---|
| `display:flex;justify-content:space-between;align-items:flex-end;gap:2rem;flex-wrap:wrap;margin-bottom:clamp(2rem,4vw,3rem)` | `section-head` |
| `margin-top:1.1rem` | `mt-1` |
| `margin-top:2rem` | `mt-2` |
| `display:flex;gap:1.2rem;justify-content:center;flex-wrap:wrap;margin-top:2.2rem` | `row-actions` |
| `display:flex;gap:1.5rem;justify-content:center;flex-wrap:wrap;margin-top:1.6rem` | `row-gap-lg` |
| `display:flex;justify-content:center;gap:1rem;flex-wrap:wrap` | `row-center` |
| `padding-top:clamp(.5rem,1.5vw,1.5rem)` | `section-tight-top` |
| `padding-bottom:0` | `pb-0` |
| `margin:clamp(2.6rem,6vw,4.5rem) auto` | `gal-wide` |
| `width:100%` on a button | `is-style-` not needed — the `form-foot--wide` wrapper handles it |

**If you meet an inline style not in this table, do not invent a class and do
not drop the style.** Record it at the end of your report as
`UNMAPPED STYLE: <page> <selector> <declaration>` and leave the element without
it. The styles will be collected and added to the stylesheet in one pass.

---

## What to leave out

- `data-cve-class`, `data-ve-nav`, `data-cve-*` — editor plumbing from the old
  build, meaningless here.
- The `<a class="skip">` skip link — it now lives in the header part.
- The `<!-- NAV -->`, `<!-- MENU -->`, `<!-- FOOTER -->` marker comments.
- `<span class="dot"></span>` inside a card's `.meta` — CSS draws it.
- `<span class="mark">` in a `.quote-block` — CSS draws it.
- Anything inside `<main id="main">`: keep the contents, drop the wrapper. The
  template supplies `<main>`.

---

## Output

One file per page: `content/pages/<slug>.html`, containing **only** the block
markup that goes inside `<main>`. No `<main>`, no header, no footer.

Indent with tabs, one level per nesting depth. Leave a blank line between
sibling top-level sections.

## Report back

- the file you wrote
- the page's section list, in order, so it can be checked against the source
- every `UNMAPPED STYLE:` line
- anything in the source you could not express, with the reason
