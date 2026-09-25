#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""How "official" a block theme's content is — the numbers behind the claim.

An official WordPress block theme (Twenty Twenty-Five, the Create Block Theme
output) keeps its design in theme.json and has its blocks USE it: a heading
says fontSize "x-large" and textColor "contrast", a section says
layout constrained and padding var:preset|spacing|50. A converted theme that
carries every original class on nested groups renders the same page and
edits like raw HTML. This counts which of the two a theme is, per page and in
total, so a conversion's progress is a number rather than an opinion:

    python3 block-metrics.py <theme-dir>                 every block file the theme ships
    python3 block-metrics.py <theme-dir> --json out.json the same, as data
    python3 block-metrics.py page.html other.html        named block files

What it counts, per block (core/html counted apart: it is not a block
anybody edits as one):

  presets      the block uses a theme.json preset: textColor, backgroundColor,
               fontSize, fontFamily, gradient, borderColor, or any
               var:preset|… in its style
  layout       layout.type flex, grid or constrained (core layout, not a
               wrapper class)
  classes      custom class names in className (is-style-* variations apart)
  styleVars    is-style-* block style variations
and per theme: templates, parts, patterns (patterns/*.php), pattern
references (wp:pattern), the presets theme.json declares, and the chrome —
the block types the parts are made of, the menus the theme ships as
wp_navigation posts and where they are placed (content/menus.json,
content/placements.json), and whether the site's name is core/site-title.

Exit 0; 2 = usage.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

# The block delimiter grammar WordPress's own parser uses (the attributes
# object may hold braces; it ends at the first "}" followed by the closer).
DELIMITER = re.compile(
    r"<!--\s+(?P<closer>/)?wp:(?P<ns>[a-z][a-z0-9_-]*/)?(?P<name>[a-z][a-z0-9_-]*)\s+"
    r"(?P<attrs>{(?:(?:[^}]+|}+(?=})|(?!}\s+/?-->).)*)?}\s+)?(?P<void>/)?-->", re.S)
PRESET_ATTRS = ("textColor", "backgroundColor", "fontSize", "fontFamily", "gradient", "borderColor")


def blocks_in(text):
    """(name, attrs) of every block opener in document order."""
    out = []
    for m in DELIMITER.finditer(text):
        if m.group("closer"):
            continue
        name = (m.group("ns") or "core/") + m.group("name")
        try:
            attrs = json.loads(m.group("attrs")) if m.group("attrs") else {}
        except ValueError:
            attrs = {"__unparsable": True}
        out.append((name, attrs))
    return out


def uses_preset(attrs):
    if any(attrs.get(k) for k in PRESET_ATTRS):
        return True
    return "var:preset|" in json.dumps(attrs.get("style") or {})


def measure(text):
    counts = Counter()
    names = Counter()
    for name, attrs in blocks_in(text):
        names[name] += 1
        counts["blocks"] += 1
        if name == "core/html":
            counts["html"] += 1
            continue
        counts["native"] += 1
        if uses_preset(attrs):
            counts["presets"] += 1
        layout = (attrs.get("layout") or {}).get("type")
        if layout in ("flex", "grid", "constrained"):
            counts["layout"] += 1
        if name == "core/group":
            counts["groups"] += 1
            if layout in ("flex", "grid", "constrained"):
                counts["groupsLayout"] += 1
        classes = str(attrs.get("className") or "").split()
        counts["styleVars"] += sum(1 for c in classes if c.startswith("is-style-"))
        counts["classes"] += sum(1 for c in classes if not c.startswith("is-style-"))
        if name == "core/pattern":
            counts["patternRefs"] += 1
    return counts, names


def summary(counts):
    native = counts["native"] or 0
    pct = lambda n: round(100.0 * n / native, 1) if native else 0.0
    return {
        "blocks": counts["blocks"], "native": native, "html": counts["html"],
        "presetsPct": pct(counts["presets"]), "layoutPct": pct(counts["layout"]),
        "groups": counts["groups"], "groupsCoreLayoutPct": round(100.0 * counts["groupsLayout"] / counts["groups"], 1)
        if counts["groups"] else 0.0,
        "classesPerBlock": round(counts["classes"] / native, 2) if native else 0.0,
        "styleVariations": counts["styleVars"], "patternRefs": counts["patternRefs"],
    }


def theme_files(theme):
    files = []
    for sub in ("templates", "parts", "content", "patterns"):
        base = theme / sub
        if base.is_dir():
            files += sorted(p for p in base.rglob("*") if p.suffix in (".html", ".php") and p.is_file())
    return files


def declared_presets(theme):
    doc = json.loads((theme / "theme.json").read_text()) if (theme / "theme.json").is_file() else {}
    s = doc.get("settings") or {}
    return {
        "palette": len((s.get("color") or {}).get("palette") or []),
        "fontFamilies": len((s.get("typography") or {}).get("fontFamilies") or []),
        "fontSizes": len((s.get("typography") or {}).get("fontSizes") or []),
        "spacingSizes": len((s.get("spacing") or {}).get("spacingSizes") or []),
    }


def chrome(theme):
    """What the header and footer are made of."""
    types = Counter()
    for f in sorted((theme / "parts").glob("*.html")) if (theme / "parts").is_dir() else []:
        for name, _ in blocks_in(f.read_text(encoding="utf-8", errors="replace")):
            types[name] += 1
    def load(name):
        f = theme / "content" / name
        return json.loads(f.read_text()) if f.is_file() else []
    menus, placements = load("menus.json"), load("placements.json")
    return {"partBlocks": dict(types.most_common()), "menus": len(menus),
            "menuItems": sum(len(m.get("items") or []) for m in menus), "navigationPlacements": len(placements),
            "siteTitle": types.get("core/site-title", 0) > 0}


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    out_json = argv[argv.index("--json") + 1] if "--json" in argv else ""
    if out_json in args:
        args.remove(out_json)
    if not args:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 2
    theme = Path(args[0])
    files = theme_files(theme) if len(args) == 1 and theme.is_dir() else [Path(a) for a in args]
    total, names, pages = Counter(), Counter(), {}
    for f in files:
        c, n = measure(f.read_text(encoding="utf-8", errors="replace"))
        total.update(c)
        names.update(n)
        key = str(f.relative_to(theme)) if theme.is_dir() and theme in f.parents else str(f)
        pages[key] = summary(c)
    report = {"total": summary(total), "files": pages, "blockTypes": dict(names.most_common())}
    if theme.is_dir():
        report["theme"] = {
            "templates": len(list((theme / "templates").glob("*.html"))) if (theme / "templates").is_dir() else 0,
            "parts": len(list((theme / "parts").glob("*.html"))) if (theme / "parts").is_dir() else 0,
            "patterns": len(list((theme / "patterns").glob("*.php"))) if (theme / "patterns").is_dir() else 0,
            "styleVariations": len(list((theme / "styles").glob("*.json"))) if (theme / "styles").is_dir() else 0,
            "declaredPresets": declared_presets(theme),
            "chrome": chrome(theme),
        }
    if out_json:
        Path(out_json).write_text(json.dumps(report, indent=2) + "\n")
    t = report["total"]
    print(f"blocks {t['blocks']} (native {t['native']}, core/html {t['html']}) · presets {t['presetsPct']}% · "
          f"core layout {t['layoutPct']}% (groups {t['groupsCoreLayoutPct']}% of {t['groups']}) · "
          f"classes/block {t['classesPerBlock']} · "
          f"style variations {t['styleVariations']} · pattern refs {t['patternRefs']}")
    if "theme" in report:
        th = report["theme"]
        print(f"theme: {th['templates']} templates, {th['parts']} parts, {th['patterns']} patterns, "
              f"presets declared {th['declaredPresets']}")
        ch = th["chrome"]
        print(f"chrome: {ch['menus']} menus ({ch['menuItems']} links) in {ch['navigationPlacements']} navigation "
              f"placements, site title {'yes' if ch['siteTitle'] else 'no'}; part blocks {ch['partBlocks']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
