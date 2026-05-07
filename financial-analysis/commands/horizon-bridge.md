---
description: Bridge saved Horizon discovery results into news-index as shadow upstream radar signals
argument-hint: "[request-json]"
---

# Horizon Bridge Command

Use this command when Horizon has already fetched, scored, filtered, or enriched
items and you want those saved results to enter the repo-native `news-index`
flow as source-traceable discovery candidates.

This command is an upstream discovery adapter. It does not install Horizon, run
Horizon, or replace the current evidence and publication chain.

Supported input:

- `horizon.result_path`
- `horizon.result`
- optional `horizon.input_mode = "command"` plus `horizon.command`

Default usage consumes saved JSON payloads only. A missing local Horizon
installation is not a blocker. The command runner is opt-in and does not install
Horizon.

Default behavior:

1. load a Horizon payload from `horizon.result` or `horizon.result_path`
2. flatten common saved result shapes such as `items`, `results`, `news`,
   `articles`, `filtered_items`, `enriched_items`, and `data.items`
3. normalize each item into a `news-index` candidate with `origin=horizon`,
   `channel=shadow`, and `access_mode=local_mcp` or `external_artifact`
4. preserve title, URL, source, published time, summary, score, heat, rank,
   tags, platform, and raw Horizon metadata
5. run the normal `news-index` result builder
6. emit the import summary, bridged `retrieval_result`, markdown report, and
   embedded completion-check/operator-summary surfaces

Opt-in command runner:

- set `horizon.input_mode = "command"` only when you explicitly want this
  bridge to execute a local Horizon export command first
- pass `horizon.command` as an argv array, for example
  `["python", "-m", "horizon.cli", "..."]`
- optional `horizon.timeout_seconds`, `horizon.working_directory`, and
  `horizon.result_path` are preserved in `runner_summary`
- when `horizon.result_path` is supplied in command mode, the bridge runs the
  command and then loads that file
- when no result path is supplied, the bridge parses the first JSON object or
  array from command stdout
- runner failures surface in `runner_summary` and do not silently become
  confirmation evidence

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_horizon_bridge.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Template:

- `financial-analysis\skills\autoresearch-info-index\examples\horizon-bridge-request.template.json`

Automatic companions when an output path is provided:

- `horizon-bridge-completion-check.json`
- `horizon-bridge-completion-check.md`
- `horizon-bridge-operator-summary.json`
- `horizon-bridge-operator-summary.md`

Guardrails:

- Horizon does not replace `news-index`, the claim ledger, completion-check, or
  operator-summary judgment.
- Horizon does not replace `x-index` signed-session X collection.
- Horizon does not replace Longbridge market data.
- Horizon does not replace `article_publish`, `wechat_push_readiness`, or
  `wechat_push_draft`.
- Horizon imported items default to `shadow` evidence.
- Horizon score, heat, and rank are discovery heat only. They are preserved in
  metadata but must not be treated as claim confirmation.
- Horizon command mode is explicit opt-in only; the bridge does not auto-install
  Horizon or run live discovery from a plain saved-payload request.
