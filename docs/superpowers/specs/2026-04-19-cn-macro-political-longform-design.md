# CN Macro Political Longform Design

**Goal**

为中文宏观/政治/市场长文新增一个显式可调用的成稿 preset：

- `composition_profile=cn_macro_political_longform`

它的目标不是让所有中文稿都变成长篇政治评论，而是把已经验证有效的宏观长文结构，沉淀成一个只在特定题材下生效的专用生成骨架。

---

## 1. Problem Statement

当前中文自动稿已经具备：

- 选题与排序
- 标题与副题生成
- 正文生成
- 发布包与微信推送

但对宏观/政治/市场类长文来说，现有默认结构仍然偏“通用分析稿”，主要问题是：

1. 开头常常直接进入观点，没有足够的场景感。
2. 中段容易变成并列观点堆砌，而不是围绕一条核心矛盾推进。
3. 具体样本、群体体感、制度风险、市场含义之间缺少层级递进。
4. 结尾容易重复主结论，而不是给出后续验证节点。

近期人工写作样本已经证明，宏观/政治/市场长文如果按以下结构组织，阅读体验和论证力度都会明显更强：

- 先用具体场景带入
- 尽快抛出单一核心矛盾
- 中段按“全国结构 -> 关键样本 -> 体感链条 -> 制度风险”推进
- 最后再写市场含义和验证节点

这类改进不属于 topic ranking，也不属于微信推送层，而属于**中文长文结构 preset**。

---

## 2. Scope

本次只新增一个显式 preset：

- `composition_profile=cn_macro_political_longform`

它只在以下条件同时满足时生效：

- `language_mode == "chinese"`
- `composition_profile == "cn_macro_political_longform"`

本次不改：

- topic discovery / ranking
- title soft preference / headline hook 默认逻辑
- cover selection
- publish / push runtime
- 默认中文稿件结构

这意味着：

- 不传 `composition_profile` 时，现有行为保持不变
- 非宏观/政治/市场长文不会被自动带入这套写法

---

## 3. Design Principles

### 3.1 Explicit opt-in first

第一阶段只做显式调用，不做自动题材识别。先保证这套结构在适合的题材里稳定，再决定后面是否需要 auto-routing。

### 3.2 Structure over style mimicry

沉淀的是结构动作，而不是某篇文章的句子或口头禅。重点是：

- 开头方式
- 核心矛盾
- 正文推进顺序
- 因果链表达
- 结尾收口方式

### 3.3 Macro/political specificity

这套 preset 只服务于：

- 宏观政治
- 选举与政策
- 制度风险
- 市场含义后置型长文

不试图兼容所有中文分析稿。

### 3.4 Minimal surface area

第一阶段只在中文成稿链中修改：

- section planning
- section ordering
- closing paragraph style
- macro subtitle
- scene-setting lede
- concrete case expansion
- market implication read-through formatting

不扩散到标题、封面、选题和推送链路。

---

## 4. Preset Behavior

### 4.1 Lead mode: scene-setting

开头优先使用一个具体场景、会议、闭门讨论、时间点或观察现场，把读者先拉进判断现场，而不是直接抛抽象结论。

目标效果：

- 让长文有进入感
- 降低“分析备忘录”腔调

### 4.2 Argument mode: single core contradiction

正文前 10%-15% 必须明确一条核心矛盾。后续章节都围绕这条矛盾展开，不允许第二节之后仍然在漂移找主题。

示例类型：

- 低投票倾向选民 vs 高参与度选民
- 政策承诺 vs 真实经济体感
- 机构稳定性 vs 政治任命不确定性

### 4.3 Body mode: zoom-in ladder

正文中段不做并列堆叠，而按层级推进。推荐顺序：

1. 全国/总体结构
2. 关键州、关键机构、关键人
3. 关键选民/关键变量
4. 制度或政策层风险

### 4.4 Reasoning mode: pain-chain

正文至少 1-2 节必须把抽象风险写成因果链，而不是只说“风险在扩大”。

示例形式：

- `油价 -> 通勤/取暖成本 -> 家庭消费缩减 -> 政治耐心下降`
- `出口限制 -> 供给瓶颈 -> 成本传导 -> 投资重新定价`

### 4.5 Ending mode: market watchpoints

结尾不再重复主结论，而是优先输出：

- 接下来要盯的验证节点
- 哪些变量会改变当前判断
- 哪些条件会让市场重新定价

### 4.6 Subtitle mode: macro judgment framing

启用 preset 后，副题不再沿用默认中文分析稿句式，而应优先写成：

- 从判断现场看问题走到哪一步
- 从风险定价看压力怎样传到政策和市场

目标是让副题先承接判断框架，而不是继续承担通用“开场白”功能。

### 4.7 Lede mode: scene-setting with stakes

启用 preset 后，lede 应优先采用：

- 一个具体判断现场
- 一句 stakes framing

而不是 generic analysis 开头。

### 4.8 Concrete case expansion

`关键样本` 一节在输入中存在明确命名对象时，应优先展开成 2-3 个具名样本，而不是停留在“关键州/关键机构/关键人”的抽象模板。

### 4.9 Market read-through formatting

`市场含义` 一节应优先输出编号式 read-through：

- 第一，...
- 第二，...
- 第三，...

而不是单段抽象说明。

---

## 5. Default Section Blueprint

第一版默认 section 数控制在 `6-8` 节，优先生成如下骨架：

1. **开头引入**
   - 一个具体场景或判断现场
2. **核心矛盾**
   - 全文唯一主轴
3. **关键样本 / 关键区域 / 关键人物**
   - 2-3 个具体落点
4. **体感变量 / 传导链条**
   - 将抽象风险改写成因果链
5. **制度 / 政策层变量**
   - 把具体样本接回更高层风险
6. **更远期展望**
   - 交代后续会提前暴露什么问题
7. **市场含义**
   - 单独成节，不提前泄洪
8. **结尾**
   - watchpoints 或开放但具体的问题

这不是硬性要求必须出现 8 节，而是默认生成顺序和功能分工。

---

## 6. Implementation Surface

第一阶段只改 3 个面。

### 6.1 Request normalization

文件：

- `financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py`

新增字段：

- `composition_profile`

只认一个新值：

- `cn_macro_political_longform`

### 6.2 Section planning and ordering

仍在：

- `financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py`

新增 profile-aware 分支：

- `is_cn_macro_political_longform_profile(request)`
- `build_cn_macro_political_longform_sections(...)`

它负责：

- 固定 section 功能顺序
- 引导正文按 macro/political longform 结构展开

### 6.3 Ending formatter

同样在：

- `financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py`

新增：

- `build_cn_macro_watchpoint_ending(...)`

职责：

- 把结尾从“重复主结论”改成“后续验证节点”

### 6.4 Macro subtitle / lede / section expansion

仍在：

- `financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py`

新增或扩展：

- `build_subtitle(...)` 中的 macro-profile 分支
- `build_public_lede(...)` 中的 macro-profile 分支
- `关键样本 / 制度与政策层变量 / 市场含义` 的 macro-specific paragraph builders

---

## 7. Proposed Helper Functions

第一阶段建议新增以下 helper：

- `is_cn_macro_political_longform_profile(request) -> bool`
- `build_cn_macro_scene_lead(...) -> str`
- `build_cn_macro_core_contradiction_section(...) -> dict[str, str]`
- `build_cn_macro_concrete_case_sections(...) -> list[dict[str, str]]`
- `build_cn_macro_pain_chain_section(...) -> dict[str, str]`
- `build_cn_macro_institutional_risk_section(...) -> dict[str, str]`
- `build_cn_macro_forward_outlook_section(...) -> dict[str, str]`
- `build_cn_macro_market_implications_section(...) -> dict[str, str]`
- `build_cn_macro_watchpoint_ending(...) -> str`
- `build_cn_macro_political_longform_sections(...) -> list[dict[str, str]]`
- `build_cn_macro_scene_setting_subtitle(...) -> str`
- `extract_cn_macro_case_names(...) -> list[str]`
- `build_cn_macro_concrete_case_paragraph(...) -> str`
- `build_cn_macro_institutional_bottleneck_paragraph(...) -> str`
- `build_cn_macro_market_readthroughs_paragraph(...) -> str`

这些 helper 只作为 preset 内部分支存在，不改变默认 section builder 的外部契约。

---

## 8. Acceptance Criteria

### 8.1 Default behavior unchanged

以下任一条件满足时，输出必须保持现有逻辑：

- 没传 `composition_profile`
- `language_mode != "chinese"`
- 不是显式宏观/政治/市场长文调用

### 8.2 Structure forms correctly under the preset

显式启用 preset 后：

- 生成结果默认 `6-8` 节
- 开头有 scene-setting
- 第二节明确一条核心矛盾
- 中段至少有一节具体样本
- 至少一节出现明确因果链
- 市场含义后置
- 结尾使用验证节点收口
- 副题不再回落到默认中文分析稿句式
- lede 以 scene-setting 开头
- `关键样本` 在具名输入存在时能展开命名对象
- `市场含义` 为编号式 read-through

### 8.3 No simple list-of-opinions fallback

启用 preset 后，不应退化成“观点1/观点2/观点3”的并列堆叠结构。

---

## 9. Testing Strategy

测试全部放在：

- `financial-analysis/skills/autoresearch-info-index/tests/test_article_publish.py`

第一版新增 4 类测试：

1. `test_cn_macro_profile_is_opt_in_only`
   - 不传 `composition_profile` 时，结构不变

2. `test_cn_macro_profile_builds_zoom_in_section_order`
   - 传 `composition_profile=cn_macro_political_longform`
   - 断言 section 顺序符合 blueprint

3. `test_cn_macro_profile_includes_core_contradiction_and_pain_chain`
   - 断言同时存在核心矛盾和明确因果链

4. `test_cn_macro_profile_ending_uses_watchpoints_not_summary_recap`
   - 断言结尾是验证节点，而不是主结论复述

回归要求：

- focused tests 先红绿
- 再跑全量 `test_article_publish.py`

---

## 10. Non-Goals

第一阶段明确不做：

- 自动识别所有宏观题并自动套 preset
- 针对这类题材重写标题系统
- 为这类题单独做封面策略
- 修改 topic ranking
- 把其它中文产业稿、科技稿、人物稿一起改成这种写法

---

## 11. Recommended Rollout Order

1. 先补 opt-in 与 section order 红灯测试
2. 接 `composition_profile`
3. 实现 macro longform section builder
4. 实现 watchpoint ending
5. 跑 focused tests
6. 跑全量回归

这样可以把风险集中在一个文件、一组新 helper 和一组新测试里，便于验证和回退。
