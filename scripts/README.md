# AI Search Check pages kit

Six files that let Claude Code build, test and publish the AI Search Check pages at https://check.aieconomy.ai/<slug>/.

| File | Belongs at | What it is |
| --- | --- | --- |
| CLAUDE.md | repo root | Rules every Claude Code session follows |
| README.md | scripts/ (this file) | How the kit fits together |
| pages.csv | repo root | One row per page: slug, business, seg, wave, sheet row, artifact link |
| build_pages.py | scripts/ | Builds <slug>/index.html from audits/<slug>.html + the CTA block, and refuses pages that break the rules |
| cta_block.html | scripts/ | The call-to-action box and GHL tracking used on every page |
| test_pages.py | tests/ | Offline browser test of every built page; the webhook is stubbed, nothing reaches GHL |

## First session: fit the kit into this repo

The files are uploaded flat into `checks-kit/`. In the first Claude Code session:

1. Look at how this repo currently serves https://check.aieconomy.ai/parently/ (folder, file name, any vercel.json). Do not change how existing pages are served.
2. Move the kit files to the places above, and change `build_pages.py` and `test_pages.py` so they write and read built pages in the folder Vercel already serves (instead of `site/` if that's different).
3. Save the current live Parently page as `audits/parently.html`, build it, run the test (it must PASS), and open a pull request that lists exactly what changed.

## After that

- New or updated audit: save it as `audits/<slug>.html`, check its row in pages.csv, then build, test and open a PR.
- Setup script for the cloud environment: `pip install playwright` (cloud sessions already have Chromium; the test falls back to it).

## Asking the engines

`scripts/ask_engines.py` puts one question to ChatGPT, Claude and Google AI, three times each (score out of 9), and saves the answers as JSON and Markdown for the page. Google AI comes from Google AI Mode through DataForSEO, falling back to the AI Overview on the normal results when AI Mode gives no answer. It needs `OPENAI_API_KEY`, `DATAFORSEO_LOGIN` and `DATAFORSEO_PASSWORD`; Claude uses `ANTHROPIC_API_KEY` if set, otherwise the `claude` command line. Run `python3 scripts/ask_engines.py --help` for the options.
