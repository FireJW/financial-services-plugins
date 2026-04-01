---
title: Prioritize agent runtime hardening around verification, contracts, and memory discipline
date: 2026-03-31
category: best-practices
module: agent-runtime-adoption
problem_type: best_practice
component: tooling
symptoms:
  - Capability ideas were scattered across image notes and conversation analysis without a durable priority order
  - Higher-complexity memory, security, and batch ideas risked outrunning basic correctness guardrails
  - Future runtime optimization work lacked a shared rubric for deciding what to deploy first
root_cause: inadequate_documentation
resolution_type: documentation_update
severity: medium
tags: [agent-runtime, verification-specialist, worker-contract, session-memory, compaction]
---

# Prioritize agent runtime hardening around verification, contracts, and memory discipline

## Problem
我们已经识别出一批值得借鉴的 Claude Code 风格能力，但如果不先给这些能力排优先级，后续很容易先做“更炫的自动化”，却把最重要的可靠性约束落下。对我们这种金融研究型仓库来说，这会直接放大结论漂移、上下文跑偏和多 agent 输出不一致的风险。

## Symptoms
- 关于能力建设的结论主要停留在聊天分析和图片摘录里，缺少可持续引用的文档。
- `Dream Memory`、`Batch Orchestrator`、`Security Monitor` 这类复杂能力很容易先吸引注意力，但并不能优先解决正确性问题。
- 当前仓库已经有稳定的 headless runtime 和插件兼容性测试台，但还没有一层“worker 输出合同 + verifier 复核 + session state 模板”的工程化约束。

## What Didn't Work
- 把图片里出现的所有能力都视为同等优先级来讨论，这会模糊“先保真，再扩张”的顺序。
- 直接从“完整记忆系统”或“复杂并行编排”开始想，会绕开我们最现实的痛点：如何确保多 agent 输出不失真。
- 继续停留在 runtime 源码考古层面，而不把结论落成仓库内的操作文档和计划，无法支持后续持续迭代。

## Solution
先把能力分成四档，只优先部署对“可靠性”和“意图保真”最直接的能力。

### 推荐排序

| 优先级 | 能力 | 为什么先做 |
|---|---|---|
| P0 | `Verification Specialist` 独立验证代理 | 金融研究输出最怕“像对的”，验证闭环比更复杂的记忆和编排更值钱 |
| P0 | `Worker Fork` 防跑偏 + 结构化输出合同 | 多 agent 一多，最先出问题的是输出漂移；先用结构约束把结果收住 |
| P1 | `NOW.md / Session Memory` 固定段落 + token 预算 | 长任务里最容易散的是状态，不是能力；固定结构先解决上下文失焦 |
| P1 | `Compaction` 保留原始用户指令清单 | 压缩后最常见的问题是“意图变形”，所以要单独保留用户原始要求 |
| P1 | `Explore agent` 用便宜模型 | 搜索、盘点、找文件这类低风险任务可以先省钱，不影响主结论质量 |
| P2 | `Dream Memory` 4 阶段轻量版 | 值得学，但应建立在前面的验证和状态管理已经稳住之后 |
| P2 | `Memory File` 动态路由 | 很适合研究型长流程，但前提是你已经有稳定的 memory index 和裁剪规则 |
| P2 | `Security Monitor` 规则化守卫 | 我们强调文件安全，这方向重要，但先做轻量 gate 就够 |
| P3 | `Batch Orchestrator` 大规模并行编排 | 放大效率的同时也放大漂移和状态管理复杂度，不该先上 |
| P3 | `Index` 严格裁剪和 pruning | 是好优化，但不是当前收益最高的第一批工作 |

### 先部署的最小组合

`P0 + P1` 的推荐最小组合是：

1. `Verification Specialist`
2. `Worker Fork` 结构化输出合同
3. `NOW.md` 固定结构与段落预算
4. `Compaction` 保留原始用户意图
5. `Explore` 低成本任务路由

### 建议采用的输出合同

先不要追求复杂 JSON 协议，先用可读、可验证的结构化 Markdown 合同，把 worker 产出固定到下面这组段落：

```md
## Conclusion
- 一句话结论

## Confirmed
- 已确认事实

## Unconfirmed
- 未确认项

## Risks
- 风险、反例、失效条件

## Next Step
- 建议下一步
```

这比“让 agent 更聪明”更快产生价值，因为它直接限制了输出漂移。

### 建议采用的会话状态模板

`NOW.md` 先做固定段落模板，不急着做完整记忆系统：

```md
# NOW

## Goal
## Current State
## Confirmed Facts
## Unresolved Questions
## Next Step
## Risks / Invalidation
```

每段再配一个 token 预算，优先压缩内容，不改结构。

## Why This Works
这些排序的核心逻辑是：先保证“多 agent 输出仍可信”，再去追求“更大的自动化规模”。

- `Verification Specialist` 先解决结果真假问题。
- `Worker Fork` 输出合同先解决结果形状问题。
- `NOW.md` 和 compaction 保真先解决长上下文漂移问题。
- `Explore` 便宜模型最后才去解决成本问题。

如果先上 `Dream Memory`、`Batch Orchestrator` 或复杂 `Security Monitor`，只会把一个还没收敛好的系统放大。

## Prevention
- 每次引入新的 runtime 能力前，先问它属于哪一类：
  - `correctness guardrail`
  - `state discipline`
  - `scale feature`
  - `cost optimization`
- 排序规则固定为：
  - `correctness guardrail > state discipline > scale feature > cost optimization`
- 在仓库里保留一份固定的 worker 输出合同和 verifier checklist，不允许不同流程各写一套。
- 压缩摘要时必须单列 `User Intent / Hard Constraints / Non-goals`，不允许只保留“系统总结”。
- 多 agent 扩张前，先有一组回归测试验证：
  - 输出合同是否齐全
  - 用户原始要求是否保留
  - verifier 是否能抓到缺段、越界或未确认项缺失

## Related Issues
- 现有路线图：`docs/plans/2026-03-31-001-feat-financial-research-agent-roadmap-plan.md`
- 落地计划：`docs/plans/2026-03-31-002-feat-agent-runtime-p0-p1-hardening-plan.md`
