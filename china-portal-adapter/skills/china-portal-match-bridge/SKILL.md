---
name: china-portal-match-bridge
description: Bridge China portal scan results into the local career-ops role-pack scoring flow to produce a ranked shortlist without enabling automatic submission.
---

# China Portal Match Bridge

Use this skill when the user wants one ranked shortlist from:

- China portal discovery
- normalized `job_card`
- local fit scoring

## Core Rule

Keep discovery and scoring separate:

- `china-portal-adapter` discovers and normalizes
- `career-ops-local` scores and summarizes fit

## Request Shape

- `adapter_request`
  - inline China adapter request
- or `adapter_result_path`
  - path to a previously saved adapter result
- `role_pack`
- `candidate_profile_dir`
- `tracker_path`
- `output_dir`
- `minimum_fit_score`
- `top_n`
- `language`
- `dry_run`

## Result Shape

- `task`
- `source`
- `adapter_scan_status`
- `role_pack_used`
- `total_jobs`
- `shortlisted_jobs`
- `artifacts`
- `warnings`
- `generated_at`

## Hard Boundary

This bridge does not:

- submit applications
- update the tracker automatically
- replace `job-tailor`

It does prepare:

- one shortlist
- one `tailor_queue.json`
- one request JSON per shortlisted job
