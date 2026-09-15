#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Screenshot the original and converted pages side by side and diff them.

This is the check that matches what the conversion actually promised: not that
the markup matches, but that the rendered page does. Both sides are loaded with
reduced motion on, so every scroll reveal resolves immediately and no animation
frame can land differently between two runs (pitfall #11).

    python3 visual-diff.py --original <dir> --live http://127.0.0.1:8899
    python3 visual-diff.py --original <dir> --live http://127.0.0.1:8899 --width 390
    python3 visual-diff.py --original <dir> --live http://127.0.0.1:8899 about contact

--original is the directory render-original.py wrote: one <key>.html per page.
--live is a running WordPress with the converted theme active — the version
that matters, the only one where core's own block styles, the global
stylesheet theme.json generates and the real query loops are in play. A
static preview (--preview <dir> of <key>.html files) can agree with the
original for reasons production would not repeat; the reference's did, at
0.56% against a real 26%.

Each page maps to <live>/<key>/; --path key=/route/ overrides that, and
front-page=/ is the default override.

Writes <out>/<key>-{original,converted,diff}.png and prints a per-page
difference percentage. Exit 1 when any page is at or above --threshold
(default 1.0%) or has no original to compare against.
"""

import sys
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

# A pixel has to be off by more than this on some channel to count as changed.
# Anti-aliased text differs by a shade or two between two identical renders.
CHANNEL_TOLERANCE = 12

SETTLE = """async () => {
  // A full-page screenshot scrolls the document, so lazy images can start
  // loading mid-capture and land in one run but not the next. Force them all in
  // and wait for the decode before anything is measured.
  //
  // srcset is dropped on both sides too. WordPress generates its own responsive
  // sizes and will often pick a 433px file where the static original loads the
  // 1024px one — the same photograph at a different resolution, which reads as
  // a difference on every pixel of it. That is a real improvement, not a
  // regression, and comparing at one resolution is the only way to see whether
  // anything else moved.
  const imgs = [...document.images];
  imgs.forEach(i => { i.removeAttribute('srcset'); i.removeAttribute('sizes'); });
  imgs.forEach(i => { i.loading = 'eager'; });
  await Promise.all(imgs.map(i => i.decode().catch(() => {})));
  await document.fonts.ready;
}"""


def shoot(page, target, width):
    page.set_viewport_size({"width": width, "height": 1200})
    page.goto(target if isinstance(target, str) else target.as_uri())
    page.wait_for_load_state("networkidle")
    page.evaluate(SETTLE)
    # Settle any layout that depends on fonts having arrived.
    page.wait_for_timeout(300)
    return page.screenshot(full_page=True)


def to_array(raw):
    return np.array(Image.open(BytesIO(raw)).convert("RGB"), dtype=np.int16)


def option(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def parse(argv):
    original = option(argv, "--original")
    live = option(argv, "--live")
    preview = option(argv, "--preview")
    if not original or not (live or preview) or (live and preview):
        print("usage: visual-diff.py --original <dir> (--live <url> | --preview <dir>)"
              " [--out <dir>] [--width N] [--threshold PCT] [--path key=/route/ ...] [page ...]",
              file=sys.stderr)
        return None
    paths = {"front-page": "/"}
    consumed = set()
    for i, a in enumerate(argv):
        if a == "--path" and i + 1 < len(argv):
            key, _, route = argv[i + 1].partition("=")
            paths[key] = route
            consumed.add(i + 1)
    for name in ("--original", "--live", "--preview", "--out", "--width", "--threshold"):
        if name in argv:
            consumed.add(argv.index(name) + 1)
    pages = [a for i, a in enumerate(argv) if a and not a.startswith("--") and i not in consumed]
    # Absolute paths: Playwright loads files as file:// URIs, which relative paths cannot become.
    return {
        "original": Path(original).resolve(), "live": live.rstrip("/") if live else None,
        "preview": Path(preview).resolve() if preview else None,
        "out": Path(option(argv, "--out", "preview-diff")).resolve(),
        "width": int(option(argv, "--width", "1440")),
        "threshold": float(option(argv, "--threshold", "1.0")),
        "paths": paths, "pages": pages,
    }


def main(argv):
    opt = parse(argv)
    if opt is None:
        return 2
    if not opt["original"].is_dir():
        print(f"error: {opt['original']} is not a directory", file=sys.stderr)
        return 2
    keys = sorted(p.stem for p in opt["original"].glob("*.html") if p.stem != "index")
    if opt["pages"]:
        missing = [k for k in opt["pages"] if k not in keys]
        if missing:
            print(f"error: no original for {', '.join(missing)}", file=sys.stderr)
            return 2
        keys = [k for k in keys if k in opt["pages"]]
    if not keys:
        print(f"error: no <key>.html pages in {opt['original']}", file=sys.stderr)
        return 2

    opt["out"].mkdir(parents=True, exist_ok=True)
    results = []

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(reduced_motion="reduce", device_scale_factor=1)
        page = context.new_page()

        for key in keys:
            old_file = opt["original"] / f"{key}.html"
            if opt["live"]:
                new_target = opt["live"] + opt["paths"].get(key, f"/{key}/")
            else:
                new_target = opt["preview"] / f"{key}.html"
                if not new_target.exists():
                    results.append((key, None, "no converted page to compare"))
                    continue

            old_png = shoot(page, old_file, opt["width"])
            new_png = shoot(page, new_target, opt["width"])

            a = to_array(old_png)
            b = to_array(new_png)

            h = min(a.shape[0], b.shape[0])
            height_delta = abs(a.shape[0] - b.shape[0])
            a, b = a[:h], b[:h]

            delta = np.abs(a - b).max(axis=2)
            changed = delta > CHANNEL_TOLERANCE
            pct = 100.0 * changed.sum() / changed.size

            # Paint the differing pixels so the report is readable.
            mask = Image.fromarray(np.where(changed[..., None], [255, 0, 90], b).astype(np.uint8))
            mask.save(opt["out"] / f"{key}-diff.png")
            (opt["out"] / f"{key}-original.png").write_bytes(old_png)
            (opt["out"] / f"{key}-converted.png").write_bytes(new_png)

            note = f"height differs by {height_delta}px" if height_delta > 4 else ""
            results.append((key, pct, note))

        browser.close()

    where = f"live WordPress at {opt['live']}" if opt["live"] else f"static preview {opt['preview']}"
    print(f"\nVisual diff at {opt['width']}px — {where}\n" + "-" * 52)
    worst, failed = 0.0, 0
    for key, pct, note in results:
        if pct is None:
            print(f"  !! {key:26s}  {note}")
            failed += 1
            continue
        worst = max(worst, pct)
        flag = "ok " if pct < opt["threshold"] else ("~  " if pct < 5.0 else "!! ")
        if pct >= opt["threshold"]:
            failed += 1
        print(f"  {flag}{key:26s}  {pct:6.2f}% differing pixels  {note}")

    print("-" * 52)
    print(f"  worst page: {worst:.2f}%  (threshold {opt['threshold']}%)")
    print(f"  images in {opt['out']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
