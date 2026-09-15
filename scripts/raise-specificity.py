#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Prefix every selector in a stylesheet with :root (pitfall #3).

WordPress emits its layout rules as

    :root :where(.is-layout-flow) > *            { margin-block: 0 }
    :root :where(.is-layout-flow) > :first-child { margin-block-start: 0 }

The :where() contributes nothing, but :root and :first-child each count as a
class, so those rules carry the weight of one and two classes respectively.
Most of a design is written as one or two classes too, so the cascade comes
down to source order — and core's global stylesheet is printed before the
theme's on some requests and after it on others, depending on what else is
enqueued. Margins disappear unpredictably.

Prefixing every selector with :root adds exactly one class-worth of weight to
all of them at once. The design's internal cascade is untouched, because every
rule moves by the same amount; what changes is that it now sits a step above
core's layout resets instead of level with them.

Skipped: :root and html selectors, which the prefix would break; the interior
of @keyframes, whose "from"/"to" are not selectors; and rules already prefixed,
so the script can be run twice without doubling up. A comment that sits on its
own before a selector is flushed first, or the prefix would land on it.

    python3 raise-specificity.py <theme>/assets/css/site.css            # report
    python3 raise-specificity.py <theme>/assets/css/site.css --write    # apply

Exit status: 0 done, 2 usage.
"""

import re
import sys
from pathlib import Path

# At-rules whose body holds ordinary style rules.
NESTS_RULES = ("@media", "@supports", "@container", "@layer")
# At-rules whose body is not selectors at all.
OPAQUE = ("@keyframes", "@font-face", "@page", "@property", "@counter-style")

PREFIX = ":root "


def should_skip(selector):
    s = selector.strip()
    if not s or s.startswith("@") or s.startswith(PREFIX.strip()):
        return True
    # :root and html are the prefix's own ancestors; prefixing them matches nothing.
    return bool(re.match(r"^(:root|html)\b", s))


def transform(css):
    out, i, depth, opaque_depth = [], 0, 0, None
    changed = 0
    buffer = ""

    while i < len(css):
        ch = css[i]

        # Comments pass through untouched. A comment that sits on its own,
        # before a selector, is flushed straight out — leaving it in the buffer
        # would make it part of the prelude and the prefix would land on it.
        if css.startswith("/*", i):
            end = css.find("*/", i + 2)
            end = len(css) if end == -1 else end + 2
            if buffer.strip():
                buffer += css[i:end]
            else:
                out.append(buffer + css[i:end])
                buffer = ""
            i = end
            continue

        if ch == "{":
            prelude = buffer
            buffer = ""
            stripped = prelude.strip()

            inside_opaque = opaque_depth is not None and depth > opaque_depth

            if stripped.startswith(OPAQUE):
                opaque_depth = depth
                out.append(prelude)
            elif stripped.startswith(NESTS_RULES) or inside_opaque:
                out.append(prelude)
            else:
                lead = prelude[: len(prelude) - len(prelude.lstrip())]
                parts = [p.strip() for p in stripped.split(",")]
                rebuilt = []
                for part in parts:
                    if should_skip(part):
                        rebuilt.append(part)
                    else:
                        rebuilt.append(PREFIX + part)
                        changed += 1
                out.append(lead + (",\n" + lead).join(rebuilt))

            out.append("{")
            depth += 1
            i += 1
            continue

        if ch == "}":
            out.append(buffer)
            buffer = ""
            depth -= 1
            if opaque_depth is not None and depth <= opaque_depth:
                opaque_depth = None
            out.append("}")
            i += 1
            continue

        buffer += ch
        i += 1

    out.append(buffer)
    return "".join(out), changed


def main(argv):
    flags = {a for a in argv if a.startswith("-")}
    args = [a for a in argv if not a.startswith("-")]
    if flags - {"--write"} or len(args) != 1:
        print("usage: raise-specificity.py <stylesheet.css> [--write]", file=sys.stderr)
        return 2
    css_path = Path(args[0])
    if not css_path.is_file():
        print(f"error: {css_path} is not a file", file=sys.stderr)
        return 2

    result, changed = transform(css_path.read_text(encoding="utf-8"))

    if "--write" in flags:
        css_path.write_text(result, encoding="utf-8")
        print(f"{changed} selector(s) prefixed with :root in {css_path}")
    else:
        print(f"{changed} selector(s) would be prefixed — pass --write to apply")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
