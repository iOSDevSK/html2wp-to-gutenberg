# Troubleshooting — symptom to pitfall

Every pitfall in [references/pitfalls.md](../references/pitfalls.md) is
numbered and was paid for once. This page goes the other way: from what you
see to the number to read.

| What you see | Read |
|---|---|
| A block opens as "unexpected or invalid content" the first time the page is opened | 1a (delimiter whitespace), 1c (`width`/`height` on an image), 1e (a `\u0026` that lost its backslash), 16b (a deprecated save that passes and migrates silently) |
| A form arrives with its labels and button and nothing between them | 5d — the import ran without a user who can `unfiltered_html`, and kses stripped the controls |
| The form renders, but nobody can edit it; the SEO description typed in the editor never appears | 10b, and `references/forms-and-seo.md` |
| The import says finished and the media library is empty, or the progress bar stops at 64/65 | 5b |
| Pages still point at the theme's own image files after the photographs were imported | 5c — the rebind stage |
| A page is thousands of pixels too tall; sections after some point are inside a section before it | an unclosed wrapper — `lint-html.py` names the line; 1b if a comment sits inside a container |
| Spacing and layout drift from the original although the CSS is verbatim | 3 (core's layout rules outrank yours — `raise-specificity.py`), 7 (the wrapper core added needs a bridge rule) |
| An inline style from the source is gone on the converted page | 6 |
| A page arrived at a `-2` address, or an attachment holds a page's slug | 4 |
| Permalinks did not change after the import | 5 |
| "Hello world!" or the sample page shows up in a dynamic section | 8 |
| A redirect loops | 9 |
| The form looks different only when Contact Form 7 is active | 10 |
| Menus are not in the Site Editor's Navigation screen; Appearance → Menus is back | 12b |
| `__THEME_URI__` in the page source, the JSON-LD or an editor preview | 12, 13 |
| A changed pattern does not show up | 13 — bump the theme version |
| Every template previews as the same expanded menu; broken images in the template thumbnails; an overlay covers the editor canvas | 14, 14a–14d |
| A theme linter reports thousands of files, most of them WordPress core | 11 — the sandbox is inside the theme |
| Duplicate colours, sizes or spacings in the editor's pickers | 2 |
| A script that edited block markup left blocks invalid or whitespace wrong | 16, 16a–16f |
| A repair of stored data blanked or doubled it | 15 |
| Responsive or animation settings vanish on save | 1d, 18 |
| After the cleanup and a second import, pages came back as `-2` versions | 8b in `SKILL.md` — the cleanup left a page behind |
| The sandbox tests run against an old copy of the theme | `sync.sh` names the sandbox theme after the source directory's basename; name the directory after the slug |
| The diff percentage jumps between runs | run one check at a time; a diff measured while the editor walk was running is not a measurement |

Anything not in the table: search `pitfalls.md` for the WordPress function
or block name involved; then, if it is new, it belongs there — see
[CONTRIBUTING.md](../CONTRIBUTING.md).
