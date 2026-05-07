# 文章封面图采购指南

> 本指南沉淀了实际文章发布中验证有效的封面图采购流程。
> 适用于微信公众号、头条号等需要 16:9 封面的场景。

## 核心原则

1. **贴题实拍 > 泛化素材**。如果文章主角是明确的人物、公司、产品、地点或事件，封面必须优先找该主体的近期实拍、官方现场图或可授权新闻摄影；不要默认用通用科技感、抽象插画或来源站 OpenGraph 图。
2. **真实新闻摄影 > AI 生成图**。AI 生成的封面容易显得廉价、不专业，尤其在财经/宏观类文章中。
3. **具象细节 > 抽象概念**。加油枪计价器特写 >> 抽象的"油价上涨"概念图。
4. **暗色/简洁背景 > 杂乱场景**。封面需要叠加标题文字时，暗色背景更好用。
5. **免费商用 > 版权风险**。优先 Wikimedia Commons / 官方媒体库 / Unsplash / Pexels；避免直接热链 AP/Reuters/Getty。

## 主体匹配规则

先用一句话写清楚文章的"第一视觉信号"：读者刷到封面时，应该立刻看见谁或什么。

- 人物/创始人主导：优先找该人物的近期实拍照，尽量是近 12-24 个月内、脸部清晰、构图简洁的照片。
- 公司/产品主导：优先找真实产品、门店、工厂、数据中心、发布会、车辆、芯片、Logo 所在实景，而不是抽象行业图。
- 资产/场景主导：优先找能代表核心资产的实物图，如数据中心、服务器机柜、晶圆、油轮、港口、交易大厅。
- 宏观/行业主题：没有单一主体时，再使用 Unsplash/Pexels 的高质量场景或细节特写。
- 禁止默认封面：来源站的 OpenGraph 插画、品牌默认图、抽象节点图、AI 机器人图、无关服务器图，不能直接作为最终封面，除非它和文章主线强相关且用户明确接受。

执行时不要只让包里的 `cover_image_url` 顺手流到推送。若当前封面不贴题，先换图，再跑 `wechat_push_readiness` 和 `wechat_push_draft`。

## 采购优先级

### 第零优先：贴题实拍 / 官方现场图

适用于文章有明确主体的情况，例如人物、公司、产品、数据中心、工厂、发布会或地缘现场。

- **优先来源**:
  - Wikimedia Commons，优先选择公有领域、CC BY、官方机构上传或来源清楚的图片
  - 公司官网 newsroom / media kit / press images
  - 政府机构、交易所、监管机构、大学、会议主办方等官方 Flickr / media library
  - 文章相关公司或人物的官方 X / 新闻稿配图，仅在许可或评论引用边界清楚时使用
- **搜索技巧**:
  - 用英文组合搜索：`<person/company/product> recent photo`, `<person> 2025 official photo`, `<company> data center press image`
  - 对人物封面加：`portrait`, `speaking`, `visits`, `official`, `Wikimedia Commons`
  - 对实体资产加：`factory`, `data center`, `server rack`, `facility`, `press image`
- **落地方式**:
  - 优先下载成本地文件，再用 `--cover-image-path` 推送，避免远程 URL 中的 `&`、重定向、反爬或热链失效。
  - 下载后保存在当前文章 `.tmp` 输出目录，例如 `cover-elon-musk-20250321.jpg`。
  - 如果只能使用远程 URL，必须确认命令行转义无误，并在 readiness / push 结果中确认上传的是该图。

### 第一优先：Unsplash（推荐）

- **网站**: https://unsplash.com
- **许可**: Unsplash License，免费商用，无需署名
- **搜索技巧**:
  - 用英文关键词搜索，效果远好于中文
  - 搜索具体物件而非抽象概念：`gas pump price counter` 而非 `oil price rising`
  - 加 `close-up` / `detail` 可以找到更有冲击力的特写
- **直接获取 16:9 裁切 URL**:
  ```
  https://images.unsplash.com/photo-{ID}?w=1920&h=1080&fit=crop&auto=format&q=85
  ```
  缩小尺寸加快下载：`w=900&h=506` 即可满足微信封面要求
- **下载命令**:
  ```bash
  curl -sL --connect-timeout 10 --max-time 30 \
    -o cover.jpg \
    "https://images.unsplash.com/photo-{ID}?w=900&h=506&fit=crop&auto=format&q=80"
  ```

### 第二优先：Pexels

- **网站**: https://www.pexels.com
- **许可**: Pexels License，免费商用，无需署名
- **注意**: 自动化访问可能被 Cloudflare 拦截，手动下载更可靠

### 第三优先：新闻源文章内嵌图

- AP / Reuters / Bloomberg 文章里的图片是**版权图片**
- 热链通常被屏蔽（返回占位图）
- 仅在 fair use 评论/引用场景下可截图使用，不建议做封面

### 最后手段：AI 生成

- 仅在以上都找不到合适图片时使用
- 如果用 AI 生成，提示词要求：
  - `photorealistic, editorial photography style`
  - `no text, no watermark, no logo`
  - `16:9 aspect ratio`
  - 具体场景描述而非抽象概念

## 按话题类型的搜索关键词参考

| 话题类型 | 推荐搜索词 | 避免 |
|---|---|---|
| 油价/能源 | `gas pump price counter`, `gas station price sign`, `fuel pump close-up` | `oil barrel`（太抽象） |
| 通胀/CPI | `grocery store prices`, `supermarket shopping`, `receipt close-up` | `inflation chart`（太无聊） |
| 美联储/利率 | `federal reserve building`, `wall street trading floor` | `money printing`（太俗） |
| 消费/零售 | `shopping bags`, `retail store`, `credit card payment` | `happy shopper`（太假） |
| 地缘冲突 | `strait of hormuz`, `oil tanker`, `military vessel` | AI 生成的战争场景 |
| 半导体 | `semiconductor wafer`, `chip fabrication`, `cleanroom` | `circuit board`（太泛） |
| AI/科技 | `data center`, `server rack`, `code on screen` | AI 生成的机器人 |
| 人物/创始人 | `Elon Musk 2025 official photo`, `CEO portrait Wikimedia Commons`, `founder speaking event` | 抽象科技插画、公司默认 OG 图 |
| AI 算力/数据中心 | `xAI Colossus data center`, `GPU data center press image`, `server rack close-up` | 无关云计算插画、泛化网络节点图 |

## 验证清单

下载后检查：
- [ ] 文件格式：JPEG 或 PNG
- [ ] 尺寸：至少 900×506（16:9），微信要求最小 200×200
- [ ] 文件大小：< 2MB（微信封面限制）
- [ ] 无文字/水印/Logo
- [ ] 暗色区域足够叠加标题（如果需要）
- [ ] 与文章主题直接相关，不是装饰性配图
- [ ] 若文章有明确人物/公司/产品/事件，封面能一眼识别这个主体
- [ ] 若替换过封面，readiness 和最终 push 命令使用的是 `--cover-image-path` 或已验证的贴题 URL，而不是包内旧的 `cover_image_url`
- [ ] 最终 `wechat-push-result*.json` 中 `uploaded_cover.url` / `thumb_media_id` 来自新封面，不是默认 OpenGraph 图

## 实战案例

### 2026-05-07：马斯克XAI的22万块GPU算力，为什么先给了Claude？

- **问题**: 首轮包内封面沿用了 Anthropic OpenGraph 抽象图，和标题里的"马斯克 / xAI / 22 万块 GPU"主信号不匹配。
- **最终选择**: Wikimedia Commons 上 2025-03-21 马斯克实拍照，下载到文章 `.tmp` 目录后用 `--cover-image-path` 重新推送。
- **执行教训**:
  - 这类人物 + 公司 + 算力资产文章，封面第一优先不是来源站默认图，而是人物实拍或真实数据中心 / GPU 场景。
  - 远程 URL 容易被 shell 转义、反爬或热链影响；真实推送优先用本地图片路径。
  - 推送后必须核对 `uploaded_cover.media_id` 和 `uploaded_cover.url`，确认新封面真的进了后台草稿。

### 2026-04-22：零售数据在骗你：美国消费的真相藏在加油站里

- **最终选择**: Unsplash 加油枪数字计价器特写
  - URL: `photo-1637417168775-532c76fa4fa4`
  - 暗色背景，数字跳动的戏剧感，一眼就懂"油价贵"
- **备选**: Unsplash 美国加油站外景带价格牌
  - URL: `photo-1647618983095-8490d721074b`
  - 经典新闻编辑风格，但视觉冲击力稍弱
- **被替换的**: AI 生成的 `cover-hormuz-consumer-v2.png`
  - 问题：太抽象、不够专业、缺乏真实感
- **教训**: 财经类文章封面用真实摄影图效果远好于 AI 生成图
