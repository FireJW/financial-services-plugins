---
description: Build a local Xiaohongshu image-post workflow package from benchmarks and local material
argument-hint: "[request-json]"
---

# XHS Workflow Command

Use this command when the user wants a Xiaohongshu image-post workflow that
starts from high-interaction comparable posts and ends with a local review
package.

The intended loop is:

1. import or collect benchmark XHS posts
2. rank high-heat and high-interaction examples
3. deconstruct reusable structure without copying creator text or images
4. map the pattern onto local material
5. prepare GPT Image prompts or run explicit OpenAI image generation
6. write a local package for human review
7. publish only after explicit approval

Primary generation reference:

- `JuneYaooo/xhs-writer-skill`

Related capability references:

- `autoclaw-cc/xiaohongshu-skills` for XHS browser/CLI automation
- `xpzouying/xiaohongshu-mcp` for a later MCP-style XHS surface
- `Xiangyu-CAS/xiaohongshu-ops-skill` for account and benchmark operations
- existing local `scripts/social-cards/*` only for preview/fallback, not as the
  main visual generator

## Request Shape

```json
{
  "topic": "AI capex earnings",
  "run_id": "20260502120000",
  "output_dir": ".tmp/xhs-workflow",
  "local_material": {
    "title": "Big Tech capex signal",
    "summary": "Four large technology companies are raising AI infrastructure spend.",
    "key_points": ["capex acceleration", "power demand", "investor scrutiny"]
  },
  "benchmarks": [
    {
      "url": "https://www.xiaohongshu.com/explore/demo",
      "title": "3 signals to understand AI investment",
      "likes": 1200,
      "collects": 800,
      "comments": 96,
      "posted_at": "2026-05-01"
    }
  ],
  "collector": {
    "type": "xiaohongshu-skills",
    "skills_dir": "D:/path/to/xiaohongshu-skills",
    "keyword": "AI capex",
    "apply_filters": false,
    "limit": 20
  },
  "image_generation": {
    "mode": "dry_run",
    "model": "gpt-image-2",
    "size": "1024x1536",
    "text_strategy": "local_overlay",
    "reference_images": [
      "D:/path/to/product-or-source-image.png",
      {
        "path": "D:/path/to/chart.png",
        "role": "chart"
      }
    ]
  },
  "performance_metrics": {
    "post_url": "https://www.xiaohongshu.com/explore/published",
    "after_24h": {
      "likes": 120,
      "collects": 60,
      "comments": 12,
      "shares": 5
    },
    "notes": ["collect rate is strong"]
  },
  "performance_collection": {
    "type": "xiaohongshu-skills",
    "skills_dir": "D:/path/to/xiaohongshu-skills",
    "feed_id": "abc",
    "xsec_token": "token"
  },
  "publish": {
    "type": "xiaohongshu-skills",
    "skills_dir": "D:/path/to/xiaohongshu-skills",
    "mode": "preview"
  }
}
```

`skills_dir` can be omitted when `XIAOHONGSHU_SKILLS_DIR` points to the local
`xiaohongshu-skills` checkout. Readiness checks require both the directory and
`scripts/cli.py` to exist before collector, publish-preview, or performance
collection plans are treated as runnable.

OpenAI image generation reads `OPENAI_API_KEY` from the environment unless
`image_generation.api_key` is provided. OpenAI-compatible endpoints can be set
with `OPENAI_BASE_URL` or `image_generation.base_url`; the workflow appends
`/v1/images/generations` or `/v1/images/edits` as needed.

Before auto-running collector or publish-preview commands, this workflow sends a
no-browser bridge preflight ping. If the bridge server or browser extension is
not connected, it records `bridge_server_not_running` or `bridge_not_connected`
and does not call the `xiaohongshu-skills` CLI. This prevents the upstream CLI
from opening Chrome when the intended browser is Edge.

When `collector.type=xiaohongshu-skills`, the generated package includes
`collector_plan.json`. It contains the `python scripts/cli.py search-feeds ...`
command to run from the referenced `xiaohongshu-skills` checkout. This workflow
does not run that command automatically because it may depend on browser login
state and platform risk controls.

Collector runs default to keyword-only search so they do not click fragile XHS
filter controls. To request upstream filtering explicitly, set `sort_by` and/or
`note_type`; set `apply_filters=false` to force keyword-only collection even
when filter fields are present.

To run the collector explicitly before building the package:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --run-collector --output "<result.json>"
```

This writes the collector stdout to `collector_result.json`, then imports that
file as the benchmark source for the same run. Use this only when the referenced
`xiaohongshu-skills` checkout is installed, logged in if needed, and safe to run.

## Local Helper

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --output "<result.json>"
```

Run readiness first when connecting imported benchmarks, OpenAI image
generation, or reference images:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --doctor --output "<doctor.json>"
```

Doctor mode does not generate a package. It checks:

- benchmark input or benchmark file availability
- collector readiness when `--run-collector` is used or `collector.type` is set
- local `xiaohongshu-skills` CLI availability when that adapter is configured
- OpenAI API key requirement when `image_generation.mode=openai`
- local reference image paths for OpenAI image edits
- OCR availability and whether model-text QC can run locally
- output directory parent availability

Use `image_generation.mode=dry_run` first. It writes prompts and package
metadata without making network calls.

`reference_images` is the bridge to the `xhs-writer-skill` style image-to-image
flow. In dry-run mode the workflow records those images in
`generation/prompts.json` and adds prompt instructions to preserve concrete
source details while improving XHS card composition.

## Text Strategy

`image_generation.text_strategy` controls where visible card text is created.
If omitted, the workflow uses `local_overlay`.

- `local_overlay`: safest default. The image model creates a textless
  background only; exact `card_plan.json` title and message text is rendered
  locally into the final PNGs.
- `model_text_with_qc`: higher expression. The image model may render text, but
  prompts are locked to each card's `title` and `message` only. The package
  records `allowed_text`, `forbidden_text_policy`, and `qc_required=true` in
  `generation/prompts.json`. Final cards must pass OCR/QC or receive manual
  text review before publish preview.
- `hybrid_overlay`: recommended middle path when backgrounds need stronger
  layout. The image model creates layout-rich panels and visual hierarchy but
  still avoids readable factual text; exact facts are overlaid locally.

For `model_text_with_qc`, the prompt forbids any unprovided dates, years,
times, numbers, company names, tickers, logos, labels, watermarks, hashtags,
chart axes, timestamps, or metadata. If `tesseract` is available, the workflow
OCRs final cards and blocks text QC on obvious forbidden patterns such as
`2024-01`, `2024/01`, `2024.01`, `09:30`, unallowed years, and unallowed
number/date strings. If OCR is not available, QC status becomes
`needs_manual_text_qc`; the workflow blocks `publish_plan.json` with
`status=blocked_qc` and removes the `fill-publish` command until text QC is
resolved.

OCR discovery checks `TESSERACT_CMD` or `TESSERACT_EXE`, then `PATH`, then common
Windows installs including `D:/Tools/Tesseract-OCR/tesseract.exe`.

Recommended production loop for stronger expression:

1. Run `model_text_with_qc` generation.
2. Check `qc_report.json` and `qc_report.md` for OCR/text QC results.
3. Manually review every generated card against `allowed_text`.
4. Run `--run-publish-preview` only after text is accepted.
5. Publish manually in XHS. This workflow must not run automatic
   `click-publish`.

To import benchmark output from `xiaohongshu-skills` or another collector:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --benchmark-file "<xhs-search-result.json>" --benchmark-source "xiaohongshu-skills.search-feeds" --output "<result.json>"
```

Accepted benchmark JSON shapes include arrays, `benchmarks`, `feeds`, `items`,
`notes`, `results`, and nested `data` objects. The runtime normalizes common
XHS metric fields such as `likes`, `like_count`, `collect_count`, and
`comment_count`.

Use `image_generation.mode=openai` only after the package plan is acceptable
and `OPENAI_API_KEY` is configured. The model is configurable; do not hard-code
third-party defaults when official OpenAI docs or account availability differ.

When `mode=openai` and local `reference_images` are present, the runtime uses
the OpenAI image edit endpoint with multipart `image[]` files. Remote image URLs
are not passed directly to the API in this version; download or provide local
files first.

If backgrounds are generated manually, pass them back in card order and compose
the final cards locally:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --image-mode compose --background-image "D:/path/to/card-01-background.png" --background-image "D:/path/to/card-02-background.png" --output "<result.json>"
```

For a real GPT Image run from the CLI, first run doctor:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --doctor --image-mode openai --image-model gpt-image-2 --reference-image "D:/path/to/source.png" --output "<doctor.json>"
```

If doctor reports `ready`, run generation:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --image-mode openai --image-model gpt-image-2 --image-size 1024x1536 --text-strategy hybrid_overlay --reference-image "D:/path/to/source.png" --output "<result.json>"
```

To allow model-rendered text under OCR/manual QC:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --image-mode openai --image-model gpt-image-2 --image-size 1024x1536 --text-strategy model_text_with_qc --output "<result.json>"
```

## Outputs

The workflow writes one package directory containing:

- `request.json`
- `source_ledger.json`
- `benchmarks.json`
- `deconstruction.md`
- `patterns.json`
- `content_brief.json`
- `card_plan.json`
- `draft.md`
- `caption.md`
- `hashtags.txt`
- `generation/prompts.json`
- `generation/model_run.json`
- `backgrounds/card-*.png` when images are generated or composed
- `images/card-*.png` final cards with local text overlay
- `qc_report.json`
- `qc_report.md`
- `performance_review.json`
- `performance_collection_plan.json`
- `review.md`
- `publish_plan.json`
- `publish_preview_run.json`
- `meta.json`

`performance_metrics` is optional. When present, the workflow records a local
post-performance review so the same benchmark pattern can be compared against
future runs. It does not fetch metrics from XHS automatically in this version.

`performance_collection.type=xiaohongshu-skills` creates a
`performance_collection_plan.json` with a `get-feed-detail` command. Run that
command outside the package flow, save the JSON, then import it:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --performance-file "<xhs-detail-result.json>" --output "<result.json>"
```

`publish.type=xiaohongshu-skills` creates a preview-only `publish_plan.json`.
When card images exist, it writes `publish/title.txt` and `publish/content.txt`
and prepares a `python scripts/cli.py fill-publish ...` command only when QC is
reviewable. If text QC is blocked or needs manual review, `publish_plan.json`
uses `status=blocked_qc` and leaves `command=[]`. It never adds a click-publish
step; the final publish action stays manual. Do not add or run automatic
`click-publish` from this workflow.

To explicitly run the preview fill step after package generation:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --run-publish-preview --output "<result.json>"
```

This only executes `fill-publish`. The workflow blocks `click-publish` even when
a malformed plan or request attempts to include it. Use this only after card
images exist, `publish_plan.json` is not `blocked_qc`, and the referenced
`xiaohongshu-skills` checkout is installed and logged in as needed.

## Publish Gate

This command does not automatically publish. A package with clear QC remains
`ready_for_review`, and `qc_report` keeps `publish_approval` failed until a
human explicitly approves it. A package with `needs_manual_text_qc` or
`blocked_text_qc` keeps the publish preview blocked until the text issue is
resolved.
