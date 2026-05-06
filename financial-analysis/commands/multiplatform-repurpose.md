---
description: Repurpose one source Markdown article into platform-native review packages
argument-hint: "[request-json|publish-package-json|article-publish-result-json]"
---

# Multiplatform Repurpose Command

Use this command when a source Markdown article or existing publish package
needs reviewable variants for WeChat, Toutiao, Xiaohongshu, short video,
WeChat Channels, Bilibili, X, LinkedIn, and Substack.

This command only writes local artifacts. It does not push to any platform.

Local helper:

```powershell
financial-analysis\skills\autoresearch-info-index\scripts\run_multiplatform_repurpose.cmd "<request.json>"
```

Shortcut from repo-native publish artifacts:

```powershell
financial-analysis\skills\autoresearch-info-index\scripts\run_multiplatform_repurpose.cmd "<article-publish-result.json>"
financial-analysis\skills\autoresearch-info-index\scripts\run_multiplatform_repurpose.cmd "<article-publish-reuse-result.json>"
financial-analysis\skills\autoresearch-info-index\scripts\run_multiplatform_repurpose.cmd "<publish-package.json>"
```

The helper recognizes `article_publish`, `article_publish_reuse`, and
`publish-package/v1` inputs, then writes a normalized request beside the normal
manifest artifacts. This is still local-only repurposing; it does not push or
approve a live publish.

Default output:

```text
.tmp/multiplatform-content-repurposer/<run-id>/dist/<platform-name>/
```

Each platform dist package includes `platform-profile.json`,
`quality-scorecard.md`, and `rewrite-packet.md` so the human edit or downstream
LLM rewrite can enforce platform length, voice, required elements, citation
integrity, caveat visibility, and the supplied what-not-to-say boundaries.

Open the top-level `report.md` first. Its review queue lists the content,
rewrite packet, scorecard, human edit checklist, and what-not-to-say file for
each generated platform.

The run also writes `multiplatform-completion-check.json` and
`multiplatform-completion-check.md`. Treat `ready` as safe to move into human
editing, `warning` as review-before-reuse, and `blocked` as not ready.

Read the usage doc first:

```text
financial-analysis/skills/autoresearch-info-index/references/multiplatform-content-repurposer/README.md
```
