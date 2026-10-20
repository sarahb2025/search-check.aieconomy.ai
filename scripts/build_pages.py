#!/usr/bin/env python3
"""Build check pages: audits/<slug>.html + scripts/cta_block.html -> <slug>/index.html

For every row in pages.csv that has an audit file, this:
  1. removes the old call-to-action box and the old tracking script,
  2. inserts scripts/cta_block.html with the row's slug, seg, wave and business,
  3. runs the content checks (no self-booking link, no em dashes, no Gatha, one webhook),
  4. writes <slug>/index.html (the folder Vercel serves at /<slug>/).

Usage: python3 scripts/build_pages.py [slug ...]   (no slugs = build every page that has an audit)
Exit code 1 if any page fails a check; failing pages are not written.
"""
import csv, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
HOOK = "https://services.leadconnectorhq.com/hooks/0G1q3az6pgxch6abG2iE/webhook-trigger/2c30da22-00b4-4f6f-82ce-c088a7e6da77"
BLOCK = (ROOT / "scripts" / "cta_block.html").read_text()

BANNED = {
    "self-booking link": re.compile(r"calendar\.app\.google|calendly\.com", re.I),
    "em dash": re.compile("—"),
    "mentions Gatha": re.compile(r"gatha", re.I),
    "unfilled placeholder": re.compile(r"'SLUG'|'SEG'|BUSINESS NAME"),
}


def js(s):
    return json.dumps(s)[1:-1].replace("'", "\\'")


def strip_old(html):
    """Remove the old CTA box and old tracking script, return (html, insert_at)."""
    start = html.find('<div class="cta">')
    if start == -1:
        raise ValueError('no <div class="cta"> found')
    end = html.find('<div class="bio">', start)
    if end == -1:  # older template: the CTA box has no bio after it, so end at its closing tag
        end = html.find("</div>", start) + len("</div>")
    html = html[:start] + "<!--CTA-->" + html[end:]
    # drop any script that posts to a webhook (the old tracking code)
    html = re.sub(r"<script>(?:(?!</script>).)*?(?:HOOK|leadconnectorhq)(?:(?!</script>).)*?</script>\s*", "", html, flags=re.S)
    return html


def build(row):
    slug = row["slug"].strip()
    src = ROOT / "audits" / f"{slug}.html"
    if not src.exists():
        return None, ["no audit file (audits/%s.html)" % slug]
    block = (BLOCK
             .replace("slug:'SLUG'", "slug:'%s'" % js(slug))
             .replace("seg:'SEG'", "seg:'%s'" % js(row["seg"].strip() or "other"))
             .replace("wave:'2'", "wave:'%s'" % js(row["wave"].strip() or "2"))
             .replace("BUSINESS NAME", js(row["business"].strip())))
    html = strip_old(src.read_text()).replace("<!--CTA-->", block)
    problems = [name for name, rx in BANNED.items() if rx.search(html)]
    if html.count(HOOK) != 1:
        problems.append("webhook appears %d times (expected 1)" % html.count(HOOK))
    return html, problems


def main(argv):
    rows = list(csv.DictReader(open(ROOT / "pages.csv", newline="")))
    if argv:
        rows = [r for r in rows if r["slug"] in argv]
    failed = 0
    for row in rows:
        html, problems = build(row)
        if html is None:
            print(f"SKIP  {row['slug']}: {problems[0]}")
            continue
        if problems:
            failed += 1
            print(f"FAIL  {row['slug']}: " + "; ".join(problems))
            continue
        out = ROOT / row["slug"] / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html)
        print(f"OK    {row['slug']} -> {row['slug']}/index.html")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
