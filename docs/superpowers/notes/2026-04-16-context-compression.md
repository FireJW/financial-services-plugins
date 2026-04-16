# 2026-04-16 上下文压缩

日期：`2026-04-16`

## 当前仓库关系

- `D:\Users\rickylu\dev\financial-services-stock`
  - 快照/导出目录
  - 不是可直接提交的 git 仓库
- `D:\Users\rickylu\dev\financial-services-plugins`
  - canonical 仓库，但 `.git` 已损坏
  - 只读看待，不再作为提交目标
- `D:\Users\rickylu\dev\financial-services-plugins-clean`
  - 当前健康 git 仓库
  - 当前所有可提交工作统一同步到这里

## 已完成主线

1. shortlist wrapper 已恢复并增强：
   - `month_end_shortlist.py`
   - `month_end_shortlist_runtime.py`
   - `x_style_assisted_shortlist.py`
   - `macro_health_assisted_shortlist.py`
2. 决策摘要链已闭环：
   - `blocked -> 不执行`
   - `near_miss/watch -> 继续观察`
   - `qualified -> 可执行`
3. `Decision Factors` 已补成解释层：
   - 技术形态
   - 关键事件
   - 下一步推演
   - 判断逻辑
   - 交易层
   - 观察点
4. `top_picks` 报告层上限已扩到 `10`
5. X 用户清单已同步：
   - 保留：`twikejin` `tuolaji2024` `aleabitoreddit` `jukan05` `Ariston_Macro`
   - 移除：`mack8858`

## 已确认损坏项

- `financial-services-plugins`
  - git objects / pack 损坏
- 历史测试文件损坏：
  - `test_month_end_shortlist_runtime.py`
  - `test_month_end_shortlist_runtime_1.py`
  - `test_tradingagents_pilot_matrix.py`

处理原则：

1. 不猜修损坏内容
2. 不在坏仓库上继续开发
3. 用 focused regression 覆盖真实行为
4. 把损坏测试从主验证路径中隔离

## 当前 durable 文档

- `2026-04-16-decision-factors-change-summary.md`
- `2026-04-16-damage-report.md`
- `2026-04-16-repo-target-clarification.md`
- `2026-04-16-postclose-review-all.md`

## 当前验证面

- focused shortlist wrapper regression：`23 passed`

## 当前运行样本

### 两票 live 午盘/盘后诊断

- `601600.SS` -> `不执行`
- `002837.SZ` -> `继续观察`

### 三票完整交易计划盘后复盘

- `001309.SZ` -> `不执行`
- `002460.SZ` -> `继续观察`
- `002709.SZ` -> `继续观察`

## 下一步主线

1. 把本轮 `quarantine-corrupted` 与损坏说明同步进 clean repo 并提交
2. 保留正式盘后复盘稿，作为后续 daily review 模板实例
3. 在健康 worktree 上继续跑 `2026-04-17` 交易计划
4. 优先走 repo 自带 `month-end-shortlist` / assisted-shortlist 命令，不临时拼流程
