---
name: decision-journal-publishing
description: Build and operate an evidence-layered finance publishing brand with a professional-user commercial center and a retail-safe acquisition wrapper. Use when defining account positioning, audience split, compliance-safe content boundaries, one-product launch plans, first template-pack offers, or weekly publishing SOPs for finance and market commentary brands. Especially useful when the goal is to turn fast-moving news plus AI workflows into a paid content and template business without drifting into illegal stock-picking, prophecy-style marketing, or generic AI-tips content.
---

# Decision Journal Publishing

Use this skill to design or run a finance content account that converts trust into
reusable paid assets.

## Hard Rules

1. Optimize for trust and repeatability, not "精准预言".
2. Keep professional users as the commercial center; retail expansion is a wrapper,
   not the core business.
3. In the first 30 days, sell one paid product only.
4. In the first 30 days, treat WeChat and Toutiao as the required core platforms.
5. Give frameworks and context for free; sell reusable assets, not longer articles.
6. Frame forward views as scenarios, trigger conditions, and invalidation rules.
7. Every public finance post must carry a time boundary, usage boundary, and
   invalidation logic.
8. Never write certainty, guaranteed return, or individualized buy/sell language.
9. Keep AI in a supporting role. The product is judgment infrastructure, not AI
   theater.
10. Always state what is intentionally deferred.

## Read These References As Needed

- For audience, positioning, and prediction-safe framing, read
  [references/positioning.md](references/positioning.md).
- For platform roles and packaging rules, read
  [references/platform-system.md](references/platform-system.md).
- For product ladder, pricing, and conversion logic, read
  [references/monetization.md](references/monetization.md).
- For the recommended first paid products and launch sequencing, read
  [references/first-offer.md](references/first-offer.md).
- For 10W+ case review, benchmark splits, and article-indexing rules, read
  [references/benchmarking.md](references/benchmarking.md).
- For cadence, topic planning, and workflow integration, read
  [references/operating-playbook.md](references/operating-playbook.md).
- For a concrete first-month posting schedule, read
  [references/launch-calendar-30d.md](references/launch-calendar-30d.md).
- For concrete post structures, CTA language, and product-pack templates, read
  [references/templates.md](references/templates.md).

## Local Helper Scripts

- [scripts/run_benchmark_index.cmd](scripts/run_benchmark_index.cmd) runs the
  benchmark-case indexing and review flow
- [scripts/run_benchmark_library_refresh.cmd](scripts/run_benchmark_library_refresh.cmd)
  refreshes reviewed cases, appends machine observations, and fills the
  candidate inbox
- [scripts/run_benchmark_readiness.cmd](scripts/run_benchmark_readiness.cmd)
  audits whether the checked-in refresh request is actually ready for 24h
  automation
- [cases/benchmark-case-library.json](cases/benchmark-case-library.json) is the
  reviewed benchmark library for WeChat and Toutiao
- [cases/benchmark-case-candidates.json](cases/benchmark-case-candidates.json)
  is the auto-discovered candidate inbox
- [cases/benchmark-case-observations.jsonl](cases/benchmark-case-observations.jsonl)
  is the append-only machine observation log
- [cases/benchmark-refresh-seeds.json](cases/benchmark-refresh-seeds.json) is
  the source seed file for the 24h refresh loop
- [cases/benchmark-refresh-daily-request.json](cases/benchmark-refresh-daily-request.json)
  is the scheduler-friendly request template for the 24h refresh loop; the CLI
  injects `analysis_time` when omitted
- [examples/benchmark-index-library-request.json](examples/benchmark-index-library-request.json)
  is the recommended library-backed request shape
- [examples/benchmark-index-demo-request.json](examples/benchmark-index-demo-request.json)
  is a seeded example request using the benchmark logic in this skill
- [examples/benchmark-refresh-demo-request.json](examples/benchmark-refresh-demo-request.json)
  is the local fixture refresh demo

## Workflow

### 1. Lock the audience split

Define the account in three layers:

1. core paid users
2. adjacent paid users
3. free traffic users

Default target stack:

1. Core paid: professional investors and operators who make repeated market or
   event-driven decisions.
2. Adjacent paid: high-participation retail investors who value process over tips.
3. Free traffic: generic retail observers and hot-topic readers.

Do not collapse all three into one voice. Speak to the top two; let the third layer
observe.

### 2. Define the promise and anti-promise

Lock one clear promise:

- turn noise into a decision-ready read
- separate confirmed facts, unclear signals, and inference
- provide reusable templates, not personality-only opinions

Also lock one explicit anti-promise:

- no exact-price prophecy
- no guaranteed hit rate
- no individualized stock-picking advice

If the user asks for prediction-led growth, redirect toward:

1. scenario tree
2. trigger board
3. probability range
4. invalidation condition
5. public review log

### 3. Choose the publishing shape

Phase-1 default account shape:

1. WeChat = trust, archive, conversion
2. Toutiao = cold-start traffic and angle testing
3. Xiaohongshu = optional save-worthy reuse, not required
4. X = deferred

### 4. Choose the paid asset ladder

Default ladder:

1. free post = framework and key variables
2. lead magnet = lite template
3. core paid product = reusable template pack
4. recurring offer = membership with updates, samples, workflow upgrades
5. selective high-ticket = limited consulting or bespoke packs

In the first 30 days:

1. launch one lead magnet
2. launch one template pack
3. defer membership
4. defer standalone retail paid products

### 5. Map the workflow to the existing content engine

Use the repo's existing flow wherever possible:

1. `news-index` to build evidence and freshness structure
2. `article-workflow` to turn evidence into a long-form draft
3. `article-auto-queue` to rank candidate topics
4. `article-revise` to create platform-specific second passes

The working principle is one source pack, many wrappers. Avoid writing four native
versions of the same idea.

### 6. Produce the final operating package

Default deliverable should include:

1. revised positioning
2. audience split
3. phase-1 platform split
4. free vs paid boundary
5. first product spec
6. weekly cadence
7. 30-day launch calendar
8. 90-day milestones
9. compliance guardrails
10. explicit deferred items
11. if the task is benchmark-driven, separate acquisition benchmarks from
    commercial-fit benchmarks
12. if the task includes case maintenance, keep reviewed cases, candidates, and
    machine observations as separate artifacts
13. treat reviewed-library `machine_state` as the latest readable snapshot and
    JSONL observations as the audit trail, not the other way around

## Output Requirements

Use short sections and concrete language.

Always include:

1. who the account is really for
2. what it will never promise
3. how retail expansion changes the funnel but not the core product
4. how "prediction" is reframed into transparent judgment infrastructure
5. what the first paid asset is
6. which platforms are required now vs deferred
7. which offers are intentionally not being launched yet

If the user asks for benchmark-based review:

1. collect at least two WeChat and two Toutiao reference cases when possible
2. do not let `10W+` stand in for buyer quality
3. explicitly label each case as `acquisition`, `commercial-fit`, or `mixed`
4. extract what to copy and what to avoid

## Default Judgment

If the user is torn between pro users and retail traffic:

1. keep professional users as the commercial center
2. use high-participation retail users as the volume expansion layer
3. treat generic retail as free attention, not product direction

If the user wants "死忠粉" fast:

1. build public scorekeeping
2. show judgment before outcome
3. publish invalidation rules
4. review misses openly

That creates harder trust than loud certainty.
