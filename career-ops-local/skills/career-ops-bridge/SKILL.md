---
name: career-ops-bridge
description: Shared local-first runtime for personal job-search intake, scoring, tailoring, tracking, and apply-assist tasks. Keeps personal data outside the repo and only uses an external career-ops checkout when that path is explicitly better and available.
---

# Career Ops Bridge

This is the shared runtime layer behind the `career-ops-local` plugin.

## Core Principles

- local-first for intake, scoring, tracking, and apply-assist
- private data stays under `D:\career-ops-local`
- external `career-ops` is optional
- every output keeps a human review gate
- no auto-submit in v1

## Request Contract

Core request fields:

- `task`
  - `intake | match | tailor | track | apply_assist`
- `job_source`
  - `url | text | file`
- `job_input`
- `role_pack`
- `candidate_profile_dir`
- `output_dir`
- `require_human_review`
- `language`
- `export_pdf`
- `tracker_path`

Useful optional fields:

- `job_card`
- `job_card_path`
- `job_capture_text`
- `application_status`
- `status_note`
- `decision_override`
- `dry_run`
- `run_upstream_sync_check`
- `run_upstream_verify`

## Result Contract

Every task returns:

- `task`
- `status`
- `job_id`
- `job_card`
- `fit_summary`
- `fit_score`
- `decision`
- `role_pack_used`
- `artifacts`
- `warnings`
- `human_review_items`
- `generated_at`

## Local Helper

- `scripts\run_career_ops_local.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`
- `scripts\run_bootstrap_career_ops_local.cmd [--root <path>] [--upstream-root <path>] [--clone-upstream] [--force] [--dry-run]`
- `scripts\run_export_local_profile_to_upstream.cmd [--local-root <path>] [--upstream-root <path>] [--force] [--dry-run]`
- `scripts\run_upstream_sync_check.cmd [upstream-root]`
- `scripts\run_upstream_verify.cmd [upstream-root]`
- `scripts\run_upstream_pdf_with_local_browser.cmd --upstream-root <path> [--browser-executable <path>] <input.html> <output.pdf>`

## Templates

Request templates:

- `examples/job-intake-request.template.json`
- `examples/job-match-request.template.json`
- `examples/job-tailor-request.template.json`
- `examples/job-track-request.template.json`
- `examples/job-apply-assist-request.template.json`

Private-root templates:

- `templates/private-local/profile/`
- `templates/private-local/roles/`
- `templates/private-local/config/`
- `templates/private-local/applications/`

## External Career Ops Policy

If the external checkout exists and later proves better for a bounded flow,
prefer it only for that bounded flow.

Do not make it mandatory for:

- `job-intake`
- `job-match`
- `job-track`
- `job-apply-assist`

Prefer system Chrome or Edge for upstream PDF work before attempting to
download a Playwright-managed Chromium bundle.

When upstream `sync-check` should stay green, export the local profile into:

- `cv.md`
- `config/profile.yml`
- `article-digest.md`

via `run_export_local_profile_to_upstream.cmd` instead of editing those files by
hand.
