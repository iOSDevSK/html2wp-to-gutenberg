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
"""

import re
import sys
from html.parser import HTMLParser
from pathlib import Path

THEME = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 and not sys.argv[1].startswith("-") else Path(".").resolve()
DIRS = ("content", "parts", "templates", "patterns")

VOID = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# PHP echoes and block comments are not HTML; take them out before parsing.
PHP = re.compile(r"<\?php.*?\?>", re.S)
COMMENT = re.compile(r"<!--.*?-->", re.S)


class Balance(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.problems = []

    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()[0]))

    def handle_startendtag(self, tag, attrs):
        pass

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
    source = PHP.sub("", source)
    source = COMMENT.sub("", source)

    parser = Balance()
    parser.feed(source)
    problems = list(parser.problems)
    problems += [f"{line}: <{tag}> is never closed" for tag, line in parser.stack]
    return problems


def main():
    files = [p for d in DIRS for p in sorted((THEME / d).rglob("*.html"))]
    files += sorted((THEME / "patterns").rglob("*.php"))

    total = 0
    for path in files:
        for problem in check(path):
            print(f"{path.relative_to(THEME)}:{problem}")
            total += 1

    print(f"\nChecked {len(files)} file(s). {total} problem(s).")
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
