# Live Snapshot Hardening Round 2 Design

## Goal

在现有 `discovery_profile=live_snapshot` 基础上，继续解决两类剩余问题：

1. **榜单质量还不够像“可写题”**
   - 公司/市场/冲突 read-through 题没有稳定升到 `high_fit`
   - 泛政治/泛观察类 headline 还会以 `medium_fit` 混进前排
   - `medium_fit` 太宽，导致榜单前排缺少真正强结论候选

2. **快照运行仍然偏慢**
   - 目前已经能稳定跑通，但整体耗时仍偏高
   - 缺少 per-source timing，无法直接判断是哪一层在拖慢 live snapshot

## Scope

第二轮只改：

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

可选最小 CLI 透传：

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery.py`

不改：

- `article_draft_flow_runtime.py`
- `article_publish_runtime.py`
- 任何发布链脚本
- `default`
- `international_first`
- `live_snapshot` 的 source pack 选择

## Design Principles

### 1. 不扩 profile，直接硬化现有 `live_snapshot`

第二轮不新增 profile，也不改 `live_snapshot` 的 opt-in 边界。

这轮目标是让现有 `live_snapshot` 更像“当天可写选题快照”，而不是“当天新闻列表”。

### 2. `high_fit` 必须成为真正的前排信号

第一轮里所有结果都落成 `medium_fit`，说明 `high_fit` 的门槛定义不对，不是数据源问题。

第二轮要求：

- 有明确财务、市场、冲突 read-through 的题，应该稳定命中 `high_fit`
- `high_fit` 需要在榜单排序和保留逻辑里形成真实优先级

### 3. `medium_fit` 应该是少量备选，不是默认状态

`medium_fit` 的本意是：

- 新
- 有一点可写空间
- 但判断还不够强

它不应该成为榜单前排的默认状态。

第二轮要把 `medium_fit` 收紧，并限制它在最终榜单中的占比。

### 4. timing 先做诊断，不直接做调度重构

第二轮先记录：

- 每个 source 的抓取耗时
- 整个 run 的总耗时

先让 operator 看得见慢在哪，再决定第三轮要不要改 source scheduling。

## Problems Observed In The First Live Run

基于 `2026-04-20` 的实际 `live_snapshot` 结果，观察到：

1. 前 8 条全部是 `medium_fit`
2. `字节跳动2025年海外营收占比创新高，AI投入致公司净利大降70%` 这类明显有财务和市场 read-through 的题，没有被提升为 `high_fit`
3. `多国政要密集访华背后...`、`台湾业界代表呼吁...`、`国际观察丨美伊谈判悬念丛生...` 这类泛政治/泛观察题仍然留在榜单前排
4. 运行完成但整体耗时偏高，且当前结果里没有 source-level timing 信息

## Desired Behavior

第二轮之后，希望 `live_snapshot` 更接近下面这种筛法：

### 更容易进前排

- 财报、盈利、利润率、指引变化
- 油价、风险资产、利率、航运、供给链 read-through
- 冲突升级已经开始传到市场定价
- 公司 rollout、订单、capex、供应链变化

### 更容易被压掉

- 泛时政观察
- 外交礼仪与姿态型标题
- 官媒口径或价值判断型 headline
- 没有市场、产业、公司第二层含义的“国际观察”

## Round 2 Changes

### 1. Expand `high_fit` detection

第一轮 `high_fit` 关键词集明显太窄。

第二轮扩进去的重点方向：

- 财务与结果类
  - `revenue`
  - `profit`
  - `margin`
  - `loss`
  - `guidance`
  - `earnings`
  - `capex`
  - `order`
  - `orders`
- 市场传导类
  - `oil`
  - `equities`
  - `stocks`
  - `risk assets`
  - `shipping`
  - `strait`
  - `inflation`
  - `yield`
- 冲突与谈判传导类
  - `ceasefire`
  - `negotiation`
  - `sanction`
  - `disruption`
- 中文等价词
  - `营收`
  - `利润`
  - `净利`
  - `亏损`
  - `指引`
  - `财报`
  - `资本开支`
  - `订单`
  - `油价`
  - `航运`
  - `风险资产`
  - `通胀`
  - `谈判`
  - `停火`

要求：

- `high_fit` 判断不只看 title，还要允许看更短、更干净的 signal text
- 但不能再像第一轮那样把否定句里的 `market` 一词误当成正向信号

### 2. Expand low-yield filtering for political/newsy medium-fit topics

第一轮只压掉了最直接的 `official commentary`。

第二轮增加一层更强的 `live_snapshot` 低收益过滤，覆盖：

- 泛政治观察
- 外交礼仪和访问盘点
- 官方立场复述
- `国际观察` 风格但没有市场/产业/company read-through 的题

约束：

- 仍然只在 `live_snapshot` 生效
- 不影响 `default`
- 不影响 `international_first`

### 3. Add a medium-fit retention gate

第二轮不直接重写整个排序，但增加一个保留门槛：

- `high_fit` 默认优先保留
- `medium_fit` 只保留少量上限
- `low_fit` 默认不进最终榜单

建议第一版 gate：

- 排序后保留全部 `high_fit`
- `medium_fit` 最多只保留前 `2`
- `low_fit` 直接过滤

如果 `high_fit` 数量不足，再用前 `2` 个 `medium_fit` 填充

这样做的目标是：

- 让榜单前排更像“写稿候选”
- 不让 `medium_fit` 把榜单填满

### 4. Add source timing diagnostics

第二轮新增 source timing 输出，但不改并发模型。

新增结果字段：

- `source_timings`
- `total_runtime_ms`

其中：

- `source_timings` 是一个列表，每个元素至少包含：
  - `source`
  - `duration_ms`
  - `item_count`
  - `status`
- `total_runtime_ms` 是整个 run 的 wall-clock 时间

用途：

- 让 operator 直接看到哪个 source 慢
- 为后续第三轮时延优化提供证据

## Runtime Integration

### `build_clustered_candidate()`

需要改：

- `live_snapshot_fit` 的判断逻辑
- `live_snapshot_reason` 的文案逻辑

要求：

- 明确把财务/市场/冲突传导类题拉到 `high_fit`
- 同时不再让“泛政治观察”轻易保留在 `medium_fit`

### `apply_topic_controls()`

新增：

- 第二轮的 low-yield political/newsy filter

要求：

- 仍然只在 `live_snapshot` 下生效

### `run_hot_topic_discovery()`

新增：

- source-level timing 记录
- total runtime 记录
- final fit-gated retention for `live_snapshot`

要求：

- 先做 timing 记录，再做结果层 gating
- 不改变其它 profile 的输出结构

## Output Changes

### New result fields

在完整 result 顶层新增：

- `source_timings`
- `total_runtime_ms`

### Updated `live_snapshot_reason`

第一轮的 `medium_fit` 文案太统一，几乎全是：

- `Fresh headline in the 0-6h window, but it still needs a clearer second-order read-through.`

第二轮要更具体，至少区分：

- 财务/市场/冲突传导型 `high_fit`
- 泛观察型 `medium_fit`
- 低收益快讯型 `low_fit`

## Testing

第二轮至少补这些测试：

1. 财务/市场 read-through 题命中 `high_fit`
2. 泛政治观察题在 `live_snapshot` 下被过滤
3. `medium_fit` 保留上限生效
4. `live_snapshot` 结果里包含 `source_timings` 和 `total_runtime_ms`
5. `international_first` 不受影响

## Non-Goals

第二轮明确不做：

- 改 `live_snapshot` source pack
- 接入 `agent-reach:reddit/x`
- 改文章生成
- 改发布链
- 做 source scheduler 重构

## Acceptance Criteria

只有满足以下条件，第二轮才算完成：

1. `high_fit` 不再长期为零。
2. 泛政治/泛观察类题不会继续稳定混在榜单前排。
3. `medium_fit` 不再占满整个榜单。
4. `source_timings` 和 `total_runtime_ms` 能直接落到结果里。
5. 全量 `test_article_publish.py` 回归仍然通过。
