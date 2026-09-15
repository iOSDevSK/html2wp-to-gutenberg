#!/usr/bin/env python3
"""Check that the HTML inside the block markup is balanced.

Block comments and HTML tags are two separate things that both have to line up.
A file can have every <!-- wp:x --> matched by its <!-- /wp:x --> and still be
broken, because the markup a block *saves* between those comments is ordinary
HTML: leave a <div> unclosed and the browser adopts every following section into
it. WordPress will not complain — it serialises from the comments — so the page
only looks wrong once it is rendered.

That is exactly the fault this caught on the guide page, where one unclosed
wrapper swallowed the rest of the document and made it 4,794px too tall.

    python3 lint-html.py <theme-dir>       # exits non-zero if anything is off

Exit status: 0 clean, 1 problems found, 2 nothing to check (bad path, no files).
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

DIRS = ("content", "parts", "templates", "patterns")

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# PHP echoes and block comments are not HTML; take them out before parsing.
# Newlines are kept so the line numbers still refer to the file on disk.
PHP = re.compile(r"<\?(?:php|=).*?(?:\?>|\Z)", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)


def keep_newlines(match):
    return re.sub(r"[^\n]", "", match.group(0))


class Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.problems = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        # `<div/>` is not self-closing in HTML: the browser drops the slash and
        # opens the element. Only the void elements really close themselves.
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.problems.append(f"{self.getpos()[0]}: stray </{tag}>")
            return
        if self.stack[-1][0] == tag:
            self.stack.pop()
            return
        # Find it further down: everything above was left open.
        for depth in range(len(self.stack) - 1, -1, -1):
            if self.stack[depth][0] == tag:
                for open_tag, line in self.stack[depth + 1:]:
                    self.problems.append(f"{line}: <{open_tag}> is never closed")
                del self.stack[depth:]
                return
        self.problems.append(f"{self.getpos()[0]}: </{tag}> closes nothing")


def check(path):
    source = path.read_text(encoding="utf-8")
    source = PHP.sub(keep_newlines, source)
    source = COMMENT.sub(keep_newlines, source)

    parser = Balance()
    parser.feed(source)
    parser.close()
    problems = list(parser.problems)
    # Whatever is still open at the end of the file. The line named is the
    # outermost survivor; when a later element of the same name stole this
    # one's closing tag, the culprit is that later element, not this line.
    problems += [f"{line}: <{tag}> is never closed (or a later <{tag}> took its closing tag)"
                 for tag, line in parser.stack]
    return problems


def main(argv):
    flags = {a for a in argv if a.startswith("-")}
    args = [a for a in argv if not a.startswith("-")]
    if flags or len(args) > 1:
        print("usage: lint-html.py [<theme-dir>]", file=sys.stderr)
        return 2

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

    total = 0
    for path in files:
        for problem in check(path):
            print(f"{path.relative_to(theme)}:{problem}")
            total += 1

    print(f"\nChecked {len(files)} file(s). {total} problem(s).")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
