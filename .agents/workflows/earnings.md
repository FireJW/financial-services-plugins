---
description: 财报分析报告 / Earnings Analysis Report for A-Share Companies
---

# 财报分析报告 / Earnings Analysis Report

## 概述 / Overview

为 A 股上市公司创建专业财报分析报告（8-12页），分析季报/年报业绩表现，对标市场一致预期，更新估值和投资评级。
Create professional earnings update reports (8-12 pages) for A-share companies analyzing quarterly/annual results, comparing against consensus, and updating valuation and rating.

---

## 使用方法 / How to Use

**触发命令 / Trigger**：用户提到以下关键词时触发：
- `财报分析`、`季报解读`、`年报分析`、`业绩点评`、`Earnings`
- 示例 / Examples:
  - `"分析贵州茅台2025年三季报"` → Q3 2025 earnings update for Moutai
  - `"宁德时代最新财报点评"` → Latest earnings analysis for CATL
  - `"/earnings 比亚迪 2025Q4"` → BYD Q4 2025 earnings update

**不适用 / Do NOT use if**：
- 用户要求的是 "深度研报" / "发起覆盖" → 需要 Initiation Report（更长的格式）
- 公司尚未发布最新财报 → 先确认财报发布日期

---

## 数据源 / Data Sources

### A 股财报数据接口 / A-Share Earnings Data APIs

| 优先级 | 来源 | 获取方法 | 内容 |
|--------|------|---------|------|
| 1 | **巨潮资讯网** | `http://www.cninfo.com.cn/new/disclosure` | 财报公告原文 PDF（最权威）|
| 2 | **东方财富** | `https://datacenter.eastmoney.com/securities/api/data/v1/get` | 结构化财务数据 |
| 3 | **东财个股研报** | `https://reportapi.eastmoney.com/report/list` | 券商研报、一致预期 |
| 4 | **同花顺 iFinD** | `https://basic.10jqka.com.cn/api/` | 业绩预告、快报 |
| 5 | **新浪财经** | `https://vip.stock.finance.sina.com.cn/` | 财报摘要、历史数据 |

### 关键数据获取 / Key Data Retrieval

**财报公告检索 / Filing Search**：
```
巨潮资讯 公告搜索:
GET http://www.cninfo.com.cn/new/hisAnnouncement/query?stock={股票代码}&category=category_ndbg_szsh (年报)
GET http://www.cninfo.com.cn/new/hisAnnouncement/query?stock={股票代码}&category=category_jdbg_szsh (季报)

类别 / Categories:
- category_ndbg_szsh → 年度报告 / Annual Report
- category_bndbg_szsh → 半年报 / Semi-Annual Report
- category_jdbg_szsh → 季度报告 / Quarterly Report
- category_yjyg_szsh → 业绩预告 / Earnings Preview
- category_yjkb_szsh → 业绩快报 / Earnings Flash
```

**一致预期 / Consensus Estimates**：
```
东财机构一致预期:
GET https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_PREDICT_REPORT&columns=ALL&filter=(SECURITY_CODE="{代码}")

关键字段:
- PREDICT_FINANCE_YEAR → 预测年份
- PREDICT_TOTAL_INCOME → 预测营收
- PREDICT_NET_PROFIT → 预测净利
- PREDICT_EPS → 预测EPS
- INSTITUTION_NUM → 覆盖机构数
```

**业绩预告/快报 / Earnings Preview/Flash**：
```
东财业绩预告:
GET https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_PUBLIC_OP_PREDICT&columns=ALL&filter=(SECURITY_CODE="{代码}")
```

---

## 分析流程 / Analysis Workflow

### 阶段一：数据采集 / Phase 1: Data Collection (30-60 min)

**🚨🚨🚨 关键提醒：必须使用最新财报数据 🚨🚨🚨**
**🚨🚨🚨 CRITICAL: ALWAYS USE LATEST EARNINGS DATA 🚨🚨🚨**

**开始前必须执行 / BEFORE STARTING**：
1. **确认今天日期 / Check today's date** — 写下当前日期
2. **搜索最新财报 / Search for latest** — 网页搜索 `"[公司名] 最新财报"` 或 `"[公司名] 业绩公告"`
3. **验证日期 / Verify date** — 确认财报发布日在3个月以内
4. **获取原文 / Get original filing** — 从巨潮资讯下载公告 PDF

**需要收集的材料 / Materials Needed**：
- ✅ 财报公告原文（年报/季报/业绩快报）/ Original filing (annual/quarterly/flash)
- ✅ 业绩预告（如有）/ Earnings preview (if available)
- ✅ 投资者关系活动记录表（如有电话会）/ IR meeting transcript (if available)
- ✅ 财报发布前的一致预期数据 / Pre-earnings consensus estimates
- ✅ 上一期财报的关键指标（同比基数）/ Prior period key metrics

### 阶段二：业绩分析 / Phase 2: Analysis (2-3 hours)

#### 2.1 超预期/不及预期分析 / Beat/Miss Analysis

对每个关键指标量化偏差 / Quantify variance for each metric:

```
业绩对比 / REPORTED vs ESTIMATES:
────────────────────────────────────────────────
                    实际        我方预期    一致预期    偏差
                    Reported    Our Est     Consensus   Beat/(Miss)
营业收入/Revenue    ¥XXX亿     ¥XXX亿     ¥XXX亿     ¥XX亿 (X%)
毛利率/Gross Margin XX.X%      XX.X%      XX.X%      XXbps
归母净利/Net Income ¥XX亿      ¥XX亿      ¥XX亿      ¥X亿 (X%)
扣非净利/Adj NI     ¥XX亿      ¥XX亿      ¥XX亿      ¥X亿 (X%)
EPS                ¥X.XX      ¥X.XX      ¥X.XX      ¥X.XX
```

> **A 股特殊注意 / A-Share Specifics**：
> - 重点关注**扣非后归母净利润** / Focus on non-recurring items deducted net profit
> - 注意**政府补贴**对利润的影响 / Check government subsidies impact
> - 关注**资产减值损失/信用减值损失** / Asset/credit impairment losses
> - 检查**投资收益**是否来自主营 / Whether investment income is recurring
> - 留意**会计政策变更**影响 / Accounting policy changes

**超预期分析模板 / Beat Analysis Template**：
```
■ **营收超预期X%，主要受益于XX板块强劲增长 / Revenue beat by X%, driven by XX segment**

营业收入¥XX亿，超过我们预期的¥XX亿(X%)和一致预期的¥XX亿(X%)。
超预期主要来自XX业务，同比增长XX%（vs 预期XX%），抵消了YY业务的
弱于预期表现(-X% vs 持平预期)。管理层指出ZZ因素为主要驱动力。

Revenue of ¥XXB exceeded our estimate of ¥XXB by X% and consensus of ¥XXB
by X%. Outperformance driven by XX segment growing XX% YoY (vs our XX%
estimate), offsetting weaker-than-expected YY segment.
```

#### 2.2 分部/地域/产品分析 / Segment Analysis

按以下维度分析 / Analyze by:
- 业务分部 / Business segment
- 地理区域 / Geography (domestic vs overseas, specific regions)
- 产品线 / Product line
- 渠道 / Channel (线上/线下 online/offline, 经销/直销 distributor/direct)

#### 2.3 利润率分析 / Margin Analysis

- 毛利率变动及原因 / Gross margin change and drivers
- 期间费用率变化 / Expense ratio trends (selling, G&A, R&D, finance)
- 关注非经常性损益 / Non-recurring items impact
- 前瞻性展望 / Forward outlook

#### 2.4 管理层指引分析 / Guidance Analysis

**A 股特殊情况 / A-Share Specifics**：
- A 股公司通常不给明确的定量指引 / A-share companies rarely give explicit quantitative guidance
- 关注：**业绩预告**（下一季度）中的利润增速区间 / Focus on: earnings preview profit growth range
- 关注：**投资者关系活动记录表**中的定性指引 / Focus on: IR transcript qualitative guidance
- 关注：**战略规划**中的中长期目标 / Focus on: strategic plan medium-term targets

#### 2.5 更新预测 / Update Estimates

```
预测修正 / UPDATED ESTIMATES:
────────────────────────────────────────────────
                    旧预测      新预测      变化        原因
                    Old Est     New Est     Change      Reason
2025E 营收/Rev      ¥XX亿      ¥XX亿      +X.X%      [简要原因/Brief reason]
2025E 归母净利/NI   ¥XX亿      ¥XX亿      +X.X%      [简要原因/Brief reason]
2025E EPS          ¥X.XX      ¥X.XX      +X.X%      [简要原因/Brief reason]

2026E 营收/Rev      ¥XX亿      ¥XX亿      +X.X%      [简要原因/Brief reason]
2026E 归母净利/NI   ¥XX亿      ¥XX亿      +X.X%      [简要原因/Brief reason]
2026E EPS          ¥X.XX      ¥X.XX      +X.X%      [简要原因/Brief reason]
```

#### 2.6 更新估值与目标价 / Update Valuation & Target Price

基于更新后的预测 / Based on updated estimates:
- 重新计算 DCF / Recalculate DCF (use `/dcf` workflow)
- 更新可比公司倍数 / Update peer multiples (use `/comps` workflow)
- 确定新的合理价值 / Determine new fair value
- 决定是否调整目标价 / Decide if target price changes

**目标价决策 / Target Price Decision**：
- 预测变化 > 5% → 通常调整目标价 / Usually change
- 预测变化 < 5% → 可能维持 / May maintain
- 投资逻辑增强/减弱 → 即使预测不变也可能调整 / May change even without estimate change

---

### 阶段三：图表生成 / Phase 3: Chart Generation (1-2 hours)

制作 **8-12 张图表** / Create **8-12 charts**:

1. **季度营收走势 / Quarterly Revenue Progression** — 柱状图, 最近 8-12 个季度
2. **季度归母净利走势 / Quarterly Net Income** — 柱状图, 展示超预期/不及预期
3. **季度利润率趋势 / Quarterly Margin Trends** — 折线图 (毛利率, 营业利润率, 净利率)
4. **分部/地域收入 / Revenue by Segment/Geography** — 堆叠柱状图
5. **关键经营指标 / Key Operating Metrics** — 多线图 (行业相关的KPI)
6. **业绩偏差分析 / Beat/Miss Waterfall** — 瀑布图或表格
7. **预测修正 / Estimate Revision** — 修正前 vs 修正后对比
8. **估值图 / Valuation Chart** — PE 历史区间 or EV/EBITDA

---

### 阶段四：报告撰写 / Phase 4: Report Creation (2-3 hours)

**报告结构 / Report Structure** (8-12 页 / pages):

| 页码 | 内容 | 英文 |
|------|------|------|
| 第1页 | 业绩摘要 + 评级 + 目标价 + 核心要点 | Summary + Rating + PT + Key Points |
| 第2-3页 | 详细业绩分析（超预期/不及预期解读）| Detailed Results Analysis |
| 第4-5页 | 关键指标 + 管理层指引 | Key Metrics + Guidance |
| 第6-7页 | 投资逻辑更新 + 风险提示 | Updated Thesis + Risks |
| 第8-10页 | 估值与预测更新 | Valuation & Estimates |
| 第11-12页 | 附录（可选：财务报表摘要）| Appendix (Optional) |

**输出格式 / Output Format**:
- **主要交付物 / Primary**: DOCX 报告 (8-12 pages)
- **文件命名 / Naming**: `[公司简称]_[年份]Q[季度]_业绩点评.docx`
- **例 / Example**: `贵州茅台_2025Q3_业绩点评.docx`

---

### 阶段五：质量检查 / Phase 5: Quality Check (30 min)

**内容检查 / Content**：
- [ ] 超预期/不及预期清晰量化 / Beat/miss clearly quantified
- [ ] 关键驱动因素有解释（非笼统"表现强劲"）/ Drivers explained (not generic)
- [ ] 新旧预测对比清楚 / Old vs new estimates shown
- [ ] 目标价更新或明确维持 / Target price updated or explicitly maintained
- [ ] 评级确认或变更并附理由 / Rating confirmed/changed with rationale
- [ ] 管理层指引分析（如有）/ Guidance analyzed

**数据准确性 / Accuracy**：
- [ ] 数字与公司公告原文一致 / Numbers match original filings
- [ ] 同比/环比计算正确 / YoY/QoQ math correct
- [ ] 一致预期引用发布前数据 / Consensus is pre-earnings
- [ ] 无错别字（股票代码、公司名、金额）/ No typos

**引用 / Citations**：
- [ ] 每张图表标注数据来源 / Every chart has source
- [ ] 每张表格标注数据出处 / Every table has source reference
- [ ] 管理层原话注明出处 / Management quotes cited
- [ ] 来源列表附链接 / Sources section with links

**时效性 / Timeliness**：
- [ ] 财报发布后 24-48 小时内 / Within 24-48 hours of filing
- [ ] 所有数据来自最新季度 / All data from latest quarter
