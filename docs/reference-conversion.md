# The reference conversion

[`iOSDevSK/amanda-rose-guttenberg`](https://github.com/iOSDevSK/amanda-rose-guttenberg)
is the worked example this skill was distilled from: the html2wp theme of a
fine-art wedding photography site, converted to a native block theme — slug
`amanda-rose-blocks` — with this method. The repository is private; ask its
owner for access. This page says what is in it and what it proves, so the
skill can be used without it.

## What it holds

- `steps/` — the conversion record, one note per step, with what went wrong
  and what fixed it. `steps/14-forms-blocks-seo.md` is the worked example of
  `references/forms-and-seo.md`.
- `tools/` — where this skill's `scripts/` came from, with the Amanda Rose
  values filled in. The skill's copies take those values as arguments.
- `tests/` — the regression files `references/verification.md` asks every
  generated theme to ship, run with `php tests/run.php <file>` inside a
  WordPress that has the theme active. At 2.4.3: the forms and SEO record,
  the menus, the front page, the resumable import and its rebind, the
  cleanup, and the import running as nobody with kses filtering.
- `content/` — the converted bundle: 15 pages, 10 journal entries, the terms
  and the redirect map.
- `inc/content-import.php` and `inc/content-clean.php` — the state-machine
  importer of SKILL.md step 8 and the cleanup of step 8b, as shipped.
- `inc/form-blocks.php` and `inc/seo.php` — the form block family and the
  SEO record, read at 2.4.1 or later.

## What it measured

Against a real WordPress 7.1 installed from the 2.4.3 release ZIP:

| Check | Result |
|---|---|
| pages and journal entries opened in the block editor | 27 |
| blocks | 1,303 |
| invalid blocks | 0 |
| pixel diff against the original, 1440 px | every page ≤ 0.40 % |
| pixel diff against the original, 390 px | every page ≤ 0.89 % |
| regression files | all green |
| `debug.log` | absent |

## What it got wrong first

The pitfalls file is the long answer. The short one, by release:

- **2.3.0** — the menus were not menus: a navigation block with inline links
  never reaches the Site Editor. One `wp_navigation` post per menu, resolved
  through a pattern registered in code (pitfall #12b).
- **2.4.0** — the forms were a shortcode nobody could edit and the SEO panel
  wrote to a key the theme never read. Forms became blocks the theme
  registers and delivers itself; `inc/seo.php` reads the editor's own record
  (pitfall #10b).
- **2.4.2** — a form's delivery address is part of the form, signed into the
  page so it cannot be retyped into somebody else's inbox.
- **2.4.3** — the import handed WordPress unslashed content and lost a
  backslash (pitfall #1e), and run from the command line it lost every form
  control to kses (pitfall #5d). Both fixed, and a one-shot repair added for
  sites imported before the fix (pitfall #15). Found by this skill's own
  harness, run as scripts.

Each of those is now a gate in `references/verification.md`, which is the
point of keeping the record.
