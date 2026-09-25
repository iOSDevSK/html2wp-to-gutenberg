#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""An html2wp page source as core block markup — the way official themes build.

    python3 convert-source.py <source.html> --tokens tokens.json --out page.html
    python3 convert-source.py <source.html> --tokens tokens.json --out page.html --presets off
    python3 convert-source.py <part.html> --tokens … --out … --fragment

Two modes, one mapper, so a conversion's "before" and "after" come from the
same code:

--presets off   the skill's original rule: every class survives on a block of
                the same kind (a <div class="X"> is a group with className X)
--presets on    (default) a class whose rule is one design token becomes the
                block attribute official themes use — textColor,
                backgroundColor, borderColor, fontSize (with the line height it
                carried), fontFamily, lineHeight, padding/margin/blockGap as
                var:preset|spacing|N — and a group's wrapper classes become
                core layout: flex (orientation, justification, alignment,
                wrap), grid (columnCount) and constrained (contentSize).
                A class converts only when no other class on the element
                touches the same property (a responsive md:text-4xl or a
                hover: keeps text-2xl a class: core layout and presets have
                no breakpoints), and only on a block that supports the
                attribute. Everything else stays in className — the residue
                the report counts.

Blocks: group (div, section, article, aside, header, footer, main, nav),
heading, paragraph (text, a standalone link, any inline-only element),
image, list/list-item. Anything a block cannot hold without losing
behaviour — a form, a button, an svg, an iframe, an element the old runtime
drives (data-spa-*), a link wrapping blocks — stays as core/html, verbatim.

--media-url rewrites the bundle's image tokens (__CLARA_UPLOADS_URI__…/<file>
and __CLARA_THEME_URI__/assets/<file>) to <url>/<file>. --keep lists element
paths (1.2.0 …, from the report) whose classes stay classes: the pixel gate's
revert, one element at a time.

Writes the markup and <out>.report.json (every class kept, and why).
Exit 0; 2 = usage.
"""
import argparse
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
INLINE = {"a", "span", "em", "strong", "b", "i", "u", "small", "br", "code", "sup", "sub", "mark", "abbr", "time",
          "s", "del", "ins", "q", "cite", "kbd", "var", "bdi", "bdo", "wbr"}
GROUP_TAGS = {"div", "section", "article", "aside", "header", "footer", "main", "nav", "figure", "blockquote"}
RAW_TAGS = {"form", "button", "input", "select", "textarea", "iframe", "video", "audio", "svg", "canvas", "table",
            "details", "dialog", "picture", "object", "label", "fieldset"}
DROP_TAGS = {"script", "style", "link", "meta", "title", "noscript", "template", "base"}
TEXT_BLOCKS = {"core/paragraph", "core/heading", "core/list"}


class Node:
    __slots__ = ("tag", "attrs", "children", "start", "open_end", "close_start", "end", "parent")

    def __init__(self, tag, attrs, start, open_end, parent):
        self.tag, self.attrs, self.parent = tag, attrs, parent
        self.children, self.start, self.open_end = [], start, open_end
        self.close_start = self.end = open_end

    def get(self, name, default=None):
        for k, v in self.attrs:
            if k == name:
                return v if v is not None else ""
        return default

    def classes(self):
        return (self.get("class") or "").split()


class Tree(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=False)
        self.text = text
        self.lines = [0] + [m.end() for m in re.finditer("\n", text)]
        self.root = Node("#root", [], 0, 0, None)
        self.stack = [self.root]
        self.feed(text)
        self.close()
        for node in self.stack[1:]:
            node.close_start = node.end = len(text)
        self.root.close_start = self.root.end = len(text)

    def at(self):
        line, col = self.getpos()
        return self.lines[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self.at()
        raw = self.get_starttag_text() or ""
        node = Node(tag, attrs, start, start + len(raw), self.stack[-1])
        self.stack[-1].children.append(node)
        if tag not in VOID and not raw.endswith("/>"):
            self.stack.append(node)

    def handle_endtag(self, tag):
        start = self.at()
        close = self.text.find(">", start) + 1
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                for node in self.stack[i:]:
                    node.close_start = start
                    node.end = close if node is self.stack[i] else start
                del self.stack[i:]
                return

    def _text(self, data):
        start = self.at()
        self.stack[-1].children.append((start, start + len(data)))

    handle_data = _text

    def handle_entityref(self, name):
        start = self.at()
        self.stack[-1].children.append((start, start + len(name) + 2))

    def handle_charref(self, name):
        start = self.at()
        self.stack[-1].children.append((start, start + len(name) + 3))


def wp_json(attrs):
    """Block attributes as WordPress serialises them in the delimiter."""
    s = json.dumps(attrs, ensure_ascii=False, separators=(",", ":"))
    return (s.replace("--", "\\u002d\\u002d").replace("<", "\\u003c").replace(">", "\\u003e")
            .replace("&", "\\u0026").replace('\\"', "\\u0022"))


def esc_attr(v):
    return v.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


class Converter:
    def __init__(self, source, tokens, presets, media_url, keep, layout=True):
        self.src = source
        self.tokens = tokens
        self.presets = presets
        self.use_layout = presets and layout
        self.media_url = media_url.rstrip("/") if media_url else ""
        self.keep = set(keep or [])
        self.kept = Counter()        # reason → count of classes left as classes
        self.converted = Counter()   # attribute → count
        self.blocks = Counter()

    # -- markup helpers ------------------------------------------------
    def raw(self, node):
        return self.media(self.src[node.start:node.end]) if isinstance(node, Node) else self.media(self.src[node[0]:node[1]])

    def inner(self, node):
        return self.media(self.src[node.open_end:node.close_start])

    def media(self, html):
        if not self.media_url:
            return html
        html = re.sub(r"__CLARA_UPLOADS_URI__/[^\"'\s)]*?/([^/\"'\s)]+\.(?:webp|png|jpe?g|gif|svg|avif))",
                      lambda m: f"{self.media_url}/{m.group(1)}", html)
        return re.sub(r"__CLARA_THEME_URI__/assets/([^\"'\s)]+\.(?:webp|png|jpe?g|gif|svg|avif))",
                      lambda m: f"{self.media_url}/{m.group(1).split('/')[-1]}", html)

    def text_only(self, node):
        """True when every descendant is text or an inline element."""
        for ch in node.children:
            if isinstance(ch, Node):
                if ch.tag not in INLINE or not self.text_only(ch):
                    return False
        return True

    def blank(self, ch):
        return not isinstance(ch, Node) and not self.src[ch[0]:ch[1]].strip()

    def runtime(self, node):
        return any(k.startswith("data-spa-") and k not in ("data-spa-reveal", "data-spa-reveal-at", "data-spa-id")
                   for k, _ in node.attrs) or node.get("hidden") is not None or node.get("style")

    def path(self, node):
        parts = []
        while node.parent is not None:
            siblings = [c for c in node.parent.children if isinstance(c, Node)]
            parts.append(str(siblings.index(node)))
            node = node.parent
        return ".".join(reversed(parts))

    # -- classes → attributes ---------------------------------------------
    def props(self, cls):
        return set(self.tokens["properties"].get(cls, []))

    def split(self, node, block, allow_layout=False):
        """(attributes, remaining classes) for a block made from node."""
        classes = node.classes()
        attrs, style = {}, {}
        if not self.presets or self.path(node) in self.keep:
            if classes:
                self.kept["mode"] += len(classes)
            return attrs, style, classes
        remaining, taken = [], set()
        cmap = self.tokens["classes"]
        support = {
            "core/group": {"textColor", "backgroundColor", "borderColor", "padding", "margin"},
            "core/paragraph": {"textColor", "backgroundColor", "fontSize", "fontFamily", "lineHeight", "padding", "margin"},
            "core/heading": {"textColor", "backgroundColor", "fontSize", "fontFamily", "lineHeight", "padding", "margin"},
            "core/list": {"textColor", "backgroundColor", "fontSize", "fontFamily", "lineHeight", "padding", "margin"},
            "core/image": set(),
        }[block]
        leading = next((c for c in classes if c.startswith("leading-") and c in cmap), None)
        for cls in classes:
            m = cmap.get(cls)
            if not m or "layout" in m or "blockGap" in m:
                if not m:
                    self.kept["no token"] += 1
                remaining.append(cls)
                continue
            mine = self.props(cls)
            others = set().union(*(self.props(c) for c in classes if c != cls)) if len(classes) > 1 else set()
            if mine & others and not (cls == leading and mine == {"line-height"}):
                self.kept["another class sets it (responsive, hover)"] += 1
                remaining.append(cls)
                continue
            keys = [k for k in m if k != "lineHeight" or "fontSize" not in m]
            if not all(k in support for k in keys):
                self.kept["the block has no such attribute"] += 1
                remaining.append(cls)
                continue
            for k, v in m.items():
                if k in ("textColor", "backgroundColor", "borderColor", "fontSize", "fontFamily"):
                    attrs[k] = v
                elif k == "lineHeight":
                    if "fontSize" in m and leading and leading != cls:
                        continue  # the leading-* class says the line height
                    style.setdefault("typography", {})["lineHeight"] = v
                elif k in ("padding", "margin"):
                    for side, step in v.items():
                        style.setdefault("spacing", {}).setdefault(k, {})[side] = f"var:preset|spacing|{step}"
                self.converted[k] += 1
            taken.add(cls)
        return attrs, style, remaining

    def layout(self, node, remaining):
        """Core layout for a group whose wrapper classes say flex, grid or a
        centred max width — or None, and the classes stay."""
        if not self.use_layout or self.path(node) in self.keep:
            return None, {}, remaining
        cmap, classes = self.tokens["classes"], node.classes()
        lay = {c: cmap[c]["layout"] for c in remaining if "layout" in cmap.get(c, {})}
        decl = {}
        for c, d in lay.items():
            decl.update(d)
        responsive = set().union(*(self.props(c) for c in classes if c not in lay and ":" in c)) if classes else set()
        gap_cls = next((c for c in remaining if "blockGap" in cmap.get(c, {})), None)
        if decl.get("display") == "flex" and not (responsive & ({"display"} | set(decl))):
            vertical = decl.get("flex-direction") == "column"
            align, justify = decl.get("align-items"), decl.get("justify-content")
            out = {"type": "flex"}
            # What core's flex layout can say (block-supports/layout.php):
            # horizontal — justifyContent left/center/right/space-between,
            # verticalAlignment top/center/bottom/stretch; vertical —
            # justifyContent left/center/right/stretch (align-items),
            # verticalAlignment top/center/bottom/space-between. A design
            # with no align-items stretches, as CSS does.
            if vertical:
                out["orientation"] = "vertical"
                amap = {None: "stretch", "stretch": "stretch", "center": "center", "flex-start": "left",
                        "start": "left", "flex-end": "right", "end": "right"}
                jmap = {"space-between": "space-between", "center": "center", "flex-end": "bottom", "end": "bottom",
                        "flex-start": "top", "start": "top"}
                if align not in amap or (justify and justify not in jmap):
                    self.kept["flex the core layout cannot say"] += len(lay)
                    return None, {}, remaining
                out["justifyContent"] = amap[align]
                if justify:
                    out["verticalAlignment"] = jmap[justify]
            else:
                amap = {None: "stretch", "stretch": "stretch", "center": "center", "flex-start": "top", "start": "top",
                        "flex-end": "bottom", "end": "bottom"}
                jmap = {"space-between": "space-between", "center": "center", "flex-end": "right", "end": "right",
                        "flex-start": "left", "start": "left"}
                if align not in amap or (justify and justify not in jmap):
                    self.kept["flex the core layout cannot say"] += len(lay)
                    return None, {}, remaining
                out["verticalAlignment"] = amap[align]
                if justify and jmap[justify] != "left":
                    out["justifyContent"] = jmap[justify]
            out["flexWrap"] = "wrap" if decl.get("flex-wrap") == "wrap" else "nowrap"
            style = {}
            gone = set(lay)
            if gap_cls and not (responsive & {"gap"}):
                style = {"spacing": {"blockGap": self.gap(cmap[gap_cls]["blockGap"])}}
                gone.add(gap_cls)
            self.converted["layout flex"] += 1
            return out, style, [c for c in remaining if c not in gone]
        if decl.get("display") == "grid" and "grid-template-columns" in decl and not (responsive & {"display", "grid-template-columns"}):
            m = re.fullmatch(r"repeat\((\d+),\s*minmax\(0,\s*1fr\)\)", decl["grid-template-columns"])
            if not m:
                return None, {}, remaining
            out = {"type": "grid", "columnCount": int(m.group(1))}
            style, gone = {}, set(lay)
            if gap_cls and not (responsive & {"gap"}):
                style = {"spacing": {"blockGap": self.gap(cmap[gap_cls]["blockGap"])}}
                gone.add(gap_cls)
            self.converted["layout grid"] += 1
            return out, style, [c for c in remaining if c not in gone]
        # A centred max width over content that fills it: core's constrained
        # layout, the content box measured the way theme.json's contentSize is.
        lt = self.tokens.get("layout") or {}
        maxw = [c for c in remaining if c.startswith("max-w-") and ":" not in c]
        if "mx-auto" in remaining and len(maxw) == 1 and lt and maxw[0] == f"max-w-[{lt.get('fromMaxWidth')}]" \
                and not any(c.startswith(("bg-", "border", "shadow", "rounded")) for c in classes) \
                and not (responsive & {"max-width", "margin-inline"}):
            kids = [ch for ch in node.children if isinstance(ch, Node) and ch.tag not in DROP_TAGS]
            if all(not any(k.startswith(("max-w-", "w-", "mx-", "ml-", "mr-")) for k in ch.classes()) for ch in kids):
                self.converted["layout constrained"] += 1
                return {"type": "constrained"}, {}, [c for c in remaining if c not in ("mx-auto", maxw[0])]
        return None, {}, remaining

    def gap(self, v):
        if isinstance(v, dict):
            return {k: f"var:preset|spacing|{s}" for k, s in v.items()}
        return f"var:preset|spacing|{v}"

    # -- attributes → markup ------------------------------------------------
    def support_classes(self, attrs):
        out = []
        if "textColor" in attrs:
            out += [f"has-{attrs['textColor']}-color", "has-text-color"]
        if "backgroundColor" in attrs:
            out += [f"has-{attrs['backgroundColor']}-background-color", "has-background"]
        if "borderColor" in attrs:
            out += ["has-border-color", f"has-{attrs['borderColor']}-border-color"]
        if "fontSize" in attrs:
            out.append(f"has-{attrs['fontSize']}-font-size")
        if "fontFamily" in attrs:
            out.append(f"has-{attrs['fontFamily']}-font-family")
        return out

    def css_of(self, style):
        out = []
        def var(v):
            m = re.fullmatch(r"var:preset\|([\w-]+)\|([\w-]+)", v)
            return f"var(--wp--preset--{m.group(1)}--{m.group(2)})" if m else v
        for kind in ("padding", "margin"):
            for side in ("top", "right", "bottom", "left"):
                v = ((style.get("spacing") or {}).get(kind) or {}).get(side)
                if v:
                    out.append(f"{kind}-{side}:{var(v)}")
        lh = (style.get("typography") or {}).get("lineHeight")
        if lh:
            out.append(f"line-height:{lh}")
        return ";".join(out)

    def open_attrs(self, attrs, style, classes, extra=None):
        a = dict(extra or {})
        if classes:
            a["className"] = " ".join(classes)
        a.update(attrs)
        saved = {k: v for k, v in style.items() if v}
        if saved:
            a["style"] = saved
        return a

    def class_attr(self, base, classes, attrs):
        names = ([base] if base else []) + classes + self.support_classes(attrs)
        return f' class="{esc_attr(" ".join(names))}"' if names else ""

    def style_attr(self, style):
        css = self.css_of(style)
        return f' style="{css}"' if css else ""

    def block(self, name, attrs, html):
        self.blocks[name] += 1
        short = name.replace("core/", "")
        head = f"<!-- wp:{short} {wp_json(attrs)} -->" if attrs else f"<!-- wp:{short} -->"
        return f"{head}\n{html}\n<!-- /wp:{short} -->"

    # -- nodes → blocks -------------------------------------------------------
    def html_block(self, node):
        self.blocks["core/html"] += 1
        return f"<!-- wp:html -->\n{self.raw(node)}\n<!-- /wp:html -->"

    def paragraph(self, node, content, class_node=None):
        attrs, style, classes = self.split(class_node or node, "core/paragraph")
        a = self.open_attrs(attrs, style, classes)
        return self.block("core/paragraph", a,
                          f"<p{self.class_attr('', classes, attrs)}{self.style_attr(style)}>{content}</p>")

    def heading(self, node):
        level = int(node.tag[1])
        attrs, style, classes = self.split(node, "core/heading")
        a = self.open_attrs(attrs, style, classes, {} if level == 2 else {"level": level})
        return self.block("core/heading", a,
                          f"<h{level}{self.class_attr('wp-block-heading', classes, attrs)}{self.style_attr(style)}>"
                          f"{self.inner(node)}</h{level}>")

    def image(self, node):
        src = self.media(node.get("src") or "")
        alt = node.get("alt") or ""
        classes = node.classes()
        a = {"className": " ".join(classes)} if classes else {}
        cls = " ".join(["wp-block-image"] + classes)
        return self.block("core/image", a, f'<figure class="{esc_attr(cls)}"><img src="{esc_attr(src)}" alt="{esc_attr(alt)}"/></figure>')

    def list_block(self, node):
        items = [ch for ch in node.children if isinstance(ch, Node)]
        if any(ch.tag != "li" or not self.text_only(ch) for ch in items):
            return self.html_block(node)
        attrs, style, classes = self.split(node, "core/list")
        a = self.open_attrs(attrs, style, classes, {"ordered": True} if node.tag == "ol" else {})
        lis = []
        for li in items:
            lc = li.classes()
            la = {"className": " ".join(lc)} if lc else {}
            self.blocks["core/list-item"] += 1
            head = f"<!-- wp:list-item {wp_json(la)} -->" if la else "<!-- wp:list-item -->"
            lis.append(f"{head}\n<li{self.class_attr('', lc, {})}>{self.inner(li)}</li>\n<!-- /wp:list-item -->")
        tag = node.tag
        return self.block("core/list", a, f"<{tag}{self.class_attr('wp-block-list', classes, attrs)}{self.style_attr(style)}>"
                          + "".join(lis) + f"</{tag}>")

    def group(self, node, inner_blocks):
        attrs, style, classes = self.split(node, "core/group")
        layout, lstyle, classes = self.layout(node, classes)
        for k, v in lstyle.items():
            style.setdefault(k, {}).update(v)
        extra = {"tagName": node.tag} if node.tag != "div" else {}
        if node.get("id"):
            extra["anchor"] = node.get("id")
        a = self.open_attrs(attrs, style, classes, extra)
        a["layout"] = layout or {"type": "default"}
        anchor = f' id="{esc_attr(node.get("id"))}"' if node.get("id") else ""
        body = "\n\n".join(inner_blocks)
        return self.block("core/group", a, f"<{node.tag}{anchor}{self.class_attr('wp-block-group', classes, attrs)}"
                          f"{self.style_attr(style)}>{body}</{node.tag}>")

    def lays_out(self, node):
        cmap = self.tokens["classes"]
        return any("layout" in cmap.get(c, {}) or "blockGap" in cmap.get(c, {}) for c in node.classes()) or \
            any(self.props(c) & {"display", "gap", "align-items", "justify-content"} for c in node.classes())

    def plain_paragraph(self, html):
        return self.block("core/paragraph", {}, f"<p>{html}</p>")

    def run_paragraph(self, run):
        """A run of text and inline elements between blocks: one paragraph."""
        html = "".join(self.raw(ch) for ch in run).strip()
        return self.block("core/paragraph", {}, f"<p>{html}</p>") if html else None

    def convert(self, node):
        if not isinstance(node, Node):
            return []
        tag = node.tag
        if tag in DROP_TAGS:
            return []
        if tag in RAW_TAGS or self.runtime(node):
            return [self.html_block(node)]
        if tag == "img":
            return [self.image(node)]
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            return [self.heading(node)] if self.text_only(node) else [self.html_block(node)]
        if tag in ("ul", "ol"):
            return [self.list_block(node)]
        if tag == "hr":
            return [self.html_block(node)]
        if tag == "p":
            return [self.paragraph(node, self.inner(node))] if self.text_only(node) else [self.html_block(node)]
        if self.text_only(node):
            if tag == "a" and self.lays_out(node):
                # A link that lays out its own children (a flex logo with a
                # gap): its classes stay on it, inside a plain paragraph.
                return [self.plain_paragraph(self.raw(node))]
            if tag == "a":
                rest = "".join(f' {k}="{esc_attr(v)}"' if v is not None else f" {k}" for k, v in node.attrs
                               if k not in ("class", "data-status", "data-spa-reveal", "data-spa-reveal-at", "data-spa-id"))
                return [self.paragraph(node, f"<a{rest}>{self.inner(node)}</a>")]
            if tag in INLINE or tag in GROUP_TAGS or tag == "li":
                return [self.paragraph(node, self.inner(node))]
            return [self.html_block(node)]
        if tag in INLINE:
            # A link or a span wrapping blocks (a whole card): no core block
            # is a link around blocks. Phase 3 (section recognition) decides.
            return [self.html_block(node)]
        if tag in GROUP_TAGS or tag == "li":
            return [self.group(node, self.children(node))]
        return [self.html_block(node)]

    def blockifies(self, node):
        """Does this container make its children blocks (a flex or grid
        container, at any breakpoint)? Its inline children are then boxes of
        their own; in flow they sit on a line box whose height is the
        PARENT's, and a paragraph made of one would be as tall as its own text."""
        if node is None:
            return False
        for c in node.classes():
            decl = self.tokens["classes"].get(c, {}).get("layout", {})
            if decl.get("display") in ("flex", "grid", "inline-flex", "inline-grid"):
                return True
            if ":" in c and re.search(r"(^|:)(inline-)?(flex|grid)$", c):
                return True
        return False

    def flush(self, run, out, parent=None):
        """A run of inline content between blocks. One inline element that
        its container blockifies becomes a block of its own, its classes the
        block's; anything else is one plain paragraph holding the run as it
        is written — the line box then keeps the container's height."""
        nodes = [r for r in run if isinstance(r, Node)]
        texts = [r for r in run if not isinstance(r, Node) and not self.blank(r)]
        if len(nodes) == 1 and not texts and self.blockifies(parent):
            out.extend(self.convert(nodes[0]))
        elif nodes or texts:
            para = self.run_paragraph(run)
            if para:
                out.append(para)

    def children(self, node):
        out, run = [], []
        for ch in node.children:
            if isinstance(ch, Node) and (ch.tag in INLINE and self.text_only(ch)):
                run.append(ch)
                continue
            if not isinstance(ch, Node):
                run.append(ch)
                continue
            self.flush(run, out, node)
            run = []
            out.extend(self.convert(ch))
        self.flush(run, out, node)
        return out


def page_nodes(tree, fragment):
    """The page's own content, without the shell the theme's templates now
    draw. A whole-page source is a shell element (the site's <header> and
    <footer> inside it on a self-contained page) around one main element: the
    header and footer are the theme's parts, the shell is the template's
    group and the main its <main> group, so the content is what sits inside
    the main. Returns (nodes, main element or None). A fragment is everything."""
    if fragment:
        return tree.root.children, None

    def only_element(nodes):
        els = [c for c in nodes if isinstance(c, Node) and c.tag not in DROP_TAGS]
        texts = [c for c in nodes if not isinstance(c, Node) and tree.text[c[0]:c[1]].strip()]
        return els[0] if len(els) == 1 and not texts else None

    nodes, main = tree.root.children, None
    shell = only_element(nodes)
    if shell is not None and shell.tag in ("div", "body"):
        kids = {c.tag for c in shell.children if isinstance(c, Node)}
        nodes = [c for c in shell.children if not (isinstance(c, Node) and c.tag in ("header", "footer"))] \
            if {"header", "footer"} <= kids else shell.children
    inner = only_element(nodes)
    if inner is not None and inner.tag in ("div", "main"):
        return inner.children, inner
    return nodes, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("source")
    ap.add_argument("--tokens", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--presets", choices=("on", "off"), default="on")
    ap.add_argument("--layout", choices=("on", "off"), default="on",
                    help="core layout for wrapper classes (phase 2); off keeps them classes")
    ap.add_argument("--media-url", default="")
    ap.add_argument("--fragment", action="store_true", help="a part: convert everything, no <main> to look for")
    ap.add_argument("--keep", default="", help="comma-separated element paths whose classes stay classes")
    args = ap.parse_args(argv)
    src = Path(args.source).read_text(encoding="utf-8")
    src = re.sub(r"<!--\s*(?:wp:html|/wp:html|clara-ve-key:[^>]*)\s*-->", "", src)
    tokens = json.loads(Path(args.tokens).read_text())
    conv = Converter(src, tokens, args.presets == "on", args.media_url, [k for k in args.keep.split(",") if k],
                     layout=args.layout == "on")
    tree = Tree(src)
    nodes, main_node = page_nodes(tree, args.fragment)
    holder = Node("#page", [], 0, 0, None)
    holder.children = nodes
    markup = "\n\n".join(conv.children(holder)) + "\n"
    Path(args.out).write_text(markup, encoding="utf-8")
    report = {"source": args.source, "presets": args.presets, "blocks": dict(conv.blocks.most_common()),
              "converted": dict(conv.converted.most_common()), "keptClasses": dict(conv.kept.most_common()),
              "shell": {"tag": main_node.tag, "classes": main_node.classes()} if main_node else None}
    Path(args.out + ".report.json").write_text(json.dumps(report, indent=2) + "\n")
    total = sum(conv.blocks.values())
    print(f"convert-source: {Path(args.source).name} → {total} blocks ({conv.blocks.get('core/html', 0)} core/html); "
          f"converted {sum(conv.converted.values())} class(es) to attributes, kept {sum(conv.kept.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
