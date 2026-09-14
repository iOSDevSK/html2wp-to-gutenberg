# Forms and search metadata

The two places where the first conversions produced a theme that *looked*
right and could not be *worked* in: a form the client cannot edit, and a
search description the editor's own SEO panel writes into a key the theme
never reads. Both are contracts with Visual Edit Lite, and both have to hold
with the plugin absent, because the promise of this skill is a theme that
edits in plain Gutenberg.

---

## 1. Search metadata

### Why the conversion is a stranger to the plugin

A converted theme has no `clara-content/` bundle, so
`clara_ve_active_theme_is_ours()` is **false** for it — measured on the
reference. What keeps the plugin's own `<title>`, description, `og:*` and
JSON-LD off the page is the one line the input theme already carries:

```php
add_theme_support( 'html2wp-runtime', array( 'schema' => 1 ) );
```

Keep it in `inc/theme-setup.php`. With it, `Clara_VE_SEO::emit` is unhooked
from `wp_head` and the theme is the only thing printing metadata. Drop it and
the page carries two of every tag and two schema.org entities — which is what
the stand-down exists to prevent, not a theoretical risk.

### The theme reads the plugin's record, not its own key

Because the plugin has stood down, **its SEO panel is the only SEO editor on
the site**, and it writes one post meta key:

| | |
|---|---|
| Key | `_clara_ve_seo` (array) |
| Shape | `title`, `description`, `canonical` (strings), `noindex` (bool), `og`, `twitter`, `jsonld` (arrays) |
| Written by the panel | `title`, `description`, `og['image']`, `noindex` |
| Mirror | `_clara_ve_noindex` = `'1'` while `noindex` is on, so a meta query can find those pages |

A theme that invents `_<slug>_description` and friends turns every edit in
that panel into a silent no-op: the field accepts the text, the page saves,
and the public `<meta name="description">` never changes. The reference
theme shipped exactly that, and nothing in the automated tiers noticed.

So `inc/seo.php`:

- reads `_clara_ve_seo` for the singular view, falling back — in this order —
  to the record's own empty fields, the excerpt, the term description, then
  the site tagline;
- merges `noindex` into the `wp_robots` filter rather than printing a second
  robots tag (core has printed one since 5.7);
- leaves `<title>` and canonical to core unless the record overrides them;
- stands down completely when a real SEO plugin is active — Yoast
  (`WPSEO_VERSION`), Rank Math, SEOPress, All in One SEO.

### The importer writes the same key

`inc/content-import.php` writes `_clara_ve_seo` in that shape, and only when
the meta is absent:

```php
if ( ! empty( $record['seo'] ) && ! get_post_meta( $page_id, '_clara_ve_seo', true ) ) {
    update_post_meta( $page_id, '_clara_ve_seo', $record['seo'] );
}
```

The guard is the point: a second import must not overwrite descriptions the
owner has since edited.

**URLs inside the record are stored tokenized** — the panel runs `og.image`
and `canonical` through `Clara_VE_Bundle_Format::to_portable()`, so what is in
the meta is `__CLARA_UPLOADS_URI__/…` or `__CLARA_HOME_URL__/…`. Expand those
two (and `__CLARA_THEME_URI__`, and `__THEME_URI__` from the theme's own
records) before printing. `wp_head` output passes through no content filter,
so a token that survives is shipped to search engines exactly as written —
pitfall #12, the one place it does real damage.

### No second SEO screen

Do not add a theme SEO panel to the block editor. Two SEO UIs on one install
is the mess the client asked to be rid of, and with no plugin the excerpt is
already the editing path this file's fallback order honours.

---

## 2. Forms

### The shortcode was the mistake

`[<slug>_form id="contact"]` renders correctly and cannot be edited: in the
block editor it is a text field holding a shortcode. Nobody can change a
label, a placeholder, the choices in a select or the words on the button —
which is most of what a photographer actually wants to change about a
contact form. A conversion emits **form blocks**.

### Use the plugin's block names, and register them only when it is away

Register, on `init`, this family — the names are not negotiable:

```
clara-ve/form  clara-ve/field  clara-ve/textarea  clara-ve/select
clara-ve/checkbox  clara-ve/form-group  clara-ve/submit
```

```php
add_action( 'init', function () {
    if ( class_exists( 'Clara_VE_Form_Blocks' ) ) {
        return; // Visual Edit Lite owns these names; its versions win.
    }
    // …theme's own registration, identical attributes and save markup…
}, 20 );
```

Same names mean one `post_content` works both ways: install the plugin later
and the page stays valid; deactivate it and the theme keeps rendering the
same form. A theme-prefixed family (`<slug>/form`) would be valid markup too,
but the plugin's editing popup keys on the `clara-ve/` prefix, so the client
would lose field editing the moment the plugin is present — the worse of the
two failure modes.

Identical attributes and identical `save` output are what keep the blocks
valid on both sides, and a reimplementation from prose drifts — a checkbox's
`value="yes"`, the `cve-` prefix on a generated id, a `type` on the editor's
button. Visual Edit Lite is GPL-2.0-or-later and so is any theme headed for
WordPress.org, so the safe path is to **carry a copy of
`includes/class-form-blocks.php` and `assets/form-blocks.js`** from one pinned
plugin version, renamespaced for the theme's registration guard, with the
version and attribution in the file header. Implement from the contract below
only if the theme is not GPL-compatible — and then lean hard on the drift
check in `verification.md`.

### The saved markup contract

Attributes, per block:

| Block | Attributes |
|---|---|
| `clara-ve/form` | `formId`, `formClass`, `wrapperClass`, `redirect`, `message`, `formType` (`contact` \| `list`), `listId`, `recipient` |
| `clara-ve/field` | the field set + `type` (default `text`) |
| `clara-ve/textarea` | the field set + `rows` (0 = let CSS decide) |
| `clara-ve/select` | the field set + `options` (array of strings) |
| `clara-ve/checkbox` | the field set |
| `clara-ve/form-group` | `groupClass` |
| `clara-ve/submit` | `text`, `buttonClass` |

The field set: `name`, `inputId`, `label`, `labelClass`, `hint`, `hintClass`,
`placeholder`, `required`, `wrapperClass` (default `field`), `inline`.

What `save` puts in `post_content` — this is the part that must match the
plugin exactly, because a difference here is a block validation error the day
the other side renders the page:

```html
<!-- wp:clara-ve/form {"formId":"guide","formClass":"form","wrapperClass":"ar-form","message":"Thank you — your guide is on its way."} -->
<div class="wp-block-clara-ve-form ar-form"><form class="form"><!-- wp:clara-ve/field {"name":"guide-page-email","inputId":"guide-page-email","label":"Your email","placeholder":"you@example.com","required":true,"type":"email"} -->
<div class="wp-block-clara-ve-field field"><label for="guide-page-email">Your email</label><input id="guide-page-email" name="guide-page-email" required type="email" placeholder="you@example.com"/></div>
<!-- /wp:clara-ve/field -->

<!-- wp:clara-ve/form-group {"groupClass":"form-submit-wide"} -->
<div class="wp-block-clara-ve-form-group form-submit-wide"><!-- wp:clara-ve/submit {"text":"Send me the guide","buttonClass":"btn"} -->
<button type="submit" class="btn">Send me the guide</button>
<!-- /wp:clara-ve/submit --></div>
<!-- /wp:clara-ve/form-group --></form></div>
<!-- /wp:clara-ve/form -->
```

Rules the sample encodes:

- The form wrapper `<div>` exists only when `wrapperClass` does; otherwise the
  `<form>` itself carries `wp-block-clara-ve-form`.
- A field is `<div class="wp-block-clara-ve-<kind> <wrapperClass>">` holding
  label then control — control then label for a checkbox.
- `inline` (a label and its control that the design lays out as siblings,
  a `.signup` row) adds `style="display:contents"` to that wrapper, so the
  form's own flex or grid keeps sizing the control. In the editor the wrapper
  must be a *wrapping row*, never a column: a `flex: 1 1 220px` written for
  a width becomes a 220px height and the canvas stops resembling the site.
- The label's `for` is `inputId`, or `cve-<name>` when the source had none.
- The button is a bare `<button type="submit">` with the source's class; it
  carries no `wp-block-*` class.

Only `clara-ve/form` is dynamic. Its `render_callback` re-renders the whole
form connected — same classes, same order, plus the hidden fields the handler
needs; the fields, rows and button are static blocks whose `save` output the
form's renderer receives as its inner content. Give a field a
`render_callback` of its own and the connected markup stops matching the saved
markup, which is the one difference the editor calls invalid.

`save` writes static HTML on purpose: a page still shows its form when
neither the plugin nor the theme is there to render it — it simply does not
send.

### Delivery, with no plugin in sight

The renderer strips `data-demo`, gives the `<form>` an `action` and a nonce,
and the theme answers it: honeypot, a minimum time between render and
submit, `wp_mail` to a filterable recipient (default `admin_email`), then the
`redirect` or the `message` in place. That is the same job the input theme's
runtime already did before this conversion — port it; do not leave the
delivered site with forms that only look like forms.

When Visual Edit Lite is present it registers the blocks first, so its route
answers instead: submissions land in Form Submissions, the recipient comes
from Form Settings, and Akismet and the rate limit apply. Nothing in the
theme has to detect this.

**Delivery is the owner's choice, and it travels in the page.** `formType`
decides whether a submission is emailed or handed to a mailing list, `listId`
says which list, `recipient` names an address for that one form. Register all
three even if the theme can only email — an attribute the theme does not
register is dropped the first time the page is saved without the plugin, and
the owner's setting is gone with nothing said. Honour what you can, and sign
what you honour: a recipient read straight from the request is a mail relay,
and a list id read straight from the request writes into the owner's contacts.
One `wp_hash` over the values, emitted beside them and verified on the way back
in, is the whole fix; anything unsigned falls back to the site's own address.
Tell the editor what this theme cannot do
(`window.claraVeFormBlocks.lists = false`) rather than showing a control
nothing will honour.

### Contact Form 7

Not the default any more. Generate the CF7 path only when the source site
itself used CF7 — then pitfall #10's layout deltas apply. A form the client
can edit in the block editor, delivered by the theme, is the outcome that
made the shortcode unnecessary.

### Legacy content

Keep `[<slug>_form id="…"]` registered as a renderer for pages published
before the conversion, but stop emitting it. A page that still holds the
shortcode can be converted in place: Visual Edit Lite 1.27 offers "Make this
form editable" on a shortcode or HTML block, which produces exactly the
markup above and is one Undo away from where it started.

---

## 3. Converting the source `<form>`

The mapping, in the order a child of `<form>` is tested — the same order the
plugin's own converter uses, so both produce the same tree:

| Source child | Becomes |
|---|---|
| anything containing `input[type=radio]` | `core/html` (radio groups are not editable as fields yet) |
| an element with no controls whose class reads as a message (`msg`, `message`, `success`, `thanks`) | the form's `message` attribute — it is the theme's own "sent" sentence |
| `<label>` plus the control it points at (`for`/`id`, or the next sibling) | one `inline` field |
| a bare control | one `inline` field, with any `label[for]` in the same parent |
| `<label>` wrapping a single control | one `inline` field |
| a submit button or `input[type=submit]` | `clara-ve/submit` (`buttonClass` = its class) |
| a wrapper holding exactly one control | a field whose `wrapperClass` is the wrapper's class |
| a wrapper holding several controls | `clara-ve/form-group` with `groupClass`, converted recursively |
| a `<p>` | `core/paragraph`, keeping its class |
| anything else with text | `core/html` |

Carried from the `<form>` itself: `class` → `formClass`, the single wrapping
element's class → `wrapperClass`, `data-redirect` → `redirect` (site-relative
path only), and `data-demo` is dropped by the renderer. A trailing
`<span>`/`<small>`/`<em>` inside a label becomes `hint` + `hintClass`.

Two fields of one form must never share a `name`: the second overwrites the
first in the submission. Number the duplicate (`email-2`) at conversion time,
and again whenever a field is added or duplicated in the editor.

The four reference forms and a generic one are fixtures in the plugin's
`tests/fixtures/theme-forms.json`, with `tests/form-convert.cjs` asserting
the tree. Run that conversion against your source forms before hand-writing
any of it.
