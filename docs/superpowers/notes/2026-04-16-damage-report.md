# 损坏清单与处理建议

日期：`2026-04-16`

## 范围

本清单只覆盖当前 `financial-services-*` 这条仓库线中，本轮实际发现并核实过的损坏项。

## A. Git 元数据损坏

### 仓库

- `D:\Users\rickylu\dev\financial-services-plugins`

### 现象

- `.git/objects/pack/*.idx` 非单调
- loose object 损坏
- `git status` / `git log` 不可靠

### 处理建议

- 该仓库视为**只读损坏仓库**
- 不在其上继续开发/提交
- 后续以健康仓库 `D:\Users\rickylu\dev\financial-services-plugins-clean` 为主线

---

## B. 源码缺失，仅剩 `.pyc`

### 路径

- `financial-analysis/skills/short-horizon-shortlist/scripts/__pycache__/month_end_shortlist.pyc`
- `financial-analysis/skills/short-horizon-shortlist/scripts/__pycache__/month_end_shortlist_runtime.pyc`

### 影响

- 真实核心 runtime 源码缺失
- 只能通过 wrapper / shim 恢复执行链

### 处理建议

- 不尝试修补 `.pyc`
- 继续以已恢复的 `month-end-shortlist` wrapper 源文件承接行为

---

## C. 测试文件污染/不可恢复

### 1. `test_month_end_shortlist_runtime.py`

路径：

- `D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_runtime.py`
- 备份：`D:\Users\rickylu\repo-safety-backups\financial-services-plugins\latest\tests\test_month_end_shortlist_runtime.py`

现象：

- 文件包含 `NUL` 字节
- 备份版本也同样包含 `NUL`
- 不是可安全恢复的文本 Python 文件

建议：

- 不恢复原文件
- 用新的 focused wrapper regression 测试覆盖相关行为

### 2. `test_month_end_shortlist_runtime_1.py`

路径：

- `D:\Users\rickylu\dev\financial-services-stock\tests\test_month_end_shortlist_runtime_1.py`
- 备份：`D:\Users\rickylu\repo-safety-backups\financial-services-plugins\latest\tests\test_month_end_shortlist_runtime_1.py`

现象：

- 文件头为异常拼接文本：`.426Z warning [git-origin-and-ro...`
- 虽然无 `NUL`，但不是可信的正常 Python 源
- 备份版本也同样异常

建议：

- 不恢复原文件
- 如需补 coverage，单独新建 focused tests

### 3. `test_tradingagents_pilot_matrix.py`

路径：

- `D:\Users\rickylu\dev\financial-services-stock\tests\test_tradingagents_pilot_matrix.py`
- 备份：`D:\Users\rickylu\repo-safety-backups\financial-services-plugins\latest\tests\test_tradingagents_pilot_matrix.py`

现象：

- 文件包含 `NUL` 字节
- 备份版本同样损坏

建议：

- 不恢复原文件
- 未来若要恢复该功能测试，重建新测试，不拼接旧损坏内容

---

## D. 已修复或已替代的项目

### 已重建

- `test_macro_health_assisted_shortlist.py`
- `test_x_style_assisted_shortlist.py`
- `test_month_end_shortlist_shim.py`
- `test_month_end_shortlist_benchmark_fallback.py`
- `test_month_end_shortlist_candidate_fetch_fallback.py`
- `test_month_end_shortlist_candidate_snapshot_enrichment.py`
- `test_month_end_shortlist_degraded_reporting.py`
- `test_tradingagents_package_support.py`

### 当前 focused regression 状态

- `23 passed`

这些新测试已经覆盖了本轮实际修复和恢复出的关键行为。

---

## E. 最安全的处理原则

1. 不直接修改损坏的旧测试文件内容去“猜修”
2. 不删除这些文件，除非你明确要求清理
3. 把它们当作历史损坏 artifact 记录
4. 真实行为覆盖通过新的 focused tests 继续补

当前隔离位置：

- `D:\Users\rickylu\dev\financial-services-stock\tests\quarantine-corrupted\`

---

## 当前建议

短期内：

- 维持损坏旧测试文件原样不动
- 继续使用新 focused regression 测试作为真实验证面

后续如果你要彻底收尾，可以再做一轮：

1. 把损坏旧测试统一移入 `recovered-artifacts/` 或单独 `quarantine/`
2. 在主测试目录只保留可执行、可维护的新测试

这一步涉及文件搬迁，建议等你明确确认后再做。
