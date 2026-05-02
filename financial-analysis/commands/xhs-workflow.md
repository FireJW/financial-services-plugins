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
  }
}
```

When `collector.type=xiaohongshu-skills`, the generated package includes
`collector_plan.json`. It contains the `python scripts/cli.py search-feeds ...`
command to run from the referenced `xiaohongshu-skills` checkout. This workflow
does not run that command automatically because it may depend on browser login
state and platform risk controls.

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
- `meta.json`

## Publish Gate

This command does not automatically publish. The result remains
`ready_for_review`, and `qc_report` keeps `publish_approval` failed until a
human explicitly approves the package.
