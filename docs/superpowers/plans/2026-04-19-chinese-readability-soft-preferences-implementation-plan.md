# Chinese Readability Soft Preferences Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Chinese-only readability polish layer that localizes key company/term mentions, merges stiff concession-turn fragments, converts conclusion-repeat endings into watchpoint endings when appropriate, and cleans common English residue without changing topic ranking or WeChat push logic.

**Architecture:** Keep the implementation inside `article_draft_flow_runtime.py` as a post-generation markdown polish pass. Reuse the existing Chinese generation flow: build the normal title / subtitle / sections / markdown first, then apply a bounded polish step only when `language_mode == "chinese"`. Cover the behavior with focused tests in `test_article_publish.py`, then run the full article-publish regression file.

**Tech Stack:** Python, existing autoresearch runtime helpers, pytest

---

### Task 1: Add failing tests for Chinese readability helpers

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add focused tests for term localization and concession-turn merge**

Add tests near the other article polish / title tests.

```python
    def test_chinese_readability_localizes_key_company_and_term_mentions(self) -> None:
        markdown_text = (
            "TSMC 和 ASML 先后上修指引。\\n\\n"
            "order intake 继续维持在很强的水平，ongoing discussions around export controls 也没有消失。\\n"
        )

        polished = article_draft_flow_runtime.polish_chinese_article_markdown(
            markdown_text,
            {"language_mode": "chinese", "topic": "AI 基建投资"},
            {},
            {},
        )

        self.assertIn("台积电（TSMC）", polished)
        self.assertIn("阿斯麦（ASML）", polished)
        self.assertIn("新增订单（order intake）", polished)
        self.assertIn("出口管制（export controls）", polished)

    def test_chinese_readability_merges_short_concession_and_turn_sentences(self) -> None:
        markdown_text = (
            "这个担心不是完全没有道理。\\n\\n"
            "但过去几天，台积电（TSMC）和阿斯麦（ASML）先后交出来的数字，已经把这条线按了回去。\\n"
        )

        polished = article_draft_flow_runtime.polish_chinese_article_markdown(
            markdown_text,
            {"language_mode": "chinese", "topic": "AI 基建投资"},
            {},
            {},
        )

        self.assertIn("这个担心不是完全没有道理。但过去几天", polished)
        self.assertNotIn("这个担心不是完全没有道理。\\n\\n但过去几天", polished)
```

- [ ] **Step 2: Run the focused tests to verify they fail**

Run:

```bash
pytest D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "chinese_readability_localizes or chinese_readability_merges" -v
```

Expected:

- FAIL because `polish_chinese_article_markdown()` does not exist yet

- [ ] **Step 3: Commit the red test**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "test(autoresearch): add chinese readability polish coverage"
```

---

### Task 2: Implement localization and concession-turn polish helpers

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\article_draft_flow_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add minimal helper functions in the Chinese markdown section**

Place the helpers near `append_source_limit_note()` / markdown rendering helpers, not in topic ranking or publish-package code.

```python
CHINESE_TERM_LOCALIZATION_MAP = (
    ("TSMC", "台积电（TSMC）"),
    ("ASML", "阿斯麦（ASML）"),
    ("order intake", "新增订单（order intake）"),
    ("export controls", "出口管制（export controls）"),
    ("Reuters", "路透社 Reuters"),
)


def localize_chinese_terms(text: str) -> str:
    localized = clean_text(text)
    for raw_term, localized_term in CHINESE_TERM_LOCALIZATION_MAP:
        if localized_term in localized:
            continue
        localized = re.sub(
            rf"(?<![A-Za-z]){re.escape(raw_term)}(?![A-Za-z])",
            localized_term,
            localized,
            count=1,
        )
    return localized


def merge_chinese_concession_turn(paragraphs: list[str]) -> list[str]:
    merged: list[str] = []
    index = 0
    while index < len(paragraphs):
        current = clean_text(paragraphs[index])
        next_text = clean_text(paragraphs[index + 1]) if index + 1 < len(paragraphs) else ""
        if (
            current
            and len(current) <= 24
            and current.endswith(("。", "！", "？"))
            and any(next_text.startswith(prefix) for prefix in ("但", "不过", "问题在于", "真正值得看的是"))
        ):
            merged.append(f"{current}{next_text}")
            index += 2
            continue
        if current:
            merged.append(current)
        index += 1
    return merged
```

- [ ] **Step 2: Add the post-generation markdown polish pass**

Implement a dedicated markdown pass that only runs in Chinese mode.

```python
def polish_chinese_article_markdown(
    markdown_text: str,
    request: dict[str, Any],
    analysis_brief: dict[str, Any],
    source_summary: dict[str, Any],
) -> str:
    if clean_text(request.get("language_mode")) != "chinese":
        return markdown_text

    blocks = [block for block in markdown_text.split("\\n\\n")]
    localized_blocks = [localize_chinese_terms(block) for block in blocks]
    merged_blocks = merge_chinese_concession_turn(localized_blocks)
    return "\\n\\n".join(block for block in merged_blocks if clean_text(block)).strip() + "\\n"
```

- [ ] **Step 3: Integrate the polish pass into both markdown build paths**

Apply it immediately after `append_source_limit_note()` in both the initial package build path and `refresh_article_package()`.

```python
    article_markdown = append_source_limit_note(article_markdown, source_summary, clean_text(request.get("language_mode")))
    if clean_text(request.get("language_mode")) == "chinese":
        article_markdown = polish_chinese_article_markdown(
            article_markdown,
            request,
            effective_analysis_brief,
            source_summary,
        )
```

and in `refresh_article_package()`:

```python
        article_package["article_markdown"] = append_source_limit_note(
            article_package["article_markdown"],
            safe_dict(render_context.get("source_summary")),
            clean_text(request_context.get("language_mode")),
        )
        if clean_text(request_context.get("language_mode")) == "chinese":
            article_package["article_markdown"] = polish_chinese_article_markdown(
                article_package["article_markdown"],
                request_context,
                safe_dict(render_context.get("analysis_brief")),
                safe_dict(render_context.get("source_summary")),
            )
```

- [ ] **Step 4: Run the focused tests again**

Run:

```bash
pytest D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "chinese_readability_localizes or chinese_readability_merges" -v
```

Expected:

- PASS

- [ ] **Step 5: Commit the helper implementation**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add chinese readability localization polish"
```

---

### Task 3: Add watchpoint-ending replacement tests

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add a focused test for watchpoint endings on industry topics**

```python
    def test_chinese_readability_replaces_repeated_conclusion_ending_with_watchpoints(self) -> None:
        markdown_text = (
            "## 结尾\\n\\n"
            "所以如果现在再问我，AI 泡沫是不是快破了，我的回答会是：至少从 TSMC 和 ASML 这组最新信号看，还没有。\\n\\n"
            "这轮故事显然还没讲完。\\n"
        )
        request = {
            "language_mode": "chinese",
            "topic": "台积电（TSMC）、阿斯麦（ASML）同步上修：AI 基建投资远未见顶",
            "audience_keywords": ["AI", "semiconductor", "chips", "infrastructure"],
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["真正值得看的是 AI 基建链条会不会继续兑现。"],
            "open_questions_zh": ["云厂商 capex、Blackwell 出货、先进封装订单会不会继续维持紧张？"],
        }
        source_summary = {"topic": request["topic"], "core_verdict": "AI 基建投资仍未见顶。"}

        polished = article_draft_flow_runtime.polish_chinese_article_markdown(
            markdown_text,
            request,
            analysis_brief,
            source_summary,
        )

        self.assertIn("更值得盯的，是接下来几个验证节点", polished)
        self.assertIn("capex", polished)
        self.assertIn("Blackwell", polished)
        self.assertIn("先进封装", polished)
```

- [ ] **Step 2: Run the focused test to verify it fails**

Run:

```bash
pytest D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "watchpoint" -v
```

Expected:

- FAIL because no ending replacement logic exists yet

- [ ] **Step 3: Commit the red test**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "test(autoresearch): cover chinese watchpoint endings"
```

---

### Task 4: Implement watchpoint-ending replacement and residue cleanup

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\article_draft_flow_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add ending-eligibility and watchpoint builder helpers**

```python
def article_prefers_watchpoint_ending(
    request: dict[str, Any],
    analysis_brief: dict[str, Any],
    source_summary: dict[str, Any],
) -> bool:
    text = " ".join(
        [
            clean_text(request.get("topic")),
            clean_text(source_summary.get("topic")),
            " ".join(clean_string_list(request.get("audience_keywords"))),
            " ".join(clean_string_list(analysis_brief.get("market_or_reader_relevance_zh"))),
        ]
    ).lower()
    return any(token in text for token in ("ai", "semiconductor", "chips", "台积电", "阿斯麦", "capex", "供应链"))


def build_watchpoint_ending(
    request: dict[str, Any],
    analysis_brief: dict[str, Any],
    source_summary: dict[str, Any],
) -> str:
    watchpoints = clean_string_list(analysis_brief.get("open_questions_zh"))[:3]
    lead = "更值得盯的，是接下来几个验证节点："
    if not watchpoints:
        return lead
    lines = [lead]
    for item in watchpoints:
        lines.append(f"- {item.rstrip('。')}")
    return "\\n".join(lines)
```

- [ ] **Step 2: Add a narrow ending replacement helper**

```python
def replace_chinese_repeated_conclusion_ending(
    markdown_text: str,
    request: dict[str, Any],
    analysis_brief: dict[str, Any],
    source_summary: dict[str, Any],
) -> str:
    if not article_prefers_watchpoint_ending(request, analysis_brief, source_summary):
        return markdown_text
    if "## 结尾" not in markdown_text:
        return markdown_text
    head, _sep, _tail = markdown_text.partition("## 结尾")
    ending = "## 结尾\\n\\n" + build_watchpoint_ending(request, analysis_brief, source_summary) + "\\n"
    return head.rstrip() + "\\n\\n" + ending
```

- [ ] **Step 3: Extend the Chinese markdown polish pass**

Keep the ordering deterministic:

```python
def polish_chinese_article_markdown(...):
    ...
    polished = "\\n\\n".join(block for block in merged_blocks if clean_text(block)).strip() + "\\n"
    polished = replace_chinese_repeated_conclusion_ending(
        polished,
        request,
        analysis_brief,
        source_summary,
    )
    return polished
```

- [ ] **Step 4: Run the focused test again**

Run:

```bash
pytest D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -k "watchpoint" -v
```

Expected:

- PASS

- [ ] **Step 5: Commit the ending logic**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add chinese watchpoint endings"
```

---

### Task 5: Run regression verification

**Files:**
- Verify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Run the full article-publish test file**

Run:

```bash
pytest D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py -v
```

Expected:

- PASS for the full file

- [ ] **Step 2: Spot-check the new helper behavior with a small local sample**

Run:

```python
sample = """TSMC 和 ASML 先后上修指引。

这个担心不是完全没有道理。

但过去几天，TSMC 和 ASML 先后交出来的数字，已经把这条线按了回去。

## 结尾

所以如果现在再问我，AI 泡沫是不是快破了，我的回答会是：至少从 TSMC 和 ASML 这组最新信号看，还没有。
"""
print(
    polish_chinese_article_markdown(
        sample,
        {"language_mode": "chinese", "topic": "台积电（TSMC）、阿斯麦（ASML）同步上修：AI 基建投资远未见顶", "audience_keywords": ["AI", "chips"]},
        {"open_questions_zh": ["第二季度云厂商 capex 指引会不会继续上修", "英伟达 Blackwell 的出货节奏是否顺畅"]},
        {"topic": "台积电（TSMC）、阿斯麦（ASML）同步上修：AI 基建投资远未见顶", "core_verdict": "AI 基建投资仍未见顶"},
    )
)
```

Expected:

- `台积电（TSMC）`
- `阿斯麦（ASML）`
- merged concession-turn sentence
- watchpoint ending text

- [ ] **Step 3: Commit the final verified implementation**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py D:/Users/rickylu/dev/financial-services-plugins/docs/superpowers/specs/2026-04-19-chinese-readability-soft-preferences-design.md D:/Users/rickylu/dev/financial-services-plugins/docs/superpowers/plans/2026-04-19-chinese-readability-soft-preferences-implementation-plan.md
git commit -m "feat(autoresearch): add chinese readability soft preferences"
```
