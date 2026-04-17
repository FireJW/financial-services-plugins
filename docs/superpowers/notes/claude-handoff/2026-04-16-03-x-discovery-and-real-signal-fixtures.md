# X Discovery And Real Signal Fixtures

## Current X/discovery status

X is already a first-class logic input layer in this repo.

The system currently supports:

- direct X-derived discovery candidates
- batch-style X ingestion
- inline `x_discovery_request`
- file-based `x_discovery_request_path`
- batch-style request payloads with `subject_registry`
- chain inference from `logic_basket_rules`
- rumor -> response -> confirmation / denial handling

## Current real handles wired in

Real fixture/example inputs currently include:

- `twikejin`
- `LinQingV`
- `tuolaji2024`
- `dmjk001`

These are already wired into the real-X fixture. They are not hypothetical.

## Where the real fixture lives

Fixture:

- `tests/fixtures/x_discovery_real/multi-source-batch.request.json`

Example template:

- `financial-analysis/skills/month-end-shortlist/examples/x-discovery-real-multi-source-batch.template.json`

## Why `dmjk001` matters

The latest handoff explicitly includes:

- `https://x.com/dmjk001/status/2044774708391125067`

This post is used for `中际旭创` Q1 expectation framing, especially around:

- `800G`
- `1.6T`
- Q1 volume ramp
- gross margin stable improvement

This matters because it reflects the intended product behavior:

- not waiting only for fully-landed official decomposition
- allowing market interpretation to enter the expectation surface

## What the discovery lane already models

At discovery/event level, the system already models:

- rumor confidence range
- market validation
- event state
- trading usability
- discovery bucket
- multi-source event cards
- trading-profile buckets
- trading-profile playbook

Current event-state thinking includes:

- `official_confirmed`
- `response_confirmed`
- `response_ambiguous`
- `response_denied`
- `rumor_unconfirmed`

## Current real-X artifact status

The current example artifact paths are:

- `.tmp/real-x-event-card-example/report.md`
- `.tmp/real-x-event-card-example/result.json`

Important warning:

- these artifacts are currently stale relative to local source/tests
- rerunning the example currently fails before fresh output is written

Current failure:

- `ValueError: could not convert string to float: '-'`

Observed when the wrapper script calls into the compiled shortlist runtime.

Interpretation:

- the X/discovery ingestion path itself is not the primary blocker
- the blocker is a stale/sample request value that still trips compiled runtime
  parsing during example regeneration

## Practical guidance for Claude

If improving X-side usefulness:

1. start from the real fixture, not synthetic inputs
2. trust current source/tests over the stale `.tmp` artifact
3. fix the example rerun path before judging the latest local reporting output
4. improve synthesis before adding even more fields
5. continue treating X/community as a logic + reaction layer, not just a quote
   layer
