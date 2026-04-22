# Article Quality Upgrade — 热点文章深度与标题优化

> Date: 2026-04-22
> Status: Draft

## Why

当前文章流程产出的内容偏向"信息汇总"，标题偏向"关键词堆砌"。
以最近发布的美伊冲突文章为例：标题「美伊冲突第49天：停火倒计时、霍尔木兹重开与框架协议博弈」——三个名词并列，缺乏张力和洞察钩子。

对标远川研究所、泽平宏观、Economist、Bloomberg Opinion 的水准，需要在三个层面升级：

1. **标题**：从信息堆砌 → 策略化生成（洞察型/对比型/决策框架型/紧迫型自动匹配）
2. **深度**：从事实汇总 → 因果推演 + 反直觉洞察 + 场景决策框架
3. **选题**：从热度排名 → 信息差优先（大家都在讨论但没人说清楚的话题）

## Phases

| Phase | Focus | Impact | Files |
|-------|-------|--------|-------|
| 1 | Title Strategy Engine | 立竿见影 | `article_draft_flow_runtime.py` |
| 2 | Depth Enhancement Layer | 质量跃升 | `article_revise_flow_runtime.py`, `article_brief_runtime.py` |
| 3 | Topic Scoring Upgrade | 长期价值 | `hot_topic_discovery_runtime.py` |

---

## Phase 1: Title Strategy Engine

### Problem

当前 `finalize_article_title()` 只有 4 种标题策略：
- `neutral`：无前缀，直接用 topic 文本
- `traffic`：前缀 "刚刚，"
- `aggressive`：前缀 "突发！"
- `headline_frame`：演员判断型（仅限 NVIDIA/TSMC/Tesla 等硬编码实体）

缺失的策略类型：
- **洞察型**：「霍尔木兹海峡"开了"，但油轮为什么不敢走？」
- **对比/反转型**：「油价暴跌11%，但聪明钱在做空」
- **决策框架型**：「美伊停火倒计时：三个信号判断真降温还是假和平」
- **悬念型**：「被忽略的关税数据揭示了什么」

### Solution

新增 `HEADLINE_STRATEGY_MATRIX`，根据话题特征自动匹配最佳标题策略：

```python
HEADLINE_STRATEGIES = {
    "insight": {
        "trigger": "canonical_facts 中存在与公众认知矛盾的事实",
        "templates_zh": [
            "{fact}，但{counter_fact}",
            "{surface_event}背后，{hidden_logic}",
            "被忽略的{data_point}揭示了什么",
        ],
        "templates_en": [
            "{fact}. Here's why that's misleading.",
            "The {data_point} everyone missed",
        ],
    },
    "contrast": {
        "trigger": "scenario_matrix 中存在对立场景 或 not_proven 与 canonical 冲突",
        "templates_zh": [
            "{positive_signal}，但{negative_signal}",
            "{actor}说{claim_a}，数据说{claim_b}",
            "{event}：谁在赢，谁在装",
        ],
    },
    "decision_frame": {
        "trigger": "scenario_matrix 有 ≥2 个概率差异大的场景",
        "templates_zh": [
            "{topic}：{n}个信号判断{question}",
            "看懂{event}只需要盯住这{n}件事",
        ],
    },
    "urgency": {
        "trigger": "timeliness ≤ 6h 且 source_count ≥ 3",
        "templates_zh": ["刚刚，{event}", "突发！{event}"],
    },
    "question": {
        "trigger": "open_questions 中有高价值未解问题",
        "templates_zh": [
            "{event}，接下来最该问的问题是什么",
            "{topic}最大的悬念不是{obvious}，而是{hidden}",
        ],
    },
}
```

### Implementation

**文件**: `article_draft_flow_runtime.py`

**Step 1** — 新增标题策略匹配函数 `resolve_headline_strategy()`：

```python
def resolve_headline_strategy(
    request: dict,
    analysis_brief: dict,
    source_summary: dict,
) -> str:
    """根据 brief 内容特征选择最佳标题策略。返回策略名。"""
    canonical = safe_list(analysis_brief.get("canonical_facts"))
    not_proven = safe_list(analysis_brief.get("not_proven"))
    scenarios = safe_list(analysis_brief.get("scenario_matrix"))
    open_qs = safe_list(analysis_brief.get("open_questions"))

    # 有矛盾事实 → insight
    if canonical and not_proven and any(
        np.get("status") == "denied" for np in not_proven
    ):
        return "insight"

    # 场景对立 → contrast
    if len(scenarios) >= 2:
        probs = [parse_probability_range(s) for s in scenarios]
        if max(probs) - min(probs) > 20:
            return "contrast"

    # 多场景 + 明确触发条件 → decision_frame
    if len(scenarios) >= 2 and all(s.get("trigger") for s in scenarios):
        return "decision_frame"

    # 高时效 + 多源 → urgency
    if is_within_hours(request, 6) and source_count(source_summary) >= 3:
        return "urgency"

    # 有未解高价值问题 → question
    if len(open_qs) >= 2:
        return "question"

    return "insight"  # 默认用洞察型
```

**Step 2** — 新增多候选标题生成 `generate_title_candidates()`：

```python
def generate_title_candidates(
    strategy: str,
    request: dict,
    analysis_brief: dict,
    source_summary: dict,
) -> list[dict]:
    """生成 3-5 个候选标题，每个带 strategy + score。"""
    # 从 brief 提取填充变量
    slots = extract_title_slots(analysis_brief, source_summary)
    templates = HEADLINE_STRATEGIES[strategy]["templates_zh"]
    candidates = []
    for tpl in templates:
        title = fill_template(tpl, slots)
        if title and not title_has_hanging_tail(title):
            candidates.append({
                "title": compact_chinese_title(title, limit=30),
                "strategy": strategy,
                "score": score_title_candidate(title, analysis_brief),
            })
    # 也生成当前默认标题作为 baseline
    candidates.append({
        "title": build_title(request, ..., ...),
        "strategy": "baseline",
        "score": 50,
    })
    return sorted(candidates, key=lambda c: c["score"], reverse=True)
```

**Step 3** — 新增标题评分 `score_title_candidate()`：

```python
def score_title_candidate(title: str, brief: dict) -> int:
    score = 50  # baseline
    # 包含反直觉元素 +15
    if any(m in title for m in ("但", "却", "不是", "而是", "为什么")):
        score += 15
    # 包含具体数字 +10
    if re.search(r"\d+", title):
        score += 10
    # 长度 12-25 字 +10 (最佳区间)
    if 12 <= len(title) <= 25:
        score += 10
    # 包含问句 +8
    if "？" in title or "?" in title:
        score += 8
    # 避免纯名词堆砌 (无动词/连词) -15
    if not any(v in title for v in ("是", "在", "但", "却", "为", "让", "把")):
        score -= 15
    return clamp(score, 0, 100)
```

**Step 4** — 修改 `finalize_article_title()` 调用链：

在现有 `finalize_article_title()` 中，当 `headline_hook_mode == "auto"` 时，
先调用 `resolve_headline_strategy()` → `generate_title_candidates()` → 取最高分候选。
如果最高分候选 > baseline 分数 + 10，使用新标题；否则保留原标题。

**插入点**: `finalize_article_title()` line 4958，在 `apply_headline_hook()` 之前。

---

## Phase 2: Depth Enhancement Layer

### Problem

红队检查只防 overclaiming（过度声称），不防 underclaiming（深度不足）。
文章可以忽略大部分 canonical_facts、全部 scenario_matrix、全部 open_questions，仍然通过。
`has_boundary_language()` 是二值检查（有任何一个标记词就通过），缺乏比例性。
`restructure_angle()` 按 risk 文本长度选角度（最短=最安全），而非按分析深度。

### Solution

在 `build_red_team_review()` 中新增 3 个检查维度：

#### 2a. Evidence Utilization Check（证据利用率检查）

```python
def check_evidence_utilization(
    article_text: str,
    canonical_facts: list,
    scenarios: list,
    open_questions: list,
) -> dict:
    """检查文章是否充分利用了 brief 中的分析素材。"""
    # 计算 canonical_facts 在文章中的出现率
    fact_hits = sum(
        1 for f in canonical_facts
        if fact_fingerprint(f) in article_text.lower()
    )
    fact_ratio = fact_hits / max(len(canonical_facts), 1)

    # 检查 scenario 是否被转化为决策框架
    scenario_used = any(
        scenario_fingerprint(s) in article_text.lower()
        for s in scenarios
    )

    # 检查 open_questions 是否被提及
    question_used = any(
        question_fingerprint(q) in article_text.lower()
        for q in open_questions
    )

    severity = "pass"
    if fact_ratio < 0.4:
        severity = "major"  # 使用不到 40% 的已确认事实
    if not scenario_used and len(scenarios) >= 2:
        severity = max_severity(severity, "major")
    if not question_used and len(open_questions) >= 2:
        severity = max_severity(severity, "minor")

    return {
        "attack_id": "shallow-evidence-utilization",
        "severity": severity,
        "fact_utilization_ratio": round(fact_ratio, 2),
        "scenario_used": scenario_used,
        "question_used": question_used,
    }
```

#### 2b. Proportional Boundary Check（比例性边界检查）

替换现有的 `has_boundary_language()` 二值检查：

```python
def check_proportional_boundaries(
    article_text: str,
    not_proven_claims: list,
) -> dict:
    """每个 not_proven claim 应该有对应的边界标记。"""
    if not not_proven_claims:
        return {"attack_id": "missing-proportional-boundaries", "severity": "pass"}

    boundary_markers_zh = ["未证实", "未确认", "不明确", "推断", "尚未", "仍不足以"]
    boundary_markers_en = ["not proven", "unclear", "inference", "unconfirmed"]
    all_markers = boundary_markers_zh + boundary_markers_en

    marker_count = sum(article_text.lower().count(m) for m in all_markers)
    claim_count = len(not_proven_claims)

    # 期望：至少 marker_count >= claim_count * 0.5
    ratio = marker_count / max(claim_count, 1)
    severity = "pass"
    if ratio < 0.3:
        severity = "major"
    elif ratio < 0.5:
        severity = "minor"

    return {
        "attack_id": "missing-proportional-boundaries",
        "severity": severity,
        "boundary_ratio": round(ratio, 2),
        "marker_count": marker_count,
        "claim_count": claim_count,
    }
```

#### 2c. Counter-Intuitive Insight Requirement（反直觉洞察要求）

```python
INSIGHT_MARKERS_ZH = [
    "但", "却", "反而", "真正的", "被忽略", "关键不在",
    "表面上", "实际上", "换句话说", "矛盾在于", "核心问题是",
]
INSIGHT_MARKERS_EN = [
    "but", "however", "actually", "the real", "overlooked",
    "counterintuitively", "the key issue", "what matters",
]

def check_insight_depth(article_text: str) -> dict:
    """检查文章是否包含反直觉或深度分析标记。"""
    all_markers = INSIGHT_MARKERS_ZH + INSIGHT_MARKERS_EN
    hits = sum(1 for m in all_markers if m in article_text.lower())

    severity = "pass"
    if hits < 2:
        severity = "minor"  # 建议性，不阻断
    if hits == 0:
        severity = "major"  # 完全没有分析深度标记

    return {
        "attack_id": "shallow-insight-depth",
        "severity": severity,
        "insight_marker_count": hits,
    }
```

### Implementation

**文件**: `article_revise_flow_runtime.py`

**插入点**: `build_red_team_review()` 函数（line 348），在现有 6 个 attack 检查之后追加 3 个新检查。

```python
# 现有检查 (保留不动)
attacks.extend([
    check_shadow_single_source_thesis(...),
    check_uncited_promoted_claims(...),
    check_non_core_promoted_claims(...),
    check_missing_boundary_language(...),
    check_visual_overreach(...),
    check_blocked_sources_hidden(...),
])

# 新增深度检查
attacks.extend([
    check_evidence_utilization(article_text, canonical_facts, scenarios, open_questions),
    check_proportional_boundaries(article_text, not_proven_claims),
    check_insight_depth(article_text),
])
```

**质量门更新**: 在 `build_quality_gate()` 中：
- `shallow-evidence-utilization` MAJOR → gate = "revise"（不阻断，要求修订）
- `missing-proportional-boundaries` MAJOR → gate = "revise"
- `shallow-insight-depth` MAJOR → gate = "revise"

**`rewrite_request_after_attack()` 扩展**:
当新 attack 触发时，向 `must_include` 注入：
- evidence-utilization: "确保引用至少 {n} 个已确认事实，并将场景分析转化为读者决策框架"
- proportional-boundaries: "为每个未确认声明添加明确的不确定性标记"
- insight-depth: "文章需要至少一个反直觉洞察或因果推演，不能只是信息汇总"

---

## Phase 3: Topic Scoring Upgrade

### Problem

当前 5 个评分维度（timeliness 25%, debate 20%, relevance 25%, depth 15%, SEO 15%）
选出的是"大家都在讨论的话题"，而不是"大家都在讨论但没人说清楚的话题"。

X 优质作者列表（7人）只用于 x-stock-picker-style，未接入选题评分。
`contrarian_frame` bonus 只检查标题关键词（+3），不利用 X 作者信号。

### Solution

#### 3a. 新增 `information_gap` 评分维度

```python
def information_gap_score(candidate: dict) -> int:
    """评估话题的信息差：公开讨论热度高但解释深度低。"""
    score = 20  # baseline

    # 高讨论量 + 低深度源 = 高信息差
    source_count = len(candidate.get("source_items", []))
    domain_diversity = candidate.get("domain_diversity", 0)
    has_analysis_source = any(
        s.get("source_tier", 99) <= 2
        for s in candidate.get("source_items", [])
    )

    # 多源讨论但缺少深度分析源 → 信息差大
    if source_count >= 3 and not has_analysis_source:
        score += 30
    elif source_count >= 2 and not has_analysis_source:
        score += 20

    # 社交媒体热度高但专业媒体覆盖低 → 信息差大
    social_count = sum(
        1 for s in candidate.get("source_items", [])
        if s.get("provider", "") in ("weibo", "zhihu", "reddit")
    )
    pro_count = source_count - social_count
    if social_count >= 2 and pro_count <= 1:
        score += 15

    # 有矛盾信号 → 信息差大（公众困惑）
    if candidate.get("has_contradicting_signals"):
        score += 15

    return clamp(score, 0, 100)
```

**权重调整**: 从现有维度中各减少一点，给 information_gap 10%：

| 维度 | 原权重 | 新权重 |
|------|--------|--------|
| timeliness | 25% | 22% |
| debate | 20% | 18% |
| relevance | 25% | 23% |
| depth | 15% | 14% |
| SEO | 15% | 13% |
| **information_gap** | — | **10%** |

#### 3b. X 作者信号整合

新增 `x_author_signal_bonus()`，在评分阶段检查话题是否与 X 优质作者的近期关注重叠：

```python
X_WATCHLIST_AUTHORS = {
    "twikejin": {"tier": 1, "focus": ["A股主题", "AI基建", "光模块"]},
    "LinQingV": {"tier": 1, "focus": ["存储", "DRAM", "兆易创新"]},
    "tuolaji2024": {"tier": 1, "focus": ["光互联", "光模块"]},
    "dmjk001": {"tier": 2, "focus": ["光互联", "硅光"]},
    "Ariston_Macro": {"tier": 1, "focus": ["宏观", "利率", "政策"]},
    "aleabitoreddit": {"tier": 2, "focus": ["AI基建", "半导体"]},
    "jukan05": {"tier": 2, "focus": ["半导体供应链"]},
}

def x_author_signal_bonus(candidate: dict) -> int:
    """X 优质作者关注的话题获得加分。"""
    bonus = 0
    topic_text = candidate.get("title", "").lower()
    for author, profile in X_WATCHLIST_AUTHORS.items():
        for focus in profile["focus"]:
            if focus.lower() in topic_text:
                tier_bonus = 6 if profile["tier"] == 1 else 3
                bonus += tier_bonus
                break  # 每个作者最多贡献一次
    return min(bonus, 15)  # cap at +15
```

#### 3c. Contrarian Signal 增强

扩展现有 `POSITIVE_FEEDBACK_CONTRARIAN_MARKERS`，从 +3 提升到 +8，
并新增基于 X 作者的反共识检测：

```python
# 扩展标记词
CONTRARIAN_MARKERS_EXTENDED = POSITIVE_FEEDBACK_CONTRARIAN_MARKERS + (
    "误判", "被低估", "被高估", "反转", "拐点",
    "underestimated", "overestimated", "turning point",
    "the market is wrong", "consensus is",
)
```

### Implementation

**文件**: `hot_topic_discovery_runtime.py`

**Step 1**: 在 `DEFAULT_TOPIC_SCORE_WEIGHTS` (line 136) 中新增 `information_gap` 维度。

**Step 2**: 在评分主函数 `build_clustered_candidate()` 中调用 `information_gap_score()`。

**Step 3**: 在 `positive_feedback_topic_bonus()` 之后追加 `x_author_signal_bonus()`。

**Step 4**: 扩展 `POSITIVE_FEEDBACK_CONTRARIAN_MARKERS` 并提升权重。

**X 作者列表维护**: 从 `x-stock-picker-style-subject-registry.template.json` 和
`author-discovery.md` 中读取，未来支持从 `x-source-whitelist.json` 动态加载。

---

## Verification

### Phase 1 验证
1. 用美伊冲突话题的 brief 数据调用 `resolve_headline_strategy()` → 应返回 `"contrast"` 或 `"insight"`
2. `generate_title_candidates()` 应产出 ≥3 个候选，最高分候选应优于 baseline
3. 对比：baseline 标题 vs 新标题，确认新标题包含张力/洞察元素

### Phase 2 验证
1. 用美伊冲突 v4 draft 文本跑 `check_evidence_utilization()` → 应检测到 fact_ratio < 0.4
2. `check_proportional_boundaries()` → 应检测到 boundary_ratio 不足
3. `check_insight_depth()` → 验证 final-article-zh.md (有深度) vs v4 draft (偏浅) 的分数差异

### Phase 3 验证
1. 用最近一次 hot-topic discovery 的候选列表重新评分，验证 information_gap 维度是否改变排名
2. 构造一个 X 作者关注领域匹配的话题，验证 x_author_signal_bonus 生效

## Backward Compatibility

- 所有新函数都是 **追加式**，不修改现有函数签名
- `headline_hook_mode` 现有值（auto/neutral/traffic/aggressive）行为不变
- 新增的红队检查 severity 默认为 "minor" 或 "major"，不会 "block"
- 评分权重调整幅度小（每个维度 ≤3%），不会剧烈改变现有排名
- `X_WATCHLIST_AUTHORS` 为静态配置，不依赖外部服务
- 所有新增代码通过 feature flag 可关闭：`enable_title_strategy=false`, `enable_depth_checks=false`, `enable_info_gap_scoring=false`
