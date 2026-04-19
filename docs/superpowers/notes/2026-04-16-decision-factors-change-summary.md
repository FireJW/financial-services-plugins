# Decision Factors 变更说明

日期：`2026-04-16`

## 本轮完成内容

这轮开发已经把 shortlist 的复盘/执行输出，从“只有结果”推进到了“有动作、有原因、有证据”的层级。

### 1. 输出链闭环

当前摘要链已经统一支持三种动作：

- `blocked -> 不执行`
- `near_miss/watch -> 继续观察`
- `qualified -> 可执行`

### 2. 新增输出层

当前结果/报告包含以下层次：

1. `午盘/盘后操作建议摘要`
2. `Decision Factors`
3. `Dropped Candidates`
4. `Diagnostic Scorecard`
5. `Near Miss Candidates`

### 3. Decision Factors 现在包含什么

对于 `qualified` / `near_miss` / `blocked`，当前 wrapper 层会尽量从已有 shortlist 结果中抽取并整理：

- 动作
- 分数
- 与 keep line 差距
- 技术形态说明
- 关键事件/催化
- 判断逻辑
- 观察点

### 4. wrapper 层增强

本轮保持了“只改 wrapper/postprocessing，不碰 compiled shortlist 内核”的边界。

关键增强包括：

- benchmark fetch 失败不再直接打断整轮 run
- 单个候选 bars fetch 失败不再打断整轮 run
- `candidate_tickers` 会被升级为 richer `universe_candidates`
- no-picks 场景会保留 `Diagnostic Scorecard`
- no-picks 场景会生成 `Near Miss Candidates`
- 历史成功样本会生成 `可执行`
- 新增 `Decision Factors` 解释层

## 当前已验证样本

### A. 实时两票复核样本

产物：

- `D:\Users\rickylu\dev\financial-services-stock\.tmp\month-end-shortlist-two-tickers-live\result.json`
- `D:\Users\rickylu\dev\financial-services-stock\.tmp\month-end-shortlist-two-tickers-live\report.md`

当前结论：

- `601600.SS` -> `不执行`
- `002837.SZ` -> `继续观察`

### B. 历史成功样本闭环

产物：

- `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\result.json`
- `D:\Users\rickylu\dev\financial-services-stock\.tmp\qualified-summary-check\report.md`

当前结论：

- `001309.SZ 德明利` -> `可执行`
- `002460.SZ 赣锋锂业` -> `可执行`
- `002709.SZ 天赐材料` -> `可执行`

## 测试状态

当前 shortlist wrapper 聚焦回归：

- `19 passed`

## 已同步的 X 用户清单

当前三个仓库的 subject registry 已同步：

- `twikejin`
- `tuolaji2024`
- `aleabitoreddit`
- `jukan05`
- `Ariston_Macro`

并且：

- `mack8858` 已移除

## 目前仍然不是这轮范围的内容

本轮没有改动：

- compiled shortlist 核心评分逻辑
- GS quant 缺桥问题
- TradingAgents 环境缺包问题
- 更深层的正式 registry/配置系统

## 推荐后续使用方式

1. 先看 `午盘/盘后操作建议摘要`
2. 再看 `Decision Factors`
3. 最后看 `Diagnostic Scorecard` / `Dropped Candidates` 做底层排查

---

这份说明是当前状态快照，不是需求文档。
