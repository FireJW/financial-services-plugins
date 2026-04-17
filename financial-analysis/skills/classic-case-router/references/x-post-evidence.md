# Case: X Post Evidence

## Use When

- the user provides an X or Twitter post URL
- the goal is to read the main post, thread, screenshots, or image claims
- the user wants source-traceable extraction instead of loose summarization

## Native Route

1. Start with [`/x-index`](../../../commands/x-index.md)
2. Reuse the last successful signed-session or screenshot path in the current
   workspace before bootstrapping a new login-state flow
3. Prefer a new Edge window over interrupting the user's current Edge pages
4. Prefer the repository's signed-session path before public scraping
5. If the extracted post needs broader verification, bridge into
   [`/news-index`](../../../commands/news-index.md)

## Required Output Shape

- main post text
- thread completeness note
- screenshot path when available
- image summary separated from post text
- source link and extraction method

## Anti-Patterns

- do not lead with OCR if direct text is available
- do not present image text as if it were original post text
- do not treat social evidence as core confirmation without stronger support
- do not close the user's current Edge windows by default when a reusable flow
  or new-window path can do the job
