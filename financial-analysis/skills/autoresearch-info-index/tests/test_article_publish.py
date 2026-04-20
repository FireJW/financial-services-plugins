from __future__ import annotations

from datetime import UTC, datetime
import json
import py_compile
import shutil
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from article_publish_runtime import (
    build_chinese_publish_markdown,
    build_news_request_from_topic,
    build_publish_package,
    build_regression_checks,
    build_report_markdown,
    normalize_request,
    run_article_publish,
    select_cover_plan,
)
from article_publish import parse_args
from article_publish_regression_check import parse_args as parse_regression_check_args
from article_publish_regression_check_runtime import run_publish_regression_check
from article_draft_flow_runtime import build_public_lede, build_subtitle, finalize_article_title
import article_draft_flow_runtime
import hot_topic_discovery_runtime
from hot_topic_discovery_runtime import run_hot_topic_discovery


class ArticlePublishRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        runtime_root = Path(__file__).resolve().parent / ".tmp-article-publish"
        if runtime_root.exists():
            shutil.rmtree(runtime_root, ignore_errors=True)
        runtime_root.mkdir(parents=True, exist_ok=True)
        self.temp_dir = runtime_root

    def tearDown(self) -> None:
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def manual_topic_candidates(self) -> list[dict]:
        return [
            {
                "title": "AI agent hiring rebound becomes a business story",
                "summary": "Multiple sources debate whether hiring demand is really returning and what it means for startups.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-agent-hiring",
                        "published_at": "2026-03-29T10:00:00+00:00",
                        "summary": "36kr reports hiring is returning at selected AI agent startups.",
                    },
                    {
                        "source_name": "zhihu",
                        "source_type": "social",
                        "url": "https://example.com/zhihu-agent-hiring",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "Zhihu users debate whether the rebound reflects real demand or another short-lived wave.",
                    },
                    {
                        "source_name": "google-news-search",
                        "source_type": "major_news",
                        "url": "https://example.com/google-agent-hiring",
                        "published_at": "2026-03-29T10:15:00+00:00",
                        "summary": "Overseas outlets argue the real shortage is operators who can ship business outcomes.",
                    },
                ],
            },
            {
                "title": "Celebrity airport outfit goes viral again",
                "summary": "A pure entertainment topic with very little business relevance.",
                "source_items": [
                    {
                        "source_name": "weibo",
                        "source_type": "social",
                        "url": "https://example.com/weibo-celebrity",
                        "published_at": "2026-03-29T10:25:00+00:00",
                        "summary": "Mostly image-driven social chatter.",
                    }
                ],
            },
        ]

    def locality_filter_candidates(self) -> list[dict]:
        return [
            {
                "title": "阜沙镇为阜沙制造出海保驾护航",
                "summary": "广东中山阜沙镇围绕本地制造和招商做地方宣传。",
                "source_items": [
                    {
                        "source_name": "中山网",
                        "source_type": "major_news",
                        "url": "https://example.com/fusha-town",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "广东中山阜沙镇围绕本地制造和招商做地方宣传。",
                    }
                ],
            },
            {
                "title": "上海发布具身智能产业新政，机器人供应链再获催化",
                "summary": "上海围绕具身智能和机器人供应链发布新政，具备产业链延伸价值。",
                "source_items": [
                    {
                        "source_name": "澎湃",
                        "source_type": "major_news",
                        "url": "https://example.com/shanghai-embodied-policy",
                        "published_at": "2026-03-29T10:18:00+00:00",
                        "summary": "上海围绕具身智能和机器人供应链发布新政，具备产业链延伸价值。",
                    }
                ],
            },
        ]

    def obituary_candidates(self) -> list[dict]:
        return [
            {
                "title": "王子杰逝世：创办丝芭、久游网，引进《劲舞团》",
                "summary": "一则偏人物回顾向的讣闻消息，缺少明确产业判断延伸。",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/obit-wangzijie",
                        "published_at": "2026-03-29T10:10:00+00:00",
                        "summary": "一则偏人物回顾向的讣闻消息，缺少明确产业判断延伸。",
                    }
                ],
            }
        ]

    def english_obituary_candidates(self) -> list[dict]:
        return [
            {
                "title": "Former Virginia Lt. Gov. Justin Fairfax and Wife Found Dead in Apparent Murder-Suicide",
                "summary": "A single-source death and crime headline without meaningful industry or market relevance.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/justin-fairfax",
                        "published_at": "2026-03-29T10:11:00+00:00",
                        "summary": "A single-source death and crime headline without meaningful industry or market relevance.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            }
        ]

    def rumor_penalty_candidates(self) -> list[dict]:
        return [
            {
                "title": "Claude Opus 4.7 或本周上线？社交平台传闻再起",
                "summary": "围绕新模型发布时间的社交平台传闻升温，但暂无官方确认。",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/claude-rumor",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "围绕新模型发布时间的社交平台传闻升温，但暂无官方确认。",
                    }
                ],
            },
            {
                "title": "腾讯正式发布并开源混元世界模型 2.0",
                "summary": "公司正式发布模型并说明能力边界。",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/tx-world-model",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "公司正式发布模型并说明能力边界。",
                    }
                ],
            },
        ]

    def international_source_candidates(self) -> list[dict]:
        return [
            {
                "title": "Claude rumor cycle returns again after another fake release window",
                "summary": "Reddit and X users are debating whether the latest Claude release rumor is real or recycled.",
                "source_items": [
                    {
                        "source_name": "Reddit r/singularity",
                        "source_type": "social",
                        "url": "https://example.com/reddit-claude-rumor",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "Reddit users are debating whether the latest Claude release rumor is real or recycled.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/singularity"],
                    },
                    {
                        "source_name": "X @modelwatch",
                        "source_type": "social",
                        "url": "https://example.com/x-claude-rumor",
                        "published_at": "2026-03-29T10:18:00+00:00",
                        "summary": "X users are comparing the rumor to previous fake release windows.",
                        "tags": ["provider:agent-reach:x"],
                    },
                    {
                        "source_name": "google-news-world",
                        "source_type": "major_news",
                        "url": "https://example.com/google-claude-rumor",
                        "published_at": "2026-03-29T10:15:00+00:00",
                        "summary": "A fallback news source summarizes the rumor spillover.",
                    },
                ],
            },
            {
                "title": "New AI startup says product demand is improving",
                "summary": "A single 36kr story claims demand is improving.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-demand",
                        "published_at": "2026-03-29T10:22:00+00:00",
                        "summary": "A single 36kr story claims demand is improving.",
                    }
                ],
            },
        ]

    def international_platform_priority_candidates(self) -> list[dict]:
        return [
            {
                "title": "AI chip bottleneck debate spills from Reddit and X into supplier checks",
                "summary": "Platform discussion is converging on whether supply bottlenecks are finally easing.",
                "source_items": [
                    {
                        "source_name": "Reddit r/singularity",
                        "source_type": "social",
                        "url": "https://example.com/reddit-chip-bottleneck",
                        "published_at": "2026-03-29T08:10:00+00:00",
                        "summary": "Reddit users are debating whether AI chip bottlenecks are easing.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/singularity"],
                    },
                    {
                        "source_name": "X @supplychainwatch",
                        "source_type": "social",
                        "url": "https://example.com/x-chip-bottleneck",
                        "published_at": "2026-03-29T08:05:00+00:00",
                        "summary": "X users are comparing supplier checks and timeline revisions.",
                        "tags": ["provider:agent-reach:x"],
                    },
                ],
            },
            {
                "title": "爆火AI超级应用获数亿元融资，赛道彻底引爆",
                "summary": "A very fresh single-source fallback headline with flashy wording but weak confirmation.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/flashy-ai-funding",
                        "published_at": "2026-03-29T10:25:00+00:00",
                        "summary": "A very fresh single-source fallback headline with flashy wording but weak confirmation.",
                    }
                ],
            },
        ]

    def international_platform_priority_edge_candidates(self) -> list[dict]:
        return [
            {
                "title": "One supplier quietly shifts guidance",
                "summary": "A small Reddit thread about a subtle supplier move.",
                "source_items": [
                    {
                        "source_name": "Reddit r/singularity",
                        "source_type": "social",
                        "url": "https://example.com/reddit-subtle-supplier-shift",
                        "published_at": "2026-03-27T10:00:00+00:00",
                        "summary": "A small Reddit thread about a subtle supplier move.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/singularity"],
                    }
                ],
            },
            {
                "title": "AI startup funding frenzy sends the whole sector soaring overnight",
                "summary": "A very fresh single-source fallback headline with flashy wording but weak confirmation.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/flashy-ai-funding-english",
                        "published_at": "2026-03-29T10:25:00+00:00",
                        "summary": "A very fresh single-source fallback headline with flashy wording but weak confirmation.",
                    }
                ],
            },
        ]

    def international_primary_source_floor_candidates(self) -> list[dict]:
        return [
            {
                "title": "AI chip bottleneck debate spills from Reddit and X into supplier checks",
                "summary": "Platform discussion is converging on whether supply bottlenecks are finally easing.",
                "source_items": [
                    {
                        "source_name": "Reddit r/singularity",
                        "source_type": "social",
                        "url": "https://example.com/reddit-chip-bottleneck-floor",
                        "published_at": "2026-03-29T08:10:00+00:00",
                        "summary": "Reddit users are debating whether AI chip bottlenecks are easing.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/singularity"],
                    },
                    {
                        "source_name": "X @supplychainwatch",
                        "source_type": "social",
                        "url": "https://example.com/x-chip-bottleneck-floor",
                        "published_at": "2026-03-29T08:05:00+00:00",
                        "summary": "X users are comparing supplier checks and timeline revisions.",
                        "tags": ["provider:agent-reach:x"],
                    },
                ],
            },
            {
                "title": "Tesla Robotaxi Hits Zero-Crash Streak in Austin Pilot",
                "summary": "A company-and-product headline tied to autonomous driving deployment.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/tesla-robotaxi-floor",
                        "published_at": "2026-03-29T10:24:00+00:00",
                        "summary": "A company-and-product headline tied to autonomous driving deployment.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "AI startup funding frenzy sends the whole sector soaring overnight",
                "summary": "A very fresh single-source fallback headline with flashy wording but weak confirmation.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/flashy-ai-funding-floor",
                        "published_at": "2026-03-29T10:25:00+00:00",
                        "summary": "A very fresh single-source fallback headline with flashy wording but weak confirmation.",
                    }
                ],
            },
            {
                "title": "Single-source AI funding headline says the whole market is exploding",
                "summary": "Another flashy fallback-only single-source funding story with weak confirmation.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/flashy-ai-funding-floor-2",
                        "published_at": "2026-03-29T10:24:00+00:00",
                        "summary": "Another flashy fallback-only single-source funding story with weak confirmation.",
                    }
                ],
            },
        ]

    def positive_feedback_topic_candidates(self) -> list[dict]:
        return [
            {
                "title": "英伟达最怕的不是华为做出好芯片，而是华为做得太慢",
                "summary": "这不是普通芯片新闻，而是中国 AI 芯片、供应链和资本市场预期一起被改写的产业判断题。",
                "source_items": [
                    {
                        "source_name": "Reuters",
                        "source_type": "major_news",
                        "url": "https://example.com/reuters-nvidia-huawei-time-gap",
                        "published_at": "2026-03-29T10:10:00+00:00",
                        "summary": "中国 AI 芯片追赶节奏会影响英伟达、华为和整条供应链的市场预期。",
                    },
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-nvidia-huawei-time-gap",
                        "published_at": "2026-03-29T10:12:00+00:00",
                        "summary": "市场开始把时间差而不是单卡性能，视为这场产业竞争的真正胜负手。",
                    },
                ],
            },
            {
                "title": "AI 圈又有一轮新融资消息传出",
                "summary": "一条泛行业融资消息，热度不低，但缺少明确主角和判断空间。",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-generic-ai-funding",
                        "published_at": "2026-03-29T10:10:00+00:00",
                        "summary": "一条泛行业融资消息，热度不低，但缺少明确主角和判断空间。",
                    },
                    {
                        "source_name": "google-news-world",
                        "source_type": "major_news",
                        "url": "https://example.com/google-generic-ai-funding",
                        "published_at": "2026-03-29T10:12:00+00:00",
                        "summary": "海外媒体也在复述这轮融资热度，但缺少清晰 actor 和市场含义。",
                    },
                ],
            },
        ]

    def feature_filter_candidates(self) -> list[dict]:
        return [
            {
                "title": "AI如何改变打工人？我们和N个行业的「牛马」聊了聊：有人转型、有人想逃",
                "summary": "一篇偏 feature 和采访感的普通观察稿。",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/feature-ai-workers",
                        "published_at": "2026-03-29T10:25:00+00:00",
                        "summary": "一篇偏 feature 和采访感的普通观察稿。",
                    }
                ],
            }
        ]

    def diplomatic_protocol_candidates(self) -> list[dict]:
        return [
            {
                "title": "桑切斯“四年四访”彰显西中关系重要性 西班牙致力搭建“欧中桥梁”",
                "summary": "偏礼宾和关系表述的外交稿，没有明确的新判断点。",
                "source_items": [
                    {
                        "source_name": "chinanews.com.cn",
                        "source_type": "major_news",
                        "url": "https://example.com/sanchez-visit",
                        "published_at": "2026-03-29T10:12:00+00:00",
                        "summary": "偏礼宾和关系表述的外交稿，没有明确的新判断点。",
                    }
                ],
            }
        ]

    def official_commentary_candidates(self) -> list[dict]:
        return [
            {
                "title": "从元首外交密集日程看中国的自信、胸怀、担当",
                "summary": "一篇价值宣示型评论稿，没有明确的市场、产业或平台判断增量。",
                "source_items": [
                    {
                        "source_name": "人民日报客户端",
                        "source_type": "major_news",
                        "url": "https://example.com/china-confidence-commentary",
                        "published_at": "2026-03-29T10:15:00+00:00",
                        "summary": "一篇价值宣示型评论稿，没有明确的市场、产业或平台判断增量。",
                    }
                ],
            }
        ]

    def reddit_meta_thread_candidates(self) -> list[dict]:
        return [
            {
                "title": "Daily General Discussion and Advice Thread - April 16, 2026",
                "summary": "A recurring subreddit meta discussion thread for general chat.",
                "source_items": [
                    {
                        "source_name": "Reddit r/investing",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/investing/comments/1smx20t/daily_general_discussion_and_advice_thread_april/",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "A recurring subreddit meta discussion thread for general chat.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/investing"],
                    }
                ],
            }
        ]

    def reddit_meta_thread_extended_candidates(self) -> list[dict]:
        return [
            {
                "title": "Rate My Portfolio - r/Stocks Quarterly Thread March 2026",
                "summary": "A recurring sticky portfolio thread.",
                "source_items": [
                    {
                        "source_name": "Reddit r/stocks",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/stocks/comments/example/rate_my_portfolio/",
                        "published_at": "2026-03-29T10:00:00+00:00",
                        "summary": "A recurring sticky portfolio thread.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/stocks"],
                    }
                ],
            },
            {
                "title": "[D] Monthly Who's Hiring And Who Wants To Be Hired? Thread",
                "summary": "A monthly hiring sticky thread.",
                "source_items": [
                    {
                        "source_name": "Reddit r/MachineLearning",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/MachineLearning/comments/example/whos_hiring/",
                        "published_at": "2026-03-29T10:01:00+00:00",
                        "summary": "A monthly hiring sticky thread.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/MachineLearning"],
                    }
                ],
            },
            {
                "title": "[D] Self-Promotion Thread",
                "summary": "A recurring self-promotion sticky thread.",
                "source_items": [
                    {
                        "source_name": "Reddit r/MachineLearning",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/MachineLearning/comments/example/self_promo/",
                        "published_at": "2026-03-29T10:02:00+00:00",
                        "summary": "A recurring self-promotion sticky thread.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/MachineLearning"],
                    }
                ],
            },
            {
                "title": "Reminder: Please Do Not Submit Tech Support Or PC Build Questions",
                "summary": "A rules and moderation reminder sticky.",
                "source_items": [
                    {
                        "source_name": "Reddit r/hardware",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/hardware/comments/example/reminder_rules/",
                        "published_at": "2026-03-29T10:03:00+00:00",
                        "summary": "A rules and moderation reminder sticky.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/hardware"],
                    }
                ],
            },
            {
                "title": "Q1 2026 Letters & Reports",
                "summary": "A roundup thread collecting quarterly investor letters and reports.",
                "source_items": [
                    {
                        "source_name": "Reddit r/SecurityAnalysis",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/SecurityAnalysis/comments/example/q1_letters_reports/",
                        "published_at": "2026-03-29T10:04:00+00:00",
                        "summary": "A roundup thread collecting quarterly investor letters and reports.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/SecurityAnalysis"],
                    }
                ],
            },
        ]

    def reddit_live_or_archival_thread_candidates(self) -> list[dict]:
        return [
            {
                "title": "/r/WorldNews Live Thread: Russian Invasion of Ukraine Day 1512, Part 1 (Thread #1659)",
                "summary": "A rolling live thread for ongoing war updates.",
                "source_items": [
                    {
                        "source_name": "Reddit r/worldnews",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/worldnews/comments/1smygo6/rworldnews_live_thread_russian_invasion_of/",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "A rolling live thread for ongoing war updates.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/worldnews"],
                    }
                ],
            },
            {
                "title": "[Week 15 - 1979] Discussing A Berkshire Hathaway Shareholder Letter (Almost) Every Week",
                "summary": "An archival recurring discussion series.",
                "source_items": [
                    {
                        "source_name": "Reddit r/ValueInvesting",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/ValueInvesting/comments/1se1v2e/week_15_1979_discussing_a_berkshire_hathaway/",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "An archival recurring discussion series.",
                        "tags": ["provider:agent-reach:reddit", "subreddit:r/ValueInvesting"],
                    }
                ],
            },
        ]

    def reddit_low_specificity_candidates(self) -> list[dict]:
        return [
            {
                "title": "Markets are debating tariffs and macro outlook again",
                "summary": "A broad subreddit thread without a concrete company, product, or supply-chain angle.",
                "source_items": [
                    {
                        "source_name": "Reddit r/investing",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/investing/comments/1smlow1/markets_are_debating_tariffs_and_macro_outlook/",
                        "published_at": "2026-03-29T10:20:00+00:00",
                        "summary": "Retail investors are debating tariffs and macro outlook again.",
                        "tags": [
                            "provider:agent-reach:reddit",
                            "subreddit:r/investing",
                            "subreddit_kind:broad_market",
                        ],
                    }
                ],
            },
            {
                "title": "NVIDIA Blackwell supplier checks point to HBM bottlenecks easing",
                "summary": "A concrete supplier-chain thread tied to NVIDIA, HBM packaging, and named vendors.",
                "source_items": [
                    {
                        "source_name": "Reddit r/stocks",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/stocks/comments/1smspecific/nvidia_blackwell_supplier_checks_point_to_hbm/",
                        "published_at": "2026-03-29T10:22:00+00:00",
                        "summary": "Users compare HBM packaging and supplier checks tied to NVIDIA Blackwell shipments.",
                        "tags": [
                            "provider:agent-reach:reddit",
                            "subreddit:r/stocks",
                            "subreddit_kind:broad_market",
                            "outbound_domain:digitimes.com",
                        ],
                    }
                ],
            },
        ]

    def self_promotional_platform_candidates(self) -> list[dict]:
        return [
            {
                "title": "I built a 3D brain that watches AI agents think in real-time (free & gives your agents memory, shared memory audit trail and decision analysis)",
                "summary": "A single-source self-promotional launch post pushing a new tool.",
                "source_items": [
                    {
                        "source_name": "Reddit r/singularity",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/singularity/comments/1snpromo/i_built_a_3d_brain_that_watches_ai_agents/",
                        "published_at": "2026-03-29T10:24:00+00:00",
                        "summary": "A single-source self-promotional launch post pushing a new tool.",
                        "tags": [
                            "provider:agent-reach:reddit",
                            "subreddit:r/singularity",
                        ],
                    }
                ],
            }
        ]

    def exhibition_promo_candidates(self) -> list[dict]:
        return [
            {
                "title": "广交会上新：低空企业一天“卖货”超百台，新兴产业出海有新招",
                "summary": "一篇偏会展宣传和卖货口径的单源稿件。",
                "source_items": [
                    {
                        "source_name": "东方财富",
                        "source_type": "major_news",
                        "url": "https://example.com/canton-fair-drone-sales",
                        "published_at": "2026-03-29T10:18:00+00:00",
                        "summary": "一篇偏会展宣传和卖货口径的单源稿件。",
                    }
                ],
            }
        ]

    def x_queryless_news_candidates(self) -> list[dict]:
        return [
            {
                "title": "NYC Mayor and Governor Announce Pied-à-Terre Tax on Luxury Second Homes",
                "summary": "A local civic-policy headline without a clear AI, industry, market, or macro transmission angle.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/nyc-tax",
                        "published_at": "2026-03-29T10:21:00+00:00",
                        "summary": "A local civic-policy headline without a clear AI, industry, market, or macro transmission angle.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "Pope Leo XIV Visits Conflict-Torn Bamenda in Cameroon",
                "summary": "A general social-affairs visit headline without a clear market or industry angle.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/pope-bamenda",
                        "published_at": "2026-03-29T10:22:00+00:00",
                        "summary": "A general social-affairs visit headline without a clear market or industry angle.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "Trump Launches Naval Blockade of Iranian Ports in Strait of Hormuz",
                "summary": "A macro-risk headline tied to oil shipping and Strait of Hormuz disruption.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/hormuz-blockade",
                        "published_at": "2026-03-29T10:23:00+00:00",
                        "summary": "A macro-risk headline tied to oil shipping and Strait of Hormuz disruption.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "Trump Announces First Israel-Lebanon Leaders' Call in 34 Years",
                "summary": "A diplomatic process headline without a direct industry, market, or platform angle.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/israel-lebanon-call",
                        "published_at": "2026-03-29T10:23:30+00:00",
                        "summary": "A diplomatic process headline without a direct industry, market, or platform angle.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "Trump Administration Cancels Catholic Shelter Contract for Migrant Children",
                "summary": "A domestic policy and social-affairs headline without a clear market or industry transmission.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/migrant-children-contract",
                        "published_at": "2026-03-29T10:23:45+00:00",
                        "summary": "A domestic policy and social-affairs headline without a clear market or industry transmission.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "Senate Rejects Sanders' Push to Block $447 Million in Arms to Israel",
                "summary": "A legislative process headline without a direct industry, company, or macro transmission angle in the title itself.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/sanders-arms-vote",
                        "published_at": "2026-03-29T10:23:50+00:00",
                        "summary": "A legislative process headline without a direct industry, company, or macro transmission angle in the title itself.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "Trump Posts AI Image of Jesus Embrace, Draws Backlash After Pope Criticism",
                "summary": "A social-platform backlash headline without a direct market, industry, or macro transmission angle.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/ai-image-jesus",
                        "published_at": "2026-03-29T10:23:55+00:00",
                        "summary": "A social-platform backlash headline without a direct market, industry, or macro transmission angle.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "Elon Musk Spotlights Video Claiming Armed Citizens Stop More Shooters",
                "summary": "A viral culture-war clip headline without a direct company, industry, or macro transmission angle.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/armed-citizens-video",
                        "published_at": "2026-03-29T10:23:58+00:00",
                        "summary": "A viral culture-war clip headline without a direct company, industry, or macro transmission angle.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "Tesla Robotaxi Hits Zero-Crash Streak in Austin Pilot",
                "summary": "A company-and-product headline tied to autonomous driving deployment.",
                "source_items": [
                    {
                        "source_name": "agent-reach:x",
                        "source_type": "social",
                        "url": "twitter://trending/tesla-robotaxi",
                        "published_at": "2026-03-29T10:24:00+00:00",
                        "summary": "A company-and-product headline tied to autonomous driving deployment.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
        ]

    def x_generic_commentary_candidates(self) -> list[dict]:
        return [
            {
                "title": "Okay, something just shifted in how I think about AI agents",
                "summary": (
                    "Google unlocked Agent Mode in Gemini 3.1. OpenAI shipped Codex to general availability. "
                    "Anthropic launched Claude Cowork. What excites me most is the question it opens for every team: "
                    "if the agent can handle execution, what do you want to spend your human attention on?"
                ),
                "source_items": [
                    {
                        "source_name": "X @coo_pr_notes",
                        "source_type": "social",
                        "url": "https://x.com/coo_pr_notes/status/2044948612782915717",
                        "published_at": "2026-04-17T01:18:37+00:00",
                        "summary": (
                            "Google unlocked Agent Mode in Gemini 3.1. OpenAI shipped Codex to general availability. "
                            "Anthropic launched Claude Cowork. What excites me most is the question it opens for every team: "
                            "if the agent can handle execution, what do you want to spend your human attention on?"
                        ),
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "AMD to bring back Ryzen 7 5800X3D as AM4 10th Anniversary Edition",
                "summary": "A concrete chip-product headline tied to the PC upgrade cycle and semiconductor demand.",
                "source_items": [
                    {
                        "source_name": "X @chipbrief",
                        "source_type": "social",
                        "url": "https://x.com/chipbrief/status/2044999999999999999",
                        "published_at": "2026-04-17T01:10:00+00:00",
                        "summary": "A concrete chip-product headline tied to the PC upgrade cycle and semiconductor demand.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
        ]

    def x_manifesto_candidates(self) -> list[dict]:
        return [
            {
                "title": "$NIO #NIO #TESLA $TSLA Beyond Tesla: The Growing Army of Robotaxi Challengers For years, Tesla has dominated headlines a",
                "summary": (
                    "Beyond Tesla: The Growing Army of Robotaxi Challengers. For years, Tesla has dominated headlines "
                    "about autonomous driving and electric ride-hailing. The future of transportation is not a single-company story. "
                    "Waymo wins on safety. Baidu wins on scale. NIO wins on vertical silicon. NVIDIA wins on open ecosystems. "
                    "The bottom line is that no single company will dominate robotaxis."
                ),
                "source_items": [
                    {
                        "source_name": "X @jan_dekkers",
                        "source_type": "social",
                        "url": "https://x.com/jan_dekkers/status/2044899572762517785",
                        "published_at": "2026-04-16T22:03:45+00:00",
                        "summary": (
                            "Beyond Tesla: The Growing Army of Robotaxi Challengers. For years, Tesla has dominated headlines "
                            "about autonomous driving and electric ride-hailing. The future of transportation is not a single-company story. "
                            "Waymo wins on safety. Baidu wins on scale. NIO wins on vertical silicon. NVIDIA wins on open ecosystems. "
                            "The bottom line is that no single company will dominate robotaxis."
                        ),
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
            {
                "title": "Tesla Robotaxi Hits Zero-Crash Streak in Austin Pilot",
                "summary": "A company-and-product headline tied to autonomous driving deployment.",
                "source_items": [
                    {
                        "source_name": "X @robotaxiwatch",
                        "source_type": "social",
                        "url": "https://x.com/robotaxiwatch/status/2045000000000000001",
                        "published_at": "2026-04-17T01:24:00+00:00",
                        "summary": "A company-and-product headline tied to autonomous driving deployment.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
        ]

    def reddit_broad_market_question_candidates(self) -> list[dict]:
        return [
            {
                "title": "Why is the market reacting so positive to an indefinite US blockade?",
                "summary": "A broad market question thread asking why stocks rallied during a blockade scenario.",
                "source_items": [
                    {
                        "source_name": "Reddit r/stocks",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/stocks/comments/1sn2uz2/why_is_the_market_reacting_so_positive_to_an/",
                        "published_at": "2026-04-16T13:00:57+00:00",
                        "summary": "A broad market question thread asking why stocks rallied during a blockade scenario.",
                        "tags": [
                            "provider:agent-reach:reddit",
                            "subreddit:r/stocks",
                            "subreddit_kind:broad_market",
                        ],
                    }
                ],
            },
            {
                "title": "Is an oil shock almost unavoidable?",
                "summary": "A macro-risk question centered on oil supply and shipping disruption.",
                "source_items": [
                    {
                        "source_name": "Reddit r/stocks",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/stocks/comments/1smdxxx/is_an_oil_shock_almost_unavoidable/",
                        "published_at": "2026-04-16T12:21:04+00:00",
                        "summary": "A macro-risk question centered on oil supply and shipping disruption.",
                        "tags": [
                            "provider:agent-reach:reddit",
                            "subreddit:r/stocks",
                            "subreddit_kind:broad_market",
                        ],
                    }
                ],
            },
        ]

    def ai_meme_entertainment_candidates(self) -> list[dict]:
        return [
            {
                "title": "Squid Games but its with AI Agents ...",
                "summary": (
                    "Imagine a Squid Game scenario but every contestant is an AI agent. "
                    "Who would win? GPT-4 vs Claude vs Gemini in a battle royale. "
                    "This is the content we need. Pure entertainment."
                ),
                "source_items": [
                    {
                        "source_name": "Reddit r/artificial",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/artificial/comments/1sn3xxx/squid_games_but_its_with_ai_agents/",
                        "published_at": "2026-04-17T02:15:00+00:00",
                        "summary": (
                            "Imagine a Squid Game scenario but every contestant is an AI agent. "
                            "Who would win? GPT-4 vs Claude vs Gemini in a battle royale."
                        ),
                        "tags": [
                            "provider:agent-reach:reddit",
                            "subreddit:r/artificial",
                        ],
                    }
                ],
            },
            {
                "title": "NVIDIA H200 supply crunch forces hyperscalers to re-bid Q3 capacity",
                "summary": "A concrete AI-infra supply-chain headline about GPU allocation and hyperscaler capex.",
                "source_items": [
                    {
                        "source_name": "X @chipbrief",
                        "source_type": "social",
                        "url": "https://x.com/chipbrief/status/2045000000000000010",
                        "published_at": "2026-04-17T01:50:00+00:00",
                        "summary": "A concrete AI-infra supply-chain headline about GPU allocation and hyperscaler capex.",
                        "tags": ["provider:agent-reach:x"],
                    }
                ],
            },
        ]

    def enterprise_ai_synthesis_candidates(self) -> list[dict]:
        return [
            {
                "title": "Amazon + Anthropic; Enterprise AI Flywheel",
                "summary": (
                    "The enterprise AI flywheel is spinning. Amazon invested in Anthropic. "
                    "Microsoft doubled down on OpenAI. Google is building Gemini into everything. "
                    "The takeaway: enterprise AI adoption is accelerating and the flywheel effect "
                    "means winners keep winning. This is the new paradigm."
                ),
                "source_items": [
                    {
                        "source_name": "Reddit r/stocks",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/stocks/comments/1sn4xxx/amazon_anthropic_enterprise_ai_flywheel/",
                        "published_at": "2026-04-17T00:30:00+00:00",
                        "summary": (
                            "The enterprise AI flywheel is spinning. Amazon invested in Anthropic. "
                            "Microsoft doubled down on OpenAI. Google is building Gemini into everything. "
                            "The takeaway: enterprise AI adoption is accelerating."
                        ),
                        "tags": [
                            "provider:agent-reach:reddit",
                            "subreddit:r/stocks",
                            "subreddit_kind:broad_market",
                        ],
                    }
                ],
            },
            {
                "title": "Netflix earnings beat by $0.44, revenue topped estimates",
                "summary": "Netflix Q1 earnings beat consensus by $0.44 per share with revenue above estimates.",
                "source_items": [
                    {
                        "source_name": "Reddit r/stocks",
                        "source_type": "social",
                        "url": "https://www.reddit.com/r/stocks/comments/1sn5xxx/netflix_earnings_beat/",
                        "published_at": "2026-04-17T00:45:00+00:00",
                        "summary": "Netflix Q1 earnings beat consensus by $0.44 per share with revenue above estimates.",
                        "tags": [
                            "provider:agent-reach:reddit",
                            "subreddit:r/stocks",
                            "subreddit_kind:broad_market",
                        ],
                    }
                ],
            },
        ]

    def build_publish_request(self) -> dict:
        return {
            "account_name": "Test Account",
            "author": "Codex",
            "digest_max_chars": 120,
            "need_open_comment": 0,
            "only_fans_can_comment": 0,
        }

    def test_build_chinese_publish_markdown_can_render_x_thread_analysis_style_with_images(self) -> None:
        selected_topic = {
            "title": "国产AI芯片崛起：三大门派、瓜分英伟达",
            "summary": "国产芯片竞争正在进入更清晰的分化阶段。",
            "story_family": "国产 AI 芯片竞争",
            "recommended_angle": "国产 AI 芯片到底到了哪一步，真正值得看的竞争格局和替代空间是什么",
            "why_now": "这件事真正值得看的，不是新闻本身，而是国产替代会不会进入更真实的商业化阶段。",
            "selection_reason": "这不是单条快讯，而是能延伸出竞争格局与产业判断的题。",
            "source_mix": "Fallback 1",
            "source_items": [
                {
                    "source_name": "36kr",
                    "url": "https://36kr.com/p/3767894822925058",
                    "published_at": "2026-04-16T12:36:07+00:00",
                    "summary": "国产崛起，英伟达不再无敌。",
                }
            ],
        }
        article_package = {
            "selected_images": [
                {
                    "asset_id": "IMG-01",
                    "path": "https://img.36krcdn.com/example-1.jpg",
                    "caption": "芯片路线图对比图",
                },
                {
                    "asset_id": "IMG-02",
                    "path": "https://img.36krcdn.com/example-2.jpg",
                    "caption": "国产厂商出货与路线对比图",
                },
            ]
        }
        request = normalize_request(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "account_name": "Test Account",
                "language_mode": "chinese",
                "composition_style": "x_thread_analysis",
            }
        )

        markdown = build_chinese_publish_markdown(selected_topic, article_package, request, developer_tooling=False)

        self.assertIn("下面我不重复新闻稿", markdown)
        self.assertIn("## 先说结论", markdown)
        self.assertIn("## 媒体没说透的点", markdown)
        self.assertIn("## 真正该盯的变量", markdown)
        self.assertIn("国产 AI 芯片到底到了哪一步", markdown)
        self.assertIn("![IMG-01](https://img.36krcdn.com/example-1.jpg)", markdown)
        self.assertIn("![IMG-02](https://img.36krcdn.com/example-2.jpg)", markdown)

    def test_build_chinese_publish_markdown_uses_semiconductor_capex_copy_instead_of_generic_funding_copy(self) -> None:
        selected_topic = {
            "title": "台积电（TSMC）、阿斯麦（ASML）同步上修：AI 基建投资远未见顶",
            "summary": "从晶圆厂和设备商的最新口径，看这轮 AI 资本开支到底走到哪一步。",
            "keywords": ["AI", "TSMC", "ASML", "semiconductor", "capex", "台积电", "阿斯麦"],
            "source_items": [
                {
                    "source_name": "Bloomberg",
                    "url": "https://example.com/tsmc-capex",
                    "published_at": "2026-04-16T12:00:00+00:00",
                    "summary": "TSMC 将 2026 年营收增长预期从不足 30% 上修至超过 30%。",
                },
                {
                    "source_name": "ASML",
                    "url": "https://example.com/asml-orders",
                    "published_at": "2026-04-15T12:00:00+00:00",
                    "summary": "ASML 在 Q1 2026 财报中上调全年营收区间，并表示新增订单维持强劲。",
                },
            ],
        }
        request = normalize_request(
            {
                "analysis_time": "2026-04-19T12:30:00+00:00",
                "account_name": "Test Account",
                "language_mode": "chinese",
            }
        )

        markdown = build_chinese_publish_markdown(selected_topic, {}, request, developer_tooling=False)

        self.assertIn("从晶圆厂、设备订单和资本开支的最新口径，看这轮 AI 基建投资到底走到哪一步。", markdown)
        self.assertIn("先进制程产能和设备订单", markdown)
        self.assertIn("资本开支、产能扩张和先进封装", markdown)
        self.assertNotIn("融资意愿、订单能见度和预算投放", markdown)
        self.assertNotIn("招聘节奏、组织扩张和行业景气度", markdown)

    def test_build_subtitle_uses_semiconductor_capex_copy_instead_of_generic_heat_copy(self) -> None:
        request = {
            "language_mode": "chinese",
            "topic": "台积电（TSMC）、阿斯麦（ASML）同步上修：AI 基建投资远未见顶",
        }
        summary = {
            "topic": "台积电（TSMC）、阿斯麦（ASML）同步上修：AI 基建投资远未见顶",
            "market_relevance_zh": ["先进制程产能和设备订单", "资本开支、产能扩张和先进封装"],
        }

        subtitle = build_subtitle(request, summary, [])

        self.assertEqual(
            subtitle,
            "从晶圆厂、设备订单和资本开支的最新口径，看这轮 AI 基建投资到底走到哪一步。",
        )

    def test_cn_macro_profile_is_opt_in_only(self) -> None:
        request = {
            "language_mode": "chinese",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["国会格局、政策阻力和市场波动率"],
            "open_questions_zh": ["哪些州会决定参议院控制权？"],
        }

        subtitle = build_subtitle(request, source_summary, [])
        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )

        self.assertNotEqual(subtitle, "先从一个具体判断现场讲起，再看这条政治风险会怎样传到市场。")
        headings = [str(item.get("heading") or "") for item in sections if isinstance(item, dict)]
        self.assertFalse(any("核心矛盾" in heading for heading in headings))

    def test_cn_macro_profile_builds_zoom_in_section_order(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["中期选举、政策僵局和市场波动率重定价"],
            "open_questions_zh": ["北卡、阿拉斯加、俄亥俄谁会先动？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )

        headings = [str(item.get("heading") or "") for item in sections if isinstance(item, dict)]
        self.assertEqual(
            headings[:6],
            [
                "开头引入",
                "核心矛盾",
                "关键样本",
                "体感变量与传导链",
                "制度与政策层变量",
                "市场含义",
            ],
        )

    def test_cn_macro_profile_includes_core_contradiction_and_pain_chain(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["油价、消费和投票意愿会不会继续形成连锁反应？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        body = "\n\n".join(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict))

        self.assertIn("结构性错位", body)
        self.assertTrue(any(token in body for token in ("油价", "通勤", "消费", "耐心")))

    def test_cn_macro_profile_ending_uses_watchpoints_not_summary_recap(self) -> None:
        ending = article_draft_flow_runtime.build_cn_macro_watchpoint_ending(
            {
                "language_mode": "chinese",
                "composition_profile": "cn_macro_political_longform",
                "topic": "2026美国中期选举：华尔街大行内部怎么看？",
            },
            {
                "open_questions_zh": [
                    "第二季度油价会不会继续抬升？",
                    "关键州民调会不会继续收窄？",
                    "美联储人事确认会不会拖延？",
                ]
            },
            {"topic": "2026美国中期选举：华尔街大行内部怎么看？"},
        )

        self.assertIn("更值得盯的，是接下来几个验证节点", ending)
        self.assertIn("第二季度油价", ending)
        self.assertNotIn("综上所述", ending)

    def test_cn_macro_profile_subtitle_uses_macro_judgment_copy(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
        }

        subtitle = build_subtitle(request, summary, [])

        self.assertEqual(
            subtitle,
            "从华尔街已经开始重新定价的那条风险线，看这轮美国中期选举压力会怎样传到政策和市场。",
        )

    def test_cn_macro_profile_lede_uses_scene_setting_open(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
            "target_length_chars": 3600,
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "recommended_thesis_zh": "真正要看的不是表面选情热度，而是选民结构、经济体感和制度风险会不会一起把政治压力传到市场。",
        }

        lede = build_public_lede(request, source_summary, analysis_brief)

        self.assertTrue(lede.startswith("一场华尔街内部闭门讨论已经把风险提前摆上了桌面"))
        self.assertIn("已经开始重新定价风险的人", lede)
        self.assertNotIn("先说结论", lede)

    def test_cn_macro_profile_lede_mentions_closed_door_discussion_when_topic_implies_it(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
            "target_length_chars": 3600,
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "recommended_thesis_zh": "真正要看的不是表面选情热度，而是选民结构、经济体感和制度风险会不会一起把政治压力传到市场。",
        }

        lede = build_public_lede(request, source_summary, analysis_brief)

        self.assertIn("闭门讨论", lede)
        self.assertIn("华尔街", lede)

    def test_cn_macro_profile_expands_concrete_cases_when_named_inputs_exist(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["北卡、阿拉斯加、俄亥俄谁会先动？", "美联储人事确认会不会拖延？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        concrete_cases = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "关键样本")

        self.assertIn("北卡", concrete_cases)
        self.assertIn("阿拉斯加", concrete_cases)
        self.assertIn("俄亥俄", concrete_cases)

    def test_cn_macro_profile_market_implications_render_numbered_readthroughs(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["第二季度油价会不会继续抬升？", "关键州民调会不会继续收窄？", "美联储人事确认会不会拖延？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        market_section = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "市场含义")

        self.assertIn("第一，", market_section)
        self.assertIn("第二，", market_section)
        self.assertIn("第三，", market_section)

    def test_cn_macro_profile_market_implications_expand_into_concrete_asset_readthroughs(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["第二季度油价会不会继续抬升？", "关键州民调会不会继续收窄？", "美联储人事确认会不会拖延？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        market_section = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "市场含义")

        self.assertIn("利率敏感资产", market_section)
        self.assertIn("长端利率", market_section)
        self.assertGreaterEqual(market_section.count("。"), 5)

    def test_cn_macro_profile_market_implications_split_into_multiple_paragraphs(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["第二季度油价会不会继续抬升？", "关键州民调会不会继续收窄？", "美联储人事确认会不会拖延？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        market_section = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "市场含义")

        self.assertIn("\n\n第二，", market_section)
        self.assertIn("\n\n第三，", market_section)

    def test_cn_macro_profile_opening_section_does_not_duplicate_lede(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
            "target_length_chars": 3600,
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "recommended_thesis_zh": "真正要看的不是表面选情热度，而是选民结构、经济体感和制度风险会不会一起把政治压力传到市场。",
        }

        lede = build_public_lede(request, source_summary, analysis_brief)
        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        opening = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "开头引入")

        self.assertNotEqual(lede, opening)
        self.assertIn("风险已经", opening)
        self.assertNotIn("闭门讨论已经把风险提前摆上了桌面", opening)

    def test_cn_macro_profile_opening_section_adds_scene_level_detail(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
            "target_length_chars": 3600,
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "recommended_thesis_zh": "真正要看的不是表面选情热度，而是选民结构、经济体感和制度风险会不会一起把政治压力传到市场。",
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        opening = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "开头引入")

        self.assertIn("判断桌面", opening)
        self.assertIn("先被摆出来", opening)
        self.assertGreaterEqual(opening.count("。"), 3)

    def test_cn_macro_profile_concrete_cases_expand_into_multiple_short_paragraphs(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["北卡、阿拉斯加、俄亥俄谁会先动？", "美联储人事确认会不会拖延？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        concrete_cases = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "关键样本")

        self.assertIn("先看北卡。", concrete_cases)
        self.assertIn("再看阿拉斯加。", concrete_cases)
        self.assertIn("最后看俄亥俄。", concrete_cases)
        self.assertGreaterEqual(concrete_cases.count("。"), 4)

    def test_cn_macro_profile_concrete_cases_add_second_layer_for_each_case(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["北卡、阿拉斯加、俄亥俄谁会先动？", "美联储人事确认会不会拖延？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        concrete_cases = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "关键样本")

        self.assertIn("如果这里先松", concrete_cases)
        self.assertIn("如果这里先卡住", concrete_cases)
        self.assertIn("如果这里先传导", concrete_cases)
        self.assertGreaterEqual(concrete_cases.count("。"), 6)

    def test_cn_macro_profile_concrete_cases_split_into_case_paragraphs(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["北卡、阿拉斯加、俄亥俄谁会先动？", "美联储人事确认会不会拖延？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        concrete_cases = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "关键样本")

        self.assertIn("\n\n再看阿拉斯加。", concrete_cases)
        self.assertIn("\n\n最后看俄亥俄。", concrete_cases)

    def test_cn_macro_profile_institutional_bottleneck_strips_question_style_input(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["美联储人事确认会不会拖延？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        institutional = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "制度与政策层变量")

        self.assertIn("美联储人事确认拖延", institutional)
        self.assertNotIn("会不会拖延？会不会变成", institutional)

    def test_cn_macro_profile_pain_chain_section_expands_household_to_local_economy_chain(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["第二季度油价会不会继续抬升？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        pain_chain = next(str(item.get("paragraph") or "") for item in sections if isinstance(item, dict) and item.get("heading") == "体感变量与传导链")

        self.assertIn("通勤和取暖成本", pain_chain)
        self.assertIn("非必要支出", pain_chain)
        self.assertIn("订单和现金流", pain_chain)
        self.assertGreaterEqual(pain_chain.count("。"), 4)

    def test_cn_macro_profile_humanize_sections_keeps_cases_and_watchpoints_clean(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
            "human_signal_ratio": 35,
        }
        sections = [
            {"heading": "关键样本", "paragraph": "先看北卡。它最容易最早暴露主线风险是不是已经开始兑现。再看阿拉斯加。它更像制度和候选人路径会不会把局部压力放大的测试点。最后看俄亥俄。它最接近经济体感会不会真正传到更广范围定价的检验。"},
            {"heading": "结尾", "paragraph": "更值得盯的，是接下来几个验证节点：第一，北卡、阿拉斯加、俄亥俄谁会先动？第二，第二季度油价会不会继续抬升？第三，美联储人事确认会不会拖延？"},
        ]

        humanized = article_draft_flow_runtime.humanize_sections(sections, request)
        combined = "\n".join(str(item.get("paragraph") or "") for item in humanized)

        self.assertNotIn("再直白一点", combined)
        self.assertNotIn("说白了", combined)

    def test_cn_macro_profile_humanize_sections_skips_all_macro_structured_headings(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
            "human_signal_ratio": 35,
        }
        sections = [
            {"heading": "开头引入", "paragraph": "开头段。第二句。"},
            {"heading": "核心矛盾", "paragraph": "矛盾段。第二句。"},
            {"heading": "关键样本", "paragraph": "样本段。第二句。"},
            {"heading": "体感变量与传导链", "paragraph": "传导段。第二句。"},
            {"heading": "制度与政策层变量", "paragraph": "制度段。第二句。"},
            {"heading": "市场含义", "paragraph": "市场段。第二句。"},
            {"heading": "更远期展望", "paragraph": "展望段。第二句。"},
            {"heading": "结尾", "paragraph": "结尾段。第二句。"},
        ]

        with patch.object(
            article_draft_flow_runtime,
            "humanize_paragraph",
            side_effect=lambda text, **_: f"[H]{text}",
        ):
            humanized = article_draft_flow_runtime.humanize_sections(sections, request)

        self.assertEqual(humanized, sections)

    def test_cn_macro_profile_humanize_sections_keeps_real_generated_cases_and_ending_clean(self) -> None:
        request = {
            "language_mode": "chinese",
            "composition_profile": "cn_macro_political_longform",
            "topic": "2026美国中期选举：华尔街大行内部怎么看？",
            "human_signal_ratio": 35,
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "共和党在中期选举中面临结构性逆风。",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["低投票倾向选民和高参与度选民之间的结构性错位"],
            "open_questions_zh": ["北卡、阿拉斯加、俄亥俄谁会先动？", "第二季度油价会不会继续抬升？", "美联储人事确认会不会拖延？"],
        }

        sections = article_draft_flow_runtime.build_sections(
            request,
            source_summary,
            {},
            [],
            [],
            analysis_brief,
        )
        humanized = article_draft_flow_runtime.humanize_sections(sections, request)
        combined = "\n".join(str(item.get("paragraph") or "") for item in humanized)

        self.assertNotIn("再直白一点", combined)
        self.assertNotIn("说白了", combined)

    def build_publish_workflow_result(
        self,
        *,
        selected_images: list[dict],
        draft_image_candidates: list[dict],
        citations: list[dict] | None = None,
        style_profile_applied: dict | None = None,
    ) -> dict:
        article_package = {
            "title": "Agent hiring reset",
            "subtitle": "A concise subtitle",
            "lede": "This is the opening paragraph.",
            "sections": [
                {
                    "heading": "What changed",
                    "paragraph": "The market is re-pricing the story, but the evidence still matters.",
                }
            ],
            "draft_thesis": "The rebound is real enough to matter, but still needs verification.",
            "article_markdown": "# Agent hiring reset\n\nThe market is re-pricing the story.",
            "selected_images": selected_images,
            "citations": citations or [],
            "style_profile_applied": style_profile_applied or {},
        }
        return {
            "review_result": {"article_package": article_package},
            "draft_result": {
                "draft_context": {
                    "image_candidates": draft_image_candidates,
                }
            },
        }

    def test_normalize_request_inherits_author_from_feedback_profile(self) -> None:
        profile_dir = self.temp_dir / "feedback-profile-author"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "global.json").write_text(
            json.dumps(
                {
                    "scope": "global",
                    "topic": "global",
                    "request_defaults": {
                        "author": "不万能的阿伟",
                        "language_mode": "chinese",
                    },
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        request = normalize_request(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "account_name": "Test Account",
                "feedback_profile_dir": str(profile_dir),
            }
        )

        self.assertEqual(request["author"], "不万能的阿伟")
        self.assertEqual(request["feedback_profile_dir"], str(profile_dir))

    def test_hot_topic_discovery_ranks_business_candidate_first(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "top_n": 2,
            }
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(len(result["ranked_topics"]), 2)
        self.assertEqual(result["ranked_topics"][0]["title"], "AI agent hiring rebound becomes a business story")
        self.assertGreater(
            result["ranked_topics"][0]["score_breakdown"]["total_score"],
            result["ranked_topics"][1]["score_breakdown"]["total_score"],
        )
        self.assertTrue(result["ranked_topics"][0]["score_reasons"][0].startswith("新鲜度 "))
        self.assertIn("Hot Topic Discovery", result["report_markdown"])

    def test_hot_topic_discovery_applies_operator_topic_controls(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "preferred_topic_keywords": ["AI", "agent"],
                "excluded_topic_keywords": ["Celebrity"],
                "min_source_count": 2,
                "top_n": 5,
            }
        )
        self.assertEqual(len(result["ranked_topics"]), 1)
        self.assertEqual(result["ranked_topics"][0]["title"], "AI agent hiring rebound becomes a business story")
        self.assertEqual(result["filtered_out_topics"][0]["title"], "Celebrity airport outfit goes viral again")
        self.assertIn("Preferred keywords: AI, agent", result["report_markdown"])
        self.assertIn("Filtered out topics: 1", result["report_markdown"])

    def test_hot_topic_discovery_filters_non_shanghai_zhejiang_local_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.locality_filter_candidates(),
                "audience_keywords": ["AI", "robotics", "industry", "supply chain"],
                "top_n": 5,
            }
        )

        self.assertEqual(len(result["ranked_topics"]), 1)
        self.assertEqual(result["ranked_topics"][0]["title"], "上海发布具身智能产业新政，机器人供应链再获催化")
        self.assertEqual(result["filtered_out_topics"][0]["title"], "阜沙镇为阜沙制造出海保驾护航")

    def test_hot_topic_discovery_filters_weak_obituary_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.obituary_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(result["filtered_out_topics"][0]["title"], "王子杰逝世：创办丝芭、久游网，引进《劲舞团》")

    def test_hot_topic_discovery_filters_english_weak_obituary_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.english_obituary_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "Former Virginia Lt. Gov. Justin Fairfax and Wife Found Dead in Apparent Murder-Suicide",
        )

    def test_hot_topic_discovery_clusters_related_claude_story_family(self) -> None:
        raw_items = [
            {
                "title": "突发：Claude引入强实名制验证，必须真人手持证件自拍，否则直接封号",
                "summary": "Anthropic 开始收紧 Claude 账号验证。",
                "url": "https://example.com/claude-verify",
                "source_name": "36kr",
                "source_type": "major_news",
                "published_at": "2026-03-29T10:20:00+00:00",
            },
            {
                "title": "Claude Opus 4.7 或本周上线，但 Anthropic 要查你证件了",
                "summary": "新模型传闻与账号验证收紧在同一轮讨论中发酵。",
                "url": "https://example.com/claude-opus-rumor",
                "source_name": "google-news-search",
                "source_type": "major_news",
                "published_at": "2026-03-29T10:22:00+00:00",
            },
        ]

        clusters = hot_topic_discovery_runtime.cluster_discovered_items(raw_items, "")
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 2)

    def test_hot_topic_discovery_keeps_unrelated_queryless_reddit_posts_separate(self) -> None:
        raw_items = [
            {
                "title": "Netflix earnings beat by $0.44, revenue topped estimates",
                "summary": "Netflix first-quarter EPS beat expectations.",
                "url": "https://www.reddit.com/r/stocks/comments/live111/netflix_earnings_beat/",
                "source_name": "Reddit r/stocks",
                "source_type": "social",
                "published_at": "2026-04-16T20:13:29+00:00",
                "subreddit": "r/stocks",
                "tags": ["provider:agent-reach:reddit", "subreddit:r/stocks"],
                "outbound_url": "https://example.com/netflix-earnings",
            },
            {
                "title": "MacBook Neo sells out for April as demand for Apple's $599 laptop outpaces supply",
                "summary": "Apple's low-cost laptop is selling through early inventory.",
                "url": "https://www.reddit.com/r/hardware/comments/live222/macbook_neo_sells_out/",
                "source_name": "Reddit r/hardware",
                "source_type": "social",
                "published_at": "2026-04-16T22:20:53+00:00",
                "subreddit": "r/hardware",
                "tags": ["provider:agent-reach:reddit", "subreddit:r/hardware"],
                "outbound_url": "https://example.com/macbook-neo",
            },
            {
                "title": "AMD to bring back Ryzen 7 5800X3D as AM4 10th Anniversary Edition",
                "summary": "AMD may revive the 5800X3D for an anniversary refresh.",
                "url": "https://www.reddit.com/r/hardware/comments/live333/amd_5800x3d_anniversary/",
                "source_name": "Reddit r/hardware",
                "source_type": "social",
                "published_at": "2026-04-16T12:51:13+00:00",
                "subreddit": "r/hardware",
                "tags": ["provider:agent-reach:reddit", "subreddit:r/hardware"],
                "outbound_url": "https://example.com/amd-5800x3d",
            },
        ]

        clusters = hot_topic_discovery_runtime.cluster_discovered_items(raw_items, "")
        self.assertEqual(len(clusters), 3)
        self.assertTrue(all(len(cluster) == 1 for cluster in clusters))

    def test_hot_topic_discovery_does_not_overmerge_queryless_reddit_posts_with_shared_boilerplate(self) -> None:
        boilerplate = (
            "&#32; submitted by &#32; <a href='https://www.reddit.com/user/example'> /u/example </a> "
            "<br/> <span>[link]</span> &#32; <span>[comments]</span>"
        )
        raw_items = [
            {
                "title": "Netflix earnings beat by $0.44, revenue topped estimates",
                "summary": boilerplate + " Netflix Q1 revenue topped estimates.",
                "url": "https://www.reddit.com/r/stocks/comments/live111/netflix_earnings_beat/",
                "source_name": "Reddit r/stocks",
                "source_type": "social",
                "published_at": "2026-04-16T20:13:29+00:00",
                "subreddit": "r/stocks",
                "tags": ["provider:agent-reach:reddit", "subreddit:r/stocks"],
                "outbound_url": "https://example.com/netflix-earnings",
            },
            {
                "title": "Douglas Dynamics (PLOW): 50% Market Share, Earnings Rebound, Clear Catalyst",
                "summary": boilerplate + " PLOW winter season demand rebounds.",
                "url": "https://www.reddit.com/r/SecurityAnalysis/comments/live222/plow_catalyst/",
                "source_name": "Reddit r/SecurityAnalysis",
                "source_type": "social",
                "published_at": "2026-04-16T14:58:22+00:00",
                "subreddit": "r/SecurityAnalysis",
                "tags": ["provider:agent-reach:reddit", "subreddit:r/SecurityAnalysis"],
                "outbound_url": "https://example.com/plow-catalyst",
            },
            {
                "title": "MacBook Neo sells out for April as demand for Apple's $599 laptop outpaces supply",
                "summary": boilerplate + " Apple inventory is selling through faster than expected.",
                "url": "https://www.reddit.com/r/hardware/comments/live333/macbook_neo_sells_out/",
                "source_name": "Reddit r/hardware",
                "source_type": "social",
                "published_at": "2026-04-16T22:20:53+00:00",
                "subreddit": "r/hardware",
                "tags": ["provider:agent-reach:reddit", "subreddit:r/hardware"],
                "outbound_url": "https://example.com/macbook-neo",
            },
        ]

        clusters = hot_topic_discovery_runtime.cluster_discovered_items(raw_items, "")
        self.assertEqual(len(clusters), 3)
        self.assertTrue(all(len(cluster) == 1 for cluster in clusters))

    def test_hot_topic_discovery_filters_generic_reddit_research_chatter(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-17T03:20:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": [
                    {
                        "title": "Can frontier AI models actually read a painting? [R]",
                        "summary": "Research-thread style discussion without a clear company, market, or industry hook.",
                        "source_items": [
                            {
                                "source_name": "Reddit r/MachineLearning",
                                "source_type": "social",
                                "url": "https://www.reddit.com/r/MachineLearning/comments/live444/frontier_ai_models_read_painting/",
                                "published_at": "2026-04-16T11:00:17+00:00",
                                "tags": ["provider:agent-reach:reddit", "subreddit:r/MachineLearning"],
                            }
                        ],
                    }
                ],
                "top_n": 6,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "Can frontier AI models actually read a painting? [R]",
        )

    def test_hot_topic_discovery_filters_explicitly_offtopic_platform_posts(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-17T03:20:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": [
                    {
                        "title": "Somewhat off-topic: Pepsi Earnings and Mystery Departure at Hershey's",
                        "summary": "A clearly labeled off-topic post from a platform thread.",
                        "source_items": [
                            {
                                "source_name": "Reddit r/ValueInvesting",
                                "source_type": "social",
                                "url": "https://www.reddit.com/r/ValueInvesting/comments/live555/pepsi_earnings_hersheys/",
                                "published_at": "2026-04-16T09:08:00+00:00",
                                "tags": ["provider:agent-reach:reddit", "subreddit:r/ValueInvesting"],
                            }
                        ],
                    }
                ],
                "top_n": 6,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "Somewhat off-topic: Pepsi Earnings and Mystery Departure at Hershey's",
        )

    def test_hot_topic_discovery_filters_generic_platform_political_statement(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-17T03:20:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": [
                    {
                        "title": "Vance calls end of Ukraine aid 'one of the proudest' achievements of Trump administration",
                        "summary": "A politician-forward statement without a clear market, industry, or supply-chain angle.",
                        "source_items": [
                            {
                                "source_name": "Reddit r/geopolitics",
                                "source_type": "social",
                                "url": "https://www.reddit.com/r/geopolitics/comments/live666/vance_calls_end_of_ukraine_aid/",
                                "published_at": "2026-04-16T08:11:01+00:00",
                                "tags": ["provider:agent-reach:reddit", "subreddit:r/geopolitics"],
                            }
                        ],
                    }
                ],
                "top_n": 6,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "Vance calls end of Ukraine aid 'one of the proudest' achievements of Trump administration",
        )

    def test_normalize_agent_reach_items_builds_x_status_url_from_id_and_author(self) -> None:
        fake_fetch_result = {
            "channels_failed": [],
            "results_by_channel": {
                "x": {
                    "items": [
                        {
                            "id": "2044948612782915717",
                            "text": "Google unlocked Agent Mode in Gemini 3.1. OpenAI shipped Codex. Anthropic launched Claude Cowork.",
                            "createdAt": "Fri Apr 17 01:18:37 +0000 2026",
                            "author": {
                                "username": "coo_pr_notes",
                                "name": "Ken｜Startup COO & PR",
                            },
                        }
                    ]
                }
            },
        }

        with patch("hot_topic_discovery_runtime.fetch_agent_reach_channels", return_value=fake_fetch_result):
            items = hot_topic_discovery_runtime.normalize_agent_reach_items(
                "agent-reach:x",
                {
                    "analysis_time": datetime(2026, 4, 17, 4, 40, tzinfo=UTC),
                    "topic": "",
                    "query": "",
                    "limit": 10,
                },
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source_name"], "X @coo_pr_notes")
        self.assertEqual(items[0]["url"], "https://x.com/coo_pr_notes/status/2044948612782915717")
        self.assertEqual(items[0]["title"], "Google unlocked Agent Mode in Gemini 3.1")
        self.assertIn("provider:agent-reach:x", items[0]["tags"])

    def test_normalize_agent_reach_items_cleans_leading_mentions_from_x_title(self) -> None:
        fake_fetch_result = {
            "channels_failed": [],
            "results_by_channel": {
                "x": {
                    "items": [
                        {
                            "id": "2044940703688536400",
                            "text": "@xalil029 @elonmusk It's the Tesla Cybercab—the new autonomous robotaxi model. Elon just confirmed it in reply to that video.",
                            "createdAt": "Fri Apr 17 00:47:11 +0000 2026",
                            "author": {
                                "username": "grok",
                                "name": "Grok",
                            },
                        }
                    ]
                }
            },
        }

        with patch("hot_topic_discovery_runtime.fetch_agent_reach_channels", return_value=fake_fetch_result):
            items = hot_topic_discovery_runtime.normalize_agent_reach_items(
                "agent-reach:x",
                {
                    "analysis_time": datetime(2026, 4, 17, 4, 40, tzinfo=UTC),
                    "topic": "",
                    "query": "",
                    "limit": 10,
                },
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["title"], "It's the Tesla Cybercab—the new autonomous robotaxi model")
        self.assertEqual(items[0]["url"], "https://x.com/grok/status/2044940703688536400")

    def test_normalize_agent_reach_items_skips_reply_style_x_posts(self) -> None:
        fake_fetch_result = {
            "channels_failed": [],
            "results_by_channel": {
                "x": {
                    "items": [
                        {
                            "id": "2044940703688536400",
                            "text": "@xalil029 @elonmusk It's the Tesla Cybercab—the new autonomous robotaxi model.",
                            "createdAt": "Fri Apr 17 00:47:11 +0000 2026",
                            "inReplyToStatusId": "2044940628354580969",
                            "author": {
                                "username": "grok",
                                "name": "Grok",
                            },
                        },
                        {
                            "id": "2044446527100448899",
                            "text": "Tesla commits to a two-year HW roadmap aimed at unsupervised robotaxi deployment.",
                            "createdAt": "Fri Apr 17 00:50:00 +0000 2026",
                            "author": {
                                "username": "robotaxiwatch",
                                "name": "Robotaxi Watch",
                            },
                        },
                    ]
                }
            },
        }

        with patch("hot_topic_discovery_runtime.fetch_agent_reach_channels", return_value=fake_fetch_result):
            items = hot_topic_discovery_runtime.normalize_agent_reach_items(
                "agent-reach:x",
                {
                    "analysis_time": datetime(2026, 4, 17, 4, 40, tzinfo=UTC),
                    "topic": "",
                    "query": "",
                    "limit": 10,
                },
            )

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["source_name"], "X @robotaxiwatch")
        self.assertEqual(items[0]["title"], "Tesla commits to a two-year HW roadmap aimed at unsupervised robotaxi deployment")

    def test_hot_topic_discovery_applies_timeliness_penalty_to_rumor_like_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.rumor_penalty_candidates(),
                "audience_keywords": ["AI", "models", "platforms", "industry"],
                "top_n": 5,
            }
        )

        topics = {item["title"]: item for item in result["ranked_topics"]}
        self.assertLess(
            topics["Claude Opus 4.7 或本周上线？社交平台传闻再起"]["score_breakdown"]["timeliness"],
            topics["腾讯正式发布并开源混元世界模型 2.0"]["score_breakdown"]["timeliness"],
        )

    def test_hot_topic_discovery_international_first_defaults_primary_and_fallback_sources(self) -> None:
        request = hot_topic_discovery_runtime.normalize_request({"discovery_profile": "international_first"})
        self.assertEqual(
            request["sources"],
            ["agent-reach:reddit", "agent-reach:x", "google-news-world", "36kr"],
        )

    def test_hot_topic_discovery_international_first_prefers_reddit_x_backed_story(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.international_source_candidates(),
                "audience_keywords": ["AI", "models", "platforms", "industry"],
                "top_n": 5,
            }
        )

        self.assertEqual(
            result["ranked_topics"][0]["title"],
            "Claude rumor cycle returns again after another fake release window",
        )

    def test_hot_topic_discovery_international_first_penalizes_fallback_only_single_source_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.international_platform_priority_candidates(),
                "audience_keywords": ["AI", "chips", "supply chain", "industry"],
                "top_n": 5,
            }
        )

        self.assertEqual(
            result["ranked_topics"][0]["title"],
            "AI chip bottleneck debate spills from Reddit and X into supplier checks",
        )

    def test_hot_topic_discovery_international_first_keeps_platform_signal_ahead_of_flashy_fallback_edge_case(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.international_platform_priority_edge_candidates(),
                "audience_keywords": ["AI", "chips", "supply chain", "industry"],
                "top_n": 5,
            }
        )

        self.assertEqual(
            result["ranked_topics"][0]["title"],
            "One supplier quietly shifts guidance",
        )

    def test_hot_topic_discovery_international_first_requires_platform_backing_for_top_four(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.international_primary_source_floor_candidates(),
                "audience_keywords": ["AI", "chips", "supply chain", "industry"],
                "top_n": 6,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        self.assertEqual(
            ranked_titles,
            [
                "AI chip bottleneck debate spills from Reddit and X into supplier checks",
                "Tesla Robotaxi Hits Zero-Crash Streak in Austin Pilot",
            ],
        )

    def test_positive_feedback_topic_helpers_flag_hard_industry_actor_and_contrarian_signals(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.positive_feedback_topic_candidates(),
                "audience_keywords": ["AI", "chips", "supply chain", "market"],
                "top_n": 2,
            }
        )

        preferred = next(
            item
            for item in result["ranked_topics"]
            if item["title"] == "英伟达最怕的不是华为做出好芯片，而是华为做得太慢"
        )

        signals = hot_topic_discovery_runtime.positive_feedback_topic_signals(preferred)

        self.assertTrue(signals["hard_industry"])
        self.assertTrue(signals["clear_actor"])
        self.assertTrue(signals["contrarian_frame"])
        self.assertTrue(signals["china_or_market_relevance"])
        self.assertGreater(hot_topic_discovery_runtime.positive_feedback_topic_bonus(preferred), 0)

    def test_positive_feedback_topic_bonus_breaks_close_score_ties_for_stronger_industry_story(self) -> None:
        with (
            patch("hot_topic_discovery_runtime.timeliness_score", return_value=60),
            patch("hot_topic_discovery_runtime.discussion_score", return_value=50),
            patch("hot_topic_discovery_runtime.relevance_score", return_value=55),
            patch("hot_topic_discovery_runtime.depth_score", return_value=45),
            patch("hot_topic_discovery_runtime.seo_score", return_value=40),
        ):
            result = run_hot_topic_discovery(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.positive_feedback_topic_candidates(),
                    "audience_keywords": [],
                    "preferred_topic_keywords": [],
                    "top_n": 2,
                }
            )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        ranked_topics = {item["title"]: item for item in result["ranked_topics"]}
        preferred = ranked_topics["英伟达最怕的不是华为做出好芯片，而是华为做得太慢"]
        generic = ranked_topics["AI 圈又有一轮新融资消息传出"]

        self.assertEqual(ranked_titles[0], "英伟达最怕的不是华为做出好芯片，而是华为做得太慢")
        self.assertGreater(
            preferred["score_breakdown"]["positive_feedback_bonus"],
            generic["score_breakdown"]["positive_feedback_bonus"],
        )
        self.assertIn(
            "positive_feedback",
            " ".join(preferred["score_reasons"]),
        )

    def test_headline_frame_helpers_expose_conclusion_style_candidates_for_eligible_chinese_topic(self) -> None:
        request = {
            "language_mode": "chinese",
            "headline_hook_mode": "neutral",
            "topic": "英伟达和华为芯片竞赛继续升级",
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": [
                "真正值得看的不是芯片跑分，而是时间差和护城河。",
                "这会影响中国 AI 芯片和资本市场的定价方式。",
            ],
            "open_questions_zh": ["如果时间差被追平，英伟达估值逻辑会不会被改写？"],
        }
        source_summary = {
            "topic": "英伟达和华为芯片竞赛继续升级",
            "core_verdict": "真正值得看的不是参数，而是时间差。",
        }

        self.assertTrue(
            article_draft_flow_runtime.headline_frame_eligible(request, source_summary, analysis_brief)
        )
        candidates = article_draft_flow_runtime.headline_frame_candidates(request, source_summary, analysis_brief)

        self.assertGreaterEqual(len(candidates), 1)
        self.assertTrue(any("英伟达" in item for item in candidates))
        self.assertTrue(any("护城河" in item or "最怕的不是" in item for item in candidates))

    def test_headline_frame_finalize_title_prefers_stronger_frame_but_leaves_ineligible_obituary_plain(self) -> None:
        eligible_request = {
            "language_mode": "chinese",
            "headline_hook_mode": "neutral",
            "topic": "英伟达和华为芯片竞赛继续升级",
        }
        eligible_analysis_brief = {
            "market_or_reader_relevance_zh": [
                "真正值得看的不是芯片跑分，而是时间差和护城河。",
                "这会影响中国 AI 芯片和资本市场的定价方式。",
            ],
        }
        eligible_source_summary = {
            "topic": "英伟达和华为芯片竞赛继续升级",
            "core_verdict": "真正值得看的不是参数，而是时间差。",
        }

        framed_title = finalize_article_title(
            "英伟达和华为芯片竞赛继续升级",
            eligible_request,
            eligible_analysis_brief,
            eligible_source_summary,
        )

        self.assertNotEqual(framed_title, "英伟达和华为芯片竞赛继续升级")
        self.assertIn("英伟达", framed_title)
        self.assertTrue("护城河" in framed_title or "最怕的不是" in framed_title)

        obituary_title = "王子杰逝世：创办丝芭、久游网，引进《劲舞团》"
        plain_title = finalize_article_title(
            obituary_title,
            {
                "language_mode": "chinese",
                "headline_hook_mode": "neutral",
                "topic": obituary_title,
            },
            {"market_or_reader_relevance_zh": ["一则人物回顾向消息，缺少产业判断延伸。"]},
            {
                "topic": obituary_title,
                "core_verdict": "一则人物回顾向消息，缺少产业判断延伸。",
            },
        )

        self.assertEqual(plain_title, obituary_title)

    def test_hot_topic_discovery_filters_generic_feature_interview_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.feature_filter_candidates(),
                "audience_keywords": ["AI", "labor", "industry"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "AI如何改变打工人？我们和N个行业的「牛马」聊了聊：有人转型、有人想逃",
        )

    def test_hot_topic_discovery_filters_diplomatic_protocol_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.diplomatic_protocol_candidates(),
                "audience_keywords": ["macro", "policy", "industry"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "桑切斯“四年四访”彰显西中关系重要性 西班牙致力搭建“欧中桥梁”",
        )

    def test_hot_topic_discovery_filters_official_commentary_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.official_commentary_candidates(),
                "audience_keywords": ["macro", "policy", "industry"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "从元首外交密集日程看中国的自信、胸怀、担当",
        )

    def test_hot_topic_discovery_international_first_emits_operator_friendly_fields(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.international_source_candidates(),
                "audience_keywords": ["AI", "models", "platforms", "industry"],
                "top_n": 5,
            }
        )

        topic = result["ranked_topics"][0]
        for field in ("story_family", "recommended_angle", "why_now", "selection_reason", "risk_flags", "source_mix"):
            self.assertIn(field, topic)

    def test_hot_topic_discovery_filters_reddit_meta_discussion_threads(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.reddit_meta_thread_candidates(),
                "audience_keywords": ["AI", "markets", "industry"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "Daily General Discussion and Advice Thread - April 16, 2026",
        )

    def test_hot_topic_discovery_filters_extended_reddit_meta_threads(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.reddit_meta_thread_extended_candidates(),
                "audience_keywords": ["AI", "markets", "industry"],
                "top_n": 10,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertIn("Rate My Portfolio - r/Stocks Quarterly Thread March 2026", filtered_titles)
        self.assertIn("[D] Monthly Who's Hiring And Who Wants To Be Hired? Thread", filtered_titles)
        self.assertIn("[D] Self-Promotion Thread", filtered_titles)
        self.assertIn("Reminder: Please Do Not Submit Tech Support Or PC Build Questions", filtered_titles)
        self.assertIn("Q1 2026 Letters & Reports", filtered_titles)

    def test_hot_topic_discovery_filters_reddit_live_and_archival_threads(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.reddit_live_or_archival_thread_candidates(),
                "audience_keywords": ["AI", "markets", "industry", "geopolitics"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertIn("/r/WorldNews Live Thread: Russian Invasion of Ukraine Day 1512, Part 1 (Thread #1659)", filtered_titles)
        self.assertIn("[Week 15 - 1979] Discussing A Berkshire Hathaway Shareholder Letter (Almost) Every Week", filtered_titles)

    def test_hot_topic_discovery_filters_low_specificity_reddit_platform_chatter(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.reddit_low_specificity_candidates(),
                "audience_keywords": ["AI", "markets", "supply chain", "semis"],
                "top_n": 5,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertIn("NVIDIA Blackwell supplier checks point to HBM bottlenecks easing", ranked_titles)
        self.assertIn("Markets are debating tariffs and macro outlook again", filtered_titles)

    def test_hot_topic_discovery_filters_self_promotional_platform_posts(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.self_promotional_platform_candidates(),
                "audience_keywords": ["AI", "agents", "infrastructure"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "I built a 3D brain that watches AI agents think in real-time (free & gives your agents memory, shared memory audit trail and decision analysis)",
        )

    def test_hot_topic_discovery_filters_exhibition_promo_topics(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.exhibition_promo_candidates(),
                "audience_keywords": ["AI", "industry", "manufacturing", "exports"],
                "top_n": 5,
            }
        )

        self.assertEqual(result["ranked_topics"], [])
        self.assertEqual(
            result["filtered_out_topics"][0]["title"],
            "广交会上新：低空企业一天“卖货”超百台，新兴产业出海有新招",
        )

    def test_hot_topic_discovery_filters_generic_x_news_but_keeps_macro_and_company_cases(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.x_queryless_news_candidates(),
                "top_n": 5,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertIn("Trump Launches Naval Blockade of Iranian Ports in Strait of Hormuz", ranked_titles)
        self.assertIn("Tesla Robotaxi Hits Zero-Crash Streak in Austin Pilot", ranked_titles)
        self.assertIn("NYC Mayor and Governor Announce Pied-à-Terre Tax on Luxury Second Homes", filtered_titles)
        self.assertIn("Pope Leo XIV Visits Conflict-Torn Bamenda in Cameroon", filtered_titles)
        self.assertIn("Trump Announces First Israel-Lebanon Leaders' Call in 34 Years", filtered_titles)
        self.assertIn("Trump Administration Cancels Catholic Shelter Contract for Migrant Children", filtered_titles)
        self.assertIn("Senate Rejects Sanders' Push to Block $447 Million in Arms to Israel", filtered_titles)
        self.assertIn("Trump Posts AI Image of Jesus Embrace, Draws Backlash After Pope Criticism", filtered_titles)
        self.assertIn("Elon Musk Spotlights Video Claiming Armed Citizens Stop More Shooters", filtered_titles)

    def test_hot_topic_discovery_filters_generic_x_commentary_but_keeps_concrete_x_industry_case(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-17T04:40:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.x_generic_commentary_candidates(),
                "audience_keywords": ["AI", "chips", "semiconductors", "market"],
                "top_n": 5,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertEqual(
            ranked_titles,
            ["AMD to bring back Ryzen 7 5800X3D as AM4 10th Anniversary Edition"],
        )
        self.assertIn("Okay, something just shifted in how I think about AI agents", filtered_titles)

    def test_hot_topic_discovery_filters_x_manifesto_but_keeps_concrete_robotaxi_headline(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-17T04:40:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.x_manifesto_candidates(),
                "audience_keywords": ["AI", "robotaxi", "autonomy", "market"],
                "top_n": 5,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertEqual(ranked_titles, ["Tesla Robotaxi Hits Zero-Crash Streak in Austin Pilot"])
        self.assertIn(
            "$NIO #NIO #TESLA $TSLA Beyond Tesla: The Growing Army of Robotaxi Challengers For years, Tesla has dominated headlines a",
            filtered_titles,
        )

    def test_hot_topic_discovery_filters_generic_broad_market_question_but_keeps_concrete_macro_case(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-17T04:40:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.reddit_broad_market_question_candidates(),
                "audience_keywords": ["macro", "markets", "energy", "shipping"],
                "top_n": 5,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertEqual(ranked_titles, ["Is an oil shock almost unavoidable?"])
        self.assertIn("Why is the market reacting so positive to an indefinite US blockade?", filtered_titles)

    def test_hot_topic_discovery_filters_ai_meme_entertainment_but_keeps_concrete_ai_infra_case(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-17T04:40:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.ai_meme_entertainment_candidates(),
                "audience_keywords": ["AI", "chips", "semiconductors", "GPU", "supply chain"],
                "top_n": 5,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertEqual(
            ranked_titles,
            ["NVIDIA H200 supply crunch forces hyperscalers to re-bid Q3 capacity"],
        )
        self.assertIn("Squid Games but its with AI Agents ...", filtered_titles)

    def test_hot_topic_discovery_filters_enterprise_ai_synthesis_but_keeps_concrete_earnings_case(self) -> None:
        result = run_hot_topic_discovery(
            {
                "analysis_time": "2026-04-17T04:40:00+00:00",
                "discovery_profile": "international_first",
                "manual_topic_candidates": self.enterprise_ai_synthesis_candidates(),
                "audience_keywords": ["AI", "earnings", "enterprise", "market"],
                "top_n": 5,
            }
        )

        ranked_titles = [item["title"] for item in result["ranked_topics"]]
        filtered_titles = {item["title"] for item in result["filtered_out_topics"]}
        self.assertEqual(
            ranked_titles,
            ["Netflix earnings beat by $0.44, revenue topped estimates"],
        )
        self.assertIn("Amazon + Anthropic; Enterprise AI Flywheel", filtered_titles)

    def test_cluster_merges_reddit_and_x_oil_items(self) -> None:
        raw_items = [
            {
                "title": "Is an oil shock almost unavoidable?",
                "summary": "Oil supply disruption risks are rising.",
                "url": "https://www.reddit.com/r/stocks/comments/oil111/oil_shock/",
                "source_name": "Reddit r/stocks",
                "source_type": "social",
                "published_at": "2026-04-16T12:21:04+00:00",
                "subreddit": "r/stocks",
                "tags": ["provider:agent-reach:reddit", "subreddit:r/stocks"],
            },
            {
                "title": "The current oil situation in Europe",
                "text": "Europe can survive without oil from Iran. Oil supply chains are shifting.",
                "source_name": "agent-reach:x",
                "source_type": "social",
                "published_at": "2026-04-16T14:00:00+00:00",
                "tags": ["provider:agent-reach:x"],
            },
        ]
        clusters = hot_topic_discovery_runtime.cluster_discovered_items(raw_items, "")
        self.assertEqual(len(clusters), 1, "Reddit and X oil items should merge into one cluster")
        self.assertEqual(len(clusters[0]), 2)

    def test_cluster_merges_reddit_and_x_semiconductor_items(self) -> None:
        raw_items = [
            {
                "title": "AMD GPU supply crunch forces hyperscalers to re-bid Q3 capacity",
                "summary": "AMD chip supply constraints are hitting cloud providers hard.",
                "url": "https://www.reddit.com/r/hardware/comments/amd111/amd_gpu_supply/",
                "source_name": "Reddit r/hardware",
                "source_type": "social",
                "published_at": "2026-04-16T12:51:13+00:00",
                "subreddit": "r/hardware",
                "tags": ["provider:agent-reach:reddit", "subreddit:r/hardware"],
            },
            {
                "title": "AMD GPU supply crunch deepens",
                "text": "AMD GPU supply constraints are now affecting hyperscaler capacity bids for Q3.",
                "source_name": "agent-reach:x",
                "source_type": "social",
                "published_at": "2026-04-16T15:00:00+00:00",
                "tags": ["provider:agent-reach:x"],
            },
        ]
        clusters = hot_topic_discovery_runtime.cluster_discovered_items(raw_items, "")
        self.assertEqual(len(clusters), 1, "Reddit and X AMD GPU supply items should merge")
        self.assertEqual(len(clusters[0]), 2)

    def test_cluster_does_not_merge_unrelated_cross_platform_items(self) -> None:
        raw_items = [
            {
                "title": "Netflix earnings beat by $0.44, revenue topped estimates",
                "summary": "Netflix Q1 EPS beat expectations.",
                "url": "https://www.reddit.com/r/stocks/comments/nflx111/netflix_earnings/",
                "source_name": "Reddit r/stocks",
                "source_type": "social",
                "published_at": "2026-04-16T20:13:29+00:00",
                "subreddit": "r/stocks",
                "tags": ["provider:agent-reach:reddit", "subreddit:r/stocks"],
            },
            {
                "title": "The current oil situation in Europe",
                "text": "Europe can survive without oil from Iran. Oil supply chains are shifting.",
                "source_name": "agent-reach:x",
                "source_type": "social",
                "published_at": "2026-04-16T14:00:00+00:00",
                "tags": ["provider:agent-reach:x"],
            },
        ]
        clusters = hot_topic_discovery_runtime.cluster_discovered_items(raw_items, "")
        self.assertEqual(len(clusters), 2, "Netflix earnings and oil situation should stay separate")

    def test_article_publish_exports_wechat_draft_package(self) -> None:
        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir),
                "draft_mode": "balanced",
            }
        )
        package = result["publish_package"]
        payload = package["draftbox_payload_template"]["articles"][0]
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["selected_topic"]["title"], "AI agent hiring rebound becomes a business story")
        self.assertTrue(Path(result["wechat_html_path"]).exists())
        self.assertTrue(Path(result["publish_package_path"]).exists())
        self.assertTrue(Path(result["automatic_acceptance_path"]).exists())
        self.assertTrue(Path(result["automatic_acceptance_report_path"]).exists())
        self.assertEqual(result["review_gate"]["status"], "awaiting_human_review")
        self.assertFalse(result["review_gate"]["approved"])
        self.assertEqual(result["publication_readiness"], "ready")
        self.assertEqual(result["workflow_manual_review"]["status"], "not_required")
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "ready")
        self.assertTrue(result["automatic_acceptance"]["accepted"])
        self.assertEqual(result["automatic_acceptance"]["status"], "accepted")
        self.assertEqual(result["automatic_acceptance"]["workflow_publication_gate"]["publication_readiness"], "ready")
        self.assertEqual(result["push_stage"]["status"], "not_requested")
        self.assertLessEqual(len(package["digest"]), 120)
        self.assertFalse(package["push_ready"])
        self.assertEqual(package["push_readiness"]["status"], "missing_cover_image")
        self.assertTrue(package["push_readiness"]["credentials_required"])
        self.assertEqual(package["push_readiness"]["cover_source"], "missing")
        self.assertEqual(package["editor_anchor_mode"], "hidden")
        self.assertEqual(payload["title"], package["title"])
        self.assertEqual(payload["content"], package["content_html"])
        self.assertEqual(payload["thumb_media_id"], "{{WECHAT_THUMB_MEDIA_ID}}")
        self.assertNotIn(package["editor_anchors"][0]["text"], package["content_html"])
        self.assertIn("run_wechat_push_draft.cmd", result["next_push_command"])
        self.assertIn("Human Review Gate", result["report_markdown"])
        self.assertIn("Automatic Acceptance", result["report_markdown"])
        self.assertIn("Publish Readiness", result["report_markdown"])
        self.assertNotIn("Chinese business and investing readers", package["content_markdown"])
        self.assertNotIn("AI and technology readers will care", package["content_markdown"])
        self.assertNotIn("真实事件、趋势或争议", package["content_markdown"])
        self.assertNotIn("有解释价值，不只是情绪型热度", package["content_markdown"])
        self.assertNotIn("google-news-search, 36kr", package["content_markdown"])
        self.assertNotIn("现在最直接的观察对象是", package["content_markdown"])
        self.assertIn("最先能确认的变化其实很具体", package["content_markdown"])
        self.assertIn("这轮讨论没有很快掉下去", package["content_markdown"])
        self.assertIn("## 接下来盯什么", package["content_markdown"])
        self.assertIn("第一，", package["content_markdown"])

    def test_build_publish_package_emits_shared_contract_fields(self) -> None:
        package = build_publish_package(
            self.build_publish_workflow_result(selected_images=[], draft_image_candidates=[]),
            {"title": "AI agent hiring rebound becomes a business story", "keywords": ["AI", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["contract_version"], "publish-package/v1")
        self.assertIn("content_markdown", package)
        self.assertIn("content_html", package)
        self.assertIn("platform_hints", package)
        self.assertIn("operator_notes", package)
        self.assertIn("sections", package)
        self.assertIn("cover_plan", package)
        self.assertIn("lede", package)
        self.assertIn("selected_images", package)
        self.assertIn("draft_thesis", package)
        self.assertIn("citations", package)
        self.assertIsInstance(package["platform_hints"], dict)
        self.assertIsInstance(package["operator_notes"], list)

    def test_article_publish_routes_shared_package_to_requested_channel(self) -> None:
        fake_toutiao_push_result = {
            "status": "ok",
            "push_backend": "browser_session",
            "review_gate": {"status": "approved"},
            "browser_session": {"manifest_path": "", "result_path": ""},
            "article_url": "",
            "title": "AI agent hiring rebound becomes a business story",
        }

        with patch("article_publish_runtime.push_publish_package_to_toutiao", return_value=fake_toutiao_push_result) as push_mock:
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing", "industry"],
                    "output_dir": str(self.temp_dir / "publish-channel-toutiao"),
                    "publish_channel": "toutiao",
                    "push_to_channel": True,
                    "human_review_approved": True,
                    "human_review_approved_by": "Editor",
                    "cover_image_path": str(self.temp_dir / "cover-channel.png"),
                }
            )

        push_mock.assert_called_once()
        self.assertEqual(result["channel_push_stage"]["channel"], "toutiao")
        self.assertEqual(result["channel_push_stage"]["status"], "ok")
        self.assertEqual(result["status"], "ok")
        self.assertIn("publish_package", result)

    def test_article_publish_channel_push_does_not_duplicate_legacy_wechat_push(self) -> None:
        fake_wechat_push_result = {
            "status": "ok",
            "push_backend": "api",
            "review_gate": {"status": "approved"},
            "workflow_publication_gate": {"publication_readiness": "ready", "manual_review": {}},
            "draft_result": {"media_id": "draft-123"},
            "push_readiness": {"status": "ready_for_api_push"},
        }

        with patch("article_publish_runtime.push_publish_package_to_wechat", return_value=fake_wechat_push_result) as push_mock:
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing", "industry"],
                    "output_dir": str(self.temp_dir / "publish-channel-wechat-no-dup"),
                    "publish_channel": "wechat",
                    "push_to_channel": True,
                    "push_to_wechat": True,
                    "human_review_approved": True,
                    "human_review_approved_by": "Editor",
                    "wechat_app_id": "wx-test",
                    "wechat_app_secret": "secret-test",
                    "allow_insecure_inline_credentials": True,
                    "cover_image_path": str(self.temp_dir / "cover-channel-wechat.png"),
                }
            )

        push_mock.assert_called_once()
        self.assertEqual(result["channel_push_stage"]["status"], "ok")
        self.assertEqual(result["push_stage"]["status"], "not_requested")

    def test_article_publish_surfaces_workflow_publication_gate_on_result_and_acceptance(self) -> None:
        workflow_result = self.build_publish_workflow_result(
            selected_images=[],
            draft_image_candidates=[],
        )
        workflow_result["manual_review"] = {
            "required": True,
            "status": "awaiting_reddit_operator_review",
            "required_count": 2,
            "high_priority_count": 1,
            "summary": "Queued Reddit comment signals still need operator review before publication.",
            "next_step": "Review the queued Reddit comment signals before publication.",
            "queue": [
                {
                    "title": "Semicap capex thread",
                    "priority_level": "high",
                    "summary": "Partial Reddit comment sampling still needs operator review.",
                }
            ],
        }
        workflow_result["publication_readiness"] = "blocked_by_reddit_operator_review"

        with patch("article_publish_runtime.run_article_workflow", return_value=workflow_result):
            result = run_article_publish(
                {
                    "analysis_time": "2026-03-29T10:30:00+00:00",
                    "manual_topic_candidates": self.manual_topic_candidates(),
                    "audience_keywords": ["AI", "business", "investing", "industry"],
                    "account_name": "Test Account",
                    "author": "Codex",
                    "output_dir": str(self.temp_dir / "reddit-gate"),
                }
            )

        self.assertEqual(result["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(result["workflow_manual_review"]["status"], "awaiting_reddit_operator_review")
        self.assertEqual(result["workflow_manual_review"]["required_count"], 2)
        self.assertEqual(
            result["automatic_acceptance"]["workflow_publication_gate"]["publication_readiness"],
            "blocked_by_reddit_operator_review",
        )
        self.assertEqual(
            result["automatic_acceptance"]["workflow_publication_gate"]["manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertIn("## Workflow Publication Gate", result["automatic_acceptance"]["report_markdown"])
        self.assertIn("blocked_by_reddit_operator_review", result["automatic_acceptance"]["report_markdown"])
        self.assertIn("awaiting_reddit_operator_review", result["automatic_acceptance"]["report_markdown"])

    def test_article_publish_chinese_mode_localizes_sources_and_title(self) -> None:
        request = {
            "analysis_time": "2026-03-29T10:30:00+00:00",
            "manual_topic_candidates": self.manual_topic_candidates(),
            "audience_keywords": ["AI", "business", "investing", "industry"],
            "account_name": "Test Account",
            "author": "Codex",
            "output_dir": str(self.temp_dir / "zh-article"),
            "draft_mode": "balanced",
            "language_mode": "chinese",
            "max_images": 2,
        }
        result = run_article_publish(request)
        package = result["publish_package"]

        self.assertEqual(package["article_framework"], "deep_analysis")
        self.assertTrue(any("\u4e00" <= ch <= "\u9fff" for ch in package["title"]))
        self.assertIn("## 来源", package["content_markdown"])
        self.assertNotEqual(package["article_framework"], "story")
        self.assertIn("## 接下来盯什么", package["content_markdown"])
        self.assertIn("第一，", package["content_markdown"])

    def test_article_publish_defaults_to_traffic_headline_hook_for_chinese_mode(self) -> None:
        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir / "traffic-title"),
                "language_mode": "chinese",
            }
        )

        package = result["publish_package"]
        self.assertTrue(package["title"].startswith("刚刚，"))
        self.assertEqual(
            package["style_profile_applied"]["effective_request"]["headline_hook_mode"],
            "traffic",
        )

    def test_chinese_readability_localizes_key_company_and_term_mentions(self) -> None:
        markdown_text = (
            "TSMC 和 ASML 先后上修指引。\n\n"
            "order intake 继续维持在很强的水平，ongoing discussions around export controls 也没有消失。\n"
        )

        polished = article_draft_flow_runtime.polish_chinese_article_markdown(
            markdown_text,
            {"language_mode": "chinese", "topic": "AI 基建投资"},
            {},
            {},
        )

        self.assertIn("台积电（TSMC）", polished)
        self.assertIn("阿斯麦（ASML）", polished)
        self.assertIn("新增订单（order intake）", polished)
        self.assertIn("出口管制（export controls）", polished)

    def test_chinese_readability_merges_short_concession_and_turn_sentences(self) -> None:
        markdown_text = (
            "这个担心不是完全没有道理。\n\n"
            "但过去几天，台积电（TSMC）和阿斯麦（ASML）先后交出来的数字，已经把这条线按了回去。\n"
        )

        polished = article_draft_flow_runtime.polish_chinese_article_markdown(
            markdown_text,
            {"language_mode": "chinese", "topic": "AI 基建投资"},
            {},
            {},
        )

        self.assertIn("这个担心不是完全没有道理。但过去几天", polished)
        self.assertNotIn("这个担心不是完全没有道理。\n\n但过去几天", polished)

    def test_chinese_readability_replaces_repeated_conclusion_ending_with_watchpoints(self) -> None:
        markdown_text = (
            "## 结尾\n\n"
            "所以如果现在再问我，AI 泡沫是不是快破了，我的回答会是：至少从 TSMC 和 ASML 这组最新信号看，还没有。\n\n"
            "这轮故事显然还没讲完。\n"
        )
        request = {
            "language_mode": "chinese",
            "topic": "台积电（TSMC）、阿斯麦（ASML）同步上修：AI 基建投资远未见顶",
            "audience_keywords": ["AI", "semiconductor", "chips", "infrastructure"],
        }
        analysis_brief = {
            "market_or_reader_relevance_zh": ["真正值得看的是 AI 基建链条会不会继续兑现。"],
            "open_questions_zh": ["云厂商 capex、Blackwell 出货、先进封装订单会不会继续维持紧张？"],
        }
        source_summary = {
            "topic": request["topic"],
            "core_verdict": "AI 基建投资仍未见顶。",
        }

        polished = article_draft_flow_runtime.polish_chinese_article_markdown(
            markdown_text,
            request,
            analysis_brief,
            source_summary,
        )

        self.assertIn("更值得盯的，是接下来几个验证节点", polished)
        self.assertIn("capex", polished)
        self.assertIn("Blackwell", polished)
        self.assertIn("先进封装", polished)

    def test_article_publish_chinese_mode_strips_noisy_source_branding_title_copy(self) -> None:
        noisy_candidates = [
            {
                "title": "MicroYuan completes A+ round financing | 36kr first release: what is confirmed, what is not",
                "summary": "A biotech AI startup announced financing and a new collaboration platform.",
                "source_items": [
                    {
                        "source_name": "36kr",
                        "source_type": "major_news",
                        "url": "https://example.com/36kr-weiyuan",
                        "published_at": "2026-03-29T10:00:00+00:00",
                        "summary": "36kr reports the financing round and platform release.",
                    }
                ],
            }
        ]
        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": noisy_candidates,
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir / "zh-noisy-title"),
                "language_mode": "chinese",
            }
        )
        package = result["publish_package"]
        self.assertNotIn("36kr", package["title"].lower())
        self.assertNotIn("first release", package["title"].lower())
        self.assertNotIn("what is confirmed", package["title"].lower())
        self.assertIn("## \u6765\u6e90", package["content_markdown"])

    def test_build_news_request_from_topic_adds_clean_public_title_and_bilingual_fields(self) -> None:
        selected_topic = {
            "title": "微元合成获3亿元A+轮融资，联合发布AI生物计算开放合作平台 | 36氪首发：哪些已经确认，哪些仍未确认",
            "summary": "一家 AI 生物计算公司完成融资并发布平台。",
            "keywords": ["AI", "融资", "平台"],
            "score_breakdown": {"relevance": 70, "debate": 55},
            "source_count": 2,
            "source_items": [
                {
                    "source_name": "36kr",
                    "source_type": "major_news",
                    "url": "https://example.com/36kr-weiyuan",
                    "published_at": "2026-03-29T10:00:00+00:00",
                    "summary": "36kr reports the financing round and platform release.",
                }
            ],
        }
        request = build_news_request_from_topic(
            selected_topic,
            {
                "analysis_time": datetime(2026, 3, 29, 10, 30, tzinfo=UTC),
                "topic": "",
            },
        )

        self.assertEqual(request["topic"], "微元合成获3亿元A+轮融资，联合发布AI生物计算开放合作平台")
        self.assertTrue(all(item.get("claim_text_zh") for item in request["claims"]))
        self.assertTrue(request["market_relevance_zh"])
        self.assertIn("哪些事实已经能被多源确认", request["questions"][0])
        self.assertEqual(request["claims"][0]["claim_text_zh"], "微元合成获3亿元A+轮融资")
        self.assertEqual(request["claims"][1]["claim_text_zh"], "联合发布AI生物计算开放合作平台")
        self.assertNotIn("真实事件、趋势或争议", request["claims"][0]["claim_text_zh"])

    def test_build_news_request_from_topic_uses_developer_tooling_relevance_without_business_shorthand(self) -> None:
        selected_topic = {
            "title": "Claude Code 泄露源码后，真正值得看的隐藏能力",
            "summary": "The leaked code shows browser control, tool calls, and workflow orchestration entrypoints.",
            "keywords": ["Claude Code", "browser", "tool call", "workflow", "permission"],
            "score_breakdown": {"relevance": 72, "debate": 58},
            "source_count": 2,
            "source_items": [
                {
                    "source_name": "X @agintender",
                    "source_type": "social",
                    "url": "https://x.com/agintender/status/1",
                    "published_at": "2026-03-29T10:00:00+00:00",
                    "summary": "The thread walks through browser control and multi-step task execution entrypoints.",
                }
            ],
        }

        request = build_news_request_from_topic(
            selected_topic,
            {
                "analysis_time": datetime(2026, 3, 29, 10, 30, tzinfo=UTC),
                "topic": "",
                "language_mode": "chinese",
            },
        )

        joined_zh = " ".join(request["market_relevance_zh"])
        claim_zh = " ".join(item["claim_text_zh"] for item in request["claims"])
        candidate_copy = " ".join(
            str(candidate.get(field) or "").strip()
            for candidate in request["candidates"]
            for field in ("text_excerpt", "post_summary", "media_summary")
            if str(candidate.get(field) or "").strip()
        )
        self.assertIn("产品边界、工具调用与权限设计", request["market_relevance_zh"])
        self.assertIn("浏览器控制、工作流编排", request["market_relevance_zh"])
        self.assertIn("这条线程顺着浏览器控制和多步任务执行入口做了拆解。", claim_zh)
        self.assertNotIn("产品能力表面、工具调用边界和权限设计", joined_zh)
        self.assertNotIn("浏览器控制、工作流编排与多步开发者执行", joined_zh)
        self.assertNotIn("融资意愿、订单能见度和预算投放", joined_zh)
        self.assertNotIn("预算", joined_zh)
        self.assertNotIn("订单", joined_zh)
        self.assertNotIn("thread walks through browser control", claim_zh.lower())
        self.assertNotIn("thread walks through browser control", candidate_copy.lower())
        self.assertNotIn("Official docs describe Claude Code browser control and Chrome integration", candidate_copy)

    def test_build_news_request_from_topic_uses_semiconductor_capex_relevance_instead_of_generic_funding_shorthand(self) -> None:
        selected_topic = {
            "title": "台积电（TSMC）、阿斯麦（ASML）同步上修：AI 基建投资远未见顶",
            "summary": "从晶圆厂和设备商的最新口径，看这轮 AI 资本开支到底走到哪一步。",
            "keywords": ["AI", "TSMC", "ASML", "semiconductor", "capex", "台积电", "阿斯麦"],
            "score_breakdown": {"relevance": 72, "debate": 58},
            "source_count": 2,
            "source_items": [
                {
                    "source_name": "Bloomberg",
                    "source_type": "major_news",
                    "url": "https://example.com/tsmc-capex",
                    "published_at": "2026-04-16T12:00:00+00:00",
                    "summary": "TSMC 将 2026 年营收增长预期从不足 30% 上修至超过 30%。",
                },
                {
                    "source_name": "ASML",
                    "source_type": "major_news",
                    "url": "https://example.com/asml-orders",
                    "published_at": "2026-04-15T12:00:00+00:00",
                    "summary": "ASML 在 Q1 2026 财报中上调全年营收区间，并表示新增订单维持强劲。",
                },
            ],
        }

        request = build_news_request_from_topic(
            selected_topic,
            {
                "analysis_time": datetime(2026, 4, 19, 12, 30, tzinfo=UTC),
                "topic": "",
                "language_mode": "chinese",
            },
        )

        joined_zh = " ".join(request["market_relevance_zh"])
        self.assertNotIn("融资意愿、订单能见度和预算投放", joined_zh)
        self.assertNotIn("招聘节奏、组织扩张和行业景气度", joined_zh)
        self.assertTrue(
            any(
                phrase in joined_zh
                for phrase in ("先进制程产能", "设备订单", "资本开支", "先进封装", "产能扩张")
            )
        )

    def test_article_publish_preserves_manual_screenshot_enrichment_and_uses_screenshot_cover(self) -> None:
        screenshot_path = self.temp_dir / "claude-code-root.png"
        screenshot_path.write_bytes(b"claude-code-root")

        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": [
                    {
                        "title": "Claude Code 泄露源码后，真正值得看的 7 个秘密功能",
                        "summary": "The leaked code and docs point to browser control, tool use boundaries, and workflow orchestration changes.",
                        "source_items": [
                            {
                                "source_name": "X @agintender",
                                "source_type": "social",
                                "url": "https://x.com/agintender/status/2038921508999901274",
                                "published_at": "2026-03-29T10:00:00+00:00",
                                "summary": "The thread captures browser control entrypoints, subagents, and permission boundaries.",
                                "root_post_screenshot_path": str(screenshot_path),
                                "artifact_manifest": [
                                    {
                                        "role": "root_post_screenshot",
                                        "path": str(screenshot_path),
                                        "summary": "Screenshot of the original X thread discussing Claude Code hidden capabilities.",
                                    }
                                ],
                                "post_summary": "Screenshot-backed thread about Claude Code browser control and hidden capabilities.",
                            },
                            {
                                "source_name": "Anthropic docs / Chrome",
                                "source_type": "major_news",
                                "url": "https://docs.anthropic.com/en/docs/claude-code/chrome",
                                "published_at": "2026-03-29T09:50:00+00:00",
                                "summary": "Official docs describe Claude Code browser control and Chrome integration.",
                            },
                        ],
                    }
                ],
                "audience_keywords": ["Claude Code", "developer tools", "workflow", "browser"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir / "claude-code-screenshot-publish"),
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
                "draft_mode": "image_first",
                "image_strategy": "screenshots_only",
                "target_length_chars": 2800,
                "headline_hook_mode": "traffic",
                "max_images": 2,
            }
        )

        selected_source = result["selected_topic"]["source_items"][0]
        self.assertEqual(selected_source["root_post_screenshot_path"], str(screenshot_path))
        self.assertEqual(len(selected_source["artifact_manifest"]), 1)

        news_request = json.loads(Path(result["news_request_path"]).read_text(encoding="utf-8-sig"))
        candidate = news_request["candidates"][0]
        self.assertEqual(candidate["root_post_screenshot_path"], str(screenshot_path))
        self.assertEqual(len(candidate["artifact_manifest"]), 1)

        draft_result = json.loads(Path(result["workflow_stage"]["draft_result_path"]).read_text(encoding="utf-8-sig"))
        package = draft_result["article_package"]
        headings = [section["heading"] for section in package["sections"]]
        joined_text = "\n".join([package["lede"], *(section["paragraph"] for section in package["sections"])])

        self.assertGreaterEqual(len(package["selected_images"]), 1)
        self.assertEqual(package["selected_images"][0]["role"], "root_post_screenshot")
        self.assertTrue(package["selected_images"][0]["caption"])
        self.assertNotIn("登录", package["selected_images"][0]["caption"])
        self.assertNotIn("/url:", package["selected_images"][0]["caption"])
        self.assertGreaterEqual(len(package["sections"]), 6)
        self.assertIn("哪些已经确认，哪些还不能写死", headings)
        self.assertIn("这件事的分水岭在哪", headings)
        self.assertNotIn("预算", joined_text)
        self.assertNotIn("订单", joined_text)
        self.assertNotIn("定价", joined_text)
        self.assertNotIn("经营变量", joined_text)
        self.assertNotIn("登录", joined_text)
        self.assertNotIn("/url:", joined_text)

        publish_package = result["publish_package"]
        self.assertEqual(publish_package["cover_plan"]["selected_cover_role"], "root_post_screenshot")
        self.assertEqual(publish_package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(publish_package["push_readiness"]["cover_source"], "dedicated_cover_candidate")
        self.assertIn("screenshot cover candidate", publish_package["cover_plan"]["selection_reason"].lower())
        self.assertIn("真正值得看的", publish_package["title"])
        self.assertFalse(publish_package["title"].startswith("刚刚，"))
        self.assertNotEqual(publish_package["title"], "刚刚，Claude Code 泄露源码后")
        self.assertNotIn("产品能力表面、工具调用边界和权限设计", publish_package["content_markdown"])
        self.assertNotIn("浏览器控制、工作流编排与多步开发者执行", publish_package["content_markdown"])
        self.assertNotIn("登录", publish_package["content_markdown"])
        self.assertNotIn("/url:", publish_package["content_markdown"])
        self.assertLessEqual(publish_package["content_markdown"].count("产品边界、权限设计"), 1)
        self.assertLessEqual(publish_package["content_markdown"].count("浏览器控制、工作流编排"), 1)
        self.assertLessEqual(publish_package["content_markdown"].count("能力边界和开发者工作流"), 1)
        self.assertEqual(
            publish_package["cover_plan"]["selection_reason"],
            publish_package["cover_plan"]["cover_selection_reason"],
        )
        self.assertTrue(publish_package["cover_plan"]["selected_cover_caption"])
        self.assertNotIn("登录", publish_package["cover_plan"]["selected_cover_caption"])
        self.assertNotIn("/url:", publish_package["cover_plan"]["selected_cover_caption"])
        regression = publish_package["regression_checks"]
        self.assertEqual(regression["section_count"], 7)
        self.assertEqual(regression["target_length_chars"], 2800)
        self.assertGreaterEqual(regression["body_char_count"], 2100)
        self.assertGreaterEqual(regression["content_char_count"], 2200)
        self.assertTrue(regression["checks"]["title_complete"])
        self.assertTrue(regression["checks"]["expanded_sections_ok"])
        self.assertTrue(regression["checks"]["ui_capture_noise_clean"])
        self.assertTrue(regression["checks"]["generic_business_talk_clean"])
        self.assertTrue(regression["checks"]["developer_focus_copy_clean"])
        self.assertTrue(regression["checks"]["developer_focus_phrase_varied"])
        self.assertTrue(regression["checks"]["wechat_transition_phrase_varied"])
        self.assertTrue(regression["checks"]["wechat_tail_tone_clean"])
        self.assertLessEqual(max(regression["developer_focus_phrase_hits"].values(), default=0), 1)
        self.assertEqual(sum(regression["wechat_tail_tone_phrase_hits"].values()), 0)
        self.assertTrue(regression["checks"]["localized_copy_expected"])
        self.assertTrue(regression["checks"]["localized_copy_clean"])
        self.assertTrue(regression["checks"]["first_image_is_screenshot"])
        self.assertTrue(regression["checks"]["screenshot_cover_preferred"])
        self.assertTrue(regression["checks"]["cover_reason_present"])
        self.assertTrue(regression["checks"]["cover_caption_clean"])
        self.assertEqual(regression["cover"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(regression["cover"]["cover_source"], "dedicated_cover_candidate")
        self.assertEqual(regression["first_image"]["role"], "root_post_screenshot")
        self.assertTrue(regression["first_image"]["caption"])
        self.assertFalse(regression["english_leak_samples"])
        self.assertEqual(regression["forbidden_phrase_hits"]["登录"], 0)
        self.assertEqual(regression["forbidden_phrase_hits"]["/url:"], 0)
        self.assertLessEqual(max(regression["wechat_transition_phrase_hits"].values(), default=0), 1)
        self.assertTrue(result["automatic_acceptance"]["accepted"])
        self.assertFalse(result["automatic_acceptance"]["decision_required"])
        self.assertFalse(result["automatic_acceptance"]["optimization_options"])
        self.assertFalse(result["automatic_acceptance"]["advisory_options"])

    def test_article_publish_prefer_images_keeps_screenshot_cover_with_mixed_visual_candidates(self) -> None:
        screenshot_path = self.temp_dir / "claude-code-mixed-root.png"
        media_path = self.temp_dir / "claude-code-mixed-media.png"
        screenshot_path.write_bytes(b"claude-code-mixed-root")
        media_path.write_bytes(b"claude-code-mixed-media")

        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": [
                    {
                        "title": "Claude Code 娉勯湶婧愮爜鍚庯紝鐪熸鍊煎緱鐪嬬殑 7 涓瀵嗗姛鑳?",
                        "summary": "The leaked code and docs point to browser control, tool use boundaries, and workflow orchestration changes.",
                        "source_items": [
                            {
                                "source_name": "X @agintender",
                                "source_type": "social",
                                "url": "https://x.com/agintender/status/2038921508999901274",
                                "published_at": "2026-03-29T10:00:00+00:00",
                                "summary": "The thread captures browser control entrypoints, subagents, and permission boundaries.",
                                "root_post_screenshot_path": str(screenshot_path),
                                "artifact_manifest": [
                                    {
                                        "role": "root_post_screenshot",
                                        "path": str(screenshot_path),
                                        "summary": "Screenshot of the original X thread discussing Claude Code hidden capabilities.",
                                    }
                                ],
                                "media_items": [
                                    {
                                        "source_url": "https://pbs.twimg.com/media/claude-code-hidden-capabilities.jpg",
                                        "local_artifact_path": str(media_path),
                                        "ocr_text_raw": "Browser mode entrypoint shown next to remote control and workflow panels.",
                                    }
                                ],
                                "post_summary": "Screenshot-backed thread about Claude Code browser control and hidden capabilities.",
                                "media_summary": "Browser-captured image from the original X post showing workflow panels.",
                            },
                            {
                                "source_name": "Anthropic docs / Chrome",
                                "source_type": "major_news",
                                "url": "https://docs.anthropic.com/en/docs/claude-code/chrome",
                                "published_at": "2026-03-29T09:50:00+00:00",
                                "summary": "Official docs describe Claude Code browser control and Chrome integration.",
                            },
                        ],
                    }
                ],
                "audience_keywords": ["Claude Code", "developer tools", "workflow", "browser"],
                "account_name": "Test Account",
                "author": "Codex",
                "output_dir": str(self.temp_dir / "claude-code-prefer-images-mixed-publish"),
                "language_mode": "chinese",
                "article_framework": "deep_analysis",
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "target_length_chars": 2800,
                "headline_hook_mode": "traffic",
                "max_images": 2,
            }
        )

        selected_source = result["selected_topic"]["source_items"][0]
        self.assertEqual(selected_source["root_post_screenshot_path"], str(screenshot_path))
        self.assertEqual(len(selected_source["artifact_manifest"]), 1)
        self.assertEqual(len(selected_source["media_items"]), 1)
        self.assertEqual(selected_source["media_items"][0]["local_artifact_path"], str(media_path))

        news_request = json.loads(Path(result["news_request_path"]).read_text(encoding="utf-8-sig"))
        candidate = news_request["candidates"][0]
        self.assertEqual(candidate["root_post_screenshot_path"], str(screenshot_path))
        self.assertEqual(len(candidate["artifact_manifest"]), 1)
        self.assertEqual(len(candidate["media_items"]), 1)
        self.assertEqual(candidate["media_items"][0]["local_artifact_path"], str(media_path))

        draft_result = json.loads(Path(result["workflow_stage"]["draft_result_path"]).read_text(encoding="utf-8-sig"))
        package = draft_result["article_package"]
        selected_images = package["selected_images"]
        selected_roles = [item["role"] for item in selected_images]
        post_media = next(item for item in selected_images if item["role"] == "post_media")

        self.assertGreaterEqual(len(selected_images), 2)
        self.assertEqual(selected_images[0]["role"], "root_post_screenshot")
        self.assertNotEqual(selected_images[0]["caption"], selected_source["media_summary"])
        self.assertIn("post_media", selected_roles)
        self.assertEqual(post_media["path"], str(media_path))
        self.assertEqual(post_media["status"], "local_ready")
        self.assertNotEqual(selected_images[0]["path"], post_media["path"])
        self.assertEqual(
            selected_images[0]["caption"],
            "这是一条带截图的线程，集中展示了 Claude Code 的浏览器控制和隐藏能力。",
        )
        self.assertEqual(
            post_media["caption"],
            "图里能看到浏览器模式入口，旁边就是远程控制和工作流面板。",
        )

        publish_package = result["publish_package"]
        cover_candidates = publish_package["cover_plan"]["cover_candidates"]
        cover_candidate_roles = [item["role"] for item in cover_candidates]

        self.assertEqual(cover_candidates[0]["role"], "post_media")
        self.assertIn("post_media", cover_candidate_roles)
        self.assertIn("root_post_screenshot", cover_candidate_roles)
        self.assertEqual(publish_package["cover_plan"]["selected_cover_role"], "root_post_screenshot")
        self.assertEqual(publish_package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(publish_package["push_readiness"]["cover_source"], "dedicated_cover_candidate")

        regression = publish_package["regression_checks"]
        self.assertTrue(regression["checks"]["first_image_is_screenshot"])
        self.assertTrue(regression["checks"]["screenshot_cover_preferred"])
        self.assertTrue(regression["checks"]["localized_copy_expected"])
        self.assertTrue(regression["checks"]["localized_copy_clean"])
        self.assertEqual(regression["first_image"]["role"], "root_post_screenshot")
        self.assertEqual(regression["cover"]["selected_cover_role"], "root_post_screenshot")
        self.assertEqual(regression["cover"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(regression["cover"]["cover_source"], "dedicated_cover_candidate")
        self.assertGreaterEqual(regression["body_char_count"], 2300)
        self.assertGreaterEqual(regression["content_char_count"], 2900)
        self.assertFalse(regression["english_leak_samples"])
        self.assertLessEqual(max(regression["developer_focus_phrase_hits"].values(), default=0), 1)
        self.assertTrue(regression["checks"]["wechat_transition_phrase_varied"])
        self.assertTrue(regression["checks"]["wechat_tail_tone_clean"])
        self.assertLessEqual(max(regression["wechat_transition_phrase_hits"].values(), default=0), 1)
        self.assertEqual(sum(regression["wechat_tail_tone_phrase_hits"].values()), 0)
        self.assertNotIn("Official docs describe Claude Code", publish_package["content_markdown"])
        self.assertNotIn("thread captures browser control", publish_package["content_markdown"].lower())
        self.assertNotIn("Browser mode entrypoint shown next to remote control", publish_package["content_markdown"])
        self.assertNotIn("Screenshot-backed thread about Claude Code", publish_package["content_markdown"])
        self.assertTrue(result["automatic_acceptance"]["accepted"])
        self.assertFalse(result["automatic_acceptance"]["advisory_options"])

    def test_article_publish_can_be_push_ready_with_explicit_cover_override(self) -> None:
        cover_path = self.temp_dir / "cover.png"
        cover_path.write_bytes(b"fake-cover")
        result = run_article_publish(
            {
                "analysis_time": "2026-03-29T10:30:00+00:00",
                "manual_topic_candidates": self.manual_topic_candidates(),
                "audience_keywords": ["AI", "business", "investing", "industry"],
                "output_dir": str(self.temp_dir / "with-cover"),
                "cover_image_path": str(cover_path),
                "wechat_app_id": "wx-test",
                "wechat_app_secret": "secret",
                "allow_insecure_inline_credentials": True,
            }
        )
        readiness = result["publish_package"]["push_readiness"]
        self.assertTrue(result["publish_package"]["push_ready"])
        self.assertEqual(readiness["status"], "ready_for_api_push")
        self.assertEqual(readiness["cover_source"], "request_override")
        self.assertEqual(result["review_gate"]["status"], "awaiting_human_review")

    def test_build_publish_package_prefers_dedicated_cover_candidate_before_body_fallback(self) -> None:
        body_image = self.temp_dir / "body-screenshot.png"
        dedicated_cover = self.temp_dir / "dedicated-cover.png"
        body_image.write_bytes(b"body-screenshot")
        dedicated_cover.write_bytes(b"dedicated-cover")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-01",
                    "image_id": "IMG-01",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "Body screenshot",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-01",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body screenshot",
                    "source_name": "fixture",
                    "score": 88,
                },
                {
                    "image_id": "IMG-02",
                    "role": "post_media",
                    "path": str(dedicated_cover),
                    "source_url": "",
                    "summary": "Dedicated cover image",
                    "source_name": "fixture",
                    "score": 72,
                },
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-02")
        self.assertEqual(package["cover_plan"]["selection_mode"], "dedicated_candidate")
        self.assertIn("dedicated cover candidate", package["cover_plan"]["selection_reason"].lower())
        self.assertEqual(package["push_readiness"]["status"], "ready_for_api_push")
        self.assertEqual(package["push_readiness"]["cover_source"], "dedicated_cover_candidate")
        self.assertIn("Prefer a text-free cover", package["cover_plan"]["cover_prompt"])
        self.assertIn("No Chinese text", package["cover_plan"]["cover_prompt"])

    def test_build_publish_package_prefers_clean_body_caption_for_screenshot_cover(self) -> None:
        body_image = self.temp_dir / "body-screenshot-clean.png"
        body_image.write_bytes(b"body-screenshot-clean")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-01",
                    "image_id": "IMG-01",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "原始帖子截图，保留了页面上下文。",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-01",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": '- text: 新鲜事一网打尽 - link "登录": - /url: /login - progressbar "加载中":',
                    "source_name": "fixture",
                    "score": 88,
                }
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "Claude Code 真正值得看的 7 个秘密功能", "keywords": ["Claude Code", "browser", "workflow"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-01")
        self.assertEqual(package["cover_plan"]["selected_cover_caption"], "原始帖子截图，保留了页面上下文。")
        self.assertNotIn("登录", package["cover_plan"]["selected_cover_caption"])
        self.assertNotIn("/url:", package["cover_plan"]["selected_cover_caption"])

    def test_build_publish_package_falls_back_to_first_usable_body_image_when_no_dedicated_cover_exists(self) -> None:
        body_image = self.temp_dir / "body-hero.png"
        body_image.write_bytes(b"body-hero")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-11",
                    "image_id": "IMG-11",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "Body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-11",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body hero",
                    "source_name": "fixture",
                    "score": 80,
                }
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-11")
        self.assertEqual(package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertIn("screenshot cover candidate", package["cover_plan"]["selection_reason"].lower())
        self.assertEqual(package["push_readiness"]["status"], "ready_for_api_push")
        self.assertEqual(package["push_readiness"]["cover_source"], "dedicated_cover_candidate")
        self.assertTrue(package["regression_checks"]["checks"]["screenshot_cover_preferred"])
        self.assertTrue(package["regression_checks"]["checks"]["cover_reason_present"])

    def test_build_publish_package_keeps_first_body_order_when_zero_indexed(self) -> None:
        first_body = self.temp_dir / "body-first.png"
        second_body = self.temp_dir / "body-second.png"
        first_body.write_bytes(b"body-first")
        second_body.write_bytes(b"body-second")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "image_id": "IMG-31",
                    "role": "root_post_screenshot",
                    "path": str(first_body),
                    "source_url": "",
                    "caption": "First body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                },
                {
                    "image_id": "IMG-32",
                    "role": "root_post_screenshot",
                    "path": str(second_body),
                    "source_url": "",
                    "caption": "Second body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_section_2",
                },
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-31",
                    "role": "root_post_screenshot",
                    "path": str(first_body),
                    "source_url": "",
                    "summary": "First body hero",
                    "source_name": "fixture",
                    "score": 80,
                },
                {
                    "image_id": "IMG-32",
                    "role": "root_post_screenshot",
                    "path": str(second_body),
                    "source_url": "",
                    "summary": "Second body hero",
                    "source_name": "fixture",
                    "score": 80,
                },
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-31")
        self.assertEqual(package["cover_plan"]["cover_candidates"][0]["body_order"], 0)
        self.assertEqual(package["cover_plan"]["selection_mode"], "screenshot_candidate")
        self.assertIn("screenshot cover candidate", package["cover_plan"]["selection_reason"].lower())

    def test_cover_source_preference_prefers_official_real_photo_for_semiconductor_topic(self) -> None:
        official_cover = self.temp_dir / "official-asml-cover.jpg"
        generated_cover = self.temp_dir / "generated-semiconductor-cover.png"
        official_cover.write_bytes(b"official-asml-cover")
        generated_cover.write_bytes(b"generated-semiconductor-cover")

        request = {
            **self.build_publish_request(),
            "topic": "台积电（TSMC）、阿斯麦（ASML）同步上修：AI 基建投资远未见顶",
            "audience_keywords": ["AI", "semiconductor", "chips", "infrastructure"],
            "cover_image_path": "",
            "cover_image_url": "",
            "image_strategy": "mixed",
        }
        cover_candidates = [
            {
                "asset_id": "IMG-GEN",
                "role": "post_media",
                "path": str(generated_cover),
                "source_url": "",
                "caption": "AI generated semiconductor hero art",
                "source_name": "local_generated",
                "status": "local_ready",
                "score": 94,
                "body_order": 0,
                "from_selected_images": True,
            },
            {
                "asset_id": "IMG-OFFICIAL",
                "role": "post_media",
                "path": str(official_cover),
                "source_url": "https://www.asml.com/newsroom/media/image.jpg",
                "caption": "ASML 官方设备照片",
                "source_name": "ASML newsroom",
                "status": "local_ready",
                "score": 78,
                "body_order": 1,
                "from_selected_images": True,
            },
        ]

        plan = select_cover_plan([], cover_candidates, request)

        self.assertEqual(plan["selected_cover_asset_id"], "IMG-OFFICIAL")
        self.assertEqual(plan["selection_mode"], "body_image_fallback")
        self.assertTrue(any(item["asset_id"] == "IMG-GEN" for item in plan["cover_candidates"]))

    def test_cover_source_preference_does_not_override_generic_topic_ordering(self) -> None:
        official_cover = self.temp_dir / "official-generic-cover.jpg"
        generated_cover = self.temp_dir / "generated-generic-cover.png"
        official_cover.write_bytes(b"official-generic-cover")
        generated_cover.write_bytes(b"generated-generic-cover")

        request = {
            **self.build_publish_request(),
            "topic": "一位创作者最近的写作方法复盘",
            "audience_keywords": ["content", "creator", "writing"],
            "cover_image_path": "",
            "cover_image_url": "",
            "image_strategy": "mixed",
        }
        cover_candidates = [
            {
                "asset_id": "IMG-GEN",
                "role": "post_media",
                "path": str(generated_cover),
                "source_url": "",
                "caption": "AI generated creator cover",
                "source_name": "local_generated",
                "status": "local_ready",
                "score": 94,
                "body_order": 0,
                "from_selected_images": True,
            },
            {
                "asset_id": "IMG-OFFICIAL",
                "role": "post_media",
                "path": str(official_cover),
                "source_url": "https://newsroom.example.com/creator-photo.jpg",
                "caption": "Newsroom creator photo",
                "source_name": "Example newsroom",
                "status": "local_ready",
                "score": 78,
                "body_order": 1,
                "from_selected_images": True,
            },
        ]

        plan = select_cover_plan([], cover_candidates, request)

        self.assertEqual(plan["selected_cover_asset_id"], "IMG-GEN")
        self.assertEqual(plan["selection_mode"], "body_image_fallback")

    def test_build_publish_package_can_use_dedicated_news_page_screenshot_as_cover(self) -> None:
        body_image = self.temp_dir / "body-hero.png"
        dedicated_screenshot = self.temp_dir / "news-page-cover.png"
        body_image.write_bytes(b"body-hero")
        dedicated_screenshot.write_bytes(b"news-page-cover")

        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-21",
                    "image_id": "IMG-21",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "Body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-21",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body hero",
                    "source_name": "fixture",
                    "score": 80,
                },
                {
                    "image_id": "IMG-22",
                    "role": "article_page_screenshot",
                    "path": str(dedicated_screenshot),
                    "source_url": "",
                    "summary": "Dedicated news page screenshot",
                    "source_name": "Example News",
                    "capture_method": "page_hints",
                    "score": 82,
                },
            ],
        )

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )

        self.assertEqual(package["cover_plan"]["selected_cover_asset_id"], "IMG-22")
        self.assertEqual(package["cover_plan"]["selected_cover_role"], "article_page_screenshot")
        self.assertEqual(package["cover_plan"]["selection_mode"], "dedicated_candidate")
        self.assertIn("dedicated cover candidate", package["cover_plan"]["selection_reason"].lower())
        self.assertEqual(package["push_readiness"]["cover_source"], "dedicated_cover_candidate")

    def test_build_publish_package_can_render_editor_anchors_inline_when_requested(self) -> None:
        workflow_result = {
            "review_result": {
                "article_package": {
                    "title": "Agent hiring reset",
                    "subtitle": "A concise subtitle",
                    "lede": "This is the opening paragraph.",
                    "sections": [
                        {"heading": "What changed", "paragraph": "Paragraph one."},
                        {"heading": "Why this matters", "paragraph": "Paragraph two."},
                    ],
                    "draft_thesis": "The rebound is real enough to matter.",
                    "article_markdown": "# Agent hiring reset",
                    "selected_images": [],
                    "citations": [],
                }
            },
            "draft_result": {"draft_context": {"image_candidates": []}},
        }
        request = self.build_publish_request()
        request["editor_anchor_mode"] = "inline"
        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            request,
        )

        self.assertEqual(package["editor_anchor_mode"], "inline")
        self.assertEqual(package["editor_anchor_visibility"], "visible_inline")
        self.assertIn(package["editor_anchors"][0]["text"], package["content_html"])
        self.assertIn("编辑锚点", package["content_html"])

    def test_build_publish_package_uses_source_titles_and_exposes_style_profile(self) -> None:
        workflow_result = self.build_publish_workflow_result(
            selected_images=[],
            draft_image_candidates=[],
            citations=[
                {
                    "citation_id": "S1",
                    "source_name": "Reuters",
                    "title": "Iran says diplomacy still needs new terms",
                    "url": "https://example.com/reuters-story",
                    "published_at": "2026-03-26T10:00:00+00:00",
                }
            ],
            style_profile_applied={
                "global_profile_applied": True,
                "topic_profile_applied": False,
                "applied_paths": [".tmp/article-feedback-profiles/global.json"],
                "style_memory": {
                    "target_band": "3.4",
                    "sample_source_declared_count": 3,
                    "sample_source_available_count": 3,
                    "sample_source_loaded_count": 3,
                    "sample_source_missing_count": 0,
                    "sample_source_runtime_mode": "curated_profile_only",
                    "corpus_derived_transitions": ["先说结论"],
                },
            },
        )
        workflow_result["manual_review"] = {
            "required": True,
            "status": "awaiting_reddit_operator_review",
            "required_count": 1,
            "high_priority_count": 1,
            "summary": "Queued Reddit comment signals still need operator review before publication.",
            "next_step": "Review the queued Reddit comment signals before publication.",
            "queue": [
                {
                    "title": "Semicap capex thread",
                    "priority_level": "high",
                    "summary": "Partial Reddit comment sampling still needs operator review.",
                }
            ],
        }
        workflow_result["publication_readiness"] = "blocked_by_reddit_operator_review"

        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            self.build_publish_request(),
        )
        report_markdown = build_report_markdown(
            {
                "selected_topic": {"title": "AI agent hiring rebound"},
                "publish_package": package,
                "manual_review": {"required": True, "approved": False, "status": "awaiting_human_review"},
                "push_stage": {},
                "discovery_stage": {},
                "workflow_stage": {},
                "next_push_command": "",
            }
        )

        self.assertNotIn("<h1", package["content_html"])
        self.assertIn("Iran says diplomacy still needs new terms", package["content_html"])
        self.assertIn("https://example.com/reuters-story", package["content_html"])
        self.assertEqual(package["style_profile_applied"]["style_memory"]["sample_source_loaded_count"], 3)
        self.assertIn("Target band: 3.4", report_markdown)
        self.assertIn("Sample source references: 3", report_markdown)
        self.assertIn("Available sample source paths: 3", report_markdown)
        self.assertIn("Runtime style source mode: curated_profile_only", report_markdown)
        self.assertIn("## Automatic Acceptance", report_markdown)
        self.assertIn("## Regression Checks", report_markdown)
        self.assertIn("Cover reason present: yes", report_markdown)
        self.assertEqual(package["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(package["workflow_manual_review"]["status"], "awaiting_reddit_operator_review")
        self.assertIn("## Workflow Reddit Operator Review", report_markdown)
        self.assertIn("Workflow queue: [high] Semicap capex thread", report_markdown)
        self.assertIn("## Optimization Options", report_markdown)

    def test_article_publish_cli_accepts_hyphenated_framework_alias(self) -> None:
        with patch.object(sys, "argv", ["article_publish.py", "--article-framework", "hot-comment"]):
            args = parse_args()
        self.assertEqual(args.article_framework, "hot_comment")

    def test_article_publish_cli_accepts_headline_hook_options(self) -> None:
        with patch.object(
            sys,
            "argv",
            [
                "article_publish.py",
                "--headline-hook-mode",
                "traffic",
                "--headline-hook-prefixes",
                "刚刚，",
                "突发！",
            ],
        ):
            args = parse_args()
        self.assertEqual(args.headline_hook_mode, "traffic")
        self.assertEqual(args.headline_hook_prefixes, ["刚刚，", "突发！"])

    def test_article_publish_regression_check_cli_accepts_target(self) -> None:
        with patch.object(sys, "argv", ["article_publish_regression_check.py", "C:\\tmp\\publish-run"]):
            args = parse_regression_check_args()
        self.assertEqual(args.target, "C:\\tmp\\publish-run")

    def test_article_publish_regression_check_validates_output_dir(self) -> None:
        body_image = self.temp_dir / "body-hero.png"
        body_image.write_bytes(b"body-hero")
        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-11",
                    "image_id": "IMG-11",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "Body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-11",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body hero",
                    "source_name": "fixture",
                    "score": 80,
                }
            ],
        )
        request = {
            **self.build_publish_request(),
            "article_framework": "deep_analysis",
            "draft_mode": "image_first",
            "image_strategy": "screenshots_only",
            "target_length_chars": 1200,
        }
        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            request,
        )

        output_dir = self.temp_dir / "publish-regression-output"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "accepted")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["decision_required"])
        self.assertEqual(result["regression_source"], "publish_package")
        self.assertFalse(result["failures"])
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "ready")
        self.assertTrue(result["regression_checks"]["checks"]["cover_reason_present"])
        self.assertIn("Publish Automatic Acceptance", result["report_markdown"])
        self.assertIn("## Workflow Publication Gate", result["report_markdown"])

    def test_article_publish_regression_check_can_fallback_to_workflow_draft(self) -> None:
        body_image = self.temp_dir / "body-hero-fallback.png"
        body_image.write_bytes(b"body-hero-fallback")
        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-21",
                    "image_id": "IMG-21",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "Body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-21",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body hero",
                    "source_name": "fixture",
                    "score": 82,
                }
            ],
        )
        request = {
            **self.build_publish_request(),
            "article_framework": "deep_analysis",
            "draft_mode": "image_first",
            "image_strategy": "screenshots_only",
            "target_length_chars": 1200,
        }
        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            request,
        )
        package.pop("regression_checks", None)

        output_dir = self.temp_dir / "publish-regression-fallback"
        workflow_dir = output_dir / "workflow"
        workflow_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")
        draft_result = {
            "request": request,
            "article_package": workflow_result["review_result"]["article_package"],
        }
        (workflow_dir / "article-draft-result.json").write_text(json.dumps(draft_result, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "accepted")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["regression_source"], "workflow_draft_fallback")
        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "ready")
        self.assertFalse(result["regression_checks"]["checks"]["expanded_sections_expected"])
        self.assertTrue(result["regression_checks"]["checks"]["expanded_sections_ok"])
        self.assertTrue(result["regression_checks"]["checks"]["screenshot_cover_preferred"])

    def test_article_publish_regression_check_surfaces_workflow_publication_gate(self) -> None:
        body_image = self.temp_dir / "body-hero-gate.png"
        body_image.write_bytes(b"body-hero-gate")
        workflow_result = self.build_publish_workflow_result(
            selected_images=[
                {
                    "asset_id": "IMG-31",
                    "image_id": "IMG-31",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "caption": "Body hero",
                    "source_name": "fixture",
                    "status": "local_ready",
                    "placement": "after_lede",
                }
            ],
            draft_image_candidates=[
                {
                    "image_id": "IMG-31",
                    "role": "root_post_screenshot",
                    "path": str(body_image),
                    "source_url": "",
                    "summary": "Body hero",
                    "source_name": "fixture",
                    "score": 82,
                }
            ],
        )
        workflow_result["manual_review"] = {
            "required": True,
            "status": "awaiting_reddit_operator_review",
            "required_count": 1,
            "high_priority_count": 1,
            "next_step": "Review the queued Reddit comment signals before publication.",
        }
        workflow_result["publication_readiness"] = "blocked_by_reddit_operator_review"
        request = {
            **self.build_publish_request(),
            "article_framework": "deep_analysis",
            "draft_mode": "image_first",
            "image_strategy": "screenshots_only",
            "target_length_chars": 1200,
        }
        package = build_publish_package(
            workflow_result,
            {"title": "AI agent hiring rebound", "keywords": ["AI", "agent", "hiring"]},
            request,
        )

        output_dir = self.temp_dir / "publish-regression-gate"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["workflow_publication_gate"]["publication_readiness"], "blocked_by_reddit_operator_review")
        self.assertEqual(
            result["workflow_publication_gate"]["manual_review"]["status"],
            "awaiting_reddit_operator_review",
        )
        self.assertIn("blocked_by_reddit_operator_review", result["report_markdown"])
        self.assertIn("awaiting_reddit_operator_review", result["report_markdown"])

    def test_article_publish_regression_check_returns_optimization_options_when_changes_are_recommended(self) -> None:
        output_dir = self.temp_dir / "publish-regression-recommended"
        output_dir.mkdir(parents=True, exist_ok=True)
        package = {
            "cover_plan": {
                "selection_mode": "body_image_fallback",
                "selected_cover_role": "post_media",
                "selected_cover_asset_id": "IMG-77",
            },
            "push_readiness": {"cover_source": "article_image"},
            "regression_checks": {
                "section_count": 4,
                "section_headings": ["先看变化本身", "真正的传导链条", "接下来盯什么", "补充说明"],
                "first_image": {
                    "asset_id": "IMG-77",
                    "role": "post_media",
                    "status": "local_ready",
                    "caption": "login /url: noisy screenshot",
                    "placement": "after_lede",
                },
                "cover": {
                    "selected_cover_asset_id": "IMG-77",
                    "selected_cover_role": "post_media",
                    "selection_mode": "body_image_fallback",
                    "selection_reason": "",
                    "cover_source": "article_image",
                },
                "forbidden_phrase_hits": {
                    "登录": 1,
                    "/url:": 1,
                    "预算": 0,
                    "订单": 0,
                    "定价": 1,
                    "经营变量": 1,
                    "经营层": 0,
                    "经营和投资判断题": 0,
                },
                "checks": {
                    "expanded_sections_expected": True,
                    "expanded_sections_ok": False,
                    "ui_capture_noise_clean": False,
                    "generic_business_talk_clean": False,
                    "first_image_is_screenshot": False,
                    "screenshot_cover_preferred": False,
                    "cover_reason_present": False,
                },
            },
        }
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "changes_recommended")
        self.assertFalse(result["accepted"])
        self.assertTrue(result["decision_required"])
        self.assertTrue(result["failures"])
        self.assertGreaterEqual(len(result["optimization_options"]), 3)
        option_areas = {item["area"] for item in result["optimization_options"]}
        self.assertIn("structure", option_areas)
        self.assertIn("screenshot_caption", option_areas)
        self.assertIn("observability", option_areas)
        self.assertIn("workflow", result["recommended_next_action"])
        self.assertIn("Optimization Options", result["report_markdown"])

    def test_article_publish_regression_check_reports_missing_screenshot_upload_source(self) -> None:
        output_dir = self.temp_dir / "publish-regression-missing-screenshot-upload-source"
        output_dir.mkdir(parents=True, exist_ok=True)
        cover_plan = {
            "selected_cover_asset_id": "IMG-02",
            "selected_cover_role": "post_media",
            "selected_cover_caption": "Body image fallback",
            "selection_mode": "body_image_fallback",
            "selection_reason": "Falling back to body image IMG-02 because no dedicated cover candidate was ready.",
        }
        push_readiness = {
            "cover_source": "article_image",
            "missing_upload_source_asset_ids": ["IMG-01"],
        }
        regression_checks = build_regression_checks(
            {
                "title": "Claude Code screenshot fallback",
                "article_framework": "quick_take",
                "lede": "We traced why the screenshot cover fell back.",
                "sections": [
                    {
                        "heading": "What broke",
                        "paragraph": "The screenshot still appears in the body, but the publish package no longer carries a usable upload source for it.",
                    }
                ],
                "selected_images": [
                    {
                        "asset_id": "IMG-01",
                        "image_id": "IMG-01",
                        "role": "root_post_screenshot",
                        "status": "missing",
                        "caption": "Root post screenshot",
                        "placement": "after_lede",
                    },
                    {
                        "asset_id": "IMG-02",
                        "image_id": "IMG-02",
                        "role": "post_media",
                        "status": "remote_only",
                        "caption": "Body image fallback",
                        "placement": "after_section_1",
                    },
                ],
            },
            {
                "article_framework": "quick_take",
                "target_length_chars": 1200,
                "draft_mode": "image_first",
                "image_strategy": "prefer_images",
                "language_mode": "english",
            },
            cover_plan,
            push_readiness,
            {},
        )
        package = {
            "cover_plan": cover_plan,
            "push_readiness": push_readiness,
            "regression_checks": regression_checks,
        }
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "changes_recommended")
        self.assertFalse(result["accepted"])
        self.assertTrue(result["regression_checks"]["cover"]["screenshot_upload_source_missing"])
        self.assertIn(
            "Screenshot cover candidate is missing a usable upload source, so cover selection fell back to a body image.",
            result["failures"],
        )
        self.assertNotIn("Cover selection no longer prefers a screenshot path.", result["failures"])
        option_areas = {item["area"] for item in result["optimization_options"]}
        self.assertIn("cover_upload_source", option_areas)
        self.assertNotIn("cover_selection", option_areas)

    def test_build_regression_checks_flags_generic_business_talk_for_macro_topics(self) -> None:
        regression_checks = build_regression_checks(
            {
                "article_framework": "deep_analysis",
                "lede": "特朗普讲话之后，市场先交易预期。",
                "sections": [
                    {
                        "heading": "正文",
                        "paragraph": "如果后面继续改写预算和定价，这条线就会越走越远。",
                    }
                ],
                "selected_images": [],
            },
            {
                "article_framework": "deep_analysis",
                "target_length_chars": 2800,
                "draft_mode": "image_first",
                "image_strategy": "screenshots_only",
            },
            {
                "selected_cover_role": "root_post_screenshot",
                "selection_mode": "screenshot_candidate",
                "selection_reason": "screenshot cover candidate",
            },
            {"cover_source": "dedicated_cover_candidate"},
            {
                "title": "特朗普今天讲话后，市场重新交易美伊战争和布油",
                "summary": "真正的核心是战争持续时间和布伦特原油会不会继续冲高。",
                "keywords": ["特朗普", "伊朗", "战争", "布油"],
            },
        )

        self.assertTrue(regression_checks["checks"]["generic_business_talk_expected"])
        self.assertFalse(regression_checks["checks"]["generic_business_talk_clean"])
        self.assertEqual(regression_checks["forbidden_phrase_hits"]["预算"], 1)
        self.assertEqual(regression_checks["forbidden_phrase_hits"]["定价"], 1)

    def test_build_regression_checks_flags_hanging_title_and_longhand_developer_copy(self) -> None:
        regression_checks = build_regression_checks(
            {
                "title": "刚刚，Claude Code 泄露源码后",
                "article_framework": "deep_analysis",
                "lede": "这篇文章试图解释为什么这条线索会继续发酵。",
                "sections": [
                    {
                        "heading": "正文",
                        "paragraph": "真正值得看的地方，还是产品能力表面、工具调用边界和权限设计，以及浏览器控制、工作流编排与多步开发者执行。",
                    }
                ],
                "selected_images": [],
            },
            {
                "article_framework": "deep_analysis",
                "target_length_chars": 2800,
                "draft_mode": "image_first",
                "image_strategy": "screenshots_only",
            },
            {
                "selected_cover_role": "root_post_screenshot",
                "selection_mode": "screenshot_candidate",
                "selection_reason": "screenshot cover candidate",
            },
            {"cover_source": "dedicated_cover_candidate"},
            {
                "title": "Claude Code 泄露源码后，真正值得看的 7 个秘密功能",
                "summary": "The leaked code shows browser control, tool calls, and workflow orchestration entrypoints.",
                "keywords": ["Claude Code", "browser", "tool call", "workflow", "permission"],
            },
        )

        self.assertFalse(regression_checks["checks"]["title_complete"])
        self.assertTrue(regression_checks["checks"]["developer_focus_copy_expected"])
        self.assertFalse(regression_checks["checks"]["developer_focus_copy_clean"])
        self.assertEqual(regression_checks["forbidden_phrase_hits"]["产品能力表面、工具调用边界和权限设计"], 1)
        self.assertEqual(regression_checks["forbidden_phrase_hits"]["浏览器控制、工作流编排与多步开发者执行"], 1)

    def test_build_regression_checks_tracks_repetitive_developer_focus_short_phrases(self) -> None:
        regression_checks = build_regression_checks(
            {
                "title": "Claude Code 真正值得看的 7 个秘密功能",
                "article_framework": "deep_analysis",
                "lede": "产品边界、权限设计已经反复被提起，产品边界、权限设计也开始进入正文。",
                "sections": [
                    {
                        "heading": "正文",
                        "paragraph": (
                            "浏览器控制、工作流编排也在反复出现。"
                            "能力边界和开发者工作流被反复复读。"
                            "哪些入口会开放、哪些权限会收口，哪些入口会开放、哪些权限会收口。"
                        ),
                    }
                ],
                "selected_images": [],
            },
            {
                "article_framework": "deep_analysis",
                "target_length_chars": 2800,
                "draft_mode": "image_first",
                "image_strategy": "screenshots_only",
            },
            {
                "selected_cover_role": "root_post_screenshot",
                "selection_mode": "screenshot_candidate",
                "selection_reason": "screenshot cover candidate",
            },
            {"cover_source": "dedicated_cover_candidate"},
            {
                "title": "Claude Code 真正值得看的 7 个秘密功能",
                "summary": "The leaked code shows browser control, tool calls, and workflow orchestration entrypoints.",
                "keywords": ["Claude Code", "browser", "tool call", "workflow", "permission"],
            },
        )

        self.assertTrue(regression_checks["checks"]["developer_focus_copy_expected"])
        self.assertTrue(regression_checks["checks"]["developer_focus_copy_clean"])
        self.assertFalse(regression_checks["checks"]["developer_focus_phrase_varied"])
        self.assertGreaterEqual(regression_checks["developer_focus_phrase_hits"]["产品边界、权限设计"], 2)
        self.assertGreaterEqual(regression_checks["developer_focus_phrase_hits"]["哪些入口会开放、哪些权限会收口"], 2)

    def test_article_publish_regression_check_returns_optional_improvements_for_threshold_pass(self) -> None:
        output_dir = self.temp_dir / "publish-regression-advisory"
        output_dir.mkdir(parents=True, exist_ok=True)
        package = {
            "cover_plan": {
                "selection_mode": "screenshot_candidate",
                "selected_cover_role": "root_post_screenshot",
                "selected_cover_asset_id": "IMG-01",
                "selection_reason": "screenshot cover candidate",
            },
            "push_readiness": {"cover_source": "dedicated_cover_candidate"},
            "regression_checks": {
                "section_count": 5,
                "target_length_chars": 2800,
                "body_char_count": 1600,
                "content_char_count": 4681,
                "section_headings": ["先看变化本身", "为什么没那么快结束", "真正的传导链条", "我的预测", "最后一句话总结"],
                "first_image": {
                    "asset_id": "IMG-01",
                    "role": "root_post_screenshot",
                    "status": "local_ready",
                    "caption": "首页截图",
                    "placement": "after_lede",
                },
                "cover": {
                    "selected_cover_asset_id": "IMG-01",
                    "selected_cover_role": "root_post_screenshot",
                    "selected_cover_caption": "首页截图",
                    "selection_mode": "screenshot_candidate",
                    "selection_reason": "screenshot cover candidate",
                    "cover_source": "dedicated_cover_candidate",
                },
                "forbidden_phrase_hits": {
                    "登录": 0,
                    "/url:": 0,
                    "预算": 0,
                    "订单": 0,
                    "定价": 0,
                    "经营变量": 0,
                    "经营层": 0,
                    "经营和投资判断题": 0,
                },
                "developer_focus_phrase_hits": {
                    "产品边界、权限设计": 3,
                    "浏览器控制、工作流编排": 1,
                    "能力边界和开发者工作流": 1,
                    "哪些入口会开放、哪些权限会收口": 2,
                },
                "wechat_transition_phrase_hits": {
                    "换句话说": 2,
                    "反过来看": 2,
                    "真正把讨论撑住的": 1,
                    "最容易误判的地方": 1,
                    "判断有没有走到这一步": 1,
                },
                "wechat_tail_tone_phrase_hits": {
                    "默认工作流": 1,
                    "源码考古": 2,
                    "真实开发流程判断题": 1,
                },
                "checks": {
                    "expanded_sections_expected": True,
                    "expanded_sections_ok": True,
                    "ui_capture_noise_clean": True,
                    "generic_business_talk_expected": True,
                    "generic_business_talk_clean": True,
                    "developer_focus_copy_expected": True,
                    "developer_focus_copy_clean": True,
                    "developer_focus_phrase_varied": False,
                    "wechat_transition_phrase_varied": False,
                    "wechat_tail_tone_expected": True,
                    "wechat_tail_tone_clean": False,
                    "screenshot_path_expected": True,
                    "first_image_is_screenshot": True,
                    "screenshot_cover_preferred": True,
                    "cover_reason_present": True,
                    "cover_caption_clean": True,
                },
            },
        }
        (output_dir / "publish-package.json").write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8-sig")

        result = run_publish_regression_check({"target": str(output_dir)})

        self.assertEqual(result["status"], "accepted")
        self.assertTrue(result["accepted"])
        self.assertFalse(result["decision_required"])
        self.assertFalse(result["optimization_options"])
        self.assertGreaterEqual(len(result["advisory_options"]), 1)
        option_areas = {item["area"] for item in result["advisory_options"]}
        self.assertIn("developer_focus_repetition_margin", option_areas)
        self.assertIn("wechat_transition_repetition_margin", option_areas)
        self.assertIn("wechat_tail_tone_margin", option_areas)
        self.assertIn("structure_margin", option_areas)
        self.assertIn("length_budget_margin", option_areas)
        self.assertIn("screenshot_caption_margin", option_areas)
        self.assertIn("可选优化项", result["recommended_next_action"])
        self.assertIn("Optional Improvements", result["report_markdown"])

    def test_publish_scripts_compile_cleanly(self) -> None:
        for name in [
            "hot_topic_discovery_runtime.py",
            "hot_topic_discovery.py",
            "article_publish_runtime.py",
            "article_publish.py",
            "article_publish_regression_check_runtime.py",
            "article_publish_regression_check.py",
        ]:
            py_compile.compile(str(SCRIPT_DIR / name), doraise=True)


if __name__ == "__main__":
    unittest.main()
