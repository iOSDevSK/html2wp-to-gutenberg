#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Check every block delimiter against WordPress's own grammar, then check
that the delimiters pair up.

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

The second pass walks the delimiters WordPress *would* accept with a stack,
the way WP_Block_Parser does: a closer pops whatever is open, by position and
not by name, and anything still open at the end of the file is closed there
with everything after it nested inside. A closer with nothing to close, a
closer for the wrong block, and an opener that is never closed are all
reported with their line numbers. Counting block names cannot see any of
these — a swallowed closer keeps every name and every count and only changes
the depth (pitfall #16).

    python3 lint-delimiters.py <theme-dir>          # report
    python3 lint-delimiters.py <theme-dir> --fix    # insert the missing whitespace

Exit status: 0 clean, 1 problems found, 2 nothing to check (bad path, no files).
"""

import re
import sys
from pathlib import Path

DIRS = ("content", "parts", "templates", "patterns")

# PHP inside a pattern file is not part of the delimiter grammar. Mask it with
# a placeholder of the SAME LENGTH (newlines kept), so offsets and line numbers
# still refer to the file on disk: `{"ref":<?php echo $id; ?>}` reads as
# `{"ref":0 ... }` and is judged as the delimiter it will become.
PHP = re.compile(r"<\?(?:php|=).*?(?:\?>|\Z)", re.S)

# Anything that looks like it was meant to be a block delimiter: from `<!--`
# up to the first `-->`. A `>` inside the attributes is fine — WordPress's own
# grammar allows it. A `-->` inside them is not, and never occurs in markup
# WordPress serialised, because serialize_block_attributes() escapes `--`.
CANDIDATE = re.compile(r"<!--\s*/?\s*wp:(?:(?!-->).)*?-->", re.S)

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


def mask_php(text):
    def blank(match):
        php = match.group(0)
        return "0" + re.sub(r"[^\n]", " ", php[1:])

    return PHP.sub(blank, text)


def explain(token):
    if not re.match(r"<!--\s", token):
        return "no space after <!--"
    if re.search(r"^<!--\s*/\s+wp:", token):
        return "whitespace between / and wp:"
    if re.search(r"\}/?-->$", token):
        return "no space between the attributes and -->"
    if re.search(r"wp:[A-Za-z0-9_/-]*\{", token):
        return "no space between the block name and its attributes"
    if re.search(r"\S/-->$", token):
        return "no space before /-->"
    if re.search(r"\S-->$", token):
        return "no space before -->"
    if re.search(r"wp:[A-Za-z0-9_/-]*[A-Z]", token):
        return "block name is not lowercase"
    return "does not match the block grammar"


def mend(token):
    """Put back what WordPress requires, touching nothing inside the attributes."""
    fixed = token
    fixed = re.sub(r"^<!--(?=\S)", "<!-- ", fixed)                       # nothing after <!--
    fixed = re.sub(r"^(<!--\s+)/\s+(?=wp:)", r"\1/", fixed)               # "/ wp:" → "/wp:"
    fixed = re.sub(r"(wp:)([A-Za-z0-9_/-]+)",
                   lambda m: m.group(1) + m.group(2).lower(), fixed, count=1)  # block names are lowercase
    fixed = re.sub(r"(wp:[a-z0-9_/-]+)(\{)", r"\1 \2", fixed)             # name against attrs
    fixed = re.sub(r"\}(/?-->)$", r"} \1", fixed)                         # attrs against the arrow
    fixed = re.sub(r"(?<=\S)(/?-->)$", r" \1", fixed)                     # bare name against the arrow
    return fixed


def repair(token):
    """The mended token, or None when whitespace and case were not all that was wrong."""
    fixed = mend(token)
    return fixed if VALID.match(fixed) else None


def line_of(text, offset):
    return text.count("\n", 0, offset) + 1


def grammar(path, fix=False):
    """First pass: every candidate delimiter against the grammar.

    Returns (problems, final_text). With --fix, malformed delimiters that only
    lacked whitespace or lowercase are repaired in place and the file rewritten.
    """
    original = path.read_text(encoding="utf-8")
    masked = mask_php(original) if path.suffix == ".php" else original

    problems = []
    edits = []  # (start, end, replacement) against `original`, ascending

    for match in CANDIDATE.finditer(masked):
        token = match.group(0)
        if VALID.match(token):
            continue
        line = line_of(masked, match.start())
        snippet = " ".join(token.split())[:88]

        if fix and repair(token):
            # Validated on the masked token; the same edits apply to the real
            # one, since none of them reach inside the attributes.
            edits.append((match.start(), match.end(), mend(original[match.start():match.end()])))
            problems.append(f"{line}: fixed — {explain(token)}\n      {snippet}")
        else:
            problems.append(f"{line}: {explain(token)}\n      {snippet}")

    final = original
    if edits:
        pieces, pos = [], 0
        for start, end, replacement in edits:
            pieces.append(original[pos:start])
            pieces.append(replacement)
            pos = end
        pieces.append(original[pos:])
        final = "".join(pieces)
        path.write_text(final, encoding="utf-8")

    return problems, final


def pairing(path, text):
    """Second pass: the delimiters WordPress accepts, walked the way it walks them."""
    masked = mask_php(text) if path.suffix == ".php" else text
    problems = []
    stack = []  # (name, line)

    for match in CANDIDATE.finditer(masked):
        token = VALID.match(match.group(0))
        if not token or token.group("void"):
            continue  # malformed ones are freeform to WordPress; the grammar pass reported them
        line = line_of(masked, match.start())
        name = (token.group("namespace") or "") + token.group("name")

        if not token.group("closer"):
            stack.append((name, line))
        elif not stack:
            problems.append(
                f"{line}: <!-- /wp:{name} --> has nothing to close — WordPress reads it as freeform HTML")
        else:
            open_name, open_line = stack.pop()
            if open_name != name:
                problems.append(
                    f"{line}: <!-- /wp:{name} --> closes <!-- wp:{open_name} --> from line {open_line}"
                    " — WordPress pops by position, not by name")

    for open_name, open_line in stack:
        problems.append(
            f"{open_line}: <!-- wp:{open_name} --> is never closed — WordPress closes it at the end"
            " of the file, with everything after it nested inside")

    return problems


def usage():
    print("usage: lint-delimiters.py [<theme-dir>] [--fix]", file=sys.stderr)
    return 2


def main(argv):
    flags = {a for a in argv if a.startswith("-")}
    args = [a for a in argv if not a.startswith("-")]
    if flags - {"--fix"} or len(args) > 1:
        return usage()
    fix = "--fix" in flags

    theme = Path(args[0]).resolve() if args else Path(".").resolve()
    if not theme.is_dir():
        print(f"error: {theme} is not a directory", file=sys.stderr)
        return 2

    files = [p for d in DIRS for p in sorted((theme / d).rglob("*.html"))]
    files += sorted((theme / "patterns").rglob("*.php"))
    if not files:
        print(f"error: nothing to check under {theme} — no *.html in {'/, '.join(DIRS)}/"
              " and no patterns/*.php", file=sys.stderr)
        return 2

    malformed = unpaired = 0
    for path in files:
        rel = path.relative_to(theme)
        problems, text = grammar(path, fix)
        for problem in problems:
            print(f"{rel}:{problem}")
        malformed += len(problems)
        for problem in pairing(path, text):
            print(f"{rel}:{problem}")
            unpaired += 1

    print(f"\nChecked {len(files)} file(s). {malformed} malformed delimiter(s), {unpaired} pairing problem(s).")
    return 1 if malformed or unpaired else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
