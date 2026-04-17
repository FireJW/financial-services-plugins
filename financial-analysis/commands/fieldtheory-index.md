---
description: Search a local Field Theory bookmark cache for matching X URLs before live fetch
argument-hint: "[request-json]"
---

# Field Theory Index Command

Use this command when you want to inspect what a local `fieldtheory-cli`
bookmark cache can contribute to an X investigation before running the normal
live `x-index` fetch path.

What it does:

1. reads a local `bookmarks.jsonl` cache
2. scores bookmarked X posts against topic / keyword / phrase / entity clues
3. returns the best matching bookmarked URLs plus a compact match report
4. emits lookup companions that can be reviewed before the operator hands those
   URLs to `x-index`

Use it for:

- debugging whether your personal bookmark memory contains useful X seeds
- surfacing old bookmarked threads for a topic before live fetch
- validating the `fieldtheory` config block you plan to pass into `x-index`

Do not treat it as a replacement for native X retrieval:

- it does not replace `x-index`
- it does not replace signed-session fetch
- it does not replace thread capture, screenshots, or the final `news-index`
  bridge
- it is allowed to return zero matches; that is a valid negative lookup, not an
  automatic failure

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_fieldtheory_bookmark_index.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Automatic companions:

- `fieldtheory-index-completion-check.json`
- `fieldtheory-index-completion-check.md`
- `fieldtheory-index-operator-summary.json`
- `fieldtheory-index-operator-summary.md`

Start from:

- `financial-analysis\skills\autoresearch-info-index\examples\fieldtheory-index-request.template.json`
- `financial-analysis\skills\autoresearch-info-index\examples\x-index-fieldtheory-request.template.json`
  when you want to wire bookmark recall directly into a later `x-index` run
