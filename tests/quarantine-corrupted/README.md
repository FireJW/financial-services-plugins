# Corrupted Test Quarantine

这些文件已确认损坏，因此从主测试目录隔离出来，避免被 `pytest` 正常收集时误触发。

当前隔离对象：

- `test_month_end_shortlist_runtime.py`
- `test_month_end_shortlist_runtime_1.py`
- `test_tradingagents_pilot_matrix.py`

处理原则：

- 原文件不做“猜修”
- 原内容原样保留，仅平移到隔离目录
- 真实行为覆盖通过新的 focused regression 测试承担

相关说明见：

- `docs/superpowers/notes/2026-04-16-damage-report.md`
