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

Important:

- this command performs a real side effect on the target official account
- it requires explicit human review approval before a real push is allowed
- it does not fake success if image upload or draft creation fails
- local image paths are allowed in the package because they will be uploaded and
  replaced before the final draft request is sent
