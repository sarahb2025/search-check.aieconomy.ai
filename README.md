#search-check-aieconomy

Shareable AI search check pages, one per prospect, served at `search-check.aieconomy.ai/[business-slug]/`. Part of AI Economy's Search Visibility campaign (direct to businesses; Gatha is reseller-only and not used here).

## Add a prospect
1. Copy `_template/` to `[business-slug]/` (lowercase, hyphens, e.g. `smith-plumbing`).
2. Fill the `{{PLACEHOLDERS}}` in `index.html`.
3. Push to `main` — Vercel deploys automatically.
4. Add the row to the tracking sheet.

## Placeholders
| Placeholder | What goes in |
| --- | --- |
| BUSINESS, DATE | Business name, date the check ran |
| CHATGPT/CLAUDE/GOOGLE_VERDICT | Short verdict: "Not mentioned", "Mentioned, competitor first", "Recommended" |
| ..._CLASS | `bad`, `mid` or `good` (colours the card) |
| ..._NOTE | One line of detail |
| PROMPT_1, PROMPT_2 | The two customer questions asked |
| P1_/P2_ engine rows | What each engine answered, one line |
| GAP_1–3, GAP_n_FIX | Why they're missing, and the fix |
| BOOK_URL | Pre-filled with Sarah's Google Calendar booking page |
| EMAIL | Sarah's email |
| FREE_CHECK_URL | Pre-filled with the "See how you show up in Search" page; swap for the live aieconomy.ai URL when ready |

## Dev setup (one-off)
- Repo under the AI Economy GitHub account (sarahb2025), Vercel connected, auto-deploy on push to `main`.
- DNS: `search-check.aieconomy.ai` CNAME → Vercel (record shown in Vercel → Domains).
- Enable Vercel Analytics for page views.
- `vercel.json` sets a 404 for `/_template/` so it's never public.
