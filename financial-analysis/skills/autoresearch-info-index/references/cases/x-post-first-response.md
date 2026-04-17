# Case: X Post First Response

Use this case when the user gives one or more X post URLs and wants to know
what the post says, what the images say, whether the thread matters, or whether
the claim is credible.

## Default Routing

1. Prefer the repository-native `x-index` workflow first.
2. Reuse the last successful X session flow, screenshots, and query path in the
   current workspace or continuing thread before bootstrapping again.
3. On Windows, prefer a new Edge window in the existing signed-in profile
   before any path that closes current Edge pages.
4. If a real signed-in browser session is already available, prefer that path
   over public-page scraping.
5. If the repository-native path degrades or returns incomplete text, use the
   logged-in gstack browser to directly read the visible text and capture a
   screenshot.
6. OCR is a supplement for images and fallback for failed text extraction, not
   the default source for post text.

## What To Extract

- exact main-post text when possible
- same-author thread continuation when it changes the claim
- image text or chart labels only as separate evidence
- a screenshot path for the root post when available
- raw claim list, not only a summary

## Output Shape

Always separate:

- `main post text`
- `thread text`
- `image evidence`
- `confirmed from the post itself`
- `not yet confirmed externally`
- `what needs stronger sources`

## Hard Rules

- Do not paraphrase away a direct quote if the exact wording matters.
- Do not merge image OCR into the main post text.
- If the post is an article-format X post, say that explicitly.
- If the reading path used a logged-in browser, say so.
- If the repository-native path failed and gstack succeeded, note that clearly.
- Do not close the user's current Edge windows unless the user explicitly
  approves that interruptive step.

## Recommended Follow-On

- If the user only wants to know what the post says, stop at a source-faithful
  readout plus a short credibility note.
- If the user wants to know whether the post is true, bridge into `news-index`
  and classify the social signal as `shadow` until stronger confirmation exists.
