#!/usr/bin/env python3
"""Quick AI readiness check of a business website, for the readiness cards on a check page.

Fetches the homepage, robots.txt, the sitemap and llms.txt, and checks nine things:
AI crawler access, sitemap, llms.txt, schema markup, meta description, one clear H1,
homepage word count, image alt text and FAQ content.

Prints JSON: {"site", "checks": [{"check", "pass", "detail"}], "note"}. The note is the
one-line summary used for the sheet's readiness column and for make_page.py --readiness.

Usage:
  python3 scripts/check_site.py https://www.example.com.au/
"""
import datetime, html, json, re, sys, urllib.error, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
AI_BOTS = ["GPTBot", "ChatGPT-User", "OAI-SearchBot", "ClaudeBot", "Claude-Web", "anthropic-ai",
           "PerplexityBot", "Google-Extended"]


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.geturl(), r.read(3_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, url, ""
    except Exception:
        return 0, url, ""


def render(url):
    """Homepage HTML from a real browser, for sites that block plain requests or build the page in script."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception:
            b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        pg = b.new_page(user_agent=UA)
        pg.goto(url, wait_until="domcontentloaded", timeout=45000)
        pg.wait_for_timeout(3000)
        out = pg.content()
        b.close()
    return out


def robots_blocks(txt):
    """AI bots that robots.txt shuts out of the whole site."""
    groups, cur, rules = [], [], False
    for line in txt.splitlines():
        line = line.split("#")[0].strip()
        if ":" not in line:
            continue
        k, v = [x.strip() for x in line.split(":", 1)]
        k = k.lower()
        if k == "user-agent":
            if rules:
                cur, rules = [], False
            if not cur:
                groups.append((cur, []))
            cur.append(v.lower())
        elif k in ("disallow", "allow") and groups:
            rules = True
            groups[-1][1].append((k, v))
    blocked = []
    for bot in AI_BOTS:
        own = [g for g in groups if bot.lower() in g[0]]
        g = own or [g for g in groups if "*" in g[0]]
        if g and any(k == "disallow" and v == "/" for k, v in g[0][1]) and not any(
                k == "allow" and v == "/" for k, v in g[0][1]):
            blocked.append(bot)
    return blocked


def text_of(h):
    h = re.sub(r"(?is)<(script|style|noscript|svg|template)[^>]*>.*?</\1>", " ", h)
    h = re.sub(r"(?s)<!--.*?-->", " ", h)
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h))).strip()


def main():
    url = sys.argv[1]
    if not url.startswith("http"):
        url = "https://" + url
    status, final, h = get(url)
    words = len(text_of(h).split()) if h else 0
    if status != 200 or words < 50:
        try:
            h = render(url)
            status = status if status == 200 else 200
        except Exception as e:
            print(json.dumps({"site": url, "error": f"could not load the homepage ({status}): {e}"}))
            sys.exit(1)
    base = "{0.scheme}://{0.netloc}".format(urllib.parse.urlsplit(final or url))

    rs, _, robots = get(base + "/robots.txt")
    robots = robots if rs == 200 and "<html" not in robots[:500].lower() else ""
    blocked = robots_blocks(robots)
    sm = [l.split(":", 1)[1].strip() for l in robots.splitlines() if l.lower().startswith("sitemap:")]
    sitemap = False
    for u in sm[:2] + [base + "/sitemap.xml", base + "/sitemap_index.xml", base + "/wp-sitemap.xml"]:
        s, _, body = get(u)
        if s == 200 and ("<urlset" in body or "<sitemapindex" in body):
            sitemap = True
            break
    ls, _, llms = get(base + "/llms.txt")
    has_llms = ls == 200 and len(llms.strip()) > 20 and "<html" not in llms[:500].lower()

    ld = re.findall(r'(?is)<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h)
    types = sorted(set(re.findall(r'"@type"\s*:\s*"([^"]+)"', " ".join(ld))))
    desc = re.search(r'(?is)<meta[^>]+name=["\']description["\'][^>]*>', h)
    desc = desc and re.search(r'(?is)content=["\']([^"\']*)', desc.group(0))
    desc = desc.group(1).strip() if desc else ""
    h1s = [text_of(x) for x in re.findall(r"(?is)<h1[^>]*>(.*?)</h1>", h)]
    h1s = [x for x in h1s if x]
    words = len(text_of(h).split())
    imgs = re.findall(r"(?is)<img\b[^>]*>", h)
    no_alt = [i for i in imgs if not re.search(r'(?i)\balt=["\'][^"\']+', i)]
    faq = "FAQPage" in types or bool(re.search(r"(?i)\b(FAQs?|frequently asked questions)\b", text_of(h)))

    checks = [
        ("AI crawler access", not blocked,
         "robots.txt lets AI assistants read the site" if not blocked
         else "robots.txt blocks " + ", ".join(blocked)),
        ("Sitemap", sitemap, "sitemap found" if sitemap else "no sitemap found"),
        ("llms.txt", has_llms, "llms.txt found" if has_llms else "no llms.txt"),
        ("Schema markup", bool(types),
         "schema on the homepage (" + ", ".join(types[:4]) + ")" if types else "no schema on the homepage"),
        ("Meta description", bool(desc), "meta description set" if desc else "no meta description"),
        ("Main heading", len(h1s) == 1,
         "one H1" if len(h1s) == 1 else ("no H1" if not h1s else f"{len(h1s)} H1 headings")),
        ("Homepage text", words >= 300, f"about {words} words on the homepage"),
        ("Image alt text", not no_alt,
         "all images have alt text" if not no_alt else f"{len(no_alt)} of {len(imgs)} images without alt text"),
        ("FAQ content", faq, "FAQ content on the homepage" if faq else "no FAQ"),
    ]
    p = sum(1 for _, ok, _ in checks if ok)
    today = datetime.date.today()
    note = (f"{p} pass, {9 - p} need work ({today.day} {today:%b}): "
            + "; ".join(d for _, ok, d in checks if not ok) + ". Passes: "
            + "; ".join(d for _, ok, d in checks if ok))
    print(json.dumps({"site": base, "checks": [{"check": c, "pass": ok, "detail": d} for c, ok, d in checks],
                      "passed": p, "note": note}, ensure_ascii=False))


if __name__ == "__main__":
    main()
