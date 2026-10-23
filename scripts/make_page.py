#!/usr/bin/env python3
"""Write audits/<slug>.html from _template/ai-search-check.html and an ask_engines.py answers file.

The page copy that needs judgement (whether each answer names the business, the "named instead"
chips and the one-line caption per engine) is written by gpt-5 from the answers, then checked
here against the house rules. Site readiness cards are kept from the page's current audit; if
it has none, pass --readiness with the sheet's readiness note and they are written from that.

Usage:
  python3 scripts/make_page.py ANSWERS.json [--readiness "note from the sheet"]
Then build and test as usual (scripts/build_pages.py, tests/test_pages.py).
"""
import argparse, datetime, html, json, os, pathlib, re, sys, urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "_template" / "ai-search-check.html"
ENGINES = ["ChatGPT", "Claude", "Google AI"]
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")

STYLE = """House rules for every word you write: Oxford English (organisation, recognised, favour), plain
words, no em dashes, no emojis, no prices or dollar figures, never mention any software tool or that
anything is tracked. Keep business names exactly as the engines wrote them."""


def gpt(prompt):
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        json.dumps({"model": "gpt-5", "reasoning": {"effort": "low"}, "input": prompt,
                    "text": {"format": {"type": "json_object"}}}).encode(),
        {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        d = json.load(r)
    out = "".join(c.get("text", "") for o in d.get("output", []) if o.get("type") == "message"
                  for c in o.get("content", []) if c.get("type") == "output_text")
    return json.loads(out)


def page_copy(a, need_readiness, readiness_note):
    answers = {e: [r["text"][:7000] for r in a["engines"][e]] for e in ENGINES}
    prompt = f"""You are writing the short copy for an "AI search check" page about one business.
Business: {a['business']} (website {a['site']})
Question put to each AI engine three times: "{a['question']}"

The nine answers, as JSON (engine -> [ask 1, ask 2, ask 3]):
{json.dumps(answers, ensure_ascii=False)}

Reply with JSON only:
{{
 "short_name": "how the business is naturally called in a sentence, e.g. 'Wood Property' for Wood Property Group",
 "engines": {{
  "<engine>": {{
   "named": [true/false for ask 1, 2, 3: does that answer name or recommend this business, under any of its names or its website?],
   "mentions": [[exact substrings of ask 1 that name this business], [...ask 2], [...ask 3]],
   "chips": ["up to 5 OTHER businesses this engine named most across its three asks, most frequent first, in a short clean form (drop branch or office suffixes after | or a dash)"],
   "caption": "one or two sentences summing up this engine's three asks"
  }} for each of ChatGPT, Claude, Google AI
 }}{', "readiness": [{"status": "pass" or "work", "title": "3 to 6 words", "text": "one sentence"}] (see below)' if need_readiness else ''}
}}

Caption style, matching these examples:
- "ChatGPT didn't name Wood Property in any of the three asks. Once it asked which kind of manager we meant; the other two times MICM and Ray White Southbank led."
- "Claude named 4DMedical straight away in all three asks, along with XV Technology and CT:VQ."
- "Google's AI answers named Readiness in one of the three asks. FlourishDx came up every time."
Say "Google's AI answers" for Google AI. Use the short name. Base every claim on the answers above.
{STYLE}
"""
    if need_readiness:
        prompt += f"""
Readiness: turn this note from our earlier site check into 4 to 7 cards, one per finding. Use only facts
the note states; do not invent. Passes first. Note: "{readiness_note}"
Example card: {{"status": "work", "title": "No llms.txt file", "text": "There's no short guide file telling AI engines which pages matter most."}}
"""
    return gpt(prompt)


# ---------- answer text to HTML ----------

def clean(md, google):
    md = re.sub(r"\n+(\*\*)?Sources:?(\*\*)?\s*\n(\s*[-*\d].*\n?)+", "\n", md)
    md = re.sub(r"\[\[\d+\]\]\([^)]*\)", "", md)
    md = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", md)
    md = re.sub(r"\(\[([^\]]+)\]\([^)]*\)\)", r"(\1)", md)
    md = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", md)
    md = md.replace("`", "")
    md = md.replace(" — ", ", ").replace("—", ", ")
    md = EMOJI.sub("", md)
    if google:
        md = re.sub(r"^\s*(Open|Closed|Opens|Closes)\b[^\n]*$", "", md, flags=re.M)
        md = re.sub(r"^\s*Call\s*(Directions)?\s*(Website)?\s*", "", md, flags=re.M)
        md = re.sub(r"^\s*[A-Z][a-z]+( [a-z]+){0,3}\s*$", lambda m: "" if len(m.group(0).split()) <= 4 and
                    re.search(r"agency|agent|store|shop|clinic|service|company|contractor|firm|office|centre|center|"
                              r"hospital|club|school|restaurant|supplier|manufacturer|dealer|broker|lawyer|attorney|"
                              r"physiotherapist|dermatologist|surgeon", m.group(0), re.I) else m.group(0), md, flags=re.M)
        md = re.sub(r"^-{3,}\s*$", "", md, flags=re.M)
        md = re.sub(r"^(\S[^\n]*?)\s?(\d\.\d) \(([\d.,]+K?)\)\s*$", r"**\1** (\2 stars, \3 reviews)", md, flags=re.M)
        # the line after a place card's rating is its category ("Custom home builder"): drop it
        lines, out, after_card = md.split("\n"), [], False
        for line in lines:
            if after_card and line.strip():
                after_card = False
                if len(line.split()) <= 5 and not re.search(r"[.,:;!?]", line):
                    continue
            out.append(line)
            if re.search(r"\(\d\.\d stars, [\d.,]+K? reviews\)\s*$", line):
                after_card = True
        md = "\n".join(out)
    return md.strip()


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    return re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)


def to_html(md):
    out = []
    for block in re.split(r"\n\s*\n", md):
        para = []
        for line in [l for l in block.split("\n") if l.strip()]:
            m = re.match(r"^(\s*)(?:[-*•]|(\d+)[.)])\s+(.*)$", line)
            if m:
                if para:
                    out.append("<p>%s</p>" % inline(" ".join(para)))
                    para = []
                tag = "ol" if m.group(2) else "ul"
                indent = ' style="margin-left:40px"' if len(m.group(1)) >= 2 else ""
                start = ' start="%s"' % m.group(2) if m.group(2) and m.group(2) != "1" else ""
                out.append("<%s%s%s><li>%s</li></%s>" % (tag, indent, start, inline(m.group(3)), tag))
            elif re.match(r"^\s*\|?\s*:?-{3,}", line):
                continue  # table rule
            elif line.lstrip().startswith("|"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                out.append("<p>%s</p>" % inline(" · ".join(c for c in cells if c)))
            elif line.startswith("#"):
                para.append("**%s**" % line.lstrip("# ").strip())
            else:
                para.append(line.strip())
        if para:
            out.append("<p>%s</p>" % inline(" ".join(para)))
    return "".join(out) or "<p>(No answer was given.)</p>"


def mark(h, mentions):
    names = sorted({html.escape(x, quote=False) for x in mentions if x and len(x) > 2}, key=len, reverse=True)
    if not names:
        return h
    rx = re.compile(r"(?<!\w)(%s)(?!\w)" % "|".join(map(re.escape, names)))
    # only touch text between tags
    return re.sub(r">([^<]+)<", lambda m: ">" + rx.sub(r"<mark>\1</mark>", m.group(1)) + "<", h)


# ---------- page ----------

def readiness_items(slug):
    src = ROOT / "audits" / f"{slug}.html"
    if not src.exists():
        return []
    return re.findall(r'<div class="i (?:pass|work)">.*?</p></div></div>', src.read_text(), re.S)


def check_copy(text):
    bad = [w for w in ["—", "$", "Gatha"] if w in text] + re.findall(r"\btrack(?:ed|ing)\b", text, re.I)
    bad += ["emoji"] if EMOJI.search(text) else []
    if bad:
        raise ValueError(f"copy breaks the house rules ({', '.join(bad)}): {text}")
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("answers")
    ap.add_argument("--readiness", default="", help="sheet readiness note, used when the audit has no readiness cards")
    args = ap.parse_args()
    a = json.load(open(args.answers))
    slug = a["slug"]
    items = readiness_items(slug)
    need = not items
    if need and not args.readiness:
        sys.exit(f"{slug}: no readiness cards in the current audit; pass --readiness")
    c = page_copy(a, need, args.readiness)
    short = c["short_name"]
    date = datetime.date.fromisoformat(a["date"])
    date_s = f"{date.day} {date:%B %Y}"
    t = TEMPLATE.read_text()

    score = {}
    for e in ENGINES:
        runs, ce = a["engines"][e], c["engines"][e]
        named = [bool(ce["named"][i]) or runs[i]["named"] for i in range(3)]
        for i in range(3):
            if bool(ce["named"][i]) != runs[i]["named"]:
                print(f"{slug} {e} ask {i + 1}: name match says {runs[i]['named']}, reading says {ce['named'][i]}; "
                      f"counting it as named", file=sys.stderr)
        score[e] = (named, ce)
    total = sum(sum(n) for n, _ in score.values())

    # engine cards
    cards = list(re.finditer(r'<div class="engine bad">(.*?)</div></div></div>\n', t, re.S))
    assert len(cards) == 3
    for m, e in reversed(list(zip(cards, ENGINES))):
        named, ce = score[e]
        n = sum(named)
        cls, verdict = ("bad", "Not named") if n == 0 else ("good" if n == 3 else "mid", f"Named in {n} of 3")
        name_html = re.search(r'<div class="name">.*?</div>', m.group(0), re.S).group(0)
        chips = "".join("<span>%s</span>" % html.escape(check_copy(x), quote=False) for x in ce["chips"][:5])
        label = "Named instead" if n == 0 else "Also named"
        new = (f'<div class="engine {cls}">{name_html}<div class="verdict">{verdict}</div>'
               f'<div class="note"><b>{label}</b><div class="chips">{chips}</div></div></div>\n')
        t = t[:m.start()] + new + t[m.end():]

    # answer panes
    panes = list(re.finditer(r'<div class="ev bad">(.*?)<div class="cap">.*?</div></div>', t, re.S))
    assert len(panes) == 3
    for m, e in reversed(list(zip(panes, ENGINES))):
        named, ce = score[e]
        n = sum(named)
        head = re.search(r'<div class="t">.*?</div>', m.group(0), re.S).group(0)
        asks = ''.join('<button aria-pressed="%s" data-r="%d" type="button">Ask %d</button>' % (
            "true" if i == 1 else "false", i, i) for i in (1, 2, 3))
        runs = ""
        for i, r in enumerate(a["engines"][e]):
            body = to_html(clean(r["text"], e == "Google AI"))
            if named[i]:
                body = mark(body, ce["mentions"][i] + [a["business"], short, a["site"]])
            runs += '<div class="run%s" data-r="%d"><div class="body">%s</div></div>' % (" on" if i == 0 else "", i + 1, body)
        cls = "bad" if n == 0 else ("good" if n == 3 else "mid")
        cap = html.escape(check_copy(ce["caption"]), quote=False)
        new = (f'<div class="ev {cls}">{head}<div class="ans"><div class="asks">{asks}'
               f'<span class="hit">Named in {n} of 3</span></div>{runs}'
               f'<p class="how">The answer as given, {date_s}. Business names as the engine wrote them.</p></div>'
               f'<div class="cap">{cap}</div></div>')
        t = t[:m.start()] + new + t[m.end():]

    # readiness
    if need:
        items = ['<div class="i %s"><span class="m"></span><div><b>%s</b><p>%s</p></div></div>' % (
            "pass" if x["status"] == "pass" else "work", html.escape(check_copy(x["title"]), quote=False),
            html.escape(check_copy(x["text"]), quote=False)) for x in c["readiness"]]
    t = re.sub(r'<div class="ready">.*?</div>(?=<div style="text-align:center;margin:20px)',
               lambda m: '<div class="ready">\n' + "\n".join(items) + "\n</div>", t, flags=re.S)

    site = a["site"]
    t = (t.replace("19 October 2026", date_s)
          .replace('<div class="num">0<small> / 9</small></div>', f'<div class="num">{total}<small> / 9</small></div>')
          .replace("[website]", html.escape(site))
          .replace("[Business name] AI search check", html.escape(a["business"]) + " AI search check")
          .replace("answers named [Business name]", "answers named " + html.escape(a["business"]))
          .replace("[Business name]", html.escape(a["business"]))
          .replace("[slug]", slug))
    t = re.sub(r"<h1>.*?</h1>", lambda m: "<h1>“%s”</h1>" % html.escape(a["question"], quote=False), t, count=1, flags=re.S)
    for left in ["[X]", "[Y]", "[Business name]", "[website]", "—"]:
        if left in t:
            sys.exit(f"{slug}: '{left}' left on the page")
    (ROOT / "audits" / f"{slug}.html").write_text(t)
    print(json.dumps({"slug": slug, "score": total,
                      **{e: sum(score[e][0]) for e in ENGINES}}))


if __name__ == "__main__":
    main()
