# Multiplatform Content Repurposer

Use this helper when one source Markdown article needs platform-native versions
without losing the original thesis, citations, or caveats.

The repurposer is deliberately not a publisher. It writes reviewable packages
under `.tmp/` and never calls WeChat, Toutiao, browser automation, Agent Reach,
or any live platform API.

## Command

```powershell
financial-analysis\skills\autoresearch-info-index\scripts\run_multiplatform_repurpose.cmd request.json
```

Optional output override:

```powershell
financial-analysis\skills\autoresearch-info-index\scripts\run_multiplatform_repurpose.cmd request.json --output-dir ".tmp\multiplatform-content-repurposer\my-run"
```

## Minimal Request

```json
{
  "contract_version": "multiplatform_repurpose_request/v1",
  "run_id": "agent-budget-discipline",
  "source_article": {
    "markdown_path": "source-article.md"
  },
  "platform_targets": [
    "wechat_article",
    "xiaohongshu_cards",
    "douyin_short_video",
    "x_thread"
  ],
  "creator_voice_guide": {
    "text": "Direct, evidence-bound, practical."
  },
  "source_notes": {
    "items": [
      {"note": "The source article is a thesis piece, not a live market report."}
    ]
  },
  "citations": [
    {
      "citation_id": "S1",
      "source_name": "Example Research",
      "title": "AI workflow adoption survey",
      "url": "https://example.com/ai-workflow-survey"
    }
  ]
}
```

## Optional Native Inputs

The request can also pass repo-native artifacts:

- `existing_publish_package_path`
- `article_brief_path`
- `evidence_bundle_path`

Inline equivalents are also accepted:

- `existing_publish_package`
- `article_brief`
- `evidence_bundle`

When present, these artifacts supply `draft_thesis`, `citations`,
`not_proven`, `misread_risks`, and operator notes for source-integrity checks.

## Supported Platform Targets

- `wechat_article`
- `toutiao_article`
- `xiaohongshu_cards`
- `douyin_short_video`
- `wechat_channels_script`
- `bilibili_long_video_outline`
- `x_thread`
- `linkedin_post`
- `substack_article`

If `platform_targets` is omitted, all supported platforms are generated.

## Output Layout

Default root:

```text
.tmp/multiplatform-content-repurposer/<run-id>/
|-- request.normalized.json
|-- source-integrity.json
|-- manifest.json
|-- report.md
`-- dist/
    |-- wechat_article/
    |   |-- article.md
    |   |-- platform-package.json
    |   |-- what-not-to-say.md
    |   `-- human-edit-required.md
    `-- <platform-name>/
        |-- <content-file>.md
        |-- platform-package.json
        |-- what-not-to-say.md
        `-- human-edit-required.md
```

Each platform package contains:

- `platform`
- `title`
- `hook`
- `body_or_script`
- `citations_used`
- `caveats_preserved`
- `what_not_to_say`
- `human_edit_required`
- `source_integrity_status`

## Source Integrity Rules

- Preserve the source `core_thesis`.
- Preserve caveats from the source Markdown `## Caveats` and
  `## Evidence Boundary` sections.
- Preserve repo-native `not_proven` and `misread_risks` when an article brief is
  supplied.
- Do not fabricate citations. If none are supplied, each platform package gets
  `citations_used=[{"status":"missing","note":"No citations were supplied."}]`
  and `source_integrity_status="needs_human_review"`.
- Do not publish directly from this output. Treat the dist files as human-edit
  packages.

## Tests

Focused regression:

```powershell
cd financial-analysis\skills\autoresearch-info-index\tests
..\scripts\python-local.cmd -m unittest test_multiplatform_repurpose -v
```

Sample source article and request fixtures live in:

```text
financial-analysis/skills/autoresearch-info-index/tests/fixtures/multiplatform-repurpose/
```
