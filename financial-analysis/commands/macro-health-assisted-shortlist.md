---
description: Run macro-health overlay first, optionally merge A-share sentiment / vol overlay, then execute the month-end shortlist
argument-hint: "[shortlist-request-json] [macro-health-request-json optional]"
---

# Macro Health Assisted Shortlist

Use this command when you want the repo to:

1. build `macro_health_overlay`
2. optionally build `sentiment_vol_overlay`
3. merge them into a shortlist request
4. run `month-end-shortlist`
5. keep the overlay artifacts and the shortlist result

Local helper:

- `financial-analysis\skills\month-end-shortlist\scripts\run_macro_health_assisted_shortlist.cmd "<shortlist-request.json>" "<macro-health-request.json>" [--output <result.json>] [--markdown-output <report.md>] [--overlay-output <overlay.json>] [--resolved-request-output <request.json>]`
- add `--sentiment-request-json "<a-share-sentiment-overlay-request.json>"` when you want the A-share VIX-like panic/euphoria layer attached too
- add `--sentiment-output "<sentiment-overlay.json>"` if you also want the resolved sentiment overlay artifact saved

Notes:

- the second argument is now optional
- if omitted, the workflow defaults to:
  - `financial-analysis\skills\macro-health-overlay\examples\macro-health-overlay-public-mix.request.template.json`
- the A-share sentiment / vol overlay is optional and should be supplied explicitly for now, because it is still a manual / semi-live hybrid layer
