# Verification — files first, then a real WordPress

Two tiers. The file tier is fast and catches markup mistakes; the WordPress
tier is the acceptance test and is **not optional** — on the reference
conversion the static tier agreed with the original at 0.56% while the real
thing was 26% out, and every fault that mattered (presets, specificity,
permalinks, slug theft, invalid blocks) was findable only in WordPress.

## Tier 1 — files

```bash
python3 <skill>/scripts/lint-delimiters.py <theme-dir>     # WP block grammar + delimiter pairing (+ --fix)
python3 <skill>/scripts/lint-html.py <theme-dir>           # tag balance inside block markup
node ~/.claude/skills/wp-block-theme-converter/scripts/doctor.mjs <theme-dir>
find <theme-dir> -name '*.php' | xargs -n1 php -l
```

The two Python scripts walk `content/` as well as `parts/`, `templates/` and
`patterns/`; the doctor does not, so the content bundle's delimiter pairing
is theirs. Both exit 2 — not 0 — when the path is wrong or nothing was found:
a green run over zero files is not a pass.

**Expected noise from the doctor.** Its `lint-block-markup` reports every
`style=` attribute it meets. Core blocks write some of those themselves —
`core/spacer`'s height, `core/column`'s `flex-basis` — and the form contract
puts `style="display:contents"` on an `inline` field (`forms-and-seo.md` §2).
Those are not faults; do not strip them. A `style` attribute on a *design*
element is one — that is the inline style `conversion-rules.md` turns into a
utility class.

## Tier 2 — throwaway WordPress (SQLite, no server stack)

The harness is in this skill's `scripts/` (see `scripts/README.md`),
vendored from the reference conversion with every project-specific value
turned into an argument:

```bash
S=<skill>/scripts
# 1. a WordPress beside the theme — the theme rsynced in, installed, imported
IMPORT_FUNCTION=<slug>_run_import bash $S/wp-sandbox/setup.sh <theme-dir>
PHP_CLI_SERVER_WORKERS=8 php -S 127.0.0.1:8899 -t <theme-dir>/../<slug>-sandbox/wordpress &
# 2. the original, composed the way the old runtime composed it
python3 $S/render-original.py --example > render-original.json      # fill in, then:
python3 $S/render-original.py --config render-original.json
# 3. the gates
python3 $S/editor-validity.py --site http://127.0.0.1:8899 --user admin --password admin-password
python3 $S/visual-diff.py  --original preview-original --live http://127.0.0.1:8899
python3 $S/visual-diff.py  --original preview-original --live http://127.0.0.1:8899 --width 390
python3 $S/measure-diff.py --original preview-original --live http://127.0.0.1:8899 \
    --css <theme>/assets/css/site.css <the page that diffed>
```

- `wp-sandbox/setup.sh` — downloads WP + the sqlite-database-integration
  drop-in (fixing its `{SQLITE_IMPLEMENTATION_FOLDER_PATH}` placeholder with
  a plain path string), writes wp-config (`DISABLE_WP_CRON` on, debug log
  on), installs, rsyncs the theme in, runs the importer named in
  `IMPORT_FUNCTION`. Builds **outside** the theme dir and refuses to do
  otherwise; `sync.sh` pushes theme changes in again.
- `render-original.py` — composes the html2wp sources with the old
  header/footer parts, expands `[wp-posts]` from the converted theme's
  `posts.json`, rewrites the `__CLARA_*` tokens to the old theme's files,
  strips `srcset`/`sizes`. Everything project-specific is in its JSON config.
- `visual-diff.py --live` — Playwright screenshots of every page against the
  rendered original, with the determinism fixes baked in: `reduced_motion`
  context, `loading=eager` + `img.decode()` + `fonts.ready` before capture,
  `srcset`/`sizes` stripped on both sides. Exit 1 at or above `--threshold`
  (1%). Serve with `PHP_CLI_SERVER_WORKERS=8` or the editor checks time out.
- `measure-diff.py` — when a page diffs, this names the element: reads
  `getBoundingClientRect` for every design class in both documents and
  prints the boxes that moved. This is the debugging tool; the pixel diff is
  only the alarm.
- `editor-validity.py` — criterion 2, below: logs in, lists every page and
  post through REST, opens each in the editor, walks the data store.

The reference's own copies — `github.com/iOSDevSK/amanda-rose-guttenberg`,
`tools/` — are the same logic with the Amanda Rose values filled in; read
them when a script's intent is unclear.

## Acceptance criteria (all of them)

1. **Visual**: every page ≤ ~1% differing pixels vs the original at 1440px
   AND 390px (reference finished at ≤0.4% / ≤0.9%).
2. **Editor validity**: walk `wp.data.select('core/block-editor')` for every
   page and post — recursive `isValid===false` count must be **0**. Wait on
   the data store (`wp.data… getBlocks().length>0`), not on canvas DOM — the
   canvas is an iframe. Run it twice on the pages holding a form: once with
   Visual Edit Lite absent and once with it active, since both register the
   `clara-ve/*` blocks (step 7).
3. **Routes**: every original URL answers — pages 200, legacy `.html` paths
   301 to the right target, old pagination/topic URLs preserved via rewrite
   rules, unknown URLs 404 (and never 301-loop).
4. **Clean logs**: `debug.log` empty through install + import + a crawl of
   every page.
5. **Importer idempotence**: run the import twice; second run creates
   nothing and overwrites nothing.
5b. **The importer survives being interrupted** — the gate that would have
   caught the reference's worst bug (pitfall #5b), and the only one that
   exercises the host condition every client site actually has. Three runs:

   ```bash
   # (i) kill it mid-media, then let it carry on. Assert the counts, not the exit code.
   php sandbox/media-only.php & PID=$!; ( sleep 4; kill -9 $PID ) & wait $PID
   php sandbox/finish-import.php
   #   → exactly <N> attachments carrying the import flag, and NO `photo-<x>-2` slug.
   #   Before the fix this left 20 attachments, 96 files on disk and an EMPTY record.

   # (ii) drive it the way the browser does: a budget so small each slice does one item.
   #   → percent never decreases, reaches 100, `finished` true, and the stage label changes.

   # (iii) the site that reported the bug: delete every attachment, drop the media
   #   record, restore the pages' raw markup, then re-run the import.
   #   → attachments back, ZERO pages still containing `__THEME_URI__/assets/images/`.
   ```

   Drive it over **HTTP through `admin-ajax.php` with a real login cookie**, not
   only from the CLI. The CLI has no request clock and cannot see the failure
   this gate is about — and the admin page is also where the progress script
   silently failed to print (pitfall #5b's aside). Grep the fetched setup page
   for the script before trusting the loop.

   Ship it as a regression file in the theme (`tests/regression-import-resume.php`
   on the reference) so it is re-run on every later change.
5c. **The menus are editable, and editing one changes the site.** Nothing in
   the pixel or validity tiers looks at this, and the reference shipped with
   menus that could not be edited anywhere (pitfall #12b). Four assertions,
   over HTTP against the real admin:

   - Appearance's submenu has **no** classic `nav-menus.php` entry, and does
     have a link to `site-editor.php?p=%2Fnavigation`.
   - `/wp/v2/navigation?context=edit` lists one menu per menu the design has,
     with the right link counts — not just WordPress's invented fallback.
   - The header part opens in the editor with every navigation block carrying
     a `ref` and `isValid !== false`, and the same number of `<nav>` elements
     drawn in the canvas as the design has.
   - Rename a link in a menu used in two places; assert **both** change on the
     front end.

   Plus the parity check that makes the conversion safe: the rendered `<nav>`
   must be byte-identical before and after the menu post exists.

6. **Animation matrix** (manual or scripted): reveal stagger, hero
   entrance/Ken Burns, marquees looping seamlessly (clone check), overlay
   menu + ESC + focus return, accordions, lightbox (arrows, backdrop,
   keyboard), page transitions, and all `prefers-reduced-motion` branches.
7. **Forms: editable, delivered, and valid on both sides** (pitfall #10b).
   In the sandbox, with no Visual Edit Lite installed:

   - open a form page in the block editor and click a field — its label,
     placeholder and, for a select, its choices must be editable, and the
     button text with it. A single block holding a shortcode is a fail;
   - submit the form on the front end and assert the mail is attempted and
     the redirect or the message happens. A form with `data-demo` or no
     `action` is a fail, whatever it looks like;
   - after a CLI import, the stored `post_content` of every form page still
     contains `<form` and `<input` — kses on a user-less request drops them
     and says nothing (pitfall #5d);
   - then activate Visual Edit Lite 1.27 or later — which registers the same
     `clara-ve/*` names — reload every form page in the editor and assert
     **0 invalid blocks**;
   - and the same trip back: with the plugin active, edit a field and save the
     page, deactivate the plugin, reopen — still **0 invalid**. Each side has
     to re-serialize what the other wrote, so one direction proves half of it.
     This is the drift check; it fails when the theme's attributes or `save`
     output have diverged from the plugin's.

   If the source site used CF7, also install it and re-run the visual diff on
   form pages — three layout deltas only appear with the plugin active
   (pitfalls #10).
8. **Search metadata reaches the page, once** (pitfall #10b). With Visual
   Edit Lite active, type a description into its SEO panel for one page,
   save, then:

   ```bash
   curl -s "http://127.0.0.1:8899/contact/" | grep -c 'og:title'         # exactly 1
   curl -s "http://127.0.0.1:8899/contact/" | grep 'name="description"'  # the typed text
   ```

   Without the plugin, the same page falls back to its excerpt. Two
   `og:title` tags mean the `html2wp-runtime` declaration went missing; an
   unchanged description means the theme is reading its own meta key.
9. **No unresolved tokens anywhere a filter cannot reach.** Two greps, both
   must be zero — the second is the one that matters, because `wp_head`
   output never passes through the content filters and a token in JSON-LD is
   invisible until a search engine reads it:

   ```bash
   grep -rn '__THEME_URI__' <theme>/parts <theme>/templates
   for u in / /about/ /journal/ /contact/; do
     curl -s "http://127.0.0.1:8899$u" | grep -c '__THEME_URI__'
   done
   ```

10. **The editor experience is a deliverable, not a side effect.** Open
   Appearance → Editor → Templates and look at the thumbnails: they must be
   distinguishable from each other. Then open one template and one page.
   Nothing broken, nothing covering the canvas, no placeholder images, no
   text that is technically present but invisible. This is where the client
   will spend their time, and nothing in tiers 1–2 looks at it. Everything in
   pitfalls #12–#14 was found this way, after every automated check was
   green.

   When something is wrong there, measure it in the canvas rather than
   reasoning from the markup — the editor's DOM differs from the front end's
   (#14b), and the visible symptom is often not the cause (#14a):

   ```python
   f = page.frame(name="editor-canvas")
   f.evaluate("() => getComputedStyle(document.querySelector('.nav-links')).gap")
   f.evaluate("() => [...document.querySelector('header.nav').children]"
              ".map(c => c.className.slice(0,60) + ' ' + Math.round(c.getBoundingClientRect().width))")
   ```

11. **If anything WRITES block markup — a script, an importer, an editor —
    the validity check is not enough on its own.** Three assertions have to
    ride with it, each one covering a failure the others miss:

    - **An unedited fixture is valid first.** Otherwise every row fails for a
      reason that has nothing to do with the change under test. Take the
      markup from `wp.blocks.getSaveContent()`, not from memory.
    - **Every attribute written is still readable back** from
      `wp.data.select('core/block-editor').getBlocks()`. `isValid` passes a
      DEPRECATED save, and WordPress migrates such a block silently on the
      next open — the attribute is gone and nothing warns.
    - **Containers still contain their children.** A group, column, quote,
      list, details or cover whose `innerContent` placeholders were flattened
      serializes empty. See pitfall 16a; it is the failure that costs a page.

    Name what the run SKIPPED, too. A block that declares no support for a
    property is correctly not tested — but silent omission reads as coverage.

12. **The import must be removable, and that is a round trip.** A theme that
    installs a site has to be able to take it back off one. Verify by doing
    it, in this order, because each step catches something the others cannot:

    - **clean** → every flagged page, post and unused attachment gone; a page
      the owner wrote themselves still there; a page of theirs that merely
      *looks* imported still there.
    - **the site still answers 200** — the front-page option must not outlive
      the page it names, or the home page 404s for everyone.
    - **import again onto the emptied site** → the pages come back at their
      own addresses, NOT as `about-2`. A cleanup that left one page behind
      still holds its slug, and `wp_unique_post_slug()` does not consider
      post_status for hierarchical types — so this is the only check that
      sees it.

    Run it against a database you have dumped first. It deletes real content,
    and a sandbox somebody is using for other work is not a fixture.

## The Gutenberg validity check, concretely

Criterion 2 is the acceptance test the whole conversion is arranged around,
and only Gutenberg can answer it — validity is decided by re-running each
block's `save()` and comparing byte for byte, which no PHP can do.
`scripts/editor-validity.py` does exactly this over every page and post;
the heart of it:

```python
page.goto(f"{SITE}/wp-admin/post.php?post={page_id}&action=edit")
page.wait_for_function(
    "() => window.wp && wp.data && wp.data.select('core/block-editor')"
    " && wp.data.select('core/block-editor').getBlocks().length > 0",
    timeout=45000)
report = page.evaluate("""() => {
    const walk = (bs, o) => { bs.forEach(b => { o.total++;
        if (b.isValid === false) o.invalid.push(b.name);
        if (b.innerBlocks?.length) walk(b.innerBlocks, o); }); return o; };
    return walk(wp.data.select('core/block-editor').getBlocks(), {total:0, invalid:[]});
}""")
```

Run it over every page AND every post, not a sample: the reference finished
at 1,025 blocks / 0 invalid, and the invalid ones cluster by block type, so
one page of the wrong kind hides fifty faults.

## A note on the SQLite sandbox

The SQLite drop-in is right for this work — no database server, disposable,
fast. Know its one limit: it **throws on binary blob writes**, so anything
gzip-compressed (a plugin's revision history, for instance) fails there and
nowhere else. If a check fails only in the sandbox and the code looks
correct, try a real MariaDB before believing it:

```bash
docker run -d --name wp-mariadb -p 3307:3306 \
  -e MARIADB_ROOT_PASSWORD=wordpress -e MARIADB_DATABASE=wordpress \
  -e MARIADB_USER=wordpress -e MARIADB_PASSWORD=wordpress mariadb:11
```

then point wp-config at `127.0.0.1:3307` and delete `wp-content/db.php`.
