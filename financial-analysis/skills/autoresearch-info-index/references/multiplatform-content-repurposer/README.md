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
  "platform_profiles": {
    "xiaohongshu_cards": {
      "voice": "Calm creator, plain language, saveable checklist.",
      "target_length": "6 cards, one idea per card",
      "must_include": [
        "keep evidence caveat visible",
        "end with a practical checklist"
      ]
    }
  },
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

## Platform Profiles

Every platform package now includes a default `platform_profile` and
`quality_scorecard`.

Use request-level `platform_profiles` when a platform needs tighter control over
format, voice, length, or required elements. Supported override fields are:

- `format`
- `voice`
- `target_length`
- `must_include`
- `quality_checks`

These profiles are review constraints. They do not relax source-integrity rules:
the repurposer still only uses supplied thesis, caveats, and citations.

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
    |   |-- platform-profile.json
    |   |-- quality-scorecard.md
    |   |-- rewrite-packet.md
    |   |-- what-not-to-say.md
    |   `-- human-edit-required.md
    `-- <platform-name>/
        |-- <content-file>.md
        |-- platform-package.json
        |-- platform-profile.json
        |-- quality-scorecard.md
        |-- rewrite-packet.md
        |-- what-not-to-say.md
        `-- human-edit-required.md
```

Start review from `report.md`. Its `Review Queue` section lists each platform's
content file, `rewrite-packet.md`, `quality-scorecard.md`,
`human-edit-required.md`, and `what-not-to-say.md` paths so the operator can
open the right artifact without inspecting `manifest.json` first.

Each platform package contains:

- `platform`
- `title`
- `hook`
- `body_or_script`
- `platform_profile`
- `quality_scorecard`
- `rewrite_packet`
- `citations_used`
- `caveats_preserved`
- `what_not_to_say`
- `human_edit_required`
- `source_integrity_status`

`rewrite-packet.md` is the safest handoff artifact for model-assisted or human
editing. It bundles the core thesis, platform profile, scorecard, allowed
citations, caveats, what-not-to-say list, human-edit checklist, and the draft to
improve without authorizing new sourcing or publishing.

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
