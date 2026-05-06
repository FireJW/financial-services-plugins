---
description: Repurpose one source Markdown article into platform-native review packages
argument-hint: "[request-json]"
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

Default output:

```text
.tmp/multiplatform-content-repurposer/<run-id>/dist/<platform-name>/
```

Each platform dist package includes `platform-profile.json`,
`quality-scorecard.md`, and `rewrite-packet.md` so the human edit or downstream
LLM rewrite can enforce platform length, voice, required elements, citation
integrity, caveat visibility, and the supplied what-not-to-say boundaries.

Read the usage doc first:

```text
financial-analysis/skills/autoresearch-info-index/references/multiplatform-content-repurposer/README.md
```
