# Sample Pool Layout

Use this layout for the first fixed bug sample set in phase 1.

## Goal

Keep the sample pool small, stable, and comparable.

- target size: 10 to 20 bugs
- one sample file per bug
- stable IDs across benchmark runs
- explicit module boundaries
- explicit repro, verification, and rollback rules

## Recommended Layout

```text
sample-pool/
├── README.md
├── sample-index.md
└── bugs/
    ├── bug-001.json
    ├── bug-002.json
    └── bug-template.json
```

## Sample Selection Rules

- prefer bugs from one code area before expanding
- prefer bugs with clear failure signals
- exclude flaky or ambiguous issues from the first pool
- exclude bugs that require large environment setup until the loop is stable

## Per-Sample Minimum

Each sample should define:

- bug ID and title
- priority
- allowed and forbidden change paths
- plain-language bug description
- exact reproduction steps
- validation commands
- rollback target

This is enough for phase 1. Add more only if repeated use proves it is needed.
