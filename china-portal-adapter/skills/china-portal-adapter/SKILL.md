---
name: china-portal-adapter
description: Local-only China portal discovery adapter for scan, normalization, filters, and operator notifications. Keeps manual submit boundaries intact.
---

# China Portal Adapter

Use this skill when the user needs discovery support on Chinese job platforms
without changing the rest of the local-first job-search pipeline.

## Core Principles

- scan and normalize first
- local sessions only
- manual submit boundary
- no full auto-apply loop
- normalize everything into our existing `job_card`

## Initial Platform Scope

- `boss`
- `liepin`
- `job51`
- `zhilian`

## v1 Request Shape

- `task`
  - `platform_probe | scan_jobs`
- `platforms`
- `keywords`
- `cities`
- `salary_filters`
- `blacklist_companies`
- `blacklist_recruiters`
- `session_mode`
  - `existing_local_only`
- optional `browser_executable_paths`
- optional `browser_profile_paths`
- optional `config_path`
- `notifications`
- optional `fixture`

## v1 Result Shape

- `source`
- `scan_status`
- `jobs`
- `warnings`
- `session_status`
- `platform_status`

## Hard Boundary

The adapter must not:

- auto-submit applications
- become the canonical tracker
- replace local fit scoring
- replace tailored packet generation

## Planned Local Helpers

The first runtime supports:

- real local `platform_probe`
- fixture-first `scan_jobs`
- non-fixture `scan_jobs` readiness gating

Default local config path:

- `D:\career-ops-local\config\china_portal_adapter.local.json`

It should later live under:

- `scripts/run_china_portal_adapter.cmd`
- `scripts/china_portal_adapter_runtime.py`

Current live-scan boundary:

- the adapter can run real local `platform_probe`
- the adapter can run bounded Boss list-page live scan in `scan_jobs`
- live scan remains list-page only and manual-submit only
- `liepin`, `job51`, and `zhilian` are still readiness-gated or scan-only for now
