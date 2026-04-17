# Structured Verifier Schema

As of 2026-04-01.

This document defines the wrapper-owned schema for `--structured-verifier`
mode. It is intentionally narrow in v1.

## Purpose

- make verifier gating machine-authoritative
- keep markdown as a derived sidecar, not a second truth source
- support deterministic fixture validation without a live model call

## Schema Version

`structured-verifier-v1`

## Required Top-Level Fields

```json
{
  "schemaVersion": "structured-verifier-v1",
  "verdict": "PASS | FAIL | PARTIAL",
  "hasAdversarialProbe": true,
  "checks": [
    {
      "title": "string",
      "commandRun": "string",
      "outputObserved": "string",
      "result": "PASS | FAIL | PARTIAL",
      "isAdversarialProbe": false
    }
  ]
}
```

## Rules

- `schemaVersion` must equal `structured-verifier-v1`
- `verdict` must be one of `PASS`, `FAIL`, `PARTIAL`
- `checks` must contain at least one entry
- each check must include:
  - `title`
  - `commandRun`
  - `outputObserved`
  - `result`
  - `isAdversarialProbe`
- at least one check must have `isAdversarialProbe = true`
- `hasAdversarialProbe` must be `true` and must match the derived value from
  `checks`

## Markdown Sidecar

The wrapper renders markdown deterministically from the structured report. The
markdown sidecar is for operators. The JSON report is the source of truth.

## Out Of Scope In V1

- deterministic preflight inside the structured artifact
- retry metadata or attempt history
- structured worker output
