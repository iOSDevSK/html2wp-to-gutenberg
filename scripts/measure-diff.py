#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Compare the geometry of the original and converted pages, element by element.

A screenshot diff says a page is wrong. This says where. For every design class
that appears in both documents it reads the browser's own layout box and
reports the ones that moved, which is usually enough to name the rule that
needs fixing. The pixel diff is the alarm; this is the debugging tool.

    python3 measure-diff.py --original <dir> --live http://127.0.0.1:8899 \\
        --css <theme>/assets/css/site.css privacy
    python3 measure-diff.py --original <dir> --live ... --css ...    # every page, worst offenders

--css is the design's stylesheet: every class it defines is measured. Classes
after the --marker line (default "BLOCK BRIDGE") are skipped — they exist only
on the converted side. --path key=/route/ maps a page to its live address,
front-page=/ by default.

Exit status: 0 measured, 2 usage.
"""

import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

# Anything smaller than this is sub-pixel noise between two layout passes.
TOLERANCE = 2.0

SCRIPT = """
(classes) => {
  const out = {};
  for (const c of classes) {
    const els = document.querySelectorAll('.' + CSS.escape(c));
    if (!els.length) continue;
    out[c] = [...els].map(el => {
      const r = el.getBoundingClientRect();
      return [
        Math.round(r.x), Math.round(r.y + window.scrollY),
        Math.round(r.width), Math.round(r.height)
      ];
    });
  }
  return out;
}
"""


def design_classes(css_path, marker):
    """Every class the design's own stylesheet defines."""
    css = css_path.read_text(encoding="utf-8")
    css = css.split(marker)[0]  # stop before the bridge
    found = set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9_-]*)", css))
    skip = {"js", "in", "open", "show", "hide", "webp", "png", "html", "css"}
    return sorted(c for c in found if c not in skip and not c.startswith("wp-"))


def measure(page, target, classes, width):
    page.set_viewport_size({"width": width, "height": 1200})
    page.goto(target if isinstance(target, str) else target.as_uri())
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)
    return page.evaluate(SCRIPT, classes)


def compare(old, new, limit):
    rows = []
    for cls, old_rects in old.items():
        new_rects = new.get(cls)
        if not new_rects:
            rows.append((cls, None, f"missing in converted ({len(old_rects)} in original)"))
            continue
        if len(old_rects) != len(new_rects):
            rows.append((cls, None, f"count {len(old_rects)} → {len(new_rects)}"))
            continue
        for i, (a, b) in enumerate(zip(old_rects, new_rects)):
            dx, dy, dw, dh = (b[j] - a[j] for j in range(4))
            worst = max(abs(dx), abs(dw), abs(dh))
            if worst > TOLERANCE:
                note = []
                if abs(dx) > TOLERANCE:
                    note.append(f"x{dx:+d}")
                if abs(dw) > TOLERANCE:
                    note.append(f"w{dw:+d}")
                if abs(dh) > TOLERANCE:
                    note.append(f"h{dh:+d}")
                rows.append((f"{cls}[{i}]", worst, " ".join(note)))

    rows.sort(key=lambda r: (r[1] is not None, -(r[1] or 0)))
    return rows[:limit]


def option(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def main(argv):
    original = option(argv, "--original")
    live = option(argv, "--live")
    preview = option(argv, "--preview")
    css = option(argv, "--css")
    if not original or not css or not (live or preview) or (live and preview):
        print("usage: measure-diff.py --original <dir> (--live <url> | --preview <dir>) --css <site.css>"
              " [--width N] [--limit N] [--marker TEXT] [--path key=/route/ ...] [page ...]",
              file=sys.stderr)
        return 2
    original, css = Path(original).resolve(), Path(css).resolve()  # file:// needs absolute
    if not original.is_dir() or not css.is_file():
        print(f"error: {original} must be a directory and {css} a file", file=sys.stderr)
        return 2

    paths, consumed = {"front-page": "/"}, set()
    for i, a in enumerate(argv):
        if a == "--path" and i + 1 < len(argv):
            key, _, route = argv[i + 1].partition("=")
            paths[key] = route
            consumed.add(i + 1)
    for name in ("--original", "--live", "--preview", "--css", "--width", "--limit", "--marker"):
        if name in argv:
            consumed.add(argv.index(name) + 1)
    wanted = [a for i, a in enumerate(argv) if a and not a.startswith("--") and i not in consumed]
    width = int(option(argv, "--width", "1440"))
    limit = int(option(argv, "--limit", "25" if wanted else "8"))
    classes = design_classes(css, option(argv, "--marker", "BLOCK BRIDGE"))

    keys = sorted(p.stem for p in original.glob("*.html") if p.stem != "index")
    if wanted:
        keys = [k for k in keys if k in wanted]
    if not keys:
        print(f"error: no pages to measure in {original}", file=sys.stderr)
        return 2

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context(reduced_motion="reduce", device_scale_factor=1)
        page = context.new_page()

        for key in keys:
            if live:
                target = live.rstrip("/") + paths.get(key, f"/{key}/")
            else:
                target = Path(preview).resolve() / f"{key}.html"
                if not target.exists():
                    print(f"\n{key}\n{'-' * 60}\n  no converted page")
                    continue

            old = measure(page, original / f"{key}.html", classes, width)
            new = measure(page, target, classes, width)
            rows = compare(old, new, limit)

            print(f"\n{key}")
            print("-" * 60)
            if not rows:
                print("  identical within tolerance")
            for cls, worst, note in rows:
                print(f"  {cls:34s} {note}")

        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
