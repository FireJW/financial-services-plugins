---
description: DCF 现金流折现估值模型 / DCF Valuation Model for A-Share Companies
---

# DCF 现金流折现估值模型 / DCF Valuation Model

## 概述 / Overview

为 A 股上市公司构建机构级 DCF 估值模型，输出包含敏感性分析的 Excel 工作簿。
Build institutional-quality DCF valuation models for A-share listed companies, producing Excel workbooks with sensitivity analysis.

---

## 使用方法 / How to Use

**触发命令 / Trigger**：用户提到以下关键词时触发：
- `DCF`、`现金流折现`、`内在价值`、`估值模型`
- 示例：`"帮我做一个贵州茅台的DCF模型"` / `"DCF model for 600519"`

**输入要求 / Required Input**：
1. **公司标识 / Company identifier**：股票代码（如 `600519`）或公司名称（如 `贵州茅台`）
2. **增长假设 / Growth assumptions**（可选）：收入增长率，或使用 `"参考一致预期"` / `"use consensus"`
3. **预测期 / Projection period**（可选，默认5年）
4. **情景假设 / Scenario cases**（可选）：悲观/基准/乐观 增长和利润率假设

---

## 数据源 / Data Sources

### A 股专用数据接口 / A-Share Data APIs

**优先级 / Priority Order**：

| 优先级 | 数据源 | 获取方法 | 说明 |
|--------|--------|---------|------|
| 1 | **东方财富 API** | `https://datacenter.eastmoney.com/securities/api/data/v1/get` | 财务报表、估值指标、一致预期 |
| 2 | **同花顺 iFinD** | `https://basic.10jqka.com.cn/api/` | 行业数据、可比公司 |
| 3 | **新浪财经 API** | `https://finance.sina.com.cn/realstock/` | 实时行情、历史K线 |
| 4 | **巨潮资讯网** | `http://www.cninfo.com.cn/new/` | 年报/季报 PDF 原文、公告 |
| 5 | **Web 搜索** | 搜索引擎 | 最新分析师报告、管理层指引 |

### 关键数据点获取 / Key Data Points

**当前行情 / Market Data**：
```
东财实时行情 API:
GET https://push2.eastmoney.com/api/qt/stock/get?secid={市场代码}.{股票代码}&fields=f43,f44,f45,f46,f47,f48,f50,f57,f58,f116,f117

参数说明：
- secid: 0.{代码}=深市, 1.{代码}=沪市
- f43=最新价, f116=市值, f117=流通市值, f50=量比
```

**财务报表 / Financial Statements**：
```
东财财报 API:
GET https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_DMSK_FN_INCOME&columns=ALL&filter=(SECURITY_CODE="{股票代码}")

报表类型 reportName:
- RPT_DMSK_FN_INCOME     → 利润表 / Income Statement
- RPT_DMSK_FN_BALANCE    → 资产负债表 / Balance Sheet
- RPT_DMSK_FN_CASHFLOW   → 现金流量表 / Cash Flow Statement
```

**一致预期 / Consensus Estimates**：
```
东财一致预期 API:
GET https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_PREDICT_REPORT&columns=ALL&filter=(SECURITY_CODE="{股票代码}")
```

---

## DCF 流程 / DCF Process Workflow

### 第一步：数据采集与验证 / Step 1: Data Retrieval & Validation

从上述 API 获取数据，交叉验证：
Fetch data from APIs above, cross-validate:

**验证清单 / Validation Checklist**：
- [ ] 净负债 vs 净现金（关键影响估值）/ Verify net debt vs net cash
- [ ] 稀释后股本（检查近期增发/回购）/ Confirm diluted shares outstanding
- [ ] 历史利润率与业务模式一致 / Validate historical margins
- [ ] 收入增速与行业基准对比 / Cross-check revenue growth with industry
- [ ] 企业所得税率合理性（A股通常15%-25%）/ Tax rate reasonable (A-share: 15%-25%)

> **A 股特殊注意 / A-Share Specifics**：
> - 高新技术企业所得税率 15%（非标准25%）/ HNTE tax rate: 15% (vs standard 25%)
> - 注意非经常性损益影响（扣非后归母净利润）/ Check non-recurring items (deducted net profit)
> - 股权激励费用调整 / Adjust for share-based compensation

### 第二步：历史分析（3-5年）/ Step 2: Historical Analysis (3-5 Years)

分析并记录 / Analyze and document:
- **收入增长趋势 / Revenue growth trends**: 计算 CAGR，识别驱动因素 / Calculate CAGR, identify drivers
- **利润率变化 / Margin progression**: 毛利率、营业利润率、FCF利润率 / Gross, operating, FCF margin
- **资本密度 / Capital intensity**: 折旧摊销和资本开支占收入比 / D&A and CapEx as % of revenue
- **营运资本效率 / Working capital efficiency**: NWC 变动占收入增量比 / NWC changes as % of revenue growth
- **回报指标 / Return metrics**: ROIC、ROE 趋势 / ROIC, ROE trends

```
历史指标摘要 / Historical Metrics (LTM):
营业收入 / Revenue: ¥XX 亿
收入增速 / Revenue growth: X% CAGR
毛利率 / Gross margin: X%
营业利润率 / Operating margin: X%
折旧摊销占收入比 / D&A % of revenue: X%
资本开支占收入比 / CapEx % of revenue: X%
自由现金流利润率 / FCF margin: X%
```

### 第三步：收入预测 / Step 3: Revenue Projections

**三情景法 / Three-Scenario Approach**：

```
悲观 / Bear Case: 保守增长（如 5-8%）
基准 / Base Case: 最可能情景（如 8-12%）
乐观 / Bull Case: 乐观增长（如 12-18%）
```

**增长率框架 / Growth Rate Framework**：
- 第1-2年 / Year 1-2: 较高增长，反映近期确定性 / Higher growth, near-term visibility
- 第3-4年 / Year 3-4: 逐步向行业平均靠拢 / Gradual moderation to industry average
- 第5年+ / Year 5+: 接近永续增长率 / Approaching terminal growth rate

### 第四步：经营费用建模 / Step 4: Operating Expense Modeling

**费用结构 / Cost Structure** (A 股常见分类 / A-Share categories):
- **销售费用 / Selling expenses**: 通常占营收 5-20%，视行业而定
- **管理费用 / G&A expenses**: 通常占营收 3-10%
- **研发费用 / R&D expenses**: 科技公司 8-20%，传统行业 1-3%
- **财务费用 / Financial expenses**: 利息收支净额

> **关键原则 / Key Principle**: 所有费用比例基于**营业收入**，不是毛利润。
> All percentages based on **REVENUE**, not gross profit.

### 第五步：自由现金流计算 / Step 5: Free Cash Flow Calculation

```
EBIT (营业利润 / Operating Profit)
(-) 所得税 / Taxes (EBIT × 税率 / Tax Rate)
= NOPAT (税后净营业利润 / Net Operating Profit After Tax)
(+) 折旧摊销 / D&A (非现金费用, 占收入% / non-cash, % of revenue)
(-) 资本开支 / CapEx (占收入% / % of revenue)
(-) Δ 营运资本 / Δ NWC (营运资本变动 / change in working capital)
= 无杠杆自由现金流 / Unlevered Free Cash Flow
```

### 第六步：加权平均资本成本 (WACC) / Step 6: Cost of Capital

**A 股 CAPM 参数 / A-Share CAPM Parameters**：

```
权益成本 / Cost of Equity = 无风险利率 / Rf + Beta × 股权风险溢价 / ERP

参数 / Parameters:
- 无风险利率 / Risk-Free Rate = 中国10年期国债收益率 / China 10Y Gov Bond Yield (~2.0-2.5%)
- Beta = 相对沪深300的5年月度Beta / 5-year monthly beta vs CSI 300
- 股权风险溢价 / ERP = 6.0-7.5%（A股通常高于美股 / A-share typically higher than US）

债务成本 / Cost of Debt:
- 税后债务成本 / After-Tax = 贷款利率 / Loan Rate × (1 - 税率 / Tax Rate)
- 参考 / Reference: LPR 利率 or 信用债收益率 / credit bond yield

WACC 典型范围 / Typical WACC Ranges:
- 大盘蓝筹 / Large-cap stable: 7-9%
- 成长股 / Growth: 9-12%
- 高成长/高风险 / High growth/risk: 12-16%
```

### 第七步：折现 / Step 7: Discounting (5-10 Year)

**年中惯例 / Mid-Year Convention**：
- 折现期 / Discount Period: 0.5, 1.5, 2.5, 3.5, 4.5
- 折现因子 / Discount Factor = 1 / (1 + WACC)^Period

### 第八步：终值计算 / Step 8: Terminal Value

**永续增长法（首选）/ Perpetuity Growth Method (Preferred)**：
```
终值FCF / Terminal FCF = 最终年FCF / Final Year FCF × (1 + 永续增长率 / Terminal Growth)
终值 / Terminal Value = 终值FCF / (WACC - 永续增长率 / Terminal Growth)

永续增长率选择 / Terminal Growth Rate:
- 保守 / Conservative: 2.0-3.0%（GDP增速 / GDP growth）
- 适中 / Moderate: 3.0-4.0%
- 激进 / Aggressive: 4.0-5.5%（仅限行业龙头 / only market leaders）
```

> **A 股注意 / A-Share Note**: 中国长期 GDP 增速预期高于美国，终值增长率可适当上调。
> China's long-term GDP growth expectations are higher than US, terminal growth can be adjusted upward.

### 第九步：企业价值到股权价值 / Step 9: Enterprise to Equity Value Bridge

```
(+) 预测期FCF现值合计 / Sum of PV of Projected FCFs = ¥X 亿
(+) 终值现值 / PV of Terminal Value = ¥Y 亿
= 企业价值 / Enterprise Value = ¥Z 亿

(-) 净负债 / Net Debt [或 + 净现金 / or + Net Cash] = ¥A 亿
= 股权价值 / Equity Value = ¥B 亿

÷ 稀释后总股本 / Diluted Shares = C 亿股
= 每股内在价值 / Implied Price = ¥XX.XX

当前股价 / Current Price = ¥YY.YY
隐含回报 / Implied Return = (内在价值 / 当前价 - 1) = XX%
```

### 第十步：敏感性分析 / Step 10: Sensitivity Analysis

构建**三张敏感性表格** / Build **three sensitivity tables**:

1. **WACC vs 永续增长率 / WACC vs Terminal Growth** — 5×5 网格
2. **收入增速 vs 营业利润率 / Revenue Growth vs Operating Margin** — 5×5 网格
3. **Beta vs 无风险利率 / Beta vs Risk-Free Rate** — 5×5 网格

每个单元格必须包含完整 DCF 重计算公式，共75个公式。
Each cell must contain full DCF recalculation formula, 75 formulas total.

---

## Excel 模型结构 / Excel Model Structure

### Sheet 架构 / Sheet Architecture

1. **DCF** — 主估值模型 + 底部敏感性分析 / Main model + sensitivity at bottom
2. **WACC** — 资本成本计算 / Cost of capital calculation

### 格式标准 / Formatting Standards

- **蓝色字体 / Blue text** (0,0,255): 所有手动输入值 / All hardcoded inputs
- **黑色字体 / Black text** (0,0,0): 所有公式 / All formulas
- **绿色字体 / Green text** (0,128,0): 跨 Sheet 引用 / Cross-sheet links
- **单位 / Units**: 人民币百万元 / RMB Millions (¥M)
- **百分比 / Percentages**: 一位小数 / 1 decimal (XX.X%)
- **每股 / Per-share**: 两位小数 / 2 decimals (¥XX.XX)

### 文件命名 / File Naming

`[股票代码]_DCF_Model_[日期].xlsx`
例 / Example: `600519_DCF_Model_2026-03-09.xlsx`

---

## 质量检查清单 / Quality Checklist

交付前确认 / Before delivery:

- [ ] 两个 Sheet: DCF（含底部敏感性）、WACC / Two sheets: DCF (with sensitivity), WACC
- [ ] 字体颜色: 蓝=输入, 黑=公式, 绿=跨Sheet / Font colors correct
- [ ] 所有手动输入值有单元格注释 / Cell comments on all inputs
- [ ] 敏感性表格75个公式全部填充 / Sensitivity tables fully populated
- [ ] 边框清晰区分各区块 / Professional borders
- [ ] 税率范围 15-25% / Tax rate 15-25%
- [ ] 终值占企业价值 50-70% / Terminal value 50-70% of EV
- [ ] 永续增长率 < WACC / Terminal growth < WACC
- [ ] 费用基于营收（非毛利润）/ OpEx based on revenue
