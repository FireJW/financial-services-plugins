# Live Snapshot Hardening Round 2 Design

## Goal

在现有 `discovery_profile=live_snapshot` 基础上做第二轮硬化，解决上一轮真实运行里暴露出来的 3 个问题：

1. `high_fit` 题太少，真实值得写的公司/市场 read-through 题仍然停在 `medium_fit`
2. 泛政治/泛观察类题仍然能混进榜单
3. source 级耗时不可见，导致 live snapshot 虽然能跑，但排查慢源和压时延都不够直接

## Scope

这轮只改：

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`
- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

不改：

- `hot_topic_discovery.py`
- `default`
- `international_first`
- 文章生成和发布链

## Design Principles

### 1. 继续保持 `live_snapshot` 显式 opt-in

这轮只是继续收紧 `live_snapshot`，不是把它接成默认流。

### 2. 优先提高题目质量，再追求更多覆盖

如果 `live_snapshot` 能稳定给出更少但更可写的候选，它就是向前走了。

这轮不追求抓到更多题，追求的是：

- 前排出现更像“可立刻写分析稿”的题
- 泛观察/泛时政/低延展题继续往下掉

### 3. source timing 只做诊断，不做复杂调度

第一阶段先让 operator 看到：

- 哪个 source 慢
- 哪个 source 失败
- 总共花了多久

这轮不做复杂 source 调度器，也不做动态超时回路。

## Problems Observed In The First Live Snapshot Run

### Problem A: all top candidates stayed `medium_fit`

上一轮真实运行里，前排候选全是 `medium_fit`。

这说明：

- 现有 `high_fit` 关键词不够覆盖真实的公司/市场 read-through
- 现在更像“只要有明显市场词就 high_fit，否则一律 medium_fit”

这会压不出真正值得写的公司题，也会放过很多只是“新 headline”的题。

### Problem B: generic political / observation headlines still leak in

像下面这类题仍然能进榜：

- 多国政要密集访华背后...
- 台湾业界代表呼吁当局...
- 国际观察丨美伊谈判悬念丛生...

这说明现在的 `live_snapshot` low-yield 过滤还太窄，更多只是压掉“官方口径模板”，但没有继续压掉：

- 泛时政观察
- 泛外交观察
- 没有价格/产业/公司传导的政治解读

### Problem C: source latency is opaque

上一轮 live snapshot 虽然最终跑完了，但耗时接近 4 分钟。

问题不是“完全跑不通”，而是：

- 不知道每个 source 花了多久
- 不知道哪个 source 拖慢了整轮

没有 timing，就没法继续做更轻的 runtime hardening。

## Round 2 Changes

### 1. Expand `high_fit` triggers for real writeable topics

这轮把 `high_fit` 从“有一些市场词”扩成“有更明确的 read-through 信号”。

新增倾向关键词：

- 公司/财务：
  - `revenue`
  - `profit`
  - `margin`
  - `loss`
  - `sales`
  - `guidance`
  - `earnings`
  - `capex`
  - `order`
  - `orders`
  - `营收`
  - `利润`
  - `净利`
  - `亏损`
  - `指引`
  - `财报`
  - `资本开支`
  - `订单`

- 市场/资产：
  - `oil`
  - `equities`
  - `stocks`
  - `bond`
  - `yield`
  - `volatility`
  - `risk asset`
  - `risk assets`
  - `油价`
  - `股市`
  - `收益率`
  - `波动率`
  - `风险资产`

- 冲突/政策传导：
  - `ceasefire`
  - `strait`
  - `shipping`
  - `sanction`
  - `tariff`
  - `negotiation`
  - `rollout`
  - `supply chain`
  - `停火`
  - `海峡`
  - `航运`
  - `制裁`
  - `关税`
  - `谈判`
  - `供应链`

目标：

- “字节 AI 投入压利润”这类题应该进入 `high_fit`
- “霍尔木兹风险 -> 油价/股市”这类题也应该进入 `high_fit`

### 2. Tighten `medium_fit` so it is not the default bucket for everything

当前 `medium_fit` 太宽，结果就是几乎所有新题都变成 `medium_fit`。

这轮把逻辑改成：

- `high_fit`: 有明确 read-through
- `medium_fit`: 新题，但仍有一定分析延展
- `low_fit`: 新题，但本质更像快讯、观察稿或泛消息

也就是说，`medium_fit` 不能再是“只要是 0-24h 就给”。

### 3. Expand low-yield filtering for political/newsy headlines

新增低价值模式识别，压掉：

- 泛政治观察
- 泛外交观察
- 泛台海/国际关系 commentary
- 没有市场、公司、供给链第二层传导的政治 headline

这轮不是全量禁政治题。

仍然保留：

- 冲突或谈判已经传导到油价、航运、股市、风险资产的题

过滤原则：

- 政治可以保留
- 但必须已经进入市场或产业 read-through

### 4. Add source timing diagnostics to the result

在 `run_hot_topic_discovery()` 里新增 source timing 记录。

输出字段：

- `source_timings`

每个 source 至少记录：

- `source`
- `duration_ms`
- `status`

其中：

- `status = ok` 表示正常返回
- `status = error` 表示异常

这个字段只做诊断，不影响 ranking。

### 5. Add lightweight timing summary to markdown report

如果 `source_timings` 有值，就在 report 里追加一节：

- `## Source Timings`

格式只需要可读，不需要复杂表格。

目标是让 operator 一眼看到：

- 哪个 source 最慢
- 哪个 source 出错

## Acceptance Criteria

这轮完成后，应满足：

1. `live_snapshot` 前排至少能出现更明确的 `high_fit` 题，而不是整榜 `medium_fit`
2. 泛政治/泛观察类题进一步减少
3. `live_snapshot` 结果里新增 `source_timings`
4. markdown report 能看到 source timing 诊断
5. 现有 `test_article_publish.py` 全量回归继续通过

## Testing

这轮新增测试优先覆盖：

1. 公司/财务 read-through 题从 `medium_fit` 升到 `high_fit`
2. 泛政治观察题被打到 `low_fit` 或直接过滤
3. 冲突-市场 read-through 题继续保留为 `high_fit`
4. `run_hot_topic_discovery()` 结果包含 `source_timings`
5. markdown report 包含 `Source Timings`

## Non-Goals

这轮不做：

- 动态 source 调度
- source blacklist / retry policy
- 把 `agent-reach:reddit/x` 并回 `live_snapshot`
- 任何文章生成链改动
