# Coding Style Guide

This file defines repository-wide coding expectations for Codex-driven work.

## Scope

These rules apply across:

- plugin commands and skills
- repository docs and workflow files
- utility scripts under `scripts/`
- temporary prototypes when they are part of an intentional task

## General Rules

- Prefer small, reviewable changes over broad cleanup.
- Preserve existing structure unless the task explicitly requires reorganization.
- Keep file edits tightly scoped to the user request.
- Use descriptive names; avoid cryptic abbreviations in new code and docs.
- Prefer straightforward control flow over clever compression.
- Add comments only when they explain non-obvious intent.

## Documentation Rules

- Treat command and skill docs as executable operator instructions.
- Keep steps concrete, ordered, and easy to verify.
- When adding examples, prefer PowerShell-compatible commands on Windows.
- Distinguish user-facing workflow docs from internal operator docs.

## Workflow Asset Rules

- Keep transient runtime output under `.tmp/`, `.tmp-*`, or `tmp-*`.
- Do not version browser profiles, caches, screenshots, or ad hoc session dumps.
- When a generated artifact must be kept, move it to a stable path such as
  `examples/` or `tests/fixtures/`.

## Script Rules

- Prefer deterministic behavior and explicit error messages.
- Support narrow verification before broad runs whenever practical.
- Avoid hidden side effects on unrelated files.

## Change Hygiene

- Update adjacent docs when operator behavior or entrypoints change.
- If a change affects repository workflow, update `.context/prefs/workflow.md`,
  `CODEX_DEVELOPMENT_FLOW.md`, or `CLAUDE.md` as needed.
