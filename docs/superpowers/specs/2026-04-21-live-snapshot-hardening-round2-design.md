# Live Snapshot Hardening Round 2 Design

## Goal

在已经上线的 `discovery_profile=live_snapshot` 基础上，继续解决两类实际问题：

1. **题目质量不够硬**
   - 前排结果里仍然混入了泛政治、泛观察、泛时政分析题
   - 很多结果都只落到 `medium_fit`
   - 真正应该升到 `high_fit` 的公司/市场/冲突 read-through 题没有被显著拉开

2. **运行过程缺少 timing 诊断**
   - 现在能跑出结果，但 source-level latency 不可见
   - 后续如果继续压缩快照时延，没有足够证据知道是哪个 source 在拖慢

这轮目标不是重做架构，而是在现有 `live_snapshot` 上做第二层硬化：

- 扩 `high_fit`
- 压掉泛政治/泛观察 `medium_fit`
- 给 `medium_fit` 增加更严格门槛
- 增加 source timing 诊断

## Scope

只改：

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

可选轻触：

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py`
  - 仅当需要把 timing 一并写出到输出文件时

不改：

- `default`
- `international_first`
- 文章生成链
- 发布链

## Design Principles

### 1. 继续保持显式 opt-in

所有新增行为仍然只作用于：

- `discovery_profile=live_snapshot`

不回灌到其它 discovery profile。

### 2. 优先拉开 `high_fit` 与 `medium_fit`

当前主要问题不是“全是错误题”，而是：

- 结果里大量题都只是 `medium_fit`
- `high_fit` 太难被命中

这轮核心不是新增更多标签，而是让：

- 真正能立刻写的题更容易进 `high_fit`
- 泛观察和泛时政题更容易被压掉或降级

### 3. 先做解释性强化，再考虑更重的 source 重构

source timing 这轮只做**诊断信息**，不做新的 source scheduler。

原因：

- 当前先把“哪个 source 慢、哪个 source 值得保留”看清
- 再决定第三轮是否需要 source-level skip / budget 控制

## Problem Analysis

### A. `high_fit` 命中面太窄

第一轮的 `high_fit` 关键词更偏：

- `oil`
- `equities`
- `stocks`
- `guidance`
- `earnings`
- `capex`
- `policy`
- `conflict`

这导致两类本来该高优先的题没有被充分识别：

1. **公司财务 read-through**
   - revenue
   - profit
   - margin
   - loss
   - growth
   - order / intake

2. **宏观/冲突 read-through**
   - ceasefire
   - negotiation
   - sanctions
   - strait
   - shipping
   - fuel / jet fuel

### B. 泛政治/泛观察题仍然能混进前排

当前 low-yield filter 主要压的是：

- 明显官方口径
- 明显宣传式标题

但还没压掉这些“更像时评而不是可写分析稿”的题：

- 多国政要密集访华背后……
- 国际观察丨美伊谈判悬念丛生……
- 台湾业界呼吁当局理性回应……

这些题的问题不是“不新”，而是：

- headline 新
- 但 read-through 不够硬
- 更像评论栏目，而不是当天分析稿入口

### C. `medium_fit` 缺少容量控制

当前 `medium_fit` 只是一个分类，不是门槛。

结果就是：

- `medium_fit` 会大量占满榜单
- `high_fit` 没有形成明显的前排优先级

这轮需要把 `medium_fit` 从“可上榜”改成“受限保留”。

### D. source latency 不可见

现在只知道整轮 `live_snapshot` 的完成时间，不知道：

- `36kr` 花了多久
- `google-news-world` 花了多久
- 哪个 source 有明显 tail latency

没有这层 timing，就没法做下一轮速度优化。

## Proposed Changes

### 1. 扩 `high_fit` 关键词面

在现有 `LIVE_SNAPSHOT_ANALYSIS_KEYWORDS` 基础上扩到两组：

#### Company / market read-through

- `revenue`
- `profit`
- `margin`
- `loss`
- `growth`
- `forecast`
- `guidance`
- `earnings`
- `net income`
- `gross margin`
- `order`
- `orders`
- `order intake`
- `capex`
- `rollout`

中文对应：

- `营收`
- `利润`
- `净利`
- `毛利率`
- `亏损`
- `增长`
- `指引`
- `财报`
- `订单`
- `新增订单`
- `资本开支`

#### Macro / conflict read-through

- `ceasefire`
- `negotiation`
- `talks`
- `sanction`
- `sanctions`
- `strait`
- `shipping`
- `freight`
- `fuel`
- `jet fuel`
- `hormuz`

中文对应：

- `停火`
- `谈判`
- `会谈`
- `制裁`
- `海峡`
- `航运`
- `运费`
- `燃油`
- `航油`
- `霍尔木兹`

### 2. 新增“泛政治/观察稿”压制层

增加一个 live-specific helper，用于识别：

- 国际观察
- 时政观察
- 背后逻辑
- 多种可能
- 如何看待
- 为什么说
- 形势走向

这一类题如果同时满足：

- 没有明显公司/市场/价格/供给链 read-through
- 没有明确量化或公司层变量

则在 `live_snapshot` 下直接过滤或降级。

这层规则只在 `live_snapshot` 生效。

### 3. 给 `medium_fit` 加保留门槛

不直接改成 hard filter 全清，而是：

#### Rule A

`high_fit` 始终优先于 `medium_fit`

#### Rule B

`medium_fit` 只有在以下情况才允许保留：

- freshness 在 `0-6h` 或 `6-24h`
- 且不是 low-yield political/observation topic
- 且 total score 不低于 live-specific floor

#### Rule C

如果当前结果中已经有足够多 `high_fit`，则只保留少量 `medium_fit`

第一阶段建议：

- `high_fit` 不限
- `medium_fit` 最多保留 `2`

这样能避免榜单被 `medium_fit` 占满。

### 4. 增加 source timing diagnostics

在 `run_hot_topic_discovery()` 的 source fetch 路径里记录每个 source 的 wall-clock duration。

新增输出字段：

- `source_timing`

结构建议：

```json
[
  {
    "source": "google-news-world",
    "duration_ms": 1240,
    "status": "ok"
  },
  {
    "source": "36kr",
    "duration_ms": 2815,
    "status": "ok"
  }
]
```

如果 source 报错：

- 仍记录 `duration_ms`
- `status = error`
- 可附带 `message`

### 5. 增强 report 输出

`report.md` 顶部增加 timing 摘要：

- source
- duration
- status

目的是让 operator 一眼看出慢源。

## Runtime Integration

### `build_clustered_candidate()`

继续在这里决定：

- `live_snapshot_fit`
- `live_snapshot_reason`

新增逻辑：

- 扩 `high_fit`
- 对明显 observation-style 标题做降级

### `apply_topic_controls()`

继续在这里做 live-specific keep/drop。

新增逻辑：

- `low_yield_observation`
- `medium_fit` 容量控制 / floor

### `run_hot_topic_discovery()`

新增：

- source fetch start/end timing
- `source_timing` 输出

## Testing

需要新增这些测试：

1. **公司财务题升到 `high_fit`**
   - 例如 revenue / profit / margin / order 语义

2. **冲突 read-through 题升到 `high_fit`**
   - 例如 Hormuz / oil / shipping / ceasefire

3. **泛政治观察题在 `live_snapshot` 下被压掉**
   - headline 新，但没有硬 read-through

4. **`medium_fit` 不会占满榜单**
   - 在有 `high_fit` 时，`medium_fit` 只保留受限数量

5. **`source_timing` 落到结果里**
   - source 成功时有 duration
   - source 失败时也有 duration + error status

6. **不影响 `international_first`**
   - 现有 `international_first` 相关测试保持绿

## Non-Goals

这轮仍然不做：

- 把 `agent-reach:reddit/x` 并入 `live_snapshot`
- source-level scheduler / budget engine
- 新的 discovery pipeline
- 文章生成 / 发布链改动

## Acceptance Criteria

只有满足以下条件，这轮才算完成：

1. `high_fit` 不再过少，至少能稳定命中公司/市场/冲突 read-through 题。
2. 泛政治/观察类 `medium_fit` 明显减少。
3. 榜单不会再被 `medium_fit` 占满。
4. `source_timing` 能告诉 operator 哪个 source 慢。
5. 全量 `test_article_publish.py` 仍然通过。
