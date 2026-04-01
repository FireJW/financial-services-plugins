# Evidence And Output Template

Use these default artifacts when running the feedback-iteration workflow.

## 1. Source Board

| Source | Exact date | Type | Evidence class | Why it matters | Reliability note |
|--------|------------|------|----------------|----------------|------------------|

Allowed evidence classes:

- `direct quote`
- `direct-ish`
- `summary`
- `supporting`
- `inference only`

## 2. Attributable Claim Inventory

| Claim | Source | Exact date | Evidence class | Can treat as confirmed? | Notes |
|------|--------|------------|----------------|--------------------------|-------|

## 3. Workflow Table

| Stage | Input | AI role | Human decision | Output artifact | Confidence |
|-------|-------|---------|----------------|-----------------|------------|

Default stages:

1. feedback collection
2. AI cleaning / clustering
3. principle extraction and prioritization
4. release mode or experiment decision
5. user-visible response loop
6. operating cadence

## 4. Weekly Artifact Template

Use this when the user wants a practical recurring output.

### Feedback Priorities Brief

- `As of`
- `Top themes`
- `Representative evidence`
- `What changed since last cycle`
- `Design principle`
- `Decision needed`
- `Ship now / preview / hold`
- `User-visible follow-up`
- `Signals to watch next cycle`

## 5. Overclaim Checklist

Before finalizing, check:

- did any summary-level source get upgraded to direct quote
- did any cadence detail come only from host notes
- did any AI step replace the human judgment node
- did any recommendation lose the source date
- did the workflow artifact distinguish confirmed vs inferred steps
