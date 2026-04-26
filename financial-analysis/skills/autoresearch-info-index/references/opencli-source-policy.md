# OpenCLI Source Policy

OpenCLI is a capture adapter, not an evidence authority.

That means every imported OpenCLI item must still be mapped into the native
`news-index` trust model explicitly instead of inheriting authority from the
fact that a page was reachable through a richer capture path.

Codex IAB Browser Use captures follow the same rule. They can preserve the
rendered URL, visible text, DOM snapshot excerpts, and screenshots from the
current Codex in-app browser, but they still enter the system as capture
adapter evidence and must be judged by `news-index`.

## V1 Rules

1. default imported OpenCLI items to `channel=shadow`
2. prefer explicit `source_type` mapping over hidden heuristics
3. keep `access_mode` truthful:
   - `public`
   - `browser_session`
   - `blocked`
4. do not fake publication timestamps
5. if publication time is unavailable, only fall back to `observed_at` when
   the policy allows it and record that fallback in metadata
6. preserve blocked or partial captures in metadata instead of silently
   discarding them

## Recommended V1 Profiles

### `generic-dynamic-page`

- `source_type`: `analysis`
- `channel`: `shadow`
- `access_mode`: `browser_session`
- `allow_observed_at_fallback`: `true`

Use for:

- hard-to-render dynamic pages
- internal dashboards or exported summaries
- one-off authenticated content where the domain is not yet curated
- one-off Codex IAB Browser Use captures of rendered dynamic pages

### `broker-research-portal`

- `source_type`: `research_note`
- `channel`: `shadow`
- `access_mode`: `browser_session`
- `allow_observed_at_fallback`: `true`

Use for:

- broker strategy portals
- research library pages
- gated notes where the capture result contains excerpts, screenshots, or
  exported files

### `official-dynamic-page`

- `source_type`: `official_release`
- `channel`: `shadow`
- `access_mode`: `browser_session`
- `allow_observed_at_fallback`: `true`

Use for:

- dynamic government or regulator pages
- official pages that require richer rendering than the public fetch path

Note:

- even when the source type is stronger, `channel` should stay explicit
- do not let an official-looking page become `core` automatically without a
  reviewed policy decision

### `company-ir-portal`

- `source_type`: `company_statement`
- `channel`: `shadow`
- `access_mode`: `browser_session`
- `allow_observed_at_fallback`: `true`

Use for:

- investor relations portals
- dynamic statement pages
- company presentation/download centers

## Excluded V1 Routes

Do not route these through OpenCLI in v1:

- X / Twitter
- WeChat public-account editing or draft flows

Reason:

- the repo already has native workflows with stronger signed-session and
  operator-memory rules for those domains
- Codex IAB can still help an operator preview or inspect those pages, but the
  imported evidence route should stay native unless a reviewed exception is
  added

## Policy Review Checklist

Before promoting a new OpenCLI site profile beyond the generic default, answer:

1. what is the real source class?
2. what makes the page hard to capture with the normal path?
3. should the imported item still start as `shadow`?
4. what is the honest timestamp fallback rule?
5. what artifacts must be retained for human review?
