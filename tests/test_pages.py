#!/usr/bin/env python3
"""Offline test of every built page listed in pages.csv. Nothing reaches GHL.

Every network request is answered locally: the page itself from <slug>/index.html, the webhook
with a fake 200, and anything else is aborted. The test fails if the page tries to
reach the real webhook in any way the stub didn't catch.

Checks per page: a page view is sent with ?e=, "I want to fix this" sends fix-this-click,
the call request form sends call-request with times, the details form sends
fix-this-form, and every payload carries slug, seg, wave, business, page and name.

Usage: python3 tests/test_pages.py [slug ...]
"""
import csv, json, pathlib, sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAKE_EMAIL = "pagetest@example.net"   # never a real contact
FAKE_NAME = "Page Test"
CORS = {"Access-Control-Allow-Origin": "*", "Access-Control-Allow-Headers": "*", "Access-Control-Allow-Methods": "POST, OPTIONS"}


def test(slug, browser):
    page_file = ROOT / slug / "index.html"
    posts, leaks = [], []
    ctx = browser.new_context()
    pg = ctx.new_page()
    pg.set_default_timeout(5000)

    def router(route):
        url, req = route.request.url, route.request
        if url.startswith(f"https://check.aieconomy.ai/{slug}/"):
            return route.fulfill(path=str(page_file), content_type="text/html")
        if "leadconnectorhq.com" in url:
            if req.method == "POST":
                posts.append(json.loads(req.post_data or "{}"))
            return route.fulfill(status=200, body="{}", headers=CORS)
        return route.abort()  # fonts, images, anything else: never leave the machine

    ctx.route("**/*", router)
    pg.on("requestfailed", lambda r: leaks.append(r.url) if "leadconnectorhq" in r.url else None)

    from urllib.parse import quote
    pg.goto(f"https://check.aieconomy.ai/{slug}/?e={quote(FAKE_EMAIL)}&n={quote(FAKE_NAME)}")
    pg.wait_for_timeout(400)
    pg.click("#fixbtn")
    pg.click("#callbtn")
    pg.fill("#cf textarea", "Tue or Wed morning")
    pg.click("#cf button[type=submit]")
    pg.wait_for_timeout(300)
    pg.reload(); pg.wait_for_timeout(300)  # same tab: must NOT send a second page view
    pg.click("#fixbtn"); pg.click("#formbtn")
    pg.click("#lf button[type=submit]")
    pg.wait_for_timeout(400)
    ctx.close()

    actions = [p.get("action") for p in posts]
    errors = []
    expected = ["page-view", "fix-this-click", "call-request", "fix-this-click", "fix-this-form"]
    if actions != expected:
        errors.append(f"actions {actions} != {expected}")
    for p in posts:
        for k in ("slug", "seg", "wave", "business", "page", "email", "name"):
            if not p.get(k):
                errors.append(f"{p.get('action')}: missing {k}")
        if p.get("slug") != slug:
            errors.append(f"{p.get('action')}: slug {p.get('slug')!r}")
        if p.get("page") != f"https://check.aieconomy.ai/{slug}/":
            errors.append(f"{p.get('action')}: page {p.get('page')!r}")
    call = next((p for p in posts if p.get("action") == "call-request"), {})
    if call.get("times") != "Tue or Wed morning":
        errors.append("call-request: times missing")
    if leaks:
        errors.append(f"unstubbed webhook requests: {leaks}")
    return errors


def main(argv):
    slugs = argv or [r["slug"] for r in csv.DictReader(open(ROOT / "pages.csv", newline="")) if (ROOT / "audits" / f"{r['slug']}.html").exists()]
    bad = 0
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception:  # cloud sessions ship Chromium here instead of the bundled build
            browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for slug in slugs:
            try:
                errs = test(slug, browser)
            except Exception as e:  # missing button, page didn't load, etc.
                errs = [f"page did not behave as expected: {str(e).splitlines()[0]}"]
            print(("PASS  " if not errs else "FAIL  ") + slug + ("" if not errs else ": " + "; ".join(sorted(set(errs)))))
            bad += bool(errs)
        browser.close()
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
