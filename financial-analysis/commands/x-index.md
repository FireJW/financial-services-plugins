---
description: Build an evidence pack from X posts and bridge it into news-index
argument-hint: "[request-json]"
---

# X Index Command

Use this command when the user wants to collect X posts as source-traceable
evidence before analysis or article writing.

The output should prioritize:

- direct main-post text extraction
- same-author thread text when available
- image OCR as supplemental evidence only
- screenshots and source links for review

Default behavior:

1. discover candidate X post URLs from manual URLs, keywords, or allowlisted accounts
2. fetch each post and try to read visible post text before any OCR fallback
3. save the root-post screenshot plus media artifacts when available
4. when `ocr_root_text` is present, derive phrase / entity clues and turn them into narrower X search queries
5. for a kept root post, try a same-author time-window scan before falling back to same-author links on the page
6. build `post_summary`, `media_summary`, and `combined_summary`
7. bridge the kept posts into `news-index` as `social` observations

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_x_index.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

For the local helper path, pass an `x-index` request JSON file. The helper
prints JSON to stdout by default and writes the human-readable Markdown report
only when `--markdown-output` is provided.

Routing note:

- If the task is specifically about X / Twitter posts, threads, screenshots, or
  outbound links, start with `x-index` before using generic browser tooling.
- `x-index` is the repository's native signed-session workflow for X evidence
  collection and should be preferred over public-page scraping.

Browser session options:

- `browser_session.strategy = "remote_debugging"` attaches to an already running
  Chrome/Edge instance with a remote debugging port. This is the preferred
  Windows path when you need a real signed-in browser session.
- `browser_session.strategy = "cookie_file"` imports a Playwright-style cookie
  JSON file into the headless browse session before each fetch.

Session priority on Windows:

1. `remote_debugging` (preferred)
   - best fit for a real signed-in X session
   - preferred when thread completeness, cards, media, and outbound links matter
2. `cookie_file` (fallback)
   - use when a stable Playwright cookie export already exists
3. public access
   - last resort only
   - expect missing thread context, blocked content, or incomplete card data

Operator defaults on Windows:

1. reuse an already running signed-session path or the latest successful
   `x-index` artifacts in the current workspace before bootstrapping again
2. prefer a new Edge window in the user's existing signed-in profile when a
   visible search/capture step is enough
3. do not close the user's current Edge windows or pages by default just to get
   X login state
4. only use an interruptive close-and-relaunch remote-debug flow after the user
   explicitly approves it

Anti-pattern:

- Do not start by scraping public X pages when a signed browser session is
  available through `remote_debugging`.
- Do not treat "close all Edge windows" as the default first move in a new
  thread when a prior successful flow or a new-window path can be reused.

Remote debugging quick start on Windows:

1. First check whether a reusable `http://127.0.0.1:9222` session or recent
   `x-index` capture already exists in the current workspace.
2. If not, prefer a new Edge window in the user's signed-in profile for visible
   search/capture before asking for any interruptive relaunch.
3. Only when the user explicitly approves a close-and-relaunch step, run:
   - `financial-analysis\skills\autoresearch-info-index\scripts\launch_edge_remote_debug.cmd`
4. Add this to the request JSON:
   - `"browser_session": { "strategy": "remote_debugging", "cdp_endpoint": "http://127.0.0.1:9222", "required": true }`

The helper above assumes the signed-in Edge profile can be relaunched for CDP
access. It is not the default first move for a continuing workspace or thread.

Cookie file quick start:

- Place a cookie JSON file inside the workspace or an output directory and add:
  - `"browser_session": { "strategy": "cookie_file", "cookie_file": "C:\\path\\to\\cookies.json" }`

Request example:

```json
{
  "topic": "Morgan Stanley focus list screenshot",
  "manual_urls": ["https://x.com/example/status/123"],
  "ocr_root_text": "Exhibit 4: Morgan Stanley China/HK Focus List\nAluminum Corp. of China Ltd. 601600.SS",
  "same_author_scan_window_hours": 48,
  "same_author_scan_limit": 12,
  "browser_session": {
    "strategy": "remote_debugging",
    "cdp_endpoint": "http://127.0.0.1:9222",
    "required": true
  }
}
```
