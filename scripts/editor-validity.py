#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-or-later
"""Open every page and post in the block editor and count invalid blocks.

This is the acceptance test the whole conversion is arranged around, and only
Gutenberg can answer it: validity is decided by re-running each block's save()
and comparing byte for byte, which no PHP can do. So a real browser logs in,
opens each post in the editor, waits on the editor's data store — not on the
canvas, which is an iframe — and walks every block recursively for
`isValid === false` (verification.md, criterion 2).

    python3 editor-validity.py --site http://127.0.0.1:8899 --user admin --password admin-password
    python3 editor-validity.py --site ... --types page            # pages only
    python3 editor-validity.py --site ... --ids 12,40             # named posts

Run it over every page AND every post, not a sample: invalid blocks cluster by
block type, so one page of the wrong kind hides fifty faults. Run it twice on
the pages holding a form — once with Visual Edit Lite absent and once with it
active (criterion 7).

Serve the sandbox with PHP_CLI_SERVER_WORKERS=8 or the editor's parallel
requests queue into timeouts; an initial load that still times out is retried
once (pitfall #17).

Exit status: 0 all valid, 1 invalid blocks or a post that would not load,
2 usage or login failure.
"""

import sys
from collections import Counter

from playwright.sync_api import TimeoutError as PWTimeout, sync_playwright

READY = (
    "() => window.wp && wp.data && wp.data.select('core/block-editor')"
    " && (wp.data.select('core/block-editor').getBlocks().length > 0"
    "     || (wp.data.select('core/editor') && wp.data.select('core/editor').getEditedPostContent() === ''))"
)

WALK = """() => {
    const walk = (bs, o) => { bs.forEach(b => { o.total++;
        if (b.isValid === false) o.invalid.push(b.name);
        if (b.innerBlocks?.length) walk(b.innerBlocks, o); }); return o; };
    return walk(wp.data.select('core/block-editor').getBlocks(), {total:0, invalid:[]});
}"""


def option(argv, name, default=None):
    if name in argv:
        i = argv.index(name)
        if i + 1 < len(argv):
            return argv[i + 1]
    return default


def login(page, site, user, password):
    page.goto(f"{site}/wp-login.php")
    page.fill("#user_login", user)
    page.fill("#user_pass", password)
    page.click("#wp-submit")
    page.wait_for_load_state("networkidle")
    return "/wp-admin" in page.url


def collect(page, site, types):
    """Every post of the given types, any status, through the REST API with the login cookie."""
    nonce = page.request.get(f"{site}/wp-admin/admin-ajax.php?action=rest-nonce").text().strip()
    rows = []
    for post_type in types:
        route = "pages" if post_type == "page" else ("posts" if post_type == "post" else post_type)
        n = 1
        while True:
            r = page.request.get(
                f"{site}/wp-json/wp/v2/{route}?per_page=100&page={n}&status=any&context=edit&_fields=id,slug,status",
                headers={"X-WP-Nonce": nonce})
            if not r.ok:
                raise RuntimeError(f"REST {route} page {n}: HTTP {r.status}")
            for row in r.json():
                rows.append((post_type, row["id"], row.get("slug", ""), row.get("status", "")))
            if n >= int(r.headers.get("x-wp-totalpages", "1")):
                break
            n += 1
    return rows


def inspect(page, site, post_id, timeout):
    page.goto(f"{site}/wp-admin/post.php?post={post_id}&action=edit")
    page.wait_for_function(READY, timeout=timeout)
    return page.evaluate(WALK)


def main(argv):
    site = option(argv, "--site")
    user = option(argv, "--user")
    password = option(argv, "--password")
    if not (site and user and password):
        print("usage: editor-validity.py --site <url> --user <u> --password <p>"
              " [--types page,post] [--ids 1,2] [--timeout SECONDS]", file=sys.stderr)
        return 2
    site = site.rstrip("/")
    types = (option(argv, "--types") or "page,post").split(",")
    only = {int(x) for x in (option(argv, "--ids") or "").split(",") if x}
    timeout = int(float(option(argv, "--timeout", "45")) * 1000)

    grand = Counter()
    invalid_by_name = Counter()
    failures = 0

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        context = browser.new_context()
        page = context.new_page()

        if not login(page, site, user, password):
            print(f"error: login as {user} at {site} failed", file=sys.stderr)
            browser.close()
            return 2

        rows = collect(page, site, types)
        if only:
            rows = [r for r in rows if r[1] in only]
        if not rows:
            print("error: nothing to inspect", file=sys.stderr)
            browser.close()
            return 2

        print(f"{'type':5s} {'id':>5s}  {'slug':32s} {'status':8s} {'blocks':>6s}  invalid")
        for post_type, post_id, slug, status in rows:
            report = None
            for attempt in (1, 2):
                try:
                    report = inspect(page, site, post_id, timeout)
                    break
                except PWTimeout:
                    if attempt == 2:
                        print(f"{post_type:5s} {post_id:5d}  {slug[:32]:32s} {status:8s}"
                              f"  !! editor did not become ready (twice)")
                        failures += 1
            if report is None:
                continue
            grand["blocks"] += report["total"]
            grand["invalid"] += len(report["invalid"])
            invalid_by_name.update(report["invalid"])
            mark = ", ".join(sorted(set(report["invalid"]))) if report["invalid"] else "—"
            print(f"{post_type:5s} {post_id:5d}  {slug[:32]:32s} {status:8s} {report['total']:6d}  "
                  f"{len(report['invalid'])} {mark}")

        browser.close()

    print("-" * 72)
    print(f"{len(rows)} post(s), {grand['blocks']} block(s), {grand['invalid']} invalid, "
          f"{failures} failed to load")
    for name, count in invalid_by_name.most_common():
        print(f"  {count:4d}  {name}")
    return 1 if grand["invalid"] or failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
