---
description: Check whether a separate last30days installation is present and usable
argument-hint: "[request-json]"
---

# Last30Days Deploy Check Command

Use this command before relying on a separate `last30days` deployment.

It should inspect:

- install root presence
- expected skill files
- required runtimes
- optional helpers such as `yt-dlp`
- env/config presence
- likely storage and SQLite history locations

The result should surface gaps clearly instead of assuming the deployment is
ready.

Default local target in this workspace:

- install root: `D:\Users\rickylu\.codex\vendor\last30days-skill`
- data/config root: `D:\Users\rickylu\.codex\vendor\last30days-data`

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_last30days_deploy_check.cmd [request.json] [--install-root <path>] [--output <result.json>] [--markdown-output <report.md>]`

Use this when the goal is to keep `last30days` deployed separately first, then
bridge only selected outputs into the current news and article workflow.
