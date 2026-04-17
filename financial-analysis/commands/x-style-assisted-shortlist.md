---
description: Run `month_end_shortlist` with advisory X-style overlays learned from one or more watched X accounts
argument-hint: "[base-request-json]"
---

# X-Style Assisted Shortlist

Use this command when the goal is not just to run a normal `月底短线` shortlist,
but to let previously learned X-user stock-picking styles act as a bounded
ranking layer.

Good fits:

- "用老法师和 tuolaji 的风格一起辅助这轮 shortlist"
- "把 x-stock-picker-style 的 batch 结果喂给月底短线筛选"
- "先保留硬过滤，再看 X 风格会把哪些票往上抬"
- "把 aleabitoreddit / jukan05 这种跨市场作者的链条逻辑映射成 A 股 shortlist overlay"

What it does:

1. starts from a normal `month_end_shortlist` base request
2. injects `x_style_batch_result_path`
3. optionally keeps only selected handles via `x_style_selected_handles`
4. runs the normal shortlist workflow
5. keeps X-derived influence bounded to:
   - `named_pick_hints`
   - `advisory_basket_hints`
   - `theme_biases`
6. preserves hard filters as the final authority

Native helpers:

- `financial-analysis\skills\month-end-shortlist\scripts\run_x_style_assisted_shortlist.cmd`
- `financial-analysis\skills\month-end-shortlist\examples\month-end-shortlist-x-style-assisted.template.json`
- `financial-analysis\skills\month-end-shortlist\examples\month-end-shortlist-cross-market-x-style-assisted.template.json`

Typical usage:

- build a request only:
  - `financial-analysis\skills\month-end-shortlist\scripts\run_x_style_assisted_shortlist.cmd "<base-request.json>" --x-style-batch-result "<batch-result.json>" --handles twikejin tuolaji2024 --request-output "<resolved-request.json>" --request-output-only`
- run directly:
  - `financial-analysis\skills\month-end-shortlist\scripts\run_x_style_assisted_shortlist.cmd "<base-request.json>" --x-style-batch-result "<batch-result.json>" --handles twikejin tuolaji2024 --output "<result.json>" --markdown-output "<report.md>"`

Cross-market mapping usage:

- first build the cross-market style batch:
  - `financial-analysis\skills\x-stock-picker-style\scripts\run_x_stock_picker_style.cmd "financial-analysis\skills\x-stock-picker-style\examples\x-stock-picker-style-cross-market-batch.template.json" --output "<cross-market-batch.json>" --markdown-output "<cross-market-batch.md>"`
- then feed it into shortlist:
  - `financial-analysis\skills\month-end-shortlist\scripts\run_x_style_assisted_shortlist.cmd "financial-analysis\skills\month-end-shortlist\examples\month-end-shortlist-cross-market-x-style-assisted.template.json" --x-style-batch-result "<cross-market-batch.json>" --handles aleabitoreddit jukan05 --output "<result.json>" --markdown-output "<report.md>"`

Recommended reading:

- `docs/runtime/x-style-assisted-shortlist-playbook.md`
- `financial-analysis/commands/month-end-shortlist.md`
- `financial-analysis/commands/x-stock-picker-style.md`
