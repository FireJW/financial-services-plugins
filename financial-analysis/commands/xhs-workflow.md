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
  "image_generation": {
    "mode": "dry_run",
    "model": "gpt-image-2",
    "size": "1024x1536"
  }
}
```

## Local Helper

```powershell
python financial-analysis/skills/autoresearch-info-index/scripts/xhs_workflow.py "<request.json>" --output "<result.json>"
```

Use `image_generation.mode=dry_run` first. It writes prompts and package
metadata without making network calls.

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
