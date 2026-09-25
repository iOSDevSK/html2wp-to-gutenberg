#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""The sibling block theme, scaffolded the way an official one is laid out.

    python3 scaffold-theme.py --old <html2wp-theme> --tokens tokens.json \\
        --out <new-theme> --slug mara-vidal-blocks --name "Mara Vidal Blocks" \\
        --css assets/styles.css [--js assets/spa-runtime.js] [--fonts-url URL] \\
        [--media-url http://site/wp-content/themes/<slug>/assets/images] [--presets on|off]

What it writes (SKILL.md steps 2, 4, 6; convert-source.py does the pages):

  theme.json     v3, the design tokens as presets (extract-tokens.py): palette,
                 font families, font sizes, spacing scale — core's own
                 defaults off — contentSize/wideSize from the design's centred
                 width, and a root block gap of 0 with blockGap on, so every
                 gap is a block's own preset and nothing is implied
  templates/     index, page, front-page: the design's page shell (a group with
                 its own classes) around the header part, a <main> group, the
                 post content and the footer part
  parts/         header and footer, converted from the source's own chrome
  content/       every page source as block markup (convert-source.py)
  assets/        the design's stylesheet UNLAYERED and raised by one :root
                 (pitfall #3: core's layout rules are unlayered, so a layered
                 utility loses to them whatever its specificity), its :root
                 variables pointed at the presets they became, its scripts,
                 its images, and bridge.css — only what core's own wrappers
                 need (the <figure> an image gains, a background's padding)
  functions.php  enqueues all of it, the editor included; style.css and
                 readme.txt with the headers Theme Check requires (carried from
                 the source; an author it lacks comes from --author or stays out)

Exit 0; 2 = usage.
"""
import argparse
import datetime
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, HERE / file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def unlayer(css):
    """@layer x{…} → its rules, in place; `@layer a,b;` statements dropped.
    The source order IS the layer order a utility-first build emits (theme,
    base, components, utilities), so unwrapping keeps the design's cascade."""
    out, i, n = [], 0, len(css)
    while i < n:
        m = re.compile(r"@layer\b[^;{]*([;{])").search(css, i)
        if not m:
            out.append(css[i:])
            break
        out.append(css[i:m.start()])
        if m.group(1) == ";":
            i = m.end()
            continue
        depth, k = 1, m.end()
        while k < n and depth:
            if css[k] == "{":
                depth += 1
            elif css[k] == "}":
                depth -= 1
            k += 1
        out.append(unlayer(css[m.end():k - 1]))
        i = k
    return "".join(out)


def style_header(path):
    """A theme's style.css header fields ({"Author": "…", …}); empty values dropped."""
    text = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
    m = re.search(r"/\*(.*?)\*/", text, re.S)
    out = {}
    for line in (m.group(1) if m else "").splitlines():
        k, sep, v = line.partition(":")
        if sep and v.strip():
            out[k.strip()] = v.strip()
    return out


def point_at_presets(css, aliases):
    """The design's top-level :root variables read theme.json's presets
    (--ember:oklch(…) → --ember:var(--wp--preset--color--ember)), so the token
    is defined once and a colour or size changed in Styles reaches the classes
    that stayed classes as well as the blocks. Same value, so the page renders
    the same; a :root inside @media or @supports (a dark scheme, a fallback)
    is the design's own and is left alone."""
    if not aliases:
        return css
    names = "|".join(re.escape(k) for k in sorted(aliases, key=len, reverse=True))
    decl = re.compile(r"(?<![\w-])(" + names + r")\s*:[^;{}]*")
    spans, depth, boundary = [], 0, 0
    for m in re.finditer(r"[{};]", css):
        if m.group() == ";":
            if depth == 0:
                boundary = m.end()
            continue
        if m.group() == "}":
            depth -= 1
            if depth == 0:
                boundary = m.end()
            continue
        depth += 1
        end = css.find("}", m.end())
        if depth == 1 and "{" not in css[m.end():end] and \
                ":root" in [x.strip() for x in css[boundary:m.start()].split(",")]:
            spans.append((m.end(), end))
    for a, b in reversed(spans):
        css = css[:a] + decl.sub(lambda d: f"{d.group(1)}:{aliases[d.group(1)]}", css[a:b]) + css[b:]
    return css


BRIDGE = """/* Block bridge — only what core's own wrappers change (SKILL.md step 4). */
:root :where(.wp-block-image){margin:0}
:root .wp-block-image > img{display:block}
{images}:root :where(.wp-block-group.has-background,p.has-background,h1.has-background,h2.has-background,h3.has-background,h4.has-background,h5.has-background,h6.has-background){padding:0}
:root :where(.wp-block-post-content,.wp-site-blocks){margin:0}
"""

FUNCTIONS = """<?php
/**
 * {name} — a block theme: the design lives in theme.json, the blocks use it.
 *
 * @package {pkg}
 */

defined( 'ABSPATH' ) || exit;

// The text is the source's, character for character: WordPress would curl
// its straight quotes and dashes, which the original never did.
add_filter( 'run_wptexturize', '__return_false' );

add_action(
	'after_setup_theme',
	static function () {{
		add_theme_support( 'editor-styles' );
		add_editor_style( array( {editor} ) );
	}}
);

add_action(
	'wp_enqueue_scripts',
	static function () {{
		$dir = get_template_directory();
		$uri = get_template_directory_uri();
{styles}
{scripts}
	}}
);
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--old", required=True)
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--css", action="append", required=True)
    ap.add_argument("--js", action="append", default=[])
    ap.add_argument("--fonts-url", default="")
    ap.add_argument("--media-url", default="")
    ap.add_argument("--presets", choices=("on", "off"), default="on")
    ap.add_argument("--layout", choices=("on", "off"), default="on")
    ap.add_argument("--author", default="", help="the style.css Author when the source theme names none")
    ap.add_argument("--chrome", default="front-page", help="the source whose <header>/<footer> become the parts")
    args = ap.parse_args(argv)
    old, out = Path(args.old), Path(args.out)
    tokens = json.loads(Path(args.tokens).read_text())
    conv_mod = load("convert_source", "convert-source.py")
    raise_mod = load("raise_specificity", "raise-specificity.py")
    if out.exists():
        shutil.rmtree(out)
    for d in ("templates", "parts", "content", "assets/images", "assets/js"):
        (out / d).mkdir(parents=True, exist_ok=True)

    # theme.json — the tokens as presets.
    lay = tokens.get("layout") or {}
    tj = {
        "$schema": "https://schemas.wp.org/wp/6.8/theme.json", "version": 3, "title": args.name,
        "settings": {
            "appearanceTools": True, "useRootPaddingAwareAlignments": False,
            "layout": {"contentSize": lay.get("contentSize", "1200px"), "wideSize": lay.get("wideSize", "1200px")},
            "color": {"defaultPalette": False, "defaultGradients": False, "defaultDuotone": False,
                      "palette": tokens["presets"]["palette"]},
            "typography": {"defaultFontSizes": False, "fluid": False, "fontFamilies": tokens["presets"]["fontFamilies"],
                           "fontSizes": tokens["presets"]["fontSizes"]},
            "spacing": {"blockGap": True, "defaultSpacingSizes": False, "spacingSizes": tokens["presets"]["spacingSizes"],
                        "units": ["px", "rem", "em", "%", "vw", "vh"]},
            "blocks": {"core/image": {"lightbox": {"enabled": False}}},
        },
        "styles": {"spacing": {"blockGap": "0px", "padding": {"top": "0px", "right": "0px", "bottom": "0px", "left": "0px"}}},
        "templateParts": [{"name": "header", "title": "Header", "area": "header"},
                          {"name": "footer", "title": "Footer", "area": "footer"}],
    }
    (out / "theme.json").write_text(json.dumps(tj, indent="\t") + "\n")
    # The headers Theme Check requires, carried from the source theme where it
    # has them; an author it lacks is not invented (--author supplies one).
    head = style_header(old / "style.css")
    author = args.author or head.get("Author", "")
    tested = head.get("Tested up to") or "7.0"
    description = (f"{args.name}: the {head.get('Theme Name') or old.name} design as a block theme. The design "
                   f"lives in theme.json, and every page is core blocks that use it.")
    fields = [("Theme Name", args.name), ("Theme URI", head.get("Theme URI", "")), ("Author", author),
              ("Author URI", head.get("Author URI", "")), ("Description", description),
              ("Requires at least", "6.6"), ("Tested up to", tested), ("Requires PHP", "7.4"), ("Version", "2.0.0"),
              ("License", "GNU General Public License v2 or later"),
              ("License URI", "https://www.gnu.org/licenses/gpl-2.0.html"), ("Text Domain", args.slug),
              ("Tags", "full-site-editing, custom-colors, editor-style")]
    (out / "style.css").write_text("/*\n" + "".join(f"{k}: {v}\n" for k, v in fields if v) + "*/\n")
    holder = author or f"the {head.get('Theme Name') or old.name} theme authors"
    (out / "readme.txt").write_text(
        f"=== {args.name} ===\nContributors: \nRequires at least: 6.6\nTested up to: {tested}\n"
        f"Requires PHP: 7.4\nStable tag: 2.0.0\nLicense: GPLv2 or later\n"
        f"License URI: https://www.gnu.org/licenses/gpl-2.0.html\n\n{description}\n\n"
        f"== Description ==\n\n{description} Colours, type sizes and spacing are presets: change them in "
        f"Appearance > Editor > Styles and every block that uses them follows.\n\n"
        f"== Copyright ==\n\n{args.name} WordPress Theme, Copyright (C) {datetime.date.today().year} {holder}.\n"
        f"{args.name} is distributed under the terms of the GNU GPL v2 or later.\n")

    # The design's stylesheet, unlayered and raised; scripts; images.
    styles, editor = [], ["'assets/bridge.css'"]
    for i, c in enumerate(args.css):
        text = unlayer((old / c).read_text(encoding="utf-8"))
        text, _ = raise_mod.transform(text)
        if args.presets == "on":
            text = point_at_presets(text, tokens.get("aliases") or {})
        name = f"assets/site-{i}.css" if len(args.css) > 1 else "assets/site.css"
        (out / name).write_text(text, encoding="utf-8")
        styles.append(name)
        editor.insert(len(editor) - 1, f"'{name}'")
    # The bridge goes BEFORE the design: it beats core's own block styles
    # (printed earlier still) and loses every tie to the design's rules.
    styles.insert(0, "assets/bridge.css")
    for j in args.js:
        shutil.copy(old / j, out / "assets/js" / Path(j).name)
    for img in list(old.rglob("*.webp")) + list(old.rglob("*.png")) + list(old.rglob("*.jpg")) + list(old.rglob("*.jpeg")):
        if "screenshot" not in img.name and "/assets/images/" not in str(img):
            shutil.copy(img, out / "assets/images" / img.name)
    if (old / "screenshot.png").is_file():
        shutil.copy(old / "screenshot.png", out / "screenshot.png")
    pkg = re.sub(r"[^A-Za-z0-9]", "", args.name.title())
    style_lines = []
    for k, s in enumerate(styles):
        dep = f"array( '{args.slug}-{k - 1}' )" if k else ("array( 'google-fonts' )" if args.fonts_url else "array()")
        style_lines.append(f"\t\twp_enqueue_style( '{args.slug}-{k}', $uri . '/{s}', {dep}, filemtime( $dir . '/{s}' ) );")
    if args.fonts_url:
        style_lines.insert(0, f"\t\twp_enqueue_style( 'google-fonts', '{args.fonts_url}', array(), null );")
    script_lines = [f"\t\twp_enqueue_script( '{args.slug}-js-{k}', $uri . '/assets/js/{Path(j).name}', array(), "
                    f"filemtime( $dir . '/assets/js/{Path(j).name}' ), array( 'strategy' => 'defer' ) );"
                    for k, j in enumerate(args.js)]
    (out / "functions.php").write_text(FUNCTIONS.format(name=args.name, pkg=pkg, editor=", ".join(editor),
                                                        styles="\n".join(style_lines), scripts="\n".join(script_lines)))

    # Pages, then the chrome.
    summary = {}
    sources = sorted((old / "clara-content" / "sources").glob("*.html"))
    shells = {}
    for src in sources:
        target = out / "content" / src.name
        rc = conv_mod.main([str(src), "--tokens", args.tokens, "--out", str(target), "--presets", args.presets,
                            "--layout", args.layout, "--media-url", args.media_url])
        report = json.loads(Path(str(target) + ".report.json").read_text())
        Path(str(target) + ".report.json").rename(out / "content" / (src.stem + ".report.json"))
        shells[src.stem] = report.get("shell")
        summary[src.stem] = report["blocks"]
    # An image's classes land on the <figure> core wraps it in: whatever
    # sized or fitted the <img> — a width, a height, an aspect ratio, object-fit
    # — now sizes the figure, and the image fills it. Rules for exactly the
    # classes the pages use, read off the design's own properties.
    image_classes = set()
    for f in (out / "content").glob("*.html"):
        for m in re.finditer(r'<figure class="wp-block-image ([^"]*)"', f.read_text(encoding="utf-8")):
            image_classes.update(m.group(1).split())
    fills = {"width": "width:100%", "height": "height:100%", "aspect-ratio": "width:100%;height:100%",
             "object-fit": "object-fit:inherit", "object-position": "object-position:inherit"}
    rules = {}
    for cls in sorted(image_classes):
        for prop in tokens["properties"].get(cls, []):
            if prop in fills:
                esc = re.sub(r"([^A-Za-z0-9_-])", r"\\\1", cls)
                rules.setdefault(fills[prop], []).append(f":root .wp-block-image.{esc} > img")
    images = "".join(",".join(sel) + "{" + decl + "}\n" for decl, sel in sorted(rules.items()))
    (out / "assets/bridge.css").write_text(BRIDGE.replace("{images}", images))
    chrome_src = old / "clara-content" / "sources" / f"{args.chrome}.html"
    html = chrome_src.read_text(encoding="utf-8")
    tree = conv_mod.Tree(html)
    conv = conv_mod.Converter(html, tokens, args.presets == "on", args.media_url, [], layout=args.layout == "on")

    def first(node, tag):
        for ch in node.children:
            if isinstance(ch, conv_mod.Node):
                if ch.tag == tag:
                    return ch
                got = first(ch, tag)
                if got:
                    return got
        return None
    parts = {}
    for tag in ("header", "footer"):
        node = first(tree.root, tag)
        if node is None:
            continue
        (out / "parts" / f"{tag}.html").write_text("\n\n".join(conv.children(node)) + "\n")
        parts[tag] = node.classes()
    shell_node = first(tree.root, "header").parent if first(tree.root, "header") else None
    shell_classes = shell_node.classes() if shell_node is not None and shell_node.tag != "#root" else []
    main_classes = next((s["classes"] for s in shells.values() if s and s.get("tag") in ("main", "div")), [])

    def part(tag):
        a = {"slug": tag, "tagName": tag}
        if parts.get(tag):
            a["className"] = " ".join(parts[tag])
        return f"<!-- wp:template-part {conv_mod.wp_json(a)} /-->"
    main_attrs = {"tagName": "main"}
    if main_classes:
        main_attrs["className"] = " ".join(main_classes)
    main_attrs["layout"] = {"type": "default"}
    main_cls = " ".join(["wp-block-group"] + main_classes)
    inner = (f"{part('header')}\n\n<!-- wp:group {conv_mod.wp_json(main_attrs)} -->\n<main class=\"{main_cls}\">"
             f"<!-- wp:post-content {{\"layout\":{{\"type\":\"default\"}}}} /--></main>\n<!-- /wp:group -->\n\n{part('footer')}")
    if shell_classes:
        shell_attrs = {"className": " ".join(shell_classes), "layout": {"type": "default"}}
        template = (f"<!-- wp:group {conv_mod.wp_json(shell_attrs)} -->\n<div class=\"wp-block-group "
                    f"{' '.join(shell_classes)}\">{inner}</div>\n<!-- /wp:group -->\n")
    else:
        template = inner + "\n"
    for name in ("index", "page", "front-page", "singular"):
        (out / "templates" / f"{name}.html").write_text(template)
    print(f"scaffold-theme: {out} — {len(sources)} page(s), parts {sorted(parts)}, presets {args.presets}; "
          f"theme.json {len(tj['settings']['color']['palette'])} colours, "
          f"{len(tj['settings']['typography']['fontSizes'])} sizes, {len(tj['settings']['spacing']['spacingSizes'])} spacing steps")
    return 0


if __name__ == "__main__":
    sys.exit(main())
