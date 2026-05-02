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
    "sort_by": "最多点赞",
    "note_type": "图文",
    "limit": 20
  },
  "image_generation": {
    "mode": "dry_run",
    "model": "gpt-image-2",
    "size": "1024x1536",
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

When `collector.type=xiaohongshu-skills`, the generated package includes
`collector_plan.json`. It contains the `python scripts/cli.py search-feeds ...`
command to run from the referenced `xiaohongshu-skills` checkout. This workflow
does not run that command automatically because it may depend on browser login
state and platform risk controls.

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
- OpenAI API key requirement when `image_generation.mode=openai`
- local reference image paths for OpenAI image edits
- output directory parent availability

Use `image_generation.mode=dry_run` first. It writes prompts and package
metadata without making network calls.

`reference_images` is the bridge to the `xhs-writer-skill` style image-to-image
flow. In dry-run mode the workflow records those images in
`generation/prompts.json` and adds prompt instructions to preserve concrete
source details while improving XHS card composition.

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

For a real GPT Image run from the CLI, first run doctor:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --doctor --image-mode openai --image-model gpt-image-2 --reference-image "D:/path/to/source.png" --output "<doctor.json>"
```

If doctor reports `ready`, run generation:

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --image-mode openai --image-model gpt-image-2 --image-size 1024x1536 --reference-image "D:/path/to/source.png" --output "<result.json>"
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
- `qc_report.json`
- `qc_report.md`
- `performance_review.json`
- `performance_collection_plan.json`
- `review.md`
- `publish_plan.json`
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
and prepares a `python scripts/cli.py fill-publish ...` command. It never adds a
click-publish step; the final publish action stays manual.

## Publish Gate

This command does not automatically publish. The result remains
`ready_for_review`, and `qc_report` keeps `publish_approval` failed until a
human explicitly approves the package.
