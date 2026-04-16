# 仓库目标说明

日期：`2026-04-16`

## 结论

这轮开发和提交的正确目标仓库是：

- `https://github.com/FireJW/financial-services-plugins.git`

不应该推送到：

- `https://github.com/FireJW/stock-kit`

## 原因

本轮改动涉及的文件路径和模块都属于 `financial-services-*` 体系，而不是 `stock-kit`：

- `financial-analysis/skills/month-end-shortlist/...`
- `financial-analysis/skills/x-stock-picker-style/...`
- `financial-analysis/skills/tradingagents-decision-bridge/...`
- `tests/test_month_end_shortlist_*`
- `docs/superpowers/...`

这些文件结构、命名和测试都和 `financial-services-plugins` 仓库线一致。

## 本地仓库状态

### 1. `financial-services-stock`

当前目录：

- `D:\Users\rickylu\dev\financial-services-stock`

这是一个快照/导出目录，不是可直接提交的 git 仓库。

### 2. `financial-services-plugins`

当前目录：

- `D:\Users\rickylu\dev\financial-services-plugins`

这是 canonical 源仓库，但当前 `.git` 已损坏，出现：

- pack index 异常
- loose object 损坏
- `git status` / `git log` 不稳定

因此不适合作为安全提交目标。

### 3. `financial-services-plugins-clean`

当前目录：

- `D:\Users\rickylu\dev\financial-services-plugins-clean`

这是当前可正常提交和推送的健康 git 仓库，并且 remote 指向：

- `https://github.com/FireJW/financial-services-plugins.git`

因此本轮最终是把变更同步到 `financial-services-plugins-clean` 后完成 commit/push。

## 本轮实际提交

提交仓库：

- `D:\Users\rickylu\dev\financial-services-plugins-clean`

提交号：

- `0fd40a9`

推送目标：

- `origin/main`
- `https://github.com/FireJW/financial-services-plugins.git`

## 后续建议

后续如果继续在 `financial-services-stock` 这类快照目录工作：

1. 先确认 canonical git 仓库
2. 先确认该 canonical 仓库是否健康
3. 再决定是否需要同步到 clean repo 后提交

不要把 `financial-services-*` 这条线的改动误推到 `stock-kit`。
