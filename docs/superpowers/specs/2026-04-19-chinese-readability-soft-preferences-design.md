# Chinese Readability Soft Preferences Design

**Goal**

把这次人工修改里验证有效的中文可读性处理，抽象成后续生文可复用的软规则层。目标不是复刻某篇文章，而是让中文成稿默认更顺、更像正式公众号文章，同时保持现有选题、标题、推送链路不变。

---

## 1. Problem Statement

当前链路已经能完成：

- 选题与排序
- 中文标题生成
- 正文生成
- 发布包与微信草稿推送

但中文成稿在最后一步仍然缺一层“面向普通中文读者”的可读性整理。最近一次人工修改已经证明，以下几点会明显提升文章顺滑度和阅读友好度：

1. 让步句和转折句分成两个过短段落时，语气会显得生硬。
2. 公司名、机构名、媒体名、术语如果裸用英文，对中文公众号读者不友好。
3. 结尾如果只是重述主结论，会显得冗余；改成“接下来盯什么”更有用。
4. 中文稿里残留英文业务短语，会降低成稿感。

这类问题不属于 topic ranking，也不属于 headline ranking，而是属于**中文成稿后处理层**。

---

## 2. Scope

本次只覆盖中文成稿可读性软规则，不改：

- topic discovery / ranking
- headline soft preference 层
- cover source preference 层
- WeChat push runtime

只在以下条件触发：

- `language_mode == "chinese"`
- 内容由自动链路生成

不覆盖：

- 明确的人工标题 / 副标题 hint
- 用户手工改写后的最终稿

---

## 3. Design Principles

### 3.1 Soft polish, not rewrite

这层只做轻量整理，不重写论证结构，不改主结论，不替换文章主体信息。

### 3.2 Chinese-first readability

优先保证普通中文读者在第一次扫读时能理解，不要求读者提前知道英文机构名或行业术语。

### 3.3 Rule abstraction, not article cloning

沉淀的是规则：

- 段落衔接
- 中文本地化
- 结尾结构
- 英文残留清洗

不是沉淀某篇文章的具体句子。

### 3.4 Existing generation flow first

优先接入现有中文 markdown 生成链路，不新开一条单独发布流程。

---

## 4. Reusable Rules To Encode

### 4.1 Concession + Turn Merge

当连续出现这类结构时：

- 短让步句
- 下一句立刻是 `但/不过/问题在于/真正值得看的是`

优先合并成一个更自然的中文段落，而不是拆成两个机械短段。

目标效果：

- 从“分析备忘录口吻”收敛到“正式中文长文口吻”
- 保留转折，不保留生硬断句

**约束**

- 只对中文段落做
- 只处理紧邻的短句，不跨大段重组

### 4.2 Chinese Term Localization

首次出现的重要公司名、机构名、媒体名、术语，优先输出：

- `中文名（英文）`
- 或 `中文术语（英文）`

第一版覆盖典型模式：

- 公司/机构：
  - `台积电（TSMC）`
  - `阿斯麦（ASML）`
  - `路透社 Reuters`
- 术语：
  - `新增订单（order intake）`
  - `出口管制（export controls）`

后续再次出现时，可以只保留中文名，避免累赘。

**约束**

- 只做高频、明确、低歧义映射
- 不试图做全量术语翻译系统

### 4.3 Watchpoint Ending

中文稿结尾默认优先落成“验证节点 / 接下来盯什么”，而不是再重复一次主结论。

目标形式：

- 先给一句短收束
- 再给 2-3 个后续验证点

适用文章：

- 产业判断
- 市场判断
- 公司口径分析
- 宏观传导类文章

不强推到：

- 快讯类
- 人物类
- 纯 feature / 解释类文章

### 4.4 English Residue Cleanup

对中文正文里残留的英文业务短语做一层轻量中文化：

- 如果已有稳定中文表达，改成中文优先
- 若保留英文有信息价值，则改成 `中文（英文）`

典型例子：

- `ongoing discussions around export controls`
  -> `出口管制（export controls）相关讨论`
- `spending boom`
  -> `花销潮（spending boom）`

**约束**

- 不碰必须原样保留的产品名
- 不改 citation URL

---

## 5. Proposed Implementation

### 5.1 Target File

主落点：

- `financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py`

原因：

- 中文标题、subtitle、markdown 成稿都主要在这里形成
- 这层最适合做“成稿前的轻量 polish”

### 5.2 New Helpers

新增 helper 建议：

- `localize_chinese_terms(text: str) -> str`
- `merge_chinese_concession_turn(paragraphs: list[str]) -> list[str]`
- `article_prefers_watchpoint_ending(request, analysis_brief, source_summary) -> bool`
- `build_watchpoint_ending(request, analysis_brief, source_summary) -> str`
- `polish_chinese_article_markdown(markdown_text, request, analysis_brief, source_summary) -> str`

### 5.3 Integration Point

建议顺序：

1. 先按现有逻辑生成中文 `article_markdown`
2. 若 `language_mode == "chinese"`：
   - 术语本地化
   - 让步/转折段落合并
   - 结尾 watchpoint 化
   - 英文残留清洗
3. 再进入 HTML/render/package

这样能保证：

- 不破坏正文主流程
- 只在最终成稿文本层轻量修整

---

## 6. Testing Strategy

新增 focused tests 到：

- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

### 6.1 Concession Merge

构造中文段落：

- `这个担心不是完全没有道理。`
- `但过去几天……`

断言输出被合并成更自然的连续表达。

### 6.2 Term Localization

构造含以下词的中文稿：

- `TSMC`
- `ASML`
- `order intake`
- `export controls`

断言输出包含：

- `台积电（TSMC）`
- `阿斯麦（ASML）`
- `新增订单（order intake）`
- `出口管制（export controls）`

### 6.3 Watchpoint Ending

构造一篇产业判断型中文稿，断言结尾不是简单复述主结论，而是出现“接下来盯什么”式验证节点。

### 6.4 Regression Safety

继续跑：

- `test_article_publish.py` 全量

保证：

- 现有标题逻辑不回归
- 现有 `content_markdown / content_html / publish_package` 不断裂

---

## 7. Non-Goals

本次不做：

- 全量行业术语词典
- 人工改稿自动学习系统
- topic ranking 偏好调整
- WeChat push 逻辑修改
- 英文文章可读性 polish

---

## 8. Acceptance Criteria

满足以下条件即视为完成：

1. 中文稿首次出现关键公司名/术语时，会自动补成中文优先形式。
2. 中文稿中常见“让步句 + 转折句”不会再机械拆成两个生硬短段。
3. 产业/市场判断类中文稿结尾会优先落成“验证节点”而不是复述主结论。
4. 中文稿里的英文业务残留会被清理到更自然的中文表达。
5. `test_article_publish.py` 全量通过。
