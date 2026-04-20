# Positive Feedback Soft Preferences Design

**Goal**

把“昨天那篇英伟达文章获得 70 次阅读”的正反馈，抽象成可复用的软规则层，用于后续选题、标题和封面选择，但不把任何单篇表现固化成硬编码默认。

**Scope**

只覆盖三个偏好层：

1. topic soft preference
2. headline soft preference
3. cover source soft preference

不改现有硬过滤，不改微信推送链，不引入新的外部依赖。

---

## 1. Problem Statement

当前链路已经能完成：

- topic discovery
- article drafting / publishing
- cover selection
- WeChat draft push

但“哪种题、哪种标题、哪类封面更容易获得阅读”这层经验，还没有被系统化吸收。现在的机制更像：

- 选题侧：按热度、相关性、深度、SEO 排序
- 标题侧：按 `headline_hook_mode` 和少量前缀做标题包装
- 封面侧：按 dedicated candidate / screenshot / body image fallback 选图

缺口在于：

- 没有一层“历史正反馈偏好”去给高表现特征加软分
- 标题和封面还缺少“哪些风格已经被用户验证有效”的偏好记忆
- 现有能力更像 rule engine，而不是带有限经验记忆的 ranking layer

---

## 2. Design Principles

### 2.1 Soft, not hard

正反馈只转成加权信号，不转成过滤门槛。

这意味着：

- 不因为某一类题以前表现好，就把别的题全部降为不可选
- 不因为某一种标题结构表现好，就强制所有中文稿都套这个模板
- 不因为真人工业图效果好，就禁用生成图

### 2.2 Feature-level abstraction, not article cloning

我们不复用“那篇文章本身”，只复用抽象特征：

- 题材特征
- 标题结构特征
- 封面来源特征

### 2.3 Existing hooks first

优先复用现有字段和流程：

- `preferred_topic_keywords`
- `headline_hook_mode`
- `style_memory`
- `cover_candidates / cover_plan`

除非现有结构确实承载不了，再加少量新字段。

---

## 3. Positive Signals To Encode

基于本轮用户反馈，先定义三组正反馈信号。

### 3.1 Topic Preference Signals

高表现题的共同特征不是“英伟达”这个具体词，而是：

- `hard_industry`: 半导体、AI 基建、先进制造、设备、产能、供应链
- `clear_actor`: 有明确主角公司/人物/平台，而不是泛宏观题
- `contrarian_frame`: 自带反直觉或判断反转空间
- `china_or_market_relevance`: 对中国语境或市场判断有直接含义

第一版实现建议：

- 给每个 candidate 计算 `positive_feedback_topic_bonus`
- bonus 来源于上述四类命中数
- bonus 只在排序总分末端做小幅加分，例如 `+4 ~ +12`

### 3.2 Headline Preference Signals

用户已经明确认可高表现标题的结构性特征：

- `X 真正的护城河是……`
- `最怕的不是……而是……`

第一版不直接生成这些标题，而是：

- 将它们抽象成 `headline_frame_candidates`
- 作为中文标题生成时的高优先级候选
- 仍然要求正文主旨能支撑这个结构

保护条件：

- 只对“明确主角 + 明确判断”的题开放
- 不对纯资讯题、讣闻、地方新闻、泛 feature 自动套这种框

### 3.3 Cover Preference Signals

用户已经给出明确反馈：

- 对半导体 / AI 基建 / 大厂人物题，官方真实图 > 本地生成示意图

第一版抽象成：

- `cover_source_preference = official_photo > newsroom_photo > article_image > generated_image`

不是禁用生成图，而是：

- 有可用官方图时，优先选官方图
- 没有时再退回生成图

---

## 4. Proposed Changes By Layer

## 4.1 Topic Discovery Layer

**Target file**

- `financial-analysis/skills/autoresearch-info-index/scripts/hot_topic_discovery_runtime.py`

新增一个辅助函数族：

- `positive_feedback_topic_signals(candidate) -> dict`
- `positive_feedback_topic_bonus(candidate) -> int`

信号建议：

- `hard_industry_hit`
- `clear_actor_hit`
- `contrarian_frame_hit`
- `china_or_market_relevance_hit`

输出：

- 写入 `candidate["positive_feedback_signals"]`
- 写入 `candidate["score_breakdown"]["positive_feedback_bonus"]`
- 在最终 `total_score` 上小幅加分
- 在 `score_reasons` 中补一句简短原因，例如：
  - `positive-feedback: hard industry + clear actor`

## 4.2 Headline Generation Layer

**Target files**

- `financial-analysis/skills/autoresearch-info-index/scripts/article_draft_flow_runtime.py`
- optionally `financial-analysis/skills/autoresearch-info-index/scripts/article_publish_runtime.py`

新增：

- `headline_frame_candidates(request, source_summary, analysis_brief) -> list[str]`
- `headline_frame_eligible(...) -> bool`

第一版只做中文标题：

- 在 `finalize_article_title()` 中
- 先正常 derive title
- 再在 eligible 时尝试 1-2 个高表现框架
- 若生成标题过长、悬空或与正文不匹配，则回退原题

核心要求：

- 不是强制替换
- 是“多给一个更强标题候选”

## 4.3 Cover Selection Layer

**Target file**

- `financial-analysis/skills/autoresearch-info-index/scripts/article_publish_runtime.py`

新增：

- `cover_source_preference_score(candidate, request, selected_topic) -> float`

给 cover candidate 打额外偏好分：

- 官方图 / newsroom 图：高分
- 普通 body image：中分
- generated / synthetic / local illustration：低分

不改现有 fallback 框架，只改变排序优先级。

---

## 5. Data Model Additions

尽量少加字段。

若需要新增，建议只加这些轻量字段：

- `positive_feedback_signals` on ranked topics
- `positive_feedback_bonus` inside topic `score_breakdown`
- `headline_frame_used` on article package effective request
- `cover_source_preference_score` in `cover_candidates`（仅调试/报告）

---

## 6. Non-Goals

第一版明确不做：

- 不做基于阅读量的自动在线学习
- 不接公众号后台真实阅读数据接口
- 不把单篇文章的标题原样固化成模板
- 不引入数据库或持久化学习系统
- 不改 topic discovery 的硬过滤规则

---

## 7. Acceptance Criteria

### 7.1 Topic

给定一组候选，若其中包含：

- 硬产业
- 明确主角
- 明确判断空间
- 中国/市场直接相关

则该类候选在总分接近时，应更容易排到前面。

### 7.2 Title

对符合条件的中文题目，系统可给出更强结论型候选标题，但：

- 不破坏现有标题生成
- 不对不适合的题强套反直觉框架

### 7.3 Cover

对半导体 / AI 基建 / 大厂人物题：

- 若同时存在官方真实图和生成图，官方图应优先成为 cover candidate

---

## 8. Risks

### 8.1 Overfitting to one successful article

风险：

- 过度把一篇 70 阅读的稿子当成普适模板

缓解：

- 只抽象特征，不复用具体文案
- bonus 保持有限，不压倒基础排序

### 8.2 Headline drift

风险：

- 强判断标题若不受正文约束，会变成标题党

缓解：

- headline frame 必须过 eligibility check
- 失败自动回退原题

### 8.3 Cover source detection ambiguity

风险：

- 很多本地文件难以区分“官方裁切图”还是“本地生成图”

缓解：

- 第一版通过 `source_name/source_url/path naming` 做启发式判断
- 先解决 80% 的明显情况

---

## 9. Recommended Next Step

下一步按最小实现推进：

1. 先做 topic soft preference
2. 再做 headline soft preference
3. 最后做 cover source soft preference

这样每层都能独立验证，不会一次把三层耦在一起。
