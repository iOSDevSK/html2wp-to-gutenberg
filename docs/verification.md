# Reading the verification

The criteria are in [references/verification.md](../references/verification.md);
this page is about the output the harness prints and what counts as a pass.

## Tier 1 — files

`lint-delimiters.py` and `lint-html.py` print one line per finding,
`file:line: message`, then a count. Zero findings and exit 0 is a pass. Exit 2
means the directory was wrong or held nothing to check — not a pass, however
green it looks. The wp-block-theme-converter doctor has its own noise on a
converted theme; `references/verification.md` says which of its lines to
ignore. `php -l` over every PHP file.

## Tier 2 — a real WordPress

`scripts/wp-sandbox/setup.sh` builds it; from then on the sandbox is served
with PHP's own server:

```bash
PHP_CLI_SERVER_WORKERS=8 php -S 127.0.0.1:8899 -t <sandbox>/wordpress
```

The workers matter: the block editor opens dozens of requests at once, and a
single-threaded server makes the editor walk time out and the diff run slow.
Run one check at a time — the pixel diff measured while the editor walk was
running came out at 3.43 % on a page that measures 0.40 % on an idle server.

### The pixel diff

`visual-diff.py` prints a line per page with the percentage of pixels that
differ, and writes three images per page to `--out`: the original, the
converted page and the diff. **Pass:** every page at or under the threshold
(about 1 %) at both 1440 px and 390 px, with the residue being text
anti-aliasing and nothing else. A page above the threshold goes to
`measure-diff.py`, which lists the design classes whose boxes moved, largest
first; the fix is bridge CSS for the wrapper that moved them, never a change
to the design's own rule.

### The editor walk

`editor-validity.py` prints one row per page and post — type, id, slug,
status, block count, invalid count — and a summary line. **Pass:** `0 invalid,
0 failed to load` across every page and post, then the same run again with
Visual Edit Lite active, which registers the same form blocks and must agree
with the theme's own registration. A block the editor calls invalid is one it
will rebuild from its attributes on "Attempt block recovery", losing whatever
the saved HTML had that the attributes do not; the pitfalls under
`pitfalls.md` §1 are the usual reasons.

### The rest

- **Forms:** submitted with the plugin deactivated, the mail composed and
  `Reply-To` set, the redirect followed; then every field's label,
  placeholder and choices edited in the editor and the change seen on the
  page.
- **SEO:** a description typed into the editor's panel appears in the page
  source once, not twice.
- **URLs:** every address from the old site answers 200 or an intentional 301.
- **`debug.log`:** absent or empty after the whole run. A notice is a finding.
- **`__THEME_URI__`:** grep the rendered pages, `parts/`, `templates/` and the
  JSON-LD in the page head. Nothing.
- **The import, twice:** the second run reports that everything was already in
  place and creates nothing. Then the cleanup, then the import again, and the
  pages come back at their own addresses rather than as `-2` versions.

### Then look

Appearance → Editor → Templates: distinguishable thumbnails, no broken images,
no overlay covering the canvas. Nothing automated examines the screen the
owner will work in, and on the reference two real defects lived only there.

## What the reference measured

Against a real WordPress 7.1 installed from the 2.4.3 release ZIP: 1,303
blocks across 27 pages and posts, 0 invalid; every page within 0.40 % at 1440
px and 0.89 % at 390 px; the theme's regression files all green;
`debug.log` absent. Those are the numbers a new conversion is measured
against, not a target to beat: a design with more text will sit a little
higher on the diff from anti-aliasing alone.
