#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""The design's tokens, as theme.json presets and a class → block-attribute map.

An official block theme keeps its design in theme.json — a palette, font
families, a type scale, a spacing scale — and its blocks use those presets.
An html2wp theme's design is a stylesheet whose rules read custom properties
(`:root{--ember:…}` and `.text-ember{color:var(--ember)}`): the tokens are
already there, named by the designer. This reads them out of the stylesheet
and the classes the pages actually use; it invents nothing.

    python3 extract-tokens.py <old-theme> --css assets/site.css --out tokens.json
    python3 extract-tokens.py <old-theme> --css … --out tokens.json --theme-json theme.json

tokens.json:

  presets    palette, fontFamilies, fontSizes, spacingSizes — only what a used
             class reads, slugs from the design's own variable names
             (--ember → "ember", --text-2xl → "2-xl", calc(var(--spacing)*5)
             → "5"), values resolved to literals
  classes    for every used class whose rule is one token: the block
             attribute that says the same (textColor, backgroundColor,
             borderColor, fontFamily, fontSize (+ the line height it carried),
             lineHeight, padding/margin sides, blockGap, and the layout
             properties convert-source.py reads)
  properties the CSS properties every class sets, variants included
             (md:px-10 → padding-inline): a class converts only when no other
             class on the element touches the same property
  layout     contentSize: the most used centred max width less its widest
             padding (what core's constrained layout measures)
  aliases    for every variable a preset came from, the preset variable it
             now reads (--ember → var(--wp--preset--color--ember)):
             scaffold-theme.py points the design's own :root at theme.json,
             so a colour changed in Styles reaches the classes that stayed
             classes too, and the token is defined once

--theme-json merges the presets into a theme.json (settings.color.palette,
typography.fontFamilies/fontSizes, spacing.spacingSizes, with core's defaults
off) and prints it or writes it there.

Exit 0; 2 = usage.
"""
import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ESCAPE = re.compile(r"\\([0-9a-fA-F]{1,6}\s?|.)")


def unescape(ident):
    def one(m):
        s = m.group(1)
        if re.fullmatch(r"[0-9a-fA-F]{1,6}\s?", s):
            return chr(int(s.strip(), 16))
        return s
    return ESCAPE.sub(one, ident)


def strip_comments(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def rules(css, context=()):
    """(selector, declarations, context) for every style rule; context is the
    chain of enclosing at-rules (@media …, @supports …; @layer is not one)."""
    i, n = 0, len(css)
    while i < n:
        j = css.find("{", i)
        if j < 0:
            return
        head = css[i:j].strip()
        depth, k = 1, j + 1
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        body = css[j + 1:k - 1]
        if head.startswith("@"):
            if head.startswith(("@media", "@supports", "@container")):
                yield from rules(body, context + (head,))
            elif head.startswith("@layer") or head.startswith("@scope"):
                yield from rules(body, context)
            # @keyframes, @font-face, @property: not rules a class sets
        else:
            if "{" in body:
                yield from rules(body, context)  # nested rule blocks
            else:
                yield head, body, context
        i = k


def declarations(body):
    out = {}
    for part in re.split(r";(?![^(]*\))", body):
        if ":" in part:
            k, v = part.split(":", 1)
            k = k.strip()
            if k:
                out[k] = v.strip()
    return out


def class_of(selector):
    """The class a selector is about, and its variant (pseudo-class, media):
    '.md\\:px-10' → ('md:px-10', ''); '.hover\\:x:hover' → ('hover:x', ':hover').
    None for anything that is not one class."""
    m = re.fullmatch(r"\.((?:\\.|[\w-])+)((?::{1,2}[\w-]+(?:\([^)]*\))?)*)", selector.strip())
    return (unescape(m.group(1)), m.group(2)) if m else None


def base_utility(name):
    """md:hover:px-10 → px-10 (variant prefixes off)."""
    depth, cut = 0, 0
    for i, ch in enumerate(name):
        if ch in "[(":
            depth += 1
        elif ch in "])":
            depth -= 1
        elif ch == ":" and depth == 0:
            cut = i + 1
    return name[cut:]


def root_vars(css):
    out = {}
    for sel, body, ctx in rules(css):
        if ctx:
            continue
        if any(s.strip() in (":root", ":host", "html") for s in sel.split(",")):
            for k, v in declarations(body).items():
                if k.startswith("--"):
                    out[k] = v
    return out


def resolve(value, env, depth=0):
    """var(--x, fallback) substituted from env, recursively."""
    if depth > 12:
        return value
    def sub(m):
        name, fallback = m.group(1).strip(), (m.group(2) or "").strip()
        if name in env:
            return resolve(env[name], env, depth + 1)
        return resolve(fallback, env, depth + 1) if fallback else m.group(0)
    prev = None
    while prev != value:
        prev = value
        value = re.sub(r"var\(\s*(--[\w-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)", sub, value)
    return value


def source_var(var, env):
    """The variable in a var() chain that holds the literal (--color-ember →
    --ember when :root says --color-ember:var(--ember))."""
    seen = set()
    while var in env and var not in seen:
        seen.add(var)
        m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*\)", env[var].strip())
        if not m:
            return var
        var = m.group(1)
    return None


def calc_rem(value):
    """calc(.25rem * 5) → 1.25 (rem), a bare rem value → its number; else None."""
    v = value.replace(" ", "")
    m = re.fullmatch(r"calc\(([\d.]+)rem\*(-?[\d.]+)\)", v) or re.fullmatch(r"calc\((-?[\d.]+)\*([\d.]+)rem\)", v)
    if m:
        return round(float(m.group(1)) * float(m.group(2)), 4)
    m = re.fullmatch(r"(-?[\d.]+)rem", v)
    return float(m.group(1)) if m else None


def num(x):
    return ("%g" % x)


def slug(text):
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", text.lower())).strip("-")


def kebab_num(n):
    """A spacing step as a slug: 5 → '5', 2.5 → '2-5'."""
    return num(n).replace(".", "-")


def label(s):
    return " ".join(w.upper() if re.fullmatch(r"\d*x[sl]", w) else w.capitalize() for w in s.replace("-", " ").split())


RESERVED_COLOR_SLUGS = {"text", "border", "link", "heading", "button"}
COLOR_PROPS = {"color": "textColor", "background-color": "backgroundColor", "border-color": "borderColor"}
SIDES = {
    "padding": ("top", "right", "bottom", "left"), "padding-inline": ("left", "right"),
    "padding-block": ("top", "bottom"), "padding-top": ("top",), "padding-right": ("right",),
    "padding-bottom": ("bottom",), "padding-left": ("left",),
    "margin": ("top", "right", "bottom", "left"), "margin-inline": ("left", "right"),
    "margin-block": ("top", "bottom"), "margin-top": ("top",), "margin-right": ("right",),
    "margin-bottom": ("bottom",), "margin-left": ("left",),
}
LAYOUT_PROPS = {"display", "align-items", "justify-content", "flex-direction", "flex-wrap", "grid-template-columns"}


def used_classes(theme, sources):
    counts = Counter()
    files = [p for d in sources for p in sorted((theme / d).rglob("*.html"))]
    for f in files:
        for m in re.finditer(r'\bclass="([^"]*)"', f.read_text(encoding="utf-8", errors="replace")):
            counts.update(m.group(1).split())
    return counts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("theme", help="the html2wp theme directory")
    ap.add_argument("--css", action="append", required=True, help="the design's stylesheet(s), relative to the theme")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sources", action="append", default=None,
                    help="directories of markup whose classes count as used (default clara-content/sources, parts)")
    ap.add_argument("--theme-json", default="", help="merge the presets into this theme.json")
    args = ap.parse_args(argv)
    theme = Path(args.theme)
    css = "\n".join(strip_comments((theme / c).read_text(encoding="utf-8", errors="replace")) for c in args.css)
    env = root_vars(css)
    used = used_classes(theme, args.sources or ["clara-content/sources", "parts"])

    # Every class the stylesheet styles: its base rule (no media, no pseudo)
    # and the properties every variant of it sets.
    base, props, anyrule, conditional = {}, {}, {}, {}
    for sel, body, ctx in rules(css):
        decl = declarations(body)
        for one in sel.split(","):
            got = class_of(one)
            if not got:
                continue
            name, pseudo = got
            props.setdefault(name, set()).update(k for k in decl if not k.startswith("--"))
            anyrule.setdefault(name, decl)
            if not ctx and not pseudo and name not in base:
                base[name] = decl
            elif ctx and not pseudo:
                # A progressive enhancement of the same class (a colour with
                # opacity: a plain fallback, then color-mix under @supports):
                # the base rule is not what renders, so it is no token.
                conditional.setdefault(name, set()).update(k for k in decl if not k.startswith("--"))

    palette, families, sizes, spacing = {}, {}, {}, {}
    mapping, aliases = {}, {}

    def alias(var, kind, name, value):
        src = source_var(var, env)
        if src and resolve(f"var({src})", env) == value:
            aliases.setdefault(src, f"var(--wp--preset--{kind}--{name})")

    def color_token(value):
        m = re.fullmatch(r"var\(\s*(--[\w-]+)\s*\)", value)
        if not m:
            return None
        var = m.group(1)
        name = re.sub(r"^--(color-)?", "", var)
        # WordPress's own generic classes: a colour called "border" would make
        # has-border-color — the marker every bordered block carries — paint
        # its TEXT in that colour.
        if slug(name) in RESERVED_COLOR_SLUGS:
            name = f"{name}-tone"
        literal = resolve(value, env)
        if "var(" in literal or not literal:
            return None
        palette.setdefault(slug(name), literal)
        alias(var, "color", slug(name), palette[slug(name)])
        return slug(name)

    for cls in used:
        decl = {k: v for k, v in (base.get(cls) or {}).items() if not k.startswith("--")}
        if not decl or set(decl) & conditional.get(cls, set()):
            continue
        keys = set(decl)
        out = {}
        if len(keys) == 1 and next(iter(keys)) in COLOR_PROPS:
            prop = next(iter(keys))
            token = color_token(decl[prop])
            if token:
                out[COLOR_PROPS[prop]] = token
        elif keys == {"font-family"}:
            m = re.fullmatch(r"var\(\s*--font-([\w-]+)\s*\)", decl["font-family"])
            if m and "var(" not in resolve(decl["font-family"], env):
                families.setdefault(slug(m.group(1)), resolve(decl["font-family"], env))
                alias(f"--font-{m.group(1)}", "font-family", slug(m.group(1)), families[slug(m.group(1))])
                out["fontFamily"] = slug(m.group(1))
        elif keys == {"font-size", "line-height"} or keys == {"font-size"}:
            m = re.fullmatch(r"var\(\s*--text-([\w-]+)\s*\)", decl["font-size"])
            if m:
                name = slug(re.sub(r"(\d)([a-z])", r"\1-\2", m.group(1)))
                sizes.setdefault(name, resolve(decl["font-size"], env))
                alias(f"--text-{m.group(1)}", "font-size", name, sizes[name])
                out["fontSize"] = name
                lh = resolve(decl.get("line-height", ""), env)
                lh = re.sub(r"^var\(--tw-leading,\s*(.*)\)$", r"\1", lh)
                mm = re.fullmatch(r"calc\(\s*([\d.]+)\s*/\s*([\d.]+)\s*\)", lh)
                if mm:
                    # Full precision: 1.3333 × 24px is 31.9992px, and a page of
                    # such lines drifts a pixel from the design's calc(2/1.5).
                    lh = ("%.10f" % (float(mm.group(1)) / float(mm.group(2)))).rstrip("0").rstrip(".")
                if lh and "var(" not in lh:
                    out["lineHeight"] = lh
        elif keys == {"line-height"}:
            lh = resolve(decl["line-height"], env)
            if "var(" not in lh:
                out["lineHeight"] = lh
        elif len(keys) == 1 and next(iter(keys)) in SIDES:
            prop = next(iter(keys))
            rem = calc_rem(resolve(decl[prop], env))
            if rem is not None and rem >= 0:
                step = round(rem / 0.25, 4) if abs(rem / 0.25 - round(rem / 0.25, 4)) < 1e-6 else None
                key = kebab_num(step) if step is not None else kebab_num(rem)
                spacing.setdefault(key, f"{num(rem)}rem")
                out["padding" if prop.startswith("padding") else "margin"] = {s: key for s in SIDES[prop]}
        elif keys <= {"gap", "row-gap", "column-gap"} and len(keys) == 1:
            prop = next(iter(keys))
            rem = calc_rem(resolve(decl[prop], env))
            if rem is not None:
                step = round(rem / 0.25, 4)
                key = kebab_num(step)
                spacing.setdefault(key, f"{num(rem)}rem")
                out["blockGap"] = {"gap": key, "row-gap": {"top": key}, "column-gap": {"left": key}}[prop]
        elif keys <= LAYOUT_PROPS:
            out["layout"] = decl
        if out:
            mapping[cls] = out

    # The centred wrapper core's constrained layout replaces: mx-auto with a
    # max width. contentSize is that width less the widest padding the same
    # element carries (core measures the content box, the design the border box).
    widths = Counter()
    for f in [p for d in (args.sources or ["clara-content/sources", "parts"]) for p in sorted((theme / d).rglob("*.html"))]:
        for m in re.finditer(r'\bclass="([^"]*)"', f.read_text(encoding="utf-8", errors="replace")):
            cls = m.group(1).split()
            if "mx-auto" not in cls:
                continue
            maxw = [c for c in cls if c.startswith("max-w-") and ":" not in c]
            pads = [c for c in cls if base_utility(c).startswith(("px-", "p-"))]
            if len(maxw) != 1:
                continue
            mw = resolve((base.get(maxw[0]) or {}).get("max-width", ""), env)
            px = [calc_rem(resolve(v, env)) for c in pads for k, v in (anyrule.get(c) or {}).items()
                  if k in ("padding-inline", "padding")]
            m2 = re.fullmatch(r"(\d+)px", mw)
            if m2:
                pad = max([p for p in px if p is not None] or [0]) * 16
                widths[(int(m2.group(1)), int(pad))] += 1
    layout = {}
    if widths:
        (mw, pad), _ = widths.most_common(1)[0]
        layout = {"contentSize": f"{mw - 2 * pad}px", "wideSize": f"{mw - 2 * pad}px", "fromMaxWidth": f"{mw}px",
                  "padding": f"{pad}px"}

    # The families the design names, used or the page's own default.
    for var, value in env.items():
        m = re.fullmatch(r"--font-([\w-]+)", var)
        if m and m.group(1) != "mono" and not re.fullmatch(r"[\d.]+", resolve(value, env).strip()) \
                and "var(" not in resolve(value, env):
            referenced = any(f"var({var})" in v for d in base.values() for v in d.values()) or \
                resolve(env.get("--default-font-family", ""), env) == resolve(value, env)
            if referenced:
                families.setdefault(slug(m.group(1)), resolve(value, env))
                alias(var, "font-family", slug(m.group(1)), families[slug(m.group(1))])
    presets = {
        "palette": [{"slug": s, "color": v, "name": label(s)} for s, v in sorted(palette.items())],
        "fontFamilies": [{"slug": s, "fontFamily": v, "name": label(s)} for s, v in sorted(families.items())],
        "fontSizes": sorted(({"slug": s, "size": v, "name": label(s)} for s, v in sizes.items()),
                            key=lambda x: calc_rem(x["size"]) or 0),
        "spacingSizes": sorted(({"slug": s, "size": v, "name": s.replace("-", ".")} for s, v in spacing.items()),
                               key=lambda x: calc_rem(x["size"]) or 0),
    }
    doc = {"presets": presets, "classes": mapping,
           "properties": {c: sorted(p) for c, p in sorted(props.items())}, "layout": layout,
           "aliases": dict(sorted(aliases.items())),
           "used": dict(used.most_common())}
    Path(args.out).write_text(json.dumps(doc, indent=2) + "\n")

    if args.theme_json:
        path = Path(args.theme_json)
        tj = json.loads(path.read_text()) if path.is_file() else {"$schema": "https://schemas.wp.org/wp/6.8/theme.json", "version": 3}
        s = tj.setdefault("settings", {})
        s.setdefault("color", {}).update({"defaultPalette": False, "defaultGradients": False, "defaultDuotone": False,
                                          "palette": presets["palette"]})
        s.setdefault("typography", {}).update({"defaultFontSizes": False, "fluid": False,
                                               "fontFamilies": presets["fontFamilies"], "fontSizes": presets["fontSizes"]})
        s.setdefault("spacing", {}).update({"defaultSpacingSizes": False, "spacingSizes": presets["spacingSizes"]})
        if layout:
            s.setdefault("layout", {}).update({"contentSize": layout["contentSize"], "wideSize": layout["wideSize"]})
        path.write_text(json.dumps(tj, indent="\t") + "\n")
    print(f"extract-tokens: {len(presets['palette'])} colours, {len(presets['fontFamilies'])} font families, "
          f"{len(presets['fontSizes'])} font sizes, {len(presets['spacingSizes'])} spacing steps; "
          f"{len(mapping)} of {len(used)} used classes map to a block attribute"
          + (f"; contentSize {layout['contentSize']}" if layout else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
