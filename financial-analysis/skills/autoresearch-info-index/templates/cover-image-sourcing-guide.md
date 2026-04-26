# 文章封面图采购指南

> 本指南沉淀了实际文章发布中验证有效的封面图采购流程。
> 适用于微信公众号、头条号等需要 16:9 封面的场景。

## 核心原则

1. **真实新闻摄影 > AI 生成图**。AI 生成的封面容易显得廉价、不专业，尤其在财经/宏观类文章中
2. **具象细节 > 抽象概念**。加油枪计价器特写 >> 抽象的"油价上涨"概念图
3. **暗色/简洁背景 > 杂乱场景**。封面需要叠加标题文字时，暗色背景更好用
4. **免费商用 > 版权风险**。优先 Unsplash/Pexels，避免直接热链 AP/Reuters/Getty

## 采购优先级

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

## 验证清单

下载后检查：
- [ ] 文件格式：JPEG 或 PNG
- [ ] 尺寸：至少 900×506（16:9），微信要求最小 200×200
- [ ] 文件大小：< 2MB（微信封面限制）
- [ ] 无文字/水印/Logo
- [ ] 暗色区域足够叠加标题（如果需要）
- [ ] 与文章主题直接相关，不是装饰性配图

## 实战案例

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
