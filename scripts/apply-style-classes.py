#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Carry the source's inline styles across as utility classes (pitfall #6).

The static build wrote one-off declarations straight onto elements. Block
markup cannot hold a style attribute, so each declaration gets a class in the
theme's stylesheet instead, and this puts that class on the element that used
to carry the style.

Matching is by class set and ordinal: the third element in the original whose
classes are exactly {h-lg} is the third block in the converted page whose own
classes are exactly {h-lg}. Matching on "contains h-lg" instead drifts the
moment an unstyled sibling shares the class — 19 misplacements on the
reference.

The pass reconciles rather than appends — it removes utility classes that do
not belong as well as adding the ones that do, so it can be run repeatedly and
always leaves the same result. Styled elements that carry no class at all are
invisible to it and must be listed by hand.

    python3 apply-style-classes.py --sources <old>/clara-content/sources \\
        --pages <theme>/content/pages --map style-classes.json            # report
    python3 apply-style-classes.py ... --write                            # apply
    python3 apply-style-classes.py --example > style-classes.json         # starter map

The map is the project's own inline-style census — every distinct `style=`
declaration in the sources, verbatim, and the class (or classes) that replace
it. An empty string means "handled elsewhere": listed so nothing reads as
unmapped, applied nowhere.

Exit status: 0 done (unmapped declarations are reported, not fatal), 2 usage.
"""

import json
import re
import sys
from pathlib import Path

# Classes the conversion adds for its own reasons, which must not be mistaken
# for part of an element's identity when matching. The reveal-delay classes
# replace data-d="N" attributes (SKILL.md step 5); add more with --ignore.
STAGGER = {"d1", "d2", "d3", "d4", "d5"}

EXAMPLE = {
    "margin-top:1.1rem": "mt-1",
    "margin-top:2rem": "mt-2",
    "padding-bottom:0": "pb-0",
    "display:flex;justify-content:space-between;align-items:flex-end;gap:2rem;flex-wrap:wrap;margin-bottom:clamp(2rem,4vw,3rem)": "section-head",
    "color:#fff;margin-top:1.1rem": "text-white mt-1",
    "width:100%": "",
}

ELEMENT = re.compile(r"<(\w+)\b([^>]*)>")
CLASS_ATTR = re.compile(r'\bclass="([^"]*)"')
STYLE_ATTR = re.compile(r'\bstyle="([^"]*)"')
BLOCK = re.compile(r"<!--\s*wp:([a-zA-Z0-9/_-]+)\s*(\{.*?\})?\s*(/)?-->")


def source_plan(html, style_class):
    """{(classset, ordinal): extra} for every styled element in the original."""
    seen, plan, unknown = {}, {}, []

    for m in ELEMENT.finditer(html):
        attrs = m.group(2)
        cls = CLASS_ATTR.search(attrs)
        if not cls:
            continue
        key = frozenset(cls.group(1).split())
        ordinal = seen.get(key, 0)
        seen[key] = ordinal + 1

        style = STYLE_ATTR.search(attrs)
        if not style:
            continue
        declaration = style.group(1).strip()
        if declaration not in style_class:
            unknown.append((sorted(key), declaration))
            continue
        extra = style_class[declaration]
        if extra:
            plan[(key, ordinal)] = set(extra.split())

    return plan, unknown


def reconcile(markup, plan, utilities, not_identity):
    """Make every block's utility classes match the plan exactly.

    Edits are collected first and applied back to front, so every earlier
    offset stays valid while the markup is rewritten.
    """
    seen, changes, edits = {}, [], []

    for m in BLOCK.finditer(markup):
        if not m.group(2):
            continue
        try:
            attrs = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
        current = str(attrs.get("className", "")).split()
        if not current:
            continue

        identity = frozenset(c for c in current if c not in not_identity)
        if not identity:
            continue
        ordinal = seen.get(identity, 0)
        seen[identity] = ordinal + 1

        want = plan.get((identity, ordinal), set())
        have = {c for c in current if c in utilities}
        if have == want:
            continue

        changes.append((sorted(identity), sorted(have), sorted(want)))
        kept = [c for c in current if c not in utilities]
        new_list = kept + sorted(want)

        attrs["className"] = " ".join(new_list)
        # The space before the arrow is grammar (pitfall #1a): `{…}-->` is not
        # a delimiter, and the reference's own copy of this script wrote it.
        opener = (
            f"<!-- wp:{m.group(1)} "
            f"{json.dumps(attrs, separators=(',', ':'))}"
            f"{' /-->' if m.group(3) else ' -->'}"
        )
        edits.append((m.start(), m.end(), opener, set(current), new_list))

    for start, end, opener, old_set, new_list in reversed(edits):
        head, tail = markup[:start], markup[end:]

        # The block's saved HTML follows the comment and repeats the class list,
        # prefixed by the block's own wp-block-* class.
        def swap(t):
            have = t.group(1).split()
            if not old_set.issubset(set(have)):
                return t.group(0)
            # Keep the block's own classes; drop the old identity AND any
            # utility already there, so stale HTML cannot double a class.
            prefix = [c for c in have if c not in old_set and c not in utilities]
            return 'class="' + " ".join(prefix + new_list) + '"'

        tail = CLASS_ATTR.sub(swap, tail, count=1)
        markup = head + opener + tail

    return markup, changes


def option(argv, name):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def main(argv):
    if "--example" in argv:
        print(json.dumps(EXAMPLE, indent=2))
        return 0

    sources = option(argv, "--sources")
    pages = option(argv, "--pages")
    map_path = option(argv, "--map")
    if not (sources and pages and map_path):
        print("usage: apply-style-classes.py --sources <dir> --pages <dir> --map <json>"
              " [--ignore cls,cls] [--write]\n       apply-style-classes.py --example",
              file=sys.stderr)
        return 2
    sources, pages, map_path = Path(sources), Path(pages), Path(map_path)
    for p in (sources, pages):
        if not p.is_dir():
            print(f"error: {p} is not a directory", file=sys.stderr)
            return 2
    if not map_path.is_file():
        print(f"error: {map_path} is not a file", file=sys.stderr)
        return 2

    style_class = json.loads(map_path.read_text(encoding="utf-8"))
    utilities = {c for v in style_class.values() for c in v.split()}
    ignore = set((option(argv, "--ignore") or "").split(",")) - {""}
    not_identity = utilities | STAGGER | ignore

    write = "--write" in argv
    total_changed = total_unknown = 0
    seen_pages = 0

    for page in sorted(pages.glob("*.html")):
        source = sources / page.name
        if not source.exists():
            continue
        seen_pages += 1

        plan, unknown = source_plan(source.read_text(encoding="utf-8"), style_class)
        markup = page.read_text(encoding="utf-8")

        markup, changes = reconcile(markup, plan, utilities, not_identity)

        if changes or unknown:
            print(f"\n{page.stem}")
            for identity, have, want in changes:
                print(f"  .{'.'.join(identity):32s} {have or '—'} → {want or '—'}")
            for classes, style in unknown:
                print(f"  ? no class for {style!r} on .{'.'.join(classes)}")

        total_changed += len(changes)
        total_unknown += len(unknown)

        if write and changes:
            page.write_text(markup, encoding="utf-8")

    if not seen_pages:
        print(f"error: no page in {pages} has a source of the same name in {sources}",
              file=sys.stderr)
        return 2

    print(f"\n{seen_pages} page(s), {total_changed} element(s) reconciled, {total_unknown} unmapped")
    if not write:
        print("dry run — pass --write to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
