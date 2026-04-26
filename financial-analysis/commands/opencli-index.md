---
description: Bridge an OpenCLI capture result into news-index as source-traceable evidence
argument-hint: "[request-json]"
---

# OpenCLI Index Command

Use this command when the source you need is dynamic, authenticated, or
site-adapted in a way that our normal public retrieval path does not cover
well, but you still want the final evidence judgment to go through the native
`news-index` flow.

This command is for the capture-adapter layer only. It does not replace:

- `news-index` scoring
- `claim_ledger`
- freshness windows
- contradiction handling
- reranking

Default behavior:

1. load an OpenCLI result payload or result file
2. normalize OpenCLI items into `news-index` candidates
3. apply an explicit source policy for source type, channel, and access mode
4. bridge the imported candidates into `news-index`
5. emit a normal `retrieval_result` plus an OpenCLI bridge report

Use it when:

- the page is authenticated or session-dependent
- the page is dynamic and public fetches are weak or incomplete
- you need to preserve screenshots, PDFs, or exported artifacts as reviewable
  evidence metadata

Do not use it when a stronger native route already exists:

- X / Twitter: use `x-index`
- WeChat browser-session flows: use the native WeChat routes

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_opencli_bridge.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Recommended v1 usage:

- `opencli.result_path` for a deterministic offline import
- `opencli.result` when a previous step already produced the payload in memory
- `opencli.input_mode = "codex_iab"` when the current Codex in-app Browser Use
  session has produced a dynamic-page capture payload
- `financial-analysis\skills\autoresearch-info-index\examples\opencli-bridge-request.template.json`
  for the bridge contract itself
- `financial-analysis\skills\autoresearch-info-index\examples\opencli-codex-iab-request.template.json`
  for the Browser Use capture contract
- start from `financial-analysis\skills\autoresearch-info-index\examples\opencli-source-profile.template.json`
  when you need a reviewed source-policy stub for a new site profile

Opt-in live runner:

- set `opencli.input_mode = "command"` only when you explicitly want the bridge
  to execute a local OpenCLI command first
- start from
  `financial-analysis\skills\autoresearch-info-index\examples\opencli-runner-request.template.json`
  for the runner contract
- runner failures are surfaced in `runner_summary`; they do not silently
  masquerade as a low-signal success
- if the runner writes a result file, that `result_path` is preserved into the
  bridge report and companion artifacts for traceability

Automatic companions:

- `opencli-bridge-completion-check.json`
- `opencli-bridge-completion-check.md`
- `opencli-bridge-operator-summary.json`
- `opencli-bridge-operator-summary.md`

Operator note:

- `opencli-index` is best treated as a capture adapter, not a source of final
  judgment
- Codex IAB Browser Use is also a capture adapter here; the bridge imports its
  visible text, final URL, screenshot, and capture metadata, then lets
  `news-index` judge the evidence
- use it to get authenticated or dynamic material into the repo's evidence
  pipeline, then let `news-index`, `completion-check`, and `operator-summary`
  decide whether the capture is actually usable
- keep X and WeChat on their native routes; use `codex_iab` here for dynamic
  non-X/non-WeChat pages that need the in-app browser's rendered view

Request example:

```json
{
  "topic": "China aluminum broker note check",
  "analysis_time": "2026-04-03T08:00:00+00:00",
  "questions": [
    "What changed in the latest broker or company-facing materials?"
  ],
  "claims": [
    {
      "claim_id": "driver-state-known",
      "claim_text": "The latest external driver can be described with an exact date."
    }
  ],
  "opencli": {
    "site_profile": "broker-research-portal",
    "result_path": "C:\\path\\to\\opencli-result.json",
    "source_policy": {
      "source_type": "research_note",
      "channel": "shadow",
      "access_mode": "browser_session",
      "allow_observed_at_fallback": true
    }
  }
}
```
