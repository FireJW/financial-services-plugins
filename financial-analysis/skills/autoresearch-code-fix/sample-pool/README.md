# Phase 1 Bug Sample Pool

Use this folder for the first small fixed sample set for the code-fix loop.

## Target Size

- 10 to 20 bugs

## Selection Rules

- each bug must be reproducible
- each bug must have a clear validation path
- each bug must have a known rollback point
- keep scope narrow enough to compare runs fairly
- prefer bugs from one codebase area before expanding

## Suggested Layout

```text
sample-pool/
├── README.md
├── sample-index.md
└── bugs/
    ├── bug-001.json
    ├── bug-002.json
    └── bug-template.json
```

See also:

- [../references/sample-pool-layout.md](../references/sample-pool-layout.md)

## Workflow

1. Add one bug record per sample.
2. Keep sample IDs stable over time.
3. Do not swap sample definitions mid-benchmark.
4. Record if a sample becomes invalid and replace it in a new sample-set version.
