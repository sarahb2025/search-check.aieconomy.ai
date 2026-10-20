# AI Search Check pages (AI Economy)

This repo holds the AI Search Check pages served at https://check.aieconomy.ai/<slug>/.
Every push to `main` deploys through Vercel. Work on a branch and open a pull request; Sarah or Karl merges.

## Layout

- `audits/<slug>.html`: the finished audit page as exported from Claude (one per business). Never hand-edit the CTA or tracking in here.
- `pages.csv`: one row per page: slug, business, seg, wave, sheet_row, artifact_link. No prospect emails in this repo.
- `scripts/cta_block.html`: the call-to-action box and GHL tracking used by every page.
- `scripts/build_pages.py`: builds `site/<slug>/index.html` from the audit + block, and refuses pages that break the rules below.
- `tests/test_pages.py`: offline browser test of every built page. The webhook is stubbed; nothing reaches GHL.
- `site/`: the built pages Vercel serves. Generated; rebuild, don't edit.

## Adding or updating pages

1. Put the audit HTML at `audits/<slug>.html` and add or check its row in `pages.csv`.
2. `python3 scripts/build_pages.py <slug>` (no slug = all).
3. `python3 tests/test_pages.py <slug>`. Every page must PASS before you commit.
4. Commit `audits/`, `pages.csv` and `site/` on a branch, open a PR listing each new URL.

## Rules

- URL format is always `https://check.aieconomy.ai/<slug>/`. Slug = business name, lower case, hyphens (`gs-diamonds`). There is no search.aieconomy.ai.
- Webhook (exactly once per page, only inside `cta_block.html`):
  `https://services.leadconnectorhq.com/hooks/0G1q3az6pgxch6abG2iE/webhook-trigger/2c30da22-00b4-4f6f-82ce-c088a7e6da77`
- Actions: `page-view` (on load, only when the link has `?e=`), `fix-this-click`, `fix-this-form`, `call-request` (with `times`). Every payload carries email, name, slug, seg, wave, business, page.
- Email links to prospects: `https://check.aieconomy.ai/<slug>/?e=<email>&n=<first name>`.
- No self-booking links (calls come in through the call request form). No prices, no em dashes, no emojis, no mention of Gatha or any tool, no mention of tracking. Oxford English.
- Contact email on pages: sarah@aieconomy.ai.

## Testing: never touch real contacts

- Never send anything to the real webhook from a test, a script or curl. Use `tests/test_pages.py`, which stubs it.
- If a live end-to-end test is truly needed, use a made-up address on a domain you control (not a prospect, not Karl, not @aieconomy.ai / @balmeragency.com.au / @gatha.ai, which GHL ignores), then delete that test contact and its tasks in GHL.

## Outreach (not in this repo)

Follow-ups, GHL stage moves and Gmail drafts run as scheduled tasks with the GHL, Gmail and Slack connectors. They only ever create drafts; nothing is sent to prospects automatically.
