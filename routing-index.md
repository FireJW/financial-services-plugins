# Routing Index

Use this file before improvising a new workflow.

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
