# Live Snapshot Hardening Round 3 Design

## Goal

第三轮只解决两件在 `2026-04-21` rerun 里已经被证实的问题：

1. `google-news-world` latency 极高
   - `36kr` 约 `463 ms`
   - `google-news-world` 约 `128633 ms`
   - 当前 `live_snapshot` 总时延仍然被 world RSS 明显拖慢

2. `low_fit / medium_fit` 仍然会占满榜单
   - 当前前排仍有很多 `low_fit`
   - `medium_fit` 也依旧偏多
   - 真正应该进入前排的 `high_fit` 题仍然不够多

这轮目标不是再扩关键词，而是：

- 给 `live_snapshot` 一个更硬的榜单门槛
- 给 source 加轻量 budget / skip 机制

## Scope

只改：

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

不改：

- `default`
- `international_first`
- 文章生成链
- 发布链

## Design Principles

### 1. 继续只作用于 `live_snapshot`

所有新增行为只在：

- `discovery_profile=live_snapshot`

下生效。

### 2. 速度优先于覆盖

对 `live_snapshot` 来说：

- 少抓一点可以接受
- 多等两分钟不可以接受

所以这轮允许为了更快的返回而牺牲部分 source 覆盖。

### 3. 榜单优先展示“可写题”，而不是“当天新闻”

如果一个题只有：

- `low_fit`
- 或没有 market/company/conflict read-through

它不应该占据 `top_n` 的主要位置。

## Problem Analysis

### A. `google-news-world` 是当前主要慢源

第二轮 rerun 里：

- `36kr` 正常
- `google-news-world` 极慢

这说明 `live_snapshot` 已经不适合继续把两个 source 当成完全对等的默认必跑源。

### B. 现在的榜单容量规则还不够硬

当前逻辑已经能：

- 给题打 `high_fit / medium_fit / low_fit`
- 过滤部分 low-yield political observation

但还没有做到：

- `low_fit` 直接挡在榜单外
- `medium_fit` 只保留少量备选

结果就是榜单仍然充满：

- `low_fit`
- `medium_fit`

而不是以 `high_fit` 为中心。

## Proposed Changes

### 1. Add live snapshot ranking floor by fit class

新增 live-specific keep rules：

#### Rule A

`low_fit` 默认不进入最终 `ranked_topics`

例外只保留给：

- `top_n` 为空时的兜底回退

但第一阶段可以先不做这个例外，直接过滤。

#### Rule B

`medium_fit` 只保留少量备选

建议：

- `high_fit` 全保留
- `medium_fit` 最多 `2`
- `low_fit` 默认过滤

这样结果页会更接近“可写题 shortlist”。

### 2. Add live snapshot minimum score floor for `medium_fit`

即使是 `medium_fit`，也必须达到一个更高的 live-specific最低分。

建议：

- `medium_fit` 至少 `70`

目的：

- 防止一些只是“当天新，但分析性弱”的题靠 freshness 混进来

### 3. Add source budget / timeout guard for `live_snapshot`

不做复杂 scheduler，只做轻量 guard：

#### Option chosen

给 `live_snapshot` 增加 source-specific timeout cap：

- `google-news-world` 在 `live_snapshot` 下有独立更低 timeout

并且如果 source 超时：

- 记录在 `source_timings`
- 不拖住整轮结果

第一阶段建议：

- `google-news-world` soft budget: `15s`
- `36kr` 继续正常

### 4. Add source priority ordering inside `live_snapshot`

`live_snapshot` 默认 source 顺序改成：

1. `36kr`
2. `google-news-world`

原因：

- `36kr` 更快
- 结果更偏可写题

即使两个都保留，顺序也应该体现这个优先级。

### 5. Extend operator output

新增一个 operator 字段：

- `live_snapshot_rank_reason`

它直接解释为什么这题最终还能留在榜单里：

- `kept as high_fit`
- `kept as one of two medium_fit backups`
- `filtered because low_fit`
- `filtered because medium_fit score below floor`

## Runtime Integration

### `run_hot_topic_discovery()`

新增：

- `live_snapshot` source budget
- source priority order

要求：

- source 超时只影响该 source
- 不拖住整轮

### `apply_topic_controls()`

新增：

- `low_fit` 过滤
- `medium_fit` score floor

### final ranking pass

在 `kept_topics` 进入最终输出前再做一次 live-specific cap：

- `high_fit` 全部
- `medium_fit` 只留前 `2`

## Testing

新增测试：

1. `low_fit` 默认不进入 `live_snapshot` 榜单
2. `medium_fit` 超出数量限制时，只保留前 `2`
3. `medium_fit` 分数低于 floor 时被过滤
4. `source_timings` 在 source 超时/报错时仍能落盘
5. `live_snapshot` 不影响 `international_first`

## Non-Goals

这轮不做：

- 新 source 接入
- `agent-reach:reddit/x` 并回 `live_snapshot`
- source-level retry orchestration
- 更复杂的 multi-stage ranking pipeline

## Acceptance Criteria

这轮完成后应满足：

1. `low_fit` 不再进入 `live_snapshot` 前排榜单
2. `medium_fit` 不再占满榜单
3. `live_snapshot` 总时延明显下降
4. `source_timings` 仍然能清楚显示慢源或超时源
5. 全量 `test_article_publish.py` 继续通过
