#!/usr/bin/env python3
"""Ask the AI engines one question, three times each, and save the answers for a check page.

Engines (3 asks each, so the score is out of 9):
  ChatGPT    OpenAI gpt-5 with web search (OPENAI_API_KEY)
  Claude     Anthropic API with web search if ANTHROPIC_API_KEY is set, else the `claude` CLI with WebSearch
  Google AI  DataForSEO Google AI Mode; if a run has no AI answer, Google AI Overview from the normal results
             (DATAFORSEO_LOGIN, DATAFORSEO_PASSWORD)

For each answer it also pulls out the business names in the order given (gpt-5-mini) and
checks whether the business was named.

Writes <out>/<slug>-<date>.json (answers, names, costs) and <slug>-<date>.md (readable copy).

Usage:
  python3 scripts/ask_engines.py --slug wood-property --business "Wood Property Group" \
      --alias "Wood Property" --site woodproperty.com.au \
      --question "Who is the best apartment property manager in Southbank, Melbourne?" \
      --location "Melbourne,Victoria,Australia" --out /mnt/project-files/ai-answers
"""
import argparse, base64, datetime, json, os, pathlib, re, subprocess, sys, tempfile, time, urllib.request

ASKS = 3


def post(url, body, headers, timeout=300):
    req = urllib.request.Request(url, json.dumps(body).encode(), dict(headers, **{"Content-Type": "application/json"}))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ---------- ChatGPT ----------

def ask_chatgpt(q, country, city):
    tool = {"type": "web_search", "user_location": {"type": "approximate", "country": country}}
    if city:
        tool["user_location"]["city"] = city
    d = post("https://api.openai.com/v1/responses", {"model": "gpt-5", "tools": [tool], "input": q},
             {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
    text = "".join(c.get("text", "") for o in d.get("output", []) if o.get("type") == "message"
                   for c in o.get("content", []) if c.get("type") == "output_text")
    searches = sum(1 for o in d.get("output", []) if o.get("type") == "web_search_call")
    u = d.get("usage", {})
    # gpt-5: $1.25 / M in, $10 / M out; web search $0.01 per call
    cost = u.get("input_tokens", 0) * 1.25e-6 + u.get("output_tokens", 0) * 10e-6 + searches * 0.01
    return {"text": text, "source": "OpenAI gpt-5, web search", "searches": searches,
            "tokens": u.get("total_tokens"), "cost": round(cost, 4)}


# ---------- Claude ----------

def ask_claude(q):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        d = post("https://api.anthropic.com/v1/messages",
                 {"model": "claude-opus-5-5", "max_tokens": 4000, "messages": [{"role": "user", "content": q}],
                  "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 5}]},
                 {"x-api-key": key, "anthropic-version": "2023-06-01"})
        text = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
        u = d.get("usage", {})
        return {"text": text, "source": "Anthropic API, web search",
                "tokens": u.get("input_tokens", 0) + u.get("output_tokens", 0), "cost": None}
    with tempfile.TemporaryDirectory() as tmp:  # empty folder so the CLI sees no project files
        r = subprocess.run(["claude", "-p", q, "--output-format", "json", "--allowedTools", "WebSearch",
                            "--system-prompt", "You are Claude, a helpful assistant. Search the web when it helps "
                            "you give a current, accurate answer. Reply in plain prose as you would in a chat."],
                           cwd=tmp, capture_output=True, text=True, timeout=600)
    d = json.loads(r.stdout)
    return {"text": d.get("result", ""), "source": "Claude (claude CLI, web search)",
            "cost": d.get("total_cost_usd")}


# ---------- Google AI (DataForSEO) ----------

def dfs(path, task):
    auth = base64.b64encode(f"{os.environ['DATAFORSEO_LOGIN']}:{os.environ['DATAFORSEO_PASSWORD']}".encode()).decode()
    d = post("https://api.dataforseo.com/v3/" + path, [task], {"Authorization": "Basic " + auth})
    t = d["tasks"][0]
    if t["status_code"] != 20000:
        raise RuntimeError(f"DataForSEO {path}: {t['status_code']} {t['status_message']}")
    return t, (t.get("result") or [{}])[0] or {}


def ai_item(result):
    for i in result.get("items") or []:
        if i.get("type") == "ai_overview":
            return i
    return None


def ask_google(q, location):
    task = {"keyword": q, "location_name": location, "language_code": "en", "device": "desktop"}
    t, r = dfs("serp/google/ai_mode/live/advanced", task)
    cost, item, source = t.get("cost", 0), ai_item(r), "Google AI Mode (DataForSEO)"
    if not item or not (item.get("markdown") or "").strip():
        t, r = dfs("serp/google/organic/live/advanced", dict(task, load_async_ai_overview=True))
        cost += t.get("cost", 0)
        item, source = ai_item(r), "Google AI Overview (DataForSEO)"
    text = (item or {}).get("markdown") or ""
    refs = [{"title": x.get("title"), "url": x.get("url")} for x in (item or {}).get("references") or []]
    return {"text": text, "source": source if text else "no Google AI answer", "references": refs,
            "cost": round(cost, 4)}


# ---------- names and mentions ----------

def extract_names(text):
    if not text.strip():
        return []
    d = post("https://api.openai.com/v1/responses",
             {"model": "gpt-5-mini", "input": "List every business or organisation this answer recommends or names as "
              "an option, in the order they first appear, exactly as written. Leave out websites that are only cited "
              "as sources (for example realestate.com.au, Google, Wikipedia). Leave out star ratings and review counts. "
              "If the answer names no businesses, reply []. Reply with a JSON array of strings only."
              "\n\nANSWER:\n" + text},
             {"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"]})
    out = "".join(c.get("text", "") for o in d.get("output", []) if o.get("type") == "message"
                  for c in o.get("content", []) if c.get("type") == "output_text")
    try:
        return json.loads(out[out.find("["):out.rfind("]") + 1])
    except ValueError:
        return []


def named(text, terms):
    return any(re.search(r"\b" + re.escape(t) + r"\b", text, re.I) for t in terms)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", required=True)
    ap.add_argument("--business", required=True)
    ap.add_argument("--alias", action="append", default=[], help="other names to count as a mention")
    ap.add_argument("--site", required=True, help="domain, e.g. woodproperty.com.au")
    ap.add_argument("--question", required=True, action="append",
                    help="give it 3 times to put a different question on each ask (e.g. one per region)")
    ap.add_argument("--title", help="question shown on the page when there are several (default: the first)")
    ap.add_argument("--match", action="append", default=[],
                    help="names to match instead of business and aliases (for names that are common words)")
    ap.add_argument("--location", default="Australia", help="DataForSEO location_name")
    ap.add_argument("--country", default="AU")
    ap.add_argument("--city", default="")
    ap.add_argument("--engines", default="chatgpt,claude,google")
    ap.add_argument("--out", default="/mnt/project-files/ai-answers")
    a = ap.parse_args()

    terms = (a.match or [a.business] + a.alias) + [a.site]
    qs = a.question
    if len(qs) not in (1, ASKS):
        sys.exit(f"give --question once or {ASKS} times")
    fns = {"chatgpt": ("ChatGPT", lambda q: ask_chatgpt(q, a.country, a.city)),
           "claude": ("Claude", lambda q: ask_claude(q)),
           "google": ("Google AI", lambda q: ask_google(q, a.location))}
    date = datetime.date.today().isoformat()
    res = {"slug": a.slug, "business": a.business, "site": a.site, "question": a.title or qs[0],
           "questions": qs if len(qs) > 1 else None,
           "location": a.location, "date": date, "engines": {}}
    for key in a.engines.split(","):
        label, fn = fns[key]
        runs = []
        for n in range(1, ASKS + 1):
            for attempt in range(3):
                try:
                    run = fn(qs[(n - 1) % len(qs)])
                    break
                except Exception as e:  # network hiccup or engine error: retry, then record it
                    print(f"{label} ask {n} attempt {attempt + 1} failed: {e}", file=sys.stderr)
                    run = {"text": "", "source": "error", "error": str(e)}
                    time.sleep(2 ** attempt * 2)
            for attempt in range(3):
                try:
                    run["names"] = extract_names(run["text"])
                    break
                except Exception as e:  # same: retry, then go without the list of names
                    print(f"{label} ask {n} names attempt {attempt + 1} failed: {e}", file=sys.stderr)
                    run["names"] = []
                    time.sleep(2 ** attempt * 2)
            run["named"] = named(run["text"], terms)
            runs.append(run)
            print(f"{label} ask {n}: {'NAMED' if run['named'] else 'not named'} ({run['source']}) "
                  f"{', '.join(run['names'][:5])}", file=sys.stderr)
        res["engines"][label] = runs
    res["score"] = sum(r["named"] for runs in res["engines"].values() for r in runs)
    res["out_of"] = sum(len(runs) for runs in res["engines"].values())

    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    base = out / f"{a.slug}-{date}"
    base.with_suffix(".json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    md = [f"# {a.business}: AI answer check ({date})", "", f"Site: {a.site}", "",
          f"Question: \"{res['question']}\"", "", f"Named in {res['score']} of {res['out_of']} answers.", ""]
    for label, runs in res["engines"].items():
        for n, r in enumerate(runs, 1):
            md += [f"## {label}, ask {n} ({r['source']})", ""] + ([f"Asked: \"{qs[n - 1]}\"", ""] if len(qs) > 1 else []) + [
                   f"Named: {'yes' if r['named'] else 'no'}. Names: {', '.join(r['names']) or 'none'}.", "",
                   r["text"] or "(no answer)", ""]
    base.with_suffix(".md").write_text("\n".join(md))
    print(f"{res['score']} / {res['out_of']}  ->  {base}.json, {base}.md")


if __name__ == "__main__":
    main()
