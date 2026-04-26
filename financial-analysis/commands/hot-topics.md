---
description: Discover and rank live hot topics before article drafting
argument-hint: "[topic-discovery-request-json]"
---

# Hot Topics Command

Use this command when you want the repo to collect live candidate topics first,
before drafting anything.

Default flow:

1. fetch from configured hot-topic sources
2. merge duplicates into topic clusters
3. score heat first, then source confirmation, depth, audience relevance, and freshness
4. return a ranked topic list with reasons

Default selection rule:

- high-heat topics enter the candidate list even when they are outside the usual
  finance, tech, or AI-infrastructure lane
- account fit and sector fit affect ranking, but they should not be hard gates
- explicit operator exclusions, such as entertainment or gossip keywords, remain
  hard filters

Local helper:

- `financial-analysis\skills\autoresearch-info-index\scripts\run_hot_topic_discovery.cmd "<request.json>" [--output <result.json>] [--markdown-output <report.md>]`

Useful source names:

- `weibo`
- `zhihu`
- `36kr`
- `google-news-world`
- `google-news-search`

Use this command when the real question is:

- `现在值得写什么`
- `今天有什么能做成公众号文章的热点`
- `先给我排个热点优先级`
