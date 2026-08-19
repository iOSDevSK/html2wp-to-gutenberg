# Verification — files first, then a real WordPress

Two tiers. The file tier is fast and catches markup mistakes; the WordPress
tier is the acceptance test and is **not optional** — on the reference
conversion the static tier agreed with the original at 0.56% while the real
thing was 26% out, and every fault that mattered (presets, specificity,
permalinks, slug theft, invalid blocks) was findable only in WordPress.

## Tier 1 — files

```bash
python3 <skill>/scripts/lint-delimiters.py <theme-dir>     # WP block grammar (+ --fix)
python3 <skill>/scripts/lint-html.py <theme-dir>           # tag balance inside block markup
node ~/.claude/skills/wp-block-theme-converter/scripts/doctor.mjs <theme-dir>
find <theme-dir> -name '*.php' | xargs -n1 php -l
```

Also lint the content bundle (`content/**/*.html`) for balanced block
comments — the theme doctor does not walk it.

## Tier 2 — throwaway WordPress (SQLite, no server stack)

The reference ships a complete, reusable harness —
`github.com/iOSDevSK/amanda-rose-guttenberg`, directory `tools/`:

- `wp-sandbox/setup.sh` — downloads WP + the sqlite-database-integration
  drop-in (fix its `{SQLITE_IMPLEMENTATION_FOLDER_PATH}` placeholder with a
  plain path string), writes wp-config (`DISABLE_WP_CRON` on), installs,
  rsyncs the theme in, runs the importer. Build it **outside** the theme dir.
- `visual-diff.py --live http://127.0.0.1:8899` — Playwright screenshots of
  every page against the rendered ORIGINAL sources, with the determinism
  fixes baked in: `reduced_motion` context, `loading=eager` + `img.decode()`
  + `fonts.ready` before capture, `srcset`/`sizes` stripped on both sides.
  Serve with `PHP_CLI_SERVER_WORKERS=8` or the editor checks time out.
- `measure-diff.py` — when a page diffs, this names the element: reads
  `getBoundingClientRect` for every design class in both documents and
  prints the boxes that moved. This is the debugging tool; the pixel diff is
  only the alarm.

Adapt paths, don't rewrite the logic.

## Acceptance criteria (all of them)

1. **Visual**: every page ≤ ~1% differing pixels vs the original at 1440px
   AND 390px (reference finished at ≤0.4% / ≤0.9%).
2. **Editor validity**: walk `wp.data.select('core/block-editor')` for every
   page and post — recursive `isValid===false` count must be **0**. Wait on
   the data store (`wp.data… getBlocks().length>0`), not on canvas DOM — the
   canvas is an iframe.
3. **Routes**: every original URL answers — pages 200, legacy `.html` paths
   301 to the right target, old pagination/topic URLs preserved via rewrite
   rules, unknown URLs 404 (and never 301-loop).
4. **Clean logs**: `debug.log` empty through install + import + a crawl of
   every page.
5. **Importer idempotence**: run the import twice; second run creates
   nothing and overwrites nothing.
6. **Animation matrix** (manual or scripted): reveal stagger, hero
   entrance/Ken Burns, marquees looping seamlessly (clone check), overlay
   menu + ESC + focus return, accordions, lightbox (arrows, backdrop,
   keyboard), page transitions, and all `prefers-reduced-motion` branches.
7. If forms use CF7: install it in the sandbox and re-run the visual diff on
   form pages — three layout deltas only appear with the plugin active (see
   pitfalls #10).
8. **No unresolved tokens anywhere a filter cannot reach.** Two greps, both
   must be zero — the second is the one that matters, because `wp_head`
   output never passes through the content filters and a token in JSON-LD is
   invisible until a search engine reads it:

   ```bash
   grep -rn '__THEME_URI__' <theme>/parts <theme>/templates
   for u in / /about/ /journal/ /contact/; do
     curl -s "http://127.0.0.1:8899$u" | grep -c '__THEME_URI__'
   done
   ```

9. **The editor experience is a deliverable, not a side effect.** Open
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

## The Gutenberg validity check, concretely

Criterion 2 is the acceptance test the whole conversion is arranged around,
and only Gutenberg can answer it — validity is decided by re-running each
block's `save()` and comparing byte for byte, which no PHP can do. Drive a
real browser:

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
