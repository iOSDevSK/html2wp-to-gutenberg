# The workflow, step by step

What the agent does at each step of [SKILL.md](../SKILL.md), what the step
produces, which gate closes it, and what it will ask you for. The numbers are
SKILL.md's; the procedure itself lives there and is not repeated here.

Before the first step the agent reads `references/pitfalls.md` and
`references/forms-and-seo.md`. It should; every entry there is something the
reference conversion paid for.

## Before you start — what you are asked for

The [Inputs required](../SKILL.md#inputs-required) list, in short: the html2wp
theme directory (it must hold `clara-content/`, or it is not an html2wp theme
and this is the wrong skill), the slug of the new theme and where its sibling
directory goes, something that shows what the original looked like, the plugins
the old site used, the tooling, and — if any gate will reuse a database — a
dump of it, because the cleanup gate deletes content.

## 1. Audit

Two inventories in parallel: the content bundle (every source page's section
list, `data-*` attributes with counts, forms and their fields, token usage, the
posts census, menus, terms, redirects) and the theme (CSS custom properties,
every JS behaviour with its selectors, every `inc/` file's role, dead code).

*Produces:* the inventory, and a list of what will deliberately **not** be
ported, with reasons. That list is the difference between "dead code removed"
and "feature lost", and it is the first thing to read when the audit is done.

## 2. Scaffold and theme.json

A new directory under the new slug, `theme.json` v3 with the design's tokens
as presets and core's own presets switched off (pitfall #2), custom templates
for the page variants so they are visible in the editor.

*Produces:* an empty theme that activates. *Gate:* `php -l`, the doctor.

## 3. Fonts

The exact cuts the old theme loaded from Google Fonts, downloaded and declared
in `theme.json` with their unicode ranges, the two above-the-fold cuts
preloaded. Same files as the CDN served, so text renders identically.

## 4. CSS

The original `site.css` verbatim, its `:root` variables pointed at the presets,
a *block bridge* section appended for the wrappers core adds, the inline styles
of the source turned into utility classes, and `raise-specificity.py` run over
the result so the design outranks core's layout rules (pitfall #3).

*Gate:* `raise-specificity.py` is idempotent — a second run changes nothing.

## 5. JS

The site's script kept classic and deferred, with the changes that would
otherwise silently break: no ids from render-time filters, real image links
for the lightbox, marquee tracks cloned at runtime, the `html.js` class set in
the head, stagger attributes turned into classes.

## 6. Parts, templates, patterns

One header, one footer, real menus as `wp_navigation` posts the importer
creates and a pattern resolves, templates as thin shells, category archives at
the original topic-page URLs, PHP patterns wherever a theme URL is needed
(pitfalls #12, #13), forms as the `clara-ve/*` block family, SEO read from the
editor's own record.

*Gate:* `lint-delimiters.py`, `lint-html.py`, and — later — the Site Editor's
Navigation screen listing the menus.

## 7. Content conversion

The bulk. A per-project `CONVERSION-GUIDE.md` is written from
`references/conversion-rules.md`, then agents convert pages in parallel by
family, each reporting its section list and every inline style it could not
map. `apply-style-classes.py` reconciles those in one pass afterwards.

*Produces:* `content/pages/*.html`, `content/posts/*.html`, `pages.json`,
`posts.json`, `terms.json`, `redirects.json`. *Gate:* both linters over
`content/`, and the section lists checked against the sources.

## 8. Importer and setup screen

One admin page, one idempotent import driven as a server-owned state machine —
media, rebind, terms, pages, posts, settings — one slice per request, its
record written after every item, everything it creates flagged (pitfall #5b).
The synchronous whole-import function stays as the CLI path and must not
depend on who calls it (pitfall #5d).

*You are asked:* nothing at this point, but the screen is what the owner will
watch for minutes, so it says that it started, where it is, and what it did.

## 8b. The cleanup

The other direction: every generated theme can take its imported content back
off the site, reading the flags it wrote, never guessing from titles, leaving
the owner's own pages, the photographs they still use and the categories still
in use. Never automatic, never part of switching themes, a dry-run listing
first, a typed confirmation last.

*You are asked:* the typed confirmation, when you run it on a real site. The
agent does not run it on a site it did not just install
([Escalation](../SKILL.md#escalation--when-to-stop-and-ask)).

## 9. Verify

Tier 1 over the files, then a throwaway WordPress built by
`scripts/wp-sandbox/setup.sh`, and the acceptance criteria run against it:
the pixel diff, the editor walk, the forms, the SEO panel, the URLs, the
`debug.log`. Then the editor is opened and looked at. What passes and how to
read the numbers is [verification.md](verification.md).

*You are asked:* to look at the diff images and the moved boxes if a page stays
above the threshold after two rounds of bridge CSS; the agent will not "fix"
it by changing the design's own rules.

## When it stops

The agent stops and asks rather than improvises when the input is not an
html2wp theme, when a page will not come under the visual threshold, when the
source does something core blocks cannot hold, when Visual Edit Lite is not
at hand for two of the gates, when a failure reproduces only on SQLite, and
before anything destructive on a site it did not just install. The list is
[Escalation](../SKILL.md#escalation--when-to-stop-and-ask).
