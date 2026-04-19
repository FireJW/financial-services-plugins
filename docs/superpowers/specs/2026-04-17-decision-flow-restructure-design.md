# Decision Flow Restructure Design

Date: `2026-04-17`
Repo: `D:\Users\rickylu\dev\financial-services-plugins-clean`
Branch: `main`

## 1. Goal

Replace three separate report sections (Decision Factors + Event Board + Chain Map)
with a single `## 决策流` section. Each ticker gets one self-contained decision
card. Event Cards section stays as-is for detailed evidence archival.

## 2. Approach: Gradual Merge (方案 C)

- **Markdown:** New `## 决策流` replaces the three old sections in report output.
- **JSON:** Old keys (`decision_factors`, `event_cards`, `chain_map_entries`) stay
  in the result dict for downstream compatibility. New key `decision_flow` added.
- Event Cards section in markdown stays unchanged (detailed evidence layer).

## 3. Decision Card Format

Each ticker = one card. Card internal order:

1. Title line: `### {ticker} | {action} | {score}分 | {chain_role}`
2. **结论** — concise, 1-2 sentences max. Why this action, what's the gap.
3. **盘中观察点** — three dimensions (技术 / 事件 / 链条)
4. **触发条件** — ↑ upgrade / ↓ downgrade / ⚡ event risk
5. **操作提醒** — concrete next action from 用法 + next_watch_items

### 3.1 结论 rules

- Short: "{判断核心}。评分 {score}，执行门槛 {keep_threshold}，差距 {gap}。"
- Do NOT explain what keep line means (user already knows after first read).
- Merge `trading_profile_judgment` first half + `logic_summary`.

### 3.2 盘中观察点 rules

- **技术:** If trend template all-pass → one line "趋势模板全部通过". Only expand
  items that FAILED. Always include RSI zone label (超买/中性偏强/中性/偏弱/超卖)
  and RS90 relative strength with brief interpretation.
- **事件:** Full event data from `key_evidence` list. Append community/market
  reaction: `社区一致性: {conviction}`, `量价验证: {validation_label}`.
- **链条:** Chain name, role, chain playbook sentence.

### 3.3 触发条件 rules

Template-generated from structured data:

- **↑ upgrade:** Based on `gap` → "评分从 {score} 修复至 {keep_threshold}+"
  with specific drivers (量能/RS/事件催化).
- **↓ downgrade:** Based on `hard_filter_failures` potential → specific trend
  template items that could fail. If currently all-pass, cite the most fragile
  (e.g., price vs MA50).
- **⚡ event risk:** Pull from `key_evidence` to build concrete thresholds.
  E.g., "实际净利润低于预告下限 160,000 万元". If no event data, omit this line.

Reserve a `trigger_overrides` field in JSON for future LLM-generated triggers.

### 3.4 操作提醒 rules

- Merge `trading_profile_usage` + `next_watch_items`.
- One actionable paragraph, not bullet points.

## 4. Card ordering

Cards sorted by: qualified first, then near_miss by score desc, then blocked.

## 5. JSON structure

```json
{
  "decision_flow": [
    {
      "ticker": "002460.SZ",
      "name": "002460.SZ",
      "action": "继续观察",
      "score": 60.0,
      "keep_threshold": 70.0,
      "gap": -10.0,
      "chain_role": "高弹性",
      "chain_name": "unknown",
      "conclusion": "...",
      "watch_points": {
        "technical": "...",
        "event": "...",
        "chain": "..."
      },
      "triggers": {
        "upgrade": "...",
        "downgrade": "...",
        "event_risk": "..."
      },
      "trigger_overrides": null,
      "operation_reminder": "...",
      "status": "near_miss"
    }
  ],
  "decision_factors": { ... },
  "event_cards": [ ... ],
  "chain_map_entries": [ ... ]
}
```

## 6. Markdown sections after restructure

Old order → New order:

| Before | After |
|--------|-------|
| Dropped Candidates | Dropped Candidates (unchanged) |
| Diagnostic Scorecard | Diagnostic Scorecard (unchanged) |
| Near Miss Candidates | Near Miss Candidates (unchanged) |
| 午盘操作建议摘要 | 午盘操作建议摘要 (unchanged) |
| Decision Factors | **REMOVED from markdown** |
| 直接可执行 / 重点观察 / 链条跟踪 | (unchanged) |
| Event Board | **REPLACED by `## 决策流`** |
| Chain Map | **REMOVED from markdown** |
| Event Cards | Event Cards (unchanged, evidence layer) |

## 7. Files to change

- `month_end_shortlist_runtime.py` — add `build_decision_flow_cards()`,
  `build_decision_flow_markdown()`, modify `enrich_live_result_reporting()`
- `earnings_momentum_discovery.py` — no changes expected
- `tests/test_month_end_shortlist_shim.py` — add decision flow assertions

## 8. Implementation slices

### Slice 1: Build decision flow data structure
- New function `build_decision_flow_card()` — one card from candidate + event data
- New function `build_decision_flow()` — orchestrate all cards
- Add `decision_flow` key to enriched result
- Unit tests for card generation

### Slice 2: Build decision flow markdown
- New function `build_decision_flow_markdown()` — render cards to markdown
- Replace Decision Factors + Event Board + Chain Map sections in report
- BOM encoding tests

### Slice 3: Trigger condition templates
- New function `build_upgrade_trigger()` — from gap + score data
- New function `build_downgrade_trigger()` — from trend template data
- New function `build_event_risk_trigger()` — from key_evidence data
- Unit tests for each trigger type

## 9. Not in scope

- Changing Event Cards section format
- Changing Diagnostic Scorecard or 午盘操作建议摘要
- Removing old JSON keys (future cleanup)
- LLM-generated trigger content (reserved interface only)
