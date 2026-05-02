# XHS GPT Image Workflow Design

Date: `2026-05-02`

## Goal

Build a clean Xiaohongshu (XHS) image-post workflow that can:

1. find high-heat, high-interaction comparable XHS posts
2. deconstruct why those posts worked
3. map the reusable structure onto local source material
4. generate polished XHS image posts with GPT Image
5. leave a local, reviewable package before any publishing step

The workflow should be useful for product/project promotion, market or finance
content, knowledge cards, and account-specific content iteration. It should not
be a blind scraper or a one-click spam publisher.

## User-Confirmed Direction

1. Use `xhs-writer-skill` as the primary reference for image-post generation.
   Its image quality and GPT Image use are the baseline to preserve.
2. Do not make the existing local HTML social-card renderer the main generator.
   It remains useful for preview, validation, and fallback exports.
3. Keep the development path clean: isolate the work in a dedicated branch or
   worktree, write the design first, then split implementation into focused
   steps.
4. Prefer a complete loop over a single drafting command:
   benchmark discovery -> viral deconstruction -> local content adaptation ->
   GPT Image generation -> QC -> optional publish -> performance review.

## External References

Use these as capability references, not as code copied wholesale:

- `JuneYaooo/xhs-writer-skill`
  - Primary generation reference.
  - Useful pieces: real-material image-to-image, 9:16 card deck output,
    selling-point scoring, viral-title formulas, caption and hashtag package.
  - Repo reference: <https://github.com/JuneYaooo/xhs-writer-skill>
- `autoclaw-cc/xiaohongshu-skills`
  - Strongest low-friction XHS automation reference.
  - Useful pieces: login check, keyword search, note detail, user profile,
    publish/fill-publish, JSON CLI shape, browser-extension bridge.
  - Repo reference: <https://github.com/autoclaw-cc/xiaohongshu-skills>
- `xpzouying/xiaohongshu-mcp`
  - Highest-star MCP option for XHS data and publishing.
  - Useful if we later want a standard MCP surface instead of direct scripts.
  - Repo reference: <https://github.com/xpzouying/xiaohongshu-mcp>
- `Xiangyu-CAS/xiaohongshu-ops-skill`
  - Operations-methodology reference.
  - Useful pieces: account analysis, home-feed analysis, viral replication,
    topic ideation, local knowledge-base loop.
  - Repo reference: <https://github.com/Xiangyu-CAS/xiaohongshu-ops-skill>
- `JimLiu/baoyu-skills`
  - Optional fallback reference for structured image cards and knowledge-style
    visuals.
  - Repo reference: <https://github.com/JimLiu/baoyu-skills>
- OpenAI image generation docs
  - Current official GPT Image surface should be treated as the source of truth
    for model names and API behavior.
  - Docs reference: <https://platform.openai.com/docs/guides/image-generation>

## Recommended Architecture

### 1. XHS Source Adapter

Purpose: collect comparable posts and optional account data.

Primary adapter order:

1. `xiaohongshu-skills` style CLI/skill adapter
2. `xiaohongshu-mcp` adapter if MCP deployment is preferred
3. manual import adapter for pasted URLs, screenshots, or exported JSON

Inputs:

- target keyword or product/topic description
- optional competitor account URLs or XHS IDs
- note type filter: image posts first
- freshness window
- minimum engagement thresholds

Outputs:

- `benchmarks.json`
- `raw/` evidence captures where allowed
- source ledger with URL, capture time, title, author, visible metrics, and
  collection method

Selection rules:

- rank by relevance, interaction strength, freshness, account similarity, and
  content-type fit
- keep the top 5-10 posts for deconstruction
- preserve source links and visible metrics, but do not copy full text or
  images into final generated output unless the user owns or explicitly
  provides those assets

### 2. Viral Deconstruction Engine

Purpose: turn benchmark posts into reusable patterns.

For each benchmark, extract:

- title pattern
- opening hook
- cover promise
- card sequence
- visual style
- proof mechanism
- CTA style
- comment trigger
- emotional driver
- target audience signal
- why-save / why-share reason

Aggregate output:

- `deconstruction.md`
- `patterns.json`

The engine should separate:

- reusable structure
- platform-native phrasing
- non-reusable competitor-specific facts
- copyrighted or creator-owned text/media

### 3. Local Content Adapter

Purpose: map the benchmark patterns onto our own material.

Inputs:

- local project/repo/article/market note path
- optional screenshots, charts, product images, source images, or user-provided
  cover assets
- account positioning profile
- target audience
- publishing goal

Output:

- `content_brief.json`
- `draft.md`
- `card_plan.json`

The adapter must keep the source-of-truth split clear:

- claims and data come from local material or verified source ledger
- layout, pacing, and hook patterns come from benchmark deconstruction
- generated cards use user-owned or user-provided material whenever possible

### 4. GPT Image Generation Adapter

Purpose: generate the final 9:16 XHS image cards.

Default behavior:

- use GPT Image for real-material image-to-image when screenshots, photos, or
  diagrams exist
- preserve realistic source detail over generic AI illustration
- generate 6-7 cards for a normal post
- write prompt, model, input images, and output path into metadata

Implementation guardrail:

- do not hard-code third-party model names such as `gpt-image-2` as the local
  default until verified against official OpenAI docs and available account
  models
- support configurable model names in a local env/config file
- prefer official GPT Image APIs for generation/editing
- keep API keys outside git and outside generated packages

Expected outputs:

- `images/card-01.png` through `images/card-07.png`
- `generation/prompts.json`
- `generation/model_run.json`
- `meta.json`

### 5. Local Preview and Fallback Renderer

Purpose: provide fast local checks without replacing GPT Image quality.

Reuse existing repo capability:

- `scripts/social-cards/render_xiaohongshu_cards.mjs`
- `scripts/social-cards/capture_xiaohongshu_cards_with_edge.mjs`
- related social-card builders where useful

Use cases:

- draft preview before paid image generation
- layout sanity check
- fallback text cards when no image API key is available
- regression snapshots for card count, dimensions, and metadata shape

### 6. QC and Publish Gate

Purpose: avoid posting broken, unsafe, or low-quality output.

QC checks:

- image count is 5-9 cards, default 6-7
- every image is portrait and XHS-ready
- title and caption are present
- hashtags are present and not spammy
- source claims are backed by local content or source ledger
- no copied competitor wording survives into final captions
- no unlicensed competitor image is reused
- generated text in images is legible
- account-specific tone profile is applied
- publish requires explicit human approval

Publishing adapters:

1. save local package only
2. fill XHS publish form for preview
3. publish after explicit approval

Default for early rollout: local package only.

### 7. Performance Review Loop

Purpose: turn published results into future operating memory.

Inputs:

- post URL
- 24h / 48h / 72h metrics
- manual notes from comments
- benchmark pattern used
- generation parameters

Outputs:

- `review.md`
- `performance.json`
- optional account knowledge-base entry

The review loop should update pattern scores, not overwrite the original
source ledger.

## Artifact Layout

Each run writes one self-contained package:

```text
output/xhs-workflow/{YYYY-MM-DD}/{slug}_{YYYYMMDDHHmm}/
|-- request.json
|-- source_ledger.json
|-- benchmarks.json
|-- deconstruction.md
|-- patterns.json
|-- content_brief.json
|-- card_plan.json
|-- draft.md
|-- caption.md
|-- hashtags.txt
|-- qc_report.md
|-- meta.json
|-- raw/
|-- generation/
|   |-- prompts.json
|   `-- model_run.json
|-- preview/
`-- images/
    |-- card-01.png
    |-- card-02.png
    |-- card-03.png
    |-- card-04.png
    |-- card-05.png
    |-- card-06.png
    `-- card-07.png
```

## Proposed Local Entry Points

The eventual implementation should expose small commands rather than one large
script:

1. `xhs-benchmark`
   - collect and rank comparable XHS posts
2. `xhs-deconstruct`
   - turn benchmark posts into reusable patterns
3. `xhs-plan`
   - map local content to a card plan
4. `xhs-generate-images`
   - run GPT Image generation/editing
5. `xhs-qc`
   - validate the package
6. `xhs-publish-preview`
   - fill/publish gate, disabled by default until approved
7. `xhs-review`
   - capture post-performance metrics

The first MVP can ship as scripts plus docs. Command wrappers can be added once
the artifact contracts are stable.

## MVP Scope

MVP should include:

1. manual or `xiaohongshu-skills`-backed benchmark import
2. benchmark ranking schema
3. deconstruction schema and markdown output
4. local content adapter for a repo/article/markdown input
5. GPT Image adapter with configurable model and key loading
6. local package writer
7. QC report
8. no automatic publish

MVP should not include:

- bulk account automation
- aggressive interaction automation
- automatic comments, likes, or favorites
- bypassing XHS login/risk controls
- copying competitor assets into generated posts

## Risk Controls

### Platform Risk

XHS automation can trigger platform risk controls. The workflow should:

- run low-frequency actions
- prefer read-only benchmark collection during MVP
- require human approval before publishing
- avoid automated engagement actions in the first version

### Copyright and Creator Risk

Benchmark posts are references, not raw material. The workflow should:

- copy structure, not text
- use own screenshots/photos/charts where possible
- store external media only when allowed and only for private analysis
- record source links and capture method

### Model/API Risk

GPT Image model names and capabilities can change. The workflow should:

- read model name from config
- keep a documented default based on current official docs
- save prompts and run metadata
- support regeneration without recollecting benchmarks

### Quality Risk

Image generation can produce unreadable text or inconsistent card style. The
workflow should:

- generate from an explicit `card_plan.json`
- keep per-card prompt constraints
- run image dimension and count checks
- require human visual review before publish

## Testing Strategy

The implementation plan should include:

- unit tests for ranking, schema validation, and artifact writing
- fixture-based tests for benchmark deconstruction
- dry-run tests that create a package without calling OpenAI or XHS
- mocked GPT Image adapter tests
- optional integration tests behind env flags for real OpenAI/XHS calls
- a manual visual checklist for generated cards

## Rollout Plan

1. Design and implementation plan only.
2. Build artifact contracts and dry-run package writer.
3. Add benchmark import adapter.
4. Add deconstruction and local content adapter.
5. Add GPT Image adapter and mocked tests.
6. Add QC.
7. Run one real private package generation.
8. Add publish preview only after the local package quality is acceptable.
9. Add performance review loop after the first real post.

## Success Criteria

The workflow is successful when a user can provide a topic or local material and
receive:

- a ranked benchmark set with source ledger
- a concise deconstruction of why the benchmarks worked
- a card plan mapped to the user's own material
- 6-7 generated XHS-ready images using GPT Image
- caption and hashtags
- QC report
- a local package that can be reviewed before publishing

## Spec Self-Review

- No placeholder sections remain.
- The design uses `xhs-writer-skill` as the primary generation reference.
- Existing local social-card scripts are kept as preview/fallback only.
- The artifact contract is explicit enough for an implementation plan.
- Publishing is intentionally gated and not part of the MVP default.
