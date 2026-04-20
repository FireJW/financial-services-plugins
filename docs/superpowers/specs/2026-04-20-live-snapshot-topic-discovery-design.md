# Live Snapshot Topic Discovery Design

## Goal

新增一个显式热点快照 profile：

- `discovery_profile=live_snapshot`

它的目标不是“抓全当天新闻”，而是更快地产出**当天可写、可延展、适合分析稿**的热点候选。

这条 profile 需要优先解决 3 个问题：

1. 多源 live discovery 太慢，容易超时。
2. 单源快照虽然能跑通，但会把很多“当天新闻”而不是“当天选题”顶上来。
3. 当前 recency/heat 规则已经能分出“新题”和“旧题”，但还缺一层专门面向 live snapshot 的 source pack 和可写性过滤。

## Scope

第一阶段只改：

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py`
- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

不改：

- `article_draft_flow_runtime.py`
- `article_publish_runtime.py`
- 任何发布链脚本
- `default` 或 `international_first` 的现有行为

## Design Principles

### 1. 显式 opt-in

`live_snapshot` 只在显式传入时生效。

它不是默认 profile，也不替换 `international_first`。

这样可以先把“当天可写热点快照”做稳，再决定是否把它接入更上游的默认流。

### 2. 快照优先于抓全

`live_snapshot` 的优化目标是：

- 更快返回一批可写候选
- 更早过滤“当天新闻但不可写”的题
- 更明确告诉 operator 为什么这题值得现在写

它不是一个完整新闻索引入口。

### 3. 可写性优先于广覆盖

同样是当天新题：

- “冲突升级后油价与风险资产重新定价”是可写题
- “某官媒口径表态”通常不是可写题

`live_snapshot` 的判断标准应该更接近“适不适合立刻写成分析稿”，而不是“是不是今天刚发生”。

## Profile Contract

### New profile value

- `discovery_profile=live_snapshot`

### New operator fields

在 `live_snapshot` 下，每个 candidate 额外输出：

- `live_snapshot_fit`
- `live_snapshot_reason`

约束：

- `live_snapshot_fit` 是一个短标签，表示它在当天快照里的适配度
- `live_snapshot_reason` 是一句 operator 可读解释，说明为什么它被保留、降级、或过滤

第一阶段推荐的 `live_snapshot_fit` 取值：

- `high_fit`
- `medium_fit`
- `low_fit`

## Default Runtime Behavior

### Default source pack

`live_snapshot` 第一阶段默认 source pack：

- `google-news-world`
- `36kr`

第一阶段明确不默认带入：

- `agent-reach:reddit`
- `agent-reach:x`

原因：

- 当前这两层更适合后续增强，不适合“当天快照”的稳定入口
- 它们会显著增加超时和噪音风险

### Default runtime parameters

`live_snapshot` 下的默认运行参数要比现有 profile 更收敛：

- `limit` 更小
- `top_n` 更小
- `max_parallel_sources` 收住

第一阶段建议：

- `limit = 8`
- `top_n = 5`
- `max_parallel_sources = 2`

如果用户显式传入这些参数，仍然以用户值为准。

## Live Snapshot Filtering

### Keep criteria

`live_snapshot` 优先保留这些题：

1. **公司/产业/市场 read-through 明确**
   - 财报
   - 指引上修/下修
   - rollout
   - 供应链变化
   - 新政策落地
   - 新冲突升级并已经进入市场定价

2. **当天事件能自然延展成判断**
   - 不只是“发生了什么”
   - 还能回答“为什么现在值得写”
   - 以及“它会改变什么判断”

3. **近窗时效与分析延展兼具**
   - 新近窗口内发生
   - 同时具备市场、产业或政策的第二层含义

### Reject criteria

`live_snapshot` 下默认更狠地压掉这些题：

1. **泛官媒口径**
   - 只有政策口号、会议表态、宣传式标题
   - 缺少明确产业/市场/公司 read-through

2. **低延展社会新闻**
   - 虽然当天新，但没有金融、产业或政策延展空间

3. **单源弱确认但缺少分析价值**
   - 只有单一 source
   - 没有 fresh catalyst 的额外证明
   - 也没有清晰的市场或产业第二层意义

4. **纯快讯型政治 headline**
   - 只有表态，没有价格、政策、供给链、公司层的进一步传导

## Live Snapshot Fit Heuristic

第一阶段不单独重写全部 ranking，而是在现有 recency/heat hardening 之上再加一层 live-specific fit 评估。

### `high_fit`

满足这些倾向的题：

- 0-24h 内的新信号
- 有明确 company / market / policy / conflict read-through
- 标题和摘要能自然延展出分析角度
- 不是单纯口径或快讯

### `medium_fit`

满足时效性，但还需要人工判断是否值得写：

- 题新
- 有一定延展空间
- 但判断空间不够强，或 source support 偏单薄

### `low_fit`

题虽然新，但不适合当天分析稿：

- 快讯感太强
- 延展空间弱
- 或明显是泛口径/泛社会新闻

## Output Semantics

### `live_snapshot_reason`

这个字段必须直接回答 operator 的问题：

- 为什么这题可以立刻写
- 为什么这题只是当天新闻
- 为什么它被降级

建议输出风格：

- `This is still a real-time writeable topic because the new signal already changes market or policy expectations.`
- `Fresh headline, but it still reads like a narrow news flash rather than an analysis topic.`
- `Same-day signal is real, but the story lacks a clear second-order read-through beyond the headline.`

第一阶段允许英文 operator 文案，后续再决定是否统一中文化。

## Runtime Integration

### `normalize_request()`

需要在 request normalization 阶段加入：

- `live_snapshot` 的默认 source pack
- `live_snapshot` 的默认 `limit/top_n/max_parallel_sources`

但必须遵守：

- 如果用户显式传入值，不覆盖用户输入

### `build_clustered_candidate()`

在现有 scoring 完成后，为 candidate 补：

- `live_snapshot_fit`
- `live_snapshot_reason`

这两个字段应该只在 `live_snapshot` 下设置。

### `apply_topic_controls()`

在 `live_snapshot` 下增加一层专用过滤：

- 泛官媒口径
- 低延展社会新闻
- 单源弱确认且无明确分析空间
- 纯快讯型政治 headline

要求：

- 不影响 `default`
- 不影响 `international_first`

## CLI Surface

### `hot_topic_discovery.py`

第一阶段不新增新的 CLI 旗标，只复用现有：

- 输入 JSON 里传 `discovery_profile=live_snapshot`

不改 CLI contract 的原因：

- 当前脚本已经支持从 JSON request 读取 profile
- 先验证运行质量，没必要扩大命令行表面

## Testing

### New tests

需要补这些测试：

1. `live_snapshot` 默认 source pack 与现有 profile 隔离
   - `default` 不变
   - `international_first` 不变
   - `live_snapshot` 用新默认 pack

2. `live_snapshot` 压掉泛官媒/泛政治快讯
   - 当天新，但因为缺少 read-through，被过滤或明显降级

3. `live_snapshot` 保留当天可写题
   - 公司、市场、冲突 read-through 明确的题，能保留并获得 `high_fit`

4. `live_snapshot` operator 字段齐全
   - `live_snapshot_fit`
   - `live_snapshot_reason`

5. `live_snapshot` 不影响 `international_first`
   - 现有 `international_first` 热点测试保持绿

### Regression target

完整回归仍然用：

- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

## Non-Goals

第一阶段明确不做：

- 把 `agent-reach:reddit/x` 并回 `live_snapshot`
- 做两阶段候选池
- 改文章生成
- 改发布链
- 改 `international_first` 的 source pack

## Acceptance Criteria

只有满足以下条件，第一阶段才算完成：

1. `live_snapshot` 显式可用，且不污染现有 profile。
2. `live_snapshot` 默认运行明显更快、更稳。
3. `live_snapshot` 的候选更接近“当天可写选题”，而不是“当天新闻列表”。
4. operator 输出能明确解释某题为什么适合立刻写。
5. 现有 `test_article_publish.py` 全量回归保持通过。
