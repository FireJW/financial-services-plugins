# CN Macro Political Longform Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an explicit `composition_profile=cn_macro_political_longform` preset that gives Chinese macro/political/market longform articles a scene-setting lead, a single core contradiction, zoom-in section ordering, pain-chain reasoning, watchpoint endings, and more specific macro subtitle / lede / concrete case / market read-through handling without changing default article behavior.

**Architecture:** Keep the entire first-stage implementation inside `article_draft_flow_runtime.py`, where title/subtitle/sections/body markdown are already assembled. Add an opt-in request flag, route only matching Chinese drafts through a dedicated macro longform section builder, then layer macro-specific subtitle, scene-setting lede, concrete case expansion, institutional bottleneck wording, and numbered market read-throughs on top. Cover the behavior with focused tests in `test_article_publish.py` before running the full article-publish regression file.

**Tech Stack:** Python, existing autoresearch runtime helpers, unittest-based regression commands in this workspace

---

### Task 1: Add opt-in profile tests and prove default behavior stays unchanged

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
- Read: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\article_draft_flow_runtime.py`

- [ ] **Step 1: Add a failing test that the macro profile is opt-in only**

Add the new test near the other article-structure tests.

```python
    def test_cn_macro_profile_is_opt_in_only(self) -> None:
        request = {
            "language_mode": "chinese",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["国会格局、政策阻力和市场波动率"],
            "open_questions_zh": ["哪些州会决定参议院控制权？"],
        }

        title = finalize_article_title(request["topic"], request, analysis_brief, source_summary)
        subtitle = build_subtitle(request, source_summary, [])
        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )

        self.assertNotEqual(subtitle, "先从一个具体判断现场讲起，再看这条政治风险会怎样传到市场。")
        self.assertFalse(any("核心矛盾" in clean_text(item.get("heading")) for item in sections if isinstance(item, dict)))
```

- [ ] **Step 2: Add a failing test that the explicit macro profile builds the expected section order**

```python
    def test_cn_macro_profile_builds_zoom_in_section_order(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["中期选举、政策僵局和市场波动率重定价"],
            "open_questions_zh": ["北卡、阿拉斯加、俄亥俄谁会先动？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )

        headings = [clean_text(item.get("heading")) for item in sections if isinstance(item, dict)]
        self.assertEqual(
            headings[:6],
            [
                "开头引入",
                "核心矛盾",
                "关键样本",
                "体感变量与传导链",
                "制度与政策层变量",
                "市场含义",
            ],
        )
```

- [ ] **Step 3: Run the focused tests to verify they fail**

Run:

```bash
& 'C:\Users\rickylu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m unittest "D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py" -k "cn_macro_profile"
```

Expected:

- FAIL because `composition_profile` is ignored and `build_sections()` still returns the generic section shape

- [ ] **Step 4: Commit the red test**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "test(autoresearch): add cn macro profile section coverage"
```

---

### Task 2: Add request normalization and profile detection helpers

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\article_draft_flow_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Normalize the new request field**

Add `composition_profile` to request normalization near the other writing-style fields.

```python
        "composition_profile": clean_text(payload.get("composition_profile")),
```

and preserve it through the request object:

```python
    request["composition_profile"] = clean_text(request.get("composition_profile"))
```

- [ ] **Step 2: Add explicit profile detection helper**

Place this near the other topic/profile predicates.

```python
def is_cn_macro_political_longform_profile(request: dict[str, Any]) -> bool:
    return (
        clean_text(request.get("language_mode")) == "chinese"
        and clean_text(request.get("composition_profile")) == "cn_macro_political_longform"
    )
```

- [ ] **Step 3: Add a narrow macro-topic context helper**

The preset is opt-in, but it still needs a sanity check so obviously unrelated topics do not get the macro outline by mistake.

```python
def looks_like_macro_political_market_longform_context(items: list[str]) -> bool:
    joined = " ".join(clean_text(item).lower() for item in items if clean_text(item))
    return any(
        token in joined
        for token in (
            "election",
            "senate",
            "house",
            "president",
            "poll",
            "federal reserve",
            "powell",
            "middle east",
            "oil",
            "congress",
            "midterm",
            "选举",
            "参议院",
            "众议院",
            "总统",
            "支持率",
            "美联储",
            "鲍威尔",
            "国会",
            "中期选举",
            "油价",
            "波动率",
        )
    )
```

- [ ] **Step 4: Run the focused tests again**

Run:

```bash
& 'C:\Users\rickylu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m unittest "D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py" -k "cn_macro_profile"
```

Expected:

- still FAIL, but now only because the dedicated section builder does not exist yet

- [ ] **Step 5: Commit the request/profile helpers**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add cn macro composition profile gate"
```

---

### Task 3: Add dedicated macro longform section builder with zoom-in ordering

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\article_draft_flow_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add focused builder helpers for each section role**

Add helpers near the existing section-building functions.

```python
def build_cn_macro_scene_lead(request: dict[str, Any], source_summary: dict[str, Any]) -> str:
    topic = clean_text(source_summary.get("topic")) or clean_text(request.get("topic"))
    return f"距离下一轮关键投票窗口已经不远，但真正先紧张起来的往往不是选民，而是已经开始重新定价风险的人。围绕{topic}，现在更值得看的不是口号，而是判断现场本身。"


def build_cn_macro_core_contradiction_section(request: dict[str, Any], source_summary: dict[str, Any], analysis_brief: dict[str, Any]) -> dict[str, str]:
    contradiction = clean_string_list(analysis_brief.get("market_or_reader_relevance_zh"))[:1]
    line = contradiction[0] if contradiction else "表面政治叙事和真实制度约束正在彼此错位。"
    return {
        "heading": "核心矛盾",
        "paragraph": f"这篇文章真正要解释的，不是单一 headline，而是一个更硬的冲突：{line}。后面所有判断，都围绕这条线展开。",
    }
```

- [ ] **Step 2: Add the full section builder with the target order**

```python
def build_cn_macro_political_longform_sections(
    request: dict[str, Any],
    source_summary: dict[str, Any],
    analysis_brief: dict[str, Any],
) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = [
        {"heading": "开头引入", "paragraph": build_cn_macro_scene_lead(request, source_summary)},
        build_cn_macro_core_contradiction_section(request, source_summary, analysis_brief),
        {
            "heading": "关键样本",
            "paragraph": "接下来要看的不是抽象总量，而是2到3个最能体现风险转向的样本：关键州、关键机构、关键人，谁先松动，谁就最早改变市场对主线的理解。",
        },
        {
            "heading": "体感变量与传导链",
            "paragraph": "真正会推动政治环境变化的，往往不是口号，而是体感。比如油价、通勤、家庭支出、消费缩减，这类变量一旦连成链，政治耐心就会先于 headline 改变。",
        },
        {
            "heading": "制度与政策层变量",
            "paragraph": "再往上一层看，需要确认的不是情绪本身，而是制度和政策层面的卡点：国会、任命、确认程序、政策时钟，这些都会决定风险是被吸收，还是继续外溢。",
        },
        {
            "heading": "更远期展望",
            "paragraph": "如果前面的结构成立，后面被提前带出来的就不只是当前一轮选情，而是更长周期里的候选人布局、政策连续性和市场对未来两到三年的重新定价。",
        },
        {
            "heading": "市场含义",
            "paragraph": "真正值得定价的，不是口号本身，而是哪条变量会先传到资产价格、政策预期和波动率上。只有把这条线讲闭环，市场含义才成立。",
        },
    ]
    return sections
```

- [ ] **Step 3: Route `build_sections()` through the preset when explicitly requested**

Add the profile branch early in the main section builder, before the generic Chinese section path:

```python
    if is_cn_macro_political_longform_profile(request):
        topic_lines = [
            clean_text(request.get("topic")),
            clean_text(source_summary.get("topic")),
            clean_text(source_summary.get("core_verdict")),
            *clean_string_list(safe_dict(analysis_brief).get("market_or_reader_relevance_zh")),
        ]
        if looks_like_macro_political_market_longform_context(topic_lines):
            return build_cn_macro_political_longform_sections(request, source_summary, analysis_brief)
```

- [ ] **Step 4: Run the focused profile tests**

Run:

```bash
& 'C:\Users\rickylu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m unittest "D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py" -k "cn_macro_profile"
```

Expected:

- PASS for the opt-in and section ordering tests

- [ ] **Step 5: Commit the section builder**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add cn macro longform section builder"
```

---

### Task 4: Add pain-chain and watchpoint-ending tests

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add a test that the preset includes both core contradiction and causal chain language**

```python
    def test_cn_macro_profile_includes_core_contradiction_and_pain_chain(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["油价、消费和投票意愿会不会继续形成连锁反应？"],
        }

        sections = article_draft_flow_runtime.build_sections(request, source_summary, {}, [], [], analysis_brief)
        body = "\\n\\n".join(clean_text(item.get("paragraph")) for item in sections if isinstance(item, dict))

        self.assertIn("结构性错位", body)
        self.assertTrue(any(token in body for token in ("油价", "通勤", "消费", "耐心")))
```

- [ ] **Step 2: Add a test that the ending uses watchpoints rather than recap-only summary**

```python
    def test_cn_macro_profile_ending_uses_watchpoints_not_summary_recap(self) -> None:
        ending = article_draft_flow_runtime.build_cn_macro_watchpoint_ending(
            {
                "language_mode": "chinese",
                "composition_profile": "cn_macro_political_longform",
                "topic": "2026美国中期选举：华尔街大行内部怎么看？",
            },
            {
                "open_questions_zh": [
                    "第二季度油价会不会继续抬升？",
                    "关键州民调会不会继续收窄？",
                    "美联储人事确认会不会拖延？",
                ]
            },
            {"topic": "2026美国中期选举：华尔街大行内部怎么看？"},
        )

        self.assertIn("更值得盯的，是接下来几个验证节点", ending)
        self.assertIn("第二季度油价", ending)
        self.assertNotIn("综上所述", ending)
```

- [ ] **Step 3: Run the new focused tests to verify they fail**

Run:

```bash
& 'C:\Users\rickylu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m unittest "D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py" -k "pain_chain or watchpoints_not_summary_recap"
```

Expected:

- FAIL because the dedicated ending builder does not exist yet

- [ ] **Step 4: Commit the red tests**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "test(autoresearch): add cn macro longform ending coverage"
```

---

### Task 5: Implement watchpoint ending and integrate it into the preset

**Files:**
- Modify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\article_draft_flow_runtime.py`
- Test: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`

- [ ] **Step 1: Add the dedicated watchpoint ending builder**

```python
def build_cn_macro_watchpoint_ending(
    request: dict[str, Any],
    analysis_brief: dict[str, Any],
    source_summary: dict[str, Any],
) -> str:
    watchpoints = clean_string_list(safe_dict(analysis_brief).get("open_questions_zh"))[:3]
    lines = ["更值得盯的，是接下来几个验证节点："]
    for item in watchpoints:
        lines.append(f"- {item}")
    if not watchpoints:
        lines.append(f"- 围绕{clean_text(source_summary.get('topic')) or clean_text(request.get('topic'))}，后续最关键的是确认哪些变量开始真正改变市场定价。")
    return "\\n".join(lines)
```

- [ ] **Step 2: Append the watchpoint ending as the final macro section**

Update the preset builder to end with a dedicated ending section:

```python
        {
            "heading": "结尾",
            "paragraph": build_cn_macro_watchpoint_ending(request, analysis_brief, source_summary),
        },
```

- [ ] **Step 3: Re-run the focused pain-chain and ending tests**

Run:

```bash
& 'C:\Users\rickylu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m unittest "D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py" -k "pain_chain or watchpoints_not_summary_recap"
```

Expected:

- PASS

- [ ] **Step 4: Commit the ending integration**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add cn macro watchpoint endings"
```

---

### Task 6: Run full regression and sample replay

**Files:**
- Verify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py`
- Verify: `D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\scripts\article_draft_flow_runtime.py`
- Optional replay scratch: `D:\Users\rickylu\dev\financial-services-plugins\.tmp\`

- [ ] **Step 1: Run the full article-publish regression file**

Run:

```bash
& 'C:\Users\rickylu\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -X utf8 -m unittest "D:\Users\rickylu\dev\financial-services-plugins\financial-analysis\skills\autoresearch-info-index\tests\test_article_publish.py"
```

Expected:

- PASS with the full file green

- [ ] **Step 2: Run one explicit macro-profile sample replay**

Create a small scratch request that passes:

```python
request = {
    "language_mode": "chinese",
    "composition_profile": "cn_macro_political_longform",
    "topic": "2026美国中期选举：华尔街大行内部怎么看？",
}
```

and verify the output contains:

- `开头引入`
- `核心矛盾`
- `体感变量与传导链`
- `市场含义`
- `结尾`

- [ ] **Step 3: Commit the verified final state**

```bash
git add D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py D:/Users/rickylu/dev/financial-services-plugins/financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py
git commit -m "feat(autoresearch): add cn macro political longform preset"
```

---

## Self-Review

### Spec coverage

- Request normalization is covered in Task 2.
- Dedicated section blueprint is covered in Task 3.
- Core contradiction and pain-chain requirements are covered in Task 4 and Task 5.
- Watchpoint ending is covered in Task 5.
- Default behavior unchanged is covered by Task 1.
- Full regression and sample replay are covered in Task 6.

No spec section is left without a corresponding task.

### Placeholder scan

The plan contains:

- exact file paths
- explicit helper names
- explicit test names
- exact verification commands
- concrete commit messages

No placeholder markers, vague cross-references, or empty implementation steps remain.

### Type consistency

The same identifiers are used consistently through the plan:

- `composition_profile`
- `cn_macro_political_longform`
- `is_cn_macro_political_longform_profile`
- `build_cn_macro_political_longform_sections`
- `build_cn_macro_watchpoint_ending`

The same request / source_summary / analysis_brief argument shape is used across tests and implementation steps.
