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
4. build `post_summary`, `media_summary`, and `combined_summary`
5. bridge the kept posts into `news-index` as `social` observations

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

Anti-pattern:

- Do not start by scraping public X pages when a signed browser session is
  available through `remote_debugging`.

Remote debugging quick start on Windows:

1. Close all normal Edge windows.
2. Run:
   - `financial-analysis\skills\autoresearch-info-index\scripts\launch_edge_remote_debug.cmd`
3. Add this to the request JSON:
   - `"browser_session": { "strategy": "remote_debugging", "cdp_endpoint": "http://127.0.0.1:9222", "required": true }`

Cookie file quick start:

- Place a cookie JSON file inside the workspace or an output directory and add:
  - `"browser_session": { "strategy": "cookie_file", "cookie_file": "C:\\path\\to\\cookies.json" }`

Request example:

```json
{
  "topic": "US-Iran negotiation chatter",
  "manual_urls": ["https://x.com/example/status/123"],
  "browser_session": {
    "strategy": "remote_debugging",
    "cdp_endpoint": "http://127.0.0.1:9222",
    "required": true
  }
}
```
