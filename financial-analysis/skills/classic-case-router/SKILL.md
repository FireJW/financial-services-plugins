---
name: classic-case-router
description: Route recurring finance, news, article, and workflow-improvement requests through a small set of proven case patterns before choosing tools. Use when a new request looks similar to past repeated work and the goal is to trigger the right existing workflow quickly and consistently.
---

# Classic Case Router

Use this skill when the request is not truly novel and instead matches a repeat
pattern we already know how to handle.

This router does not replace the underlying workflows. It selects the right
case pattern, then sends the work into the repository's native commands and
skills.

## Use This When

- the user wants latest event verification on a fast-moving topic
- the user wants X posts or threads turned into evidence
- the user wants a macro shock mapped into beneficiaries, losers, or pricing
- the user wants an evidence-backed draft article
- the user wants Codex to improve a repeated workflow such as stock analysis,
  code fixing, or document cleanup
- the user wants a proven combination of existing repo workflows plus external
  helper skills like gstack or CE, instead of an ad hoc process

## Core Rule

Do not start from scratch if a case already fits.

First:

1. classify the request into the nearest classic case
2. read the matching case markdown
3. follow its routing path into the native workflow
4. only improvise after the case path has been checked

## Case Index

- [latest-event-verification](references/latest-event-verification.md)
- [x-post-evidence](references/x-post-evidence.md)
- [macro-shock-chain-map](references/macro-shock-chain-map.md)
- [evidence-to-article](references/evidence-to-article.md)
- [workflow-improvement-loop](references/workflow-improvement-loop.md)

## Output Contract

Before doing the main work, state:

- which case matched
- why it matched
- which native workflow you are invoking next

If no case fits cleanly:

- say that explicitly
- name the closest case and why it was rejected
- then continue with the best native workflow
