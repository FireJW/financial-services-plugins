# Benchmarking

## Core Rule

Do not use `10W+` as the only benchmark filter.

For this account, benchmark cases must be split into two pools:

1. `acquisition benchmarks`
2. `commercial-fit benchmarks`

Reason:

1. a 10W+ article proves public distribution fit
2. it does not automatically prove buyer quality
3. high-paying finance readers often sit inside narrower, lower-volume content
4. if you only copy the biggest traffic spike, you will drift toward hot-topic
   finance commentary and away from reusable paid assets

## What The Cases Say

### WeChat distribution reality

Two platform signals matter:

1. Newrank reported that WeChat produced `30.78万篇` `10万+` articles in 2024,
   which means 10W+ still exists at scale inside the ecosystem.
2. Newrank also showed that `看一看` can push articles to 10W+, but those surges
   are `not always precise traffic`.

Inference:

- A WeChat 10W+ article is useful as an acquisition benchmark.
- It is not enough by itself to define the product.

### WeChat case: 秦朔朋友圈

Useful facts:

1. launch reporting in 2015 said the first manifesto post broke `10万+` on day one
2. the account was explicitly positioned around `商业财经投资`
3. later Newrank wealth rankings still show the account capable of `10万+`-level
   top articles

What to copy:

1. authority-led entry point
2. broad business consequence framing
3. a calm, public-intellectual voice rather than trader slang

What not to copy:

1. do not assume you can reproduce founder prestige on day one
2. do not confuse institutional trust with personality worship

### WeChat case: 正解局

Useful facts:

1. Newrank reported that a `正解局` piece on the Iranian president crash reached
   `10万+` article reads and `10万+` audio plays
2. the account focuses on industry, city, and enterprise interpretation rather
   than stock tips

What to copy:

1. start from a real event
2. frame the story through a concrete question
3. turn complex context into explanatory structure

What not to copy:

1. do not mistake public-affairs heat for permanent reader loyalty
2. do not over-index on audio-specific distribution luck

### WeChat commercial case: 华尔街见闻

Useful facts:

1. in Newrank's 2017 case study, 吴晓鹏 argued users do not keep paying for
   anxiety; they pay to reduce `选择成本` and `机会成本`
2. the paid product was defined as `必读`, not as a premium version of random
   hot takes

What to copy:

1. sell selection, not volume
2. sell decision speed, not information overload
3. define the paid layer as a repeated daily or weekly utility

What not to copy:

1. do not use panic as the primary sales engine
2. do not hide the paid value inside vague "more depth"

### Commercial-fit counterexample: 市值风云

Useful facts:

1. multiple reports on its financing stated WeChat average reads were around `2万`
   while Toutiao average reads were around `5万`
2. despite not living on 10W+ WeChat articles, it built a strong audience of
   professionals and high-net-worth investors, then expanded into app, reports,
   and services

What this proves:

1. commercial quality can outrun public virality
2. a narrower, more useful finance audience can monetize before it becomes a
   mass-content machine

### Toutiao distribution reality

Two platform signals matter:

1. official and near-official conference coverage in late 2025 said deep-content
   reads on Toutiao were up nearly `3x`
2. the same coverage said more than half of daily active users touch deep
   selected content, and `10万+` / `100万+` deep-text hits continue to appear

Inference:

- Toutiao is not only for shallow quick takes.
- It can support long-form analytical reach if the frame is public-facing enough.

### Toutiao case: 金融八卦女

Useful facts:

1. 2026 coverage of Toutiao's deep-content push said `金融八卦女` had many
   `10万+` and even `100万+` long-form hits
2. cumulative Toutiao article reads were reported above `5000万`
3. one cited article about holiday homestay operators reached `204万` reads and
   added about `1.2万` followers

What to copy:

1. start from an affected group, not from a framework label
2. use narrative plus structural analysis
3. make the consequence obvious before introducing the method

What not to copy:

1. do not imitate gossip tone or personality packaging
2. do not let public-business storytelling replace the judgment product

## Benchmark Pool Design

### Pool A: 10W+ acquisition benchmarks

Keep cases only if they satisfy all three:

1. `10W+` or equivalent publicly visible high-read signal
2. finance, macro, business, or decision-adjacent topic
3. visible structural lesson you can copy

Use this pool to answer:

1. what headline frames break out
2. what event types attract broad finance-curious readers
3. which platform currently rewards deep analytical text

### Pool B: commercial-fit benchmarks

Keep cases only if they satisfy all three:

1. audience is clearly high-value or high-intent
2. the business model is understandable
3. the content format leads naturally into a paid asset

Use this pool to answer:

1. what buyers actually pay for
2. what free/paid boundary works
3. what product ladder the content can support

Pool B does not need every case to be 10W+.

## Benchmark Index Template

When indexing benchmark articles, track:

1. platform
2. article or ranklist URL
3. publish date
4. read band: `3w+ / 5w+ / 10w+ / 50w+ / 100w+`
5. account positioning
6. topic type
7. hook type
8. affected group
9. publicness score
10. decision-density score
11. commercial-fit score
12. CTA type
13. what to copy
14. what to avoid

This should feel closer to a `news-index` record than a vague inspiration list.

## Library Hygiene

Use three separate artifacts:

1. `benchmark-case-library.json` for curated human-owned case metadata
2. `benchmark-refresh-seeds.json` for discovery source definitions
3. `benchmark-case-observations.jsonl` for append-only machine refreshes

Rules:

1. machine refreshes can update scoring inputs, but they do not overwrite curated notes
2. new discoveries start as `candidate`, never as `reviewed`
3. the scored benchmark pool should default to `reviewed` cases only
4. keep `canonical_url` and `fetch_url` separate when needed:
   the reference page explains why the case belongs in the library, while the
   fetch page should be the most durable public surface you can refresh
5. do not point a reviewed benchmark at a generic account feed unless the
   runtime can preserve channel-level semantics without overwriting the case
   with an unrelated latest post

## Refresh Surface Policies

`reviewed` does not mean every benchmark is backed by a first-party article URL.

Some reviewed cases are:

1. direct article benchmarks
2. recurring channel or column benchmarks
3. account-model benchmarks curated from financing or profile coverage
4. cited-case proxies where the benchmark claim is carried by platform coverage,
   not by a durable original post URL

Use `benchmark_case_shape` to declare which shape a reviewed case belongs to.

Use `refresh_surface_policy` to declare what kind of refresh surface is
acceptable:

1. `first_party_required`
2. `mirror_allowed`
3. `proxy_allowed`

Rules:

1. keep `first_party_required` as the default for normal article benchmarks
2. use `mirror_allowed` only when the benchmark is still a direct article case,
   but the durable public surface is a mirror
3. use `proxy_allowed` only when the case is intentionally refreshed from a
   commentary page, profile page, or cited-coverage page that is itself the
   benchmark evidence surface
4. benchmark index outputs should surface the evidence mode so proxy-backed
   cases are never mistaken for direct article URLs

## What This Means For Your Strategy

1. WeChat needs both `broad-hook event explainers` and `core template demos`.
2. Toutiao titles must lead with consequence, conflict, or affected group.
3. Do not use pure method jargon as the outer packaging.
4. Keep one source research engine, but write two wrappers:
   `public-facing hook` and `decision-asset core`.
5. A post can be a great acquisition case and still be a bad monetization case.
