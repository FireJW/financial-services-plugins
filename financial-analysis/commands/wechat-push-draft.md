---
description: Push a publish-package into the WeChat Official Account draft box
argument-hint: "[publish-package-or-request-json]"
---

# WeChat Push Draft Command

Use this command when the article package is already generated and you only want
the final WeChat Draft API step:

1. upload inline article images to WeChat
2. upload the cover image as permanent material
3. replace local or external image references in the HTML
4. call `draft/add`

It now also supports a browser-session fallback for the last mile when the
Official Account API path is blocked by IP whitelist or similar auth issues.

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_wechat_push_draft.cmd "<publish-package.json>" [--output <result.json>] [--markdown-output <report.md>]`

Credentials:

- pass `wechat_app_id` and `wechat_app_secret` in the request JSON
- or set `WECHAT_APP_ID` and `WECHAT_APP_SECRET`

Useful direct CLI flags:

- `--cover-image-path "<local-file>"`
- `--cover-image-url "<remote-image>"`
- `--author "<name>"`
- `--show-cover-pic 1`
- `--human-review-approved --human-review-approved-by "<reviewer>"`
- `--push-backend api|auto|browser_session`
- `--browser-session-strategy remote_debugging`
- `--browser-debug-endpoint "http://127.0.0.1:9222"`
- `--browser-editor-url "<optional-mp-editor-url>"`

Browser-session quick start on Windows:

1. prefer a real signed-in Edge profile
2. if a reusable `http://127.0.0.1:9222` session is not already open, run:
   - `financial-analysis\skills\autoresearch-info-index\scripts\launch_edge_remote_debug_wechat.cmd`
3. rerun the same push package with:
   - `--push-backend auto --browser-session-strategy remote_debugging --browser-debug-endpoint "http://127.0.0.1:9222"`

Current browser-session scope:

- best for already reviewed publish packages whose `content_html` already uses
  remote inline image URLs
- uploads the cover from a local file and drives the logged-in backend editor
- keeps a manifest and result JSON beside the publish package for replay

Important:

- this command performs a real side effect on the target official account
- it requires explicit human review approval before a real push is allowed
- it does not fake success if image upload or draft creation fails
- local image paths are allowed in the package because they will be uploaded and
  replaced before the final draft request is sent
- the result JSON / markdown summary also surfaces `workflow_publication_gate`
  so operators can still see `publication_readiness` plus Reddit review status
  without reopening `publish-package.json`
