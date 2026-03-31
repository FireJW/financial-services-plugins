---
description: Check whether a separate Agent Reach deployment is present, pinned, and usable as an upstream discovery layer
argument-hint: "[request-json]"
---

# Agent Reach Deploy Check Command

Use this command before relying on a separate `Agent Reach` deployment.

It should inspect:

- install root presence
- pseudo-home isolation on D drive
- the expected Python runtime path
- required binaries and optional helpers
- version-lock and doctor-report presence
- channel readiness for core discovery paths
- partial-install leftovers that should be cleaned

Default local targets in this workspace:

- install root: `D:\Users\rickylu\.codex\vendor\agent-reach`
- pseudo-home: `D:\Users\rickylu\.codex\vendor\agent-reach-home`
- Python runtime target: `D:\Users\rickylu\.codex\vendor\python312-full\python.exe`

Local helpers:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_agent_reach_deploy_check.cmd [request.json] [--install-root <path>] [--pseudo-home <path>] [--output <result.json>] [--markdown-output <report.md>]`
- `scripts\agent-reach\install.ps1`
- `scripts\agent-reach\clean-partial.ps1`

Use this when the goal is to keep `Agent Reach` deployed separately first, then
bridge selected findings into the current recency-first news and article
workflow without letting those findings bypass `news-index`.
