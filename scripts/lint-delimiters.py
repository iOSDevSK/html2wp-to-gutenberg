#!/usr/bin/env python3
"""Check every block delimiter against WordPress's own grammar.

WP_Block_Parser matches a delimiter with, in essence:

    <!--\\s+(/)?wp:(namespace/)?name(\\s+{attrs}\\s+)?(/)?-->

The whitespace is not decoration. `<!-- wp:paragraph {"className":"lead"}-->`
— no space before the arrow — is not a block delimiter at all. WordPress reads
the paragraph as freeform HTML, the matching `<!-- /wp:paragraph -->` then
closes the wrong thing, and every block after it nests one level too deep. On
the guide page that swallowed the whole document into a sticky form panel and
made it 4,794px too tall.

Nothing else catches this: the comments still balance, the HTML in the file
still balances, and the fault only appears once WordPress parses it.

    python3 lint-delimiters.py <theme-dir>          # report
    python3 lint-delimiters.py <theme-dir> --fix    # insert the missing whitespace
"""

import re
import sys
from pathlib import Path

THEME = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else Path(".").resolve()
DIRS = ("content", "parts", "templates", "patterns")

# Anything that looks like it was meant to be a block delimiter.
CANDIDATE = re.compile(r"<!--\s*/?\s*wp:[^>]*?-->", re.S)

# What WordPress will actually accept, transcribed from WP_Block_Parser.
VALID = re.compile(
    r"^<!--\s+"
    r"(?P<closer>/)?"
    r"wp:(?P<namespace>[a-z][a-z0-9_-]*/)?(?P<name>[a-z][a-z0-9_-]*)"
    r"\s+"  # required, with or without attributes
    r"(?P<attrs>\{(?:(?!\}\s+/?-->).)*?\}\s+)?"
    r"(?P<void>/)?-->$",
    re.S,
)


def explain(token):
    if not token.startswith("<!-- "):
        return "no space after <!--"
    if re.search(r"\}/?-->$", token):
        return "no space between the attributes and -->"
    if re.search(r"wp:[a-z0-9_/-]+\{", token):
        return "no space between the block name and its attributes"
    if re.search(r"[^\s]/-->$", token):
        return "no space before /-->"
    if re.search(r"[^\s]-->$", token):
        return "no space before -->"
    if re.search(r"wp:[A-Z]", token):
        return "block name is not lowercase"
    return "does not match the block grammar"


def repair(token):
    """Put back the whitespace WordPress requires, where that is all that is wrong."""
    fixed = re.sub(r"\}(/?-->)$", r"} \1", token)          # attrs against the arrow
    fixed = re.sub(r"^<!--(?=/?\s*wp:)", "<!-- ", fixed)    # nothing after <!--
    fixed = re.sub(r"(wp:[a-z0-9_/-]+)(\{)", r"\1 \2", fixed)  # name against attrs
    fixed = re.sub(r"(?<=[^\s])(/?-->)$", r" \1", fixed)     # bare name against the arrow
    return fixed if VALID.match(fixed) else None


def check(path, fix=False):
    text = path.read_text(encoding="utf-8")
    problems = []
    repaired = 0

    for match in CANDIDATE.finditer(text):
        token = match.group(0)
        if VALID.match(token):
            continue
        line = text.count("\n", 0, match.start()) + 1
        snippet = " ".join(token.split())[:88]

        mended = repair(token) if fix else None
        if mended:
            text = text.replace(token, mended)
            repaired += 1
            problems.append(f"{line}: fixed — {explain(token)}\n      {snippet}")
        else:
            problems.append(f"{line}: {explain(token)}\n      {snippet}")

    if fix and repaired:
        path.write_text(text, encoding="utf-8")

    return problems


def main():
    fix = "--fix" in sys.argv
    files = [p for d in DIRS for p in sorted((THEME / d).rglob("*.html"))]
    files += sorted((THEME / "patterns").rglob("*.php"))

    total = 0
    for path in files:
        for problem in check(path, fix):
            print(f"{path.relative_to(THEME)}:{problem}")
            total += 1

    print(f"\nChecked {len(files)} file(s). {total} malformed delimiter(s).")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
