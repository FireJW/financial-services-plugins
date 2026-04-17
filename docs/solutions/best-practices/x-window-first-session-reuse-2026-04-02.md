---
title: Prefer new Edge windows and reuse prior X session workflows
date: 2026-04-02
category: best-practices
module: financial-analysis
problem_type: workflow_memory
component: x-evidence
symptoms:
  - New threads repeated the X login-state bootstrap from scratch
  - The workflow over-indexed on closing Edge to recover session access
  - Previously successful query paths and capture steps were not being reused
root_cause: missing_workflow_memory
resolution_type: documentation_update
severity: medium
tags: [x-index, x-login-state, edge, workflow-memory, session-reuse]
---

# Prefer new Edge windows and reuse prior X session workflows

## Problem

X information collection was repeatedly re-running browser bootstrap steps even
when the same workspace had already produced a usable query path, screenshot
path, or signed-session notes. In practice this caused unnecessary login-state
thrash and pushed the workflow toward interruptive actions on the user's main
Edge session.

## Rule

For X post collection and X login-state handling on Windows:

1. reuse the last successful workflow in the current workspace or continuing
   thread first
2. prefer a new Edge window in the user's existing signed-in profile when a
   visible search or capture step is enough
3. do not close the user's current Edge windows or pages by default
4. only ask for a close-and-relaunch remote-debug step after the user explicitly
   approves that interruption

## What To Reuse

- the last successful search query set
- the last successful post URL or author/time-window path
- existing screenshots or root-post image paths
- any already-running `127.0.0.1:9222` session
- notes about which path worked and which bootstrap path failed

## Preferred Order

1. existing `x-index` result or prior-thread notes
2. already-running signed session
3. new Edge window in the main signed-in profile
4. isolated remote-debug relaunch with explicit approval
5. `cookie_file` fallback
6. public scraping only as last resort

## Anti-Pattern

Do not treat "close Edge first" as the default opening move for a new thread.
That should be an exception path, not the baseline workflow.
