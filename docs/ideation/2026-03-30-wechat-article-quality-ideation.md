---
date: 2026-03-30
topic: wechat-article-quality
focus: wewrite-style one-sentence hot-topic to wechat draft flow reset
---

# Ideation: WeChat Article Quality Reset

## Codebase Context

The repository already has a real end-to-end pipeline for:

- hot-topic discovery
- evidence indexing
- article brief generation
- draft rendering
- WeChat HTML packaging
- human review gating
- real WeChat draft push

The strongest part is the evidence and publishing spine. The weakest part is the reader-facing writing layer. Right now the system often leaks internal research scaffolding into the public article, which makes the generated draft feel like an analyst worksheet instead of a publishable公众号文章.

The current topic desk is also product-incomplete: the scoring logic exists, but the user cannot directly steer topic preference, score weights, or exclusion filters in a clean way.

## Ranked Ideas

### 1. Split The Workflow Into Internal Brief And Public Writer
**Description:** Keep the evidence brief, fact firewall, and risk notes internal, then add a separate public-writer stage that turns those inputs into a reader-facing article with explicit frameworks.
**Rationale:** This addresses the root cause instead of polishing bad output. The current draft is unusable because research-operator copy is being rendered as publishable prose.
**Downsides:** Requires touching the article drafting layer and updating tests that currently assert the old scaffolded headings.
**Confidence:** 96%
**Complexity:** Medium
**Status:** Explored

### 2. Turn Hot Topic Discovery Into A Configurable Topic Desk
**Description:** Expose topic preferences, exclusion keywords, score weights, and minimum thresholds so the operator can control what “worth writing” means.
**Rationale:** The user explicitly wants control over both the topic direction and the screening variables. This also moves the system closer to the original WeWrite promise.
**Downsides:** More knobs can confuse operators if defaults are not well chosen.
**Confidence:** 92%
**Complexity:** Low
**Status:** Explored

### 3. Add A Publishability Gate For Reader-Facing Copy
**Description:** Add a quality gate that flags or blocks drafts containing operator phrases, evidence-jargon titles, source-brand leakage, and internal review scaffolding.
**Rationale:** This prevents regressions after the public-writer reset and creates a durable guardrail for future edits.
**Downsides:** A strict gate can be annoying if it produces false positives on edge cases.
**Confidence:** 88%
**Complexity:** Medium
**Status:** Unexplored

### 4. Make Editor Anchors A Review Tool, Not Public Body Copy
**Description:** Keep editor anchors in the package metadata and review surface, but hide them from the default WeChat HTML unless explicitly requested inline.
**Rationale:** The user accepts manual review, but does not want the article body to read like a writing exercise template.
**Downsides:** Some operators may prefer visible inline anchors for rapid editing.
**Confidence:** 91%
**Complexity:** Low
**Status:** Explored

### 5. Adopt A No-Text-First Cover Policy
**Description:** Prefer dedicated cover candidates with no text, logos, or watermarks, and only fall back to body images when no stronger cover exists.
**Rationale:** This matches the user’s actual publishing constraint. AI-generated cover text is usually unreadable and harms trust instantly.
**Downsides:** Some topics may benefit from typographic covers, so this should stay configurable later.
**Confidence:** 90%
**Complexity:** Low
**Status:** Explored

### 6. Add A Stronger Human Review Cockpit
**Description:** Reframe review as a lightweight editor cockpit: draft summary, hidden anchors, source appendix, cover status, and push readiness in one place.
**Rationale:** Human review is a feature, not a workaround. This improves confidence without weakening automation.
**Downsides:** More operator UI/reporting logic without directly improving prose quality.
**Confidence:** 82%
**Complexity:** Medium
**Status:** Unexplored

## Rejection Summary

| # | Idea | Reason Rejected |
|---|------|-----------------|
| 1 | Fully automatic publish without review | Conflicts with the user’s safety and editorial requirements |
| 2 | Add a visible “confirmed vs unconfirmed” fact-check section to every article | Useful for internal verification, but wrong for public reader-facing prose |
| 3 | Keep source outlet names in titles for credibility | Hurts readability and makes the article feel like a clipped feed item |
| 4 | Solve article quality mainly by adding more images | The root problem is writing-layer leakage, not image scarcity |
| 5 | Launch multi-platform publishing now | Premature; current leverage is improving one high-trust WeChat workflow first |

## Session Log

- 2026-03-30: Initial ideation - 11 candidate directions considered, 6 survivors kept, top priority is splitting the internal brief from the public writer
