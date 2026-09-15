#!/usr/bin/env python3
"""Render the ORIGINAL html2wp site to standalone HTML, for comparison.

The source pages in the input theme's bundle are fragments: no head, no
header, no footer, and a handful of tokens the old runtime resolved at request
time. This composes them the way that runtime did, so the result can be
screenshotted next to the converted pages (visual-diff.py) and measured
against them (measure-diff.py).

Everything project-specific lives in a JSON config, not in this file:

    python3 render-original.py --example > render-original.json   # starter config
    python3 render-original.py --config render-original.json      # every page
    python3 render-original.py --config render-original.json about contact

Keys (paths are absolute or relative to the config file):

    old_theme        the html2wp theme directory (required)
    out              where the rendered pages go (required)
    sources          bundle pages, relative to old_theme     [clara-content/sources]
    stylesheet       relative to old_theme                   [assets/css/site.css]
    script           relative to old_theme                   [assets/js/site.js]
    header_part      relative to old_theme                   [parts/header.html]
    footer_part      relative to old_theme                   [parts/footer.html]
    header_open      wrapper the old runtime put round the header part
    header_open_hero same, on pages listed in hero_pages (transparent nav)
    hero_pages       page keys that get header_open_hero
    footer_open, footer_close, footer_strip
                     wrapper round the footer part, and strings removed from
                     the part first so it is not wrapped twice
    skip             page keys not to render (became templates, 404, …)
    posts_json       the CONVERTED theme's content/posts.json, so [wp-posts]
                     tokens expand to the same entries the live loop shows
    card_template    markup for one such entry; placeholders {image}
                     {category} {datetime} {date} {title} {excerpt} {url}
    date_format      strftime format for {date}               [%-d %b %Y]
    category_labels  slug → label for {category}
    url_map          [regex, replacement] pairs applied to every page, with
                     {assets} and {old} expanded to the old theme relative to out
    strip_patterns   regexes removed from every page (the skip link that moved
                     into the header part, for instance)
    extra_head       raw HTML inlined into <head> — @font-face rules, usually,
                     since the page's own <link> tags are dropped
    extra_head_file  a file whose contents are inlined the same way
    lang             html lang attribute                       [en]

Exit status: 0 rendered, 2 usage or config error.
"""

import json
import os
import re
import sys
from datetime import date
from pathlib import Path

EXAMPLE = {
    "old_theme": "../amanda-rose",
    "out": "./preview-original",
    "sources": "clara-content/sources",
    "stylesheet": "assets/css/site.css",
    "script": "assets/js/site.js",
    "header_part": "parts/header.html",
    "footer_part": "parts/footer-2.html",
    "header_open": "<header id=\"nav\" class=\"nav\">",
    "header_open_hero": "<header id=\"nav\" class=\"nav over\">",
    "header_close": "</header>",
    "hero_pages": ["front-page", "about", "contact"],
    "footer_open": "<footer class=\"footer\">",
    "footer_close": "</footer>",
    "footer_strip": ["<footer class=\"footer\">", "</footer>"],
    "skip": ["journal", "journal-2", "404"],
    "posts_json": "../<converted-theme>/content/posts.json",
    "card_template": (
        "\n<a href=\"{url}\" class=\"post-card reveal in\" data-cat=\"{category}\">"
        "\n  <div class=\"fig fig-4x3 zoom\"><img src=\"{image}\" alt=\"\"></div>"
        "\n  <p class=\"meta\">{category} <span class=\"dot\"></span> "
        "<time datetime=\"{datetime}\">{date}</time></p>"
        "\n  <h3>{title}</h3>"
        "\n  <p>{excerpt}</p>"
        "\n  <span class=\"tlink\">Read the story <span class=\"arw\">&rarr;</span></span>"
        "\n</a>"
    ),
    "date_format": "%-d %b %Y",
    "category_labels": {"planning": "Planning", "real-weddings": "Real weddings"},
    "url_map": [
        ["__CLARA_UPLOADS_URI__/clara-ve-import/[^/]+/", "{assets}/"],
        ["__CLARA_THEME_URI__/assets/", "{assets}/"],
        ["__CLARA_THEME_URI__", "{old}"],
        ["__CLARA_HOME_URL__", "#"],
    ],
    "strip_patterns": ["<a class=\"skip\"[^>]*>.*?</a>"],
    "extra_head": "",
    "extra_head_file": None,
    "lang": "en",
}

WP_COMMENT = re.compile(r"<!--\s*/?wp:[^>]*?-->")
CLARA_KEY = re.compile(r"<!--\s*clara-ve-key:.*?-->")
POSTS_TOKEN = re.compile(r"\[wp-posts[^\]]*\].*?\[/wp-posts\]", re.S)

DOC = """<!doctype html>
<html lang="{lang}" class="js"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — original</title>
<link rel="stylesheet" href="{stylesheet}">
{extra_head}
</head><body>
{header_open}{header}{header_close}
{body}
{footer_open}{footer}{footer_close}
<script src="{script}"></script>
</body></html>
"""


class Renderer:
    def __init__(self, cfg, base):
        self.cfg = {**EXAMPLE, **cfg}
        # abspath, not resolve(): a symlinked theme keeps the path it was given,
        # so the relative URLs written into the pages stay short and readable.
        self.old = Path(os.path.abspath(base / self.cfg["old_theme"]))
        self.out = Path(os.path.abspath(base / self.cfg["out"]))
        rel_old = os.path.relpath(self.old, self.out)
        self.rel = {"old": rel_old, "assets": f"{rel_old}/assets"}
        self.entries = None

    def resolve(self, markup):
        """Point every token at the old theme's own files."""
        markup = WP_COMMENT.sub("", markup)
        markup = CLARA_KEY.sub("", markup)
        markup = POSTS_TOKEN.sub(self.expand_posts, markup)
        for pattern, replacement in self.cfg["url_map"]:
            markup = re.sub(pattern, replacement.format(**self.rel), markup)
        # The page's own <link>/<script> tags are replaced by the document below.
        markup = re.sub(r"<link[^>]*>", "", markup)
        markup = re.sub(r"<script.*?</script>", "", markup, flags=re.S)
        for pattern in self.cfg["strip_patterns"]:
            markup = re.sub(pattern, "", markup, flags=re.S)
        # WordPress generates its own responsive sizes after import, so both
        # sides are compared at full size (pitfall #11).
        markup = re.sub(r'\s(?:srcset|sizes)="[^"]*"', "", markup)
        return markup

    def load_entries(self):
        if self.entries is not None:
            return self.entries
        path = self.cfg.get("posts_json")
        if not path:
            self.entries = []
            return self.entries
        data = json.loads((Path(path) if Path(path).is_absolute()
                           else (self.base / path)).read_text(encoding="utf-8"))
        data.sort(key=lambda e: e.get("date", ""), reverse=True)
        self.entries = data
        return data

    def cards(self, count):
        entries = self.load_entries()
        if not entries:
            print("warning: [wp-posts] token met but no posts_json configured — rendered empty",
                  file=sys.stderr)
            return ""
        labels = self.cfg["category_labels"]
        out = []
        for i in range(count):
            e = entries[i % len(entries)]
            iso = str(e.get("date", ""))[:10]
            try:
                pretty = date.fromisoformat(iso).strftime(self.cfg["date_format"])
            except ValueError:
                pretty = iso
            cat = e.get("category", "")
            out.append(self.cfg["card_template"].format(
                image=f"{self.rel['assets']}/{e.get('featured_image', '')}",
                category=labels.get(cat, cat),
                datetime=iso, date=pretty,
                title=e.get("title", ""), excerpt=e.get("excerpt", ""),
                url=e.get("url", "#"),
            ))
        return "".join(out)

    def expand_posts(self, match):
        count = re.search(r'count="(\d+)"', match.group(0))
        return self.cards(int(count.group(1)) if count else 6)

    def head_extra(self):
        extra = self.cfg.get("extra_head") or ""
        f = self.cfg.get("extra_head_file")
        if f:
            p = Path(f) if Path(f).is_absolute() else (self.base / f)
            extra += "\n" + p.read_text(encoding="utf-8")
        return extra

    def run(self, wanted):
        cfg, old = self.cfg, self.old
        header = self.resolve((old / cfg["header_part"]).read_text(encoding="utf-8"))
        footer = self.resolve((old / cfg["footer_part"]).read_text(encoding="utf-8"))
        for s in cfg["footer_strip"]:
            footer = footer.replace(s, "")

        self.out.mkdir(parents=True, exist_ok=True)
        rendered = []
        sources = old / cfg["sources"]
        for page in sorted(sources.glob("*.html")):
            key = page.stem
            if key in cfg["skip"] or (wanted and key not in wanted):
                continue
            raw = self.resolve(page.read_text(encoding="utf-8"))
            # keep only what sat inside <main>, matching the converted pages
            inner = re.search(r"<main[^>]*>(.*)</main>", raw, re.S)
            body = inner.group(1) if inner else raw
            body = f'<main id="main">{body}</main>'

            doc = DOC.format(
                lang=cfg["lang"], title=key,
                stylesheet=f"{self.rel['old']}/{cfg['stylesheet']}",
                script=f"{self.rel['old']}/{cfg['script']}",
                extra_head=self.head_extra(),
                header_open=cfg["header_open_hero"] if key in cfg["hero_pages"] else cfg["header_open"],
                header=header, header_close=cfg["header_close"],
                body=body,
                footer_open=cfg["footer_open"], footer=footer, footer_close=cfg["footer_close"],
            )
            (self.out / f"{key}.html").write_text(doc, encoding="utf-8")
            rendered.append(key)
        return rendered


def main(argv):
    if "--example" in argv:
        print(json.dumps(EXAMPLE, indent=2))
        return 0
    if "--config" not in argv:
        print("usage: render-original.py --config <file.json> [page ...]\n"
              "       render-original.py --example", file=sys.stderr)
        return 2
    cfg_path = Path(argv[argv.index("--config") + 1])
    if not cfg_path.is_file():
        print(f"error: {cfg_path} is not a file", file=sys.stderr)
        return 2
    wanted = [a for a in argv if not a.startswith("--") and a != str(cfg_path)]

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    base = cfg_path.resolve().parent
    r = Renderer(cfg, base)
    r.base = base
    for key in ("old_theme", "out"):
        if key not in cfg:
            print(f"error: config needs '{key}'", file=sys.stderr)
            return 2
    if not r.old.is_dir():
        print(f"error: old_theme {r.old} is not a directory", file=sys.stderr)
        return 2
    sources = r.old / r.cfg["sources"]
    if not sources.is_dir():
        print(f"error: {sources} is not a directory — is this an html2wp theme?", file=sys.stderr)
        return 2

    rendered = r.run(wanted)
    print(f"rendered {len(rendered)} original page(s) into {r.out}")
    for key in rendered:
        print(f"  {key}")
    return 0 if rendered else 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
