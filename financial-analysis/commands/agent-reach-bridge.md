---
description: Import Agent Reach discovery signals as shadow observations and bridge them into news-index
argument-hint: "[request-json]"
---

# Agent Reach Bridge Command

Use this command when you want to treat `Agent Reach` as a separate discovery
layer, then feed selected findings into the current recency-first workflow
without replacing the existing fact firewall.

This command should:

1. read a saved Agent Reach payload or a bridge request
2. optionally run per-channel live fetches when the local toolchain is configured
3. normalize supported findings into `news-index` candidates
4. import them as `shadow` by default with `origin=agent_reach`
5. run `news-index` on top of that imported candidate set
6. return both the import summary and the bridged `retrieval_result`

When a downstream workflow needs authoritative X evidence, use the repository's
native `x-index` path first. Treat Agent Reach as augmentation or bridging, not
as the default X indexing layer.

Default expectations:

- imported findings stay `shadow` or `background` by default
- imported findings keep `origin=agent_reach`
- imported findings do not raise the main conclusion by themselves
- one slow or blocked channel does not stall faster channels
- re-running the same URL set within 6 hours skips duplicate imports

Local helpers:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_agent_reach_bridge.cmd [request.json] [--topic <query>] [--file <payload.json>] [--pseudo-home <path>] [--channels github rss youtube] [--output <result.json>] [--markdown-output <report.md>]`
- `financial-analysis\skills\autoresearch-info-index\scripts\run_agent_reach_deploy_check.cmd`

Current live defaults on this machine:

- if you do not pass `--channels`, live fetch defaults to `github + youtube`
- `rss` joins only when feeds are explicitly supplied
- `x` joins only when Agent Reach already has usable X credentials
- repository-native `x-index + remote_debugging` remains the primary X workflow
- Agent Reach may augment X-adjacent discovery, but it does not replace the
  native `x-index` route

Use this when you want broader discovery breadth from Agent Reach or its
upstream tools, but still want `news-index`, `article-brief`, `article-draft`,
and `article-revise` to remain the authoritative downstream pipeline.
