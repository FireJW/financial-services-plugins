# Routing Index

Use this file before improvising a new workflow.

<!-- codex:native-routing-fast-map:start -->
## Native Retrieval Fast Map

Generic web search and public scraping are fallback-only when one of the
following native routes fits the task.

- Multi-channel discovery breadth, upstream augmentation, or Agent Reach import
  - Primary path: `financial-analysis/commands/agent-reach-bridge.md`
  - Fallback rule: use web search only if Agent Reach is unavailable or the
    needed source is outside the bridgeable channels
- Fast current-state note with freshness windows and claim ledger
  - Primary path: `financial-analysis/commands/news-index.md`
  - Fallback rule: use web search only if native retrieval cannot cover the
    required source set
- Live market quotes, portfolio/account data, or Longbridge-backed stock analysis
  - Primary path: `financial-analysis/commands/longbridge.md`
  - Skill path: `financial-analysis/skills/longbridge/SKILL.md`
  - Fallback rule: if Longbridge historical bars are blocked, keep Longbridge
    quote/intraday evidence and fall back to Eastmoney or Tushare for longer
    history
- Watchlist re-ranking, trigger/stop generation, or second-pass screening with
  Longbridge
  - Primary path: `financial-analysis/commands/longbridge-screen.md`
  - Fallback rule: keep Longbridge for quote/intraday confirmation and only use
    Eastmoney or Tushare to backfill longer history when needed
- Intraday plan trigger, invalidation, market-open, capital-flow, anomaly, or
  trade-stat monitoring after levels already exist
  - Primary path: `financial-analysis/commands/longbridge-intraday-monitor.md`
  - Fallback rule: do not place trades; if an endpoint is unavailable, report
    it under `unavailable` and preserve the remaining read-only evidence
- US insider-trade, institutional-investor, short-position, or quant-indicator
  enrichment for a supplied Longbridge watchlist
  - Primary path: `financial-analysis/commands/longbridge-screen.md`
  - Layer hints: `analysis_layers=["ownership_risk"]`,
    `analysis_layers=["quant"]`, or `analysis_layers=["all"]`
- Convert Longbridge screen watchlist or alert suggestions into audited
  account-side dry-run plans
  - Primary path: `financial-analysis/commands/longbridge-action-gateway.md`
  - Bridge helper:
    `financial-analysis/skills/longbridge/scripts/longbridge_action_plan_bridge.py`
  - Fallback rule: keep `longbridge-screen` read-only; never execute account
    mutations from the screen command itself
- X / Twitter threads, timestamps, screenshots, or reusable evidence packs
  - Primary path: `financial-analysis/commands/x-index.md`
  - Fallback rule: use public X scraping only after native signed-session paths
    are unavailable
- Authenticated or dynamic source capture
  - Primary path: `financial-analysis/commands/opencli-index.md`
  - Fallback rule: use manual browsing only if the page cannot be captured
    through OpenCLI or a stronger native route exists
- Topic ranking before drafting
  - Primary path: `financial-analysis/commands/hot-topics.md`
  - Fallback rule: use generic search only if the source mix is outside the
    configured discovery surface
- End-to-end article pipeline
  - Primary path: `financial-analysis/commands/article-workflow.md`
  - Fallback rule: use ad hoc browsing only when a required upstream source is
    not reachable through `news-index`, `x-index`, `agent-reach-bridge`, or
    `opencli-index`
- A-share shortlist generation or overlay-assisted ranking
  - Primary path: `financial-analysis/commands/month-end-shortlist.md`
  - Fallback rule: use generic search only if the task is truly outside the
    repo's shortlist workflow and no overlay path fits

If a fallback happens, record which native route was checked first and why it
was insufficient.
<!-- codex:native-routing-fast-map:end -->



## X post evidence extraction

- Trigger: user asks for X thread evidence, timestamps, screenshots, or original-post reconstruction
- Primary path: `financial-analysis/commands/x-index.md`
- Related docs: `financial-services-docs/docs/runtime/codex-dual-track/complexity-classification.md`, `financial-services-docs/docs/runtime/codex-dual-track/delivery-contract.md`
- Related KB: `#workflow/x-index`, `#recurring/x-evidence`
- Verification: links, timestamps, text capture, screenshot evidence
- Escalate when: batch extraction, cross-platform verification, or article-pipeline handoff is needed

## Feedback workflow reconstruction

- Trigger: user asks how a product or design team turns messy feedback into workflow or priorities
- Primary path: `financial-analysis/commands/feedback-workflow.md`
- Related docs: `financial-services-docs/docs/runtime/codex-dual-track/complexity-classification.md`, `financial-services-docs/docs/runtime/codex-dual-track/delivery-contract.md`
- Related KB: `#workflow/feedback-iteration`, `#recurring/feedback-workflow`
- Verification: dated source list, quote labels, and an explicit human judgment node
- Escalate when: fresh-source collection, moving facts, or cross-channel evidence collection is required

## A-share event-driven research

- Trigger: war, commodity, tariff, sanction, policy, or benchmark-shock analysis for one or more China stocks
- Primary path: `financial-analysis/skills/autoresearch-info-index/SKILL.md`
- Related docs: `financial-services-docs/docs/runtime/codex-dual-track/complexity-classification.md`, `financial-services-docs/docs/runtime/codex-dual-track/context-pack-template.md`, `financial-services-docs/docs/runtime/codex-dual-track/delivery-contract.md`
- Related KB: `#workflow/a-share-event`, `#recurring/macro-shock`
- Verification: exact cutoff date, confirmed vs inference-only split, transmission chain
- Escalate when: 2 or more stocks, multiple industry links, or valuation follow-through is required

## Local Obsidian KB capture

- Trigger: user asks to persist the current exchange into the local Obsidian KB
- Primary path: `CODEX_DEVELOPMENT_FLOW.md` local capture contract plus `node scripts/capture-codex-thread.mjs`
- Related docs: `financial-services-docs/docs/runtime/codex-dual-track/delivery-contract.md`, `financial-services-docs/docs/runtime/codex-dual-track/promotion-policy.md`
- Related KB: `#workflow/kb-capture`, `#promoted`
- Verification: capture command succeeds and verify script reports the thread as captured
- Escalate when: batch import, reconciliation, or missing-thread recovery is required
