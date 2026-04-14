#!/usr/bin/env node

/**
 * build_live_brief_from_article.mjs
 *
 * Bridge: article workflow output → live-brief.md
 *
 * Reads final-article-result.json (or the parent workflow-result.json) and
 * produces a live-brief.md that build_social_source_from_live_brief.mjs can
 * consume.  This closes the gap between the article pipeline and the social
 * card pipeline so the two can be chained without hand-writing a live-brief.
 *
 * Usage:
 *   node scripts/social-cards/build_live_brief_from_article.mjs \
 *     --input <final-article-result.json | workflow-result.json> \
 *     --output <live-brief.md> \
 *     [--as-of YYYY-MM-DD] \
 *     [--tags tag1,tag2,...] \
 *     [--cover-title <text>] \
 *     [--cover-subtitle <text>]
 */

import { readFile, writeFile, mkdir } from "fs/promises";
import path from "path";

// ---------------------------------------------------------------------------
// CLI arg parsing
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = {
    input: "",
    output: "",
    asOf: "",
    tags: "",
    coverTitle: "",
    coverSubtitle: "",
  };

  for (let i = 0; i < args.length; i += 1) {
    const arg = args[i];
    if (arg === "--input") {
      result.input = args[i + 1] || "";
      i += 1;
    } else if (arg === "--output") {
      result.output = args[i + 1] || "";
      i += 1;
    } else if (arg === "--as-of") {
      result.asOf = args[i + 1] || "";
      i += 1;
    } else if (arg === "--tags") {
      result.tags = args[i + 1] || "";
      i += 1;
    } else if (arg === "--cover-title") {
      result.coverTitle = args[i + 1] || "";
      i += 1;
    } else if (arg === "--cover-subtitle") {
      result.coverSubtitle = args[i + 1] || "";
      i += 1;
    }
  }

  return result;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clean(value) {
  return String(value ?? "").trim();
}

/** Strip markdown bold / italic / code / link syntax from a line. */
function stripInlineMarkdown(text) {
  return String(text ?? "")
    .replace(/\*\*(.+?)\*\*/g, "$1")
    .replace(/__(.+?)__/g, "$1")
    .replace(/\*(.+?)\*/g, "$1")
    .replace(/_(.+?)_/g, "$1")
    .replace(/`(.+?)`/g, "$1")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .trim();
}

/** Split a bilingual "中文 | English" title, return Chinese portion. */
function chinesePortion(title) {
  if (!title) return "";
  if (title.includes("|")) {
    return title.split("|")[0].trim();
  }
  return title.trim();
}

/** Convert a bilingual section heading to Chinese only. */
function chineseHeading(heading) {
  return chinesePortion(heading);
}

/** Slugify a topic string for frontmatter. */
function slugifyTopic(text) {
  return String(text ?? "")
    .toLowerCase()
    .replace(/[|｜]/g, " ")
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 80);
}

/** Parse ## sections from markdown body. Returns [{title, lines}]. */
function parseSections(markdown) {
  if (!markdown) return [];
  const blocks = markdown.split(/\n##\s+/);
  // First block is the lede (before any ##)
  const lede = blocks[0] || "";
  const sections = blocks.slice(1).map((block) => {
    const [titleLine, ...bodyLines] = block.split("\n");
    return {
      title: titleLine.trim(),
      lines: bodyLines.map((l) => l.trimEnd()).filter(Boolean),
    };
  });
  return [{ title: "__lede__", lines: lede.split("\n").map((l) => l.trimEnd()).filter(Boolean) }, ...sections];
}

/** Find the first image reference in article_markdown. */
function extractHeroImage(articleMarkdown) {
  if (!articleMarkdown) return "";
  // Try IMG-N pattern first (most specific)
  const imgN = articleMarkdown.match(/!\[IMG-\d+\]\(([^)]+)\)/);
  if (imgN) return imgN[1];
  // Try any markdown image
  const mdImg = articleMarkdown.match(/!\[[^\]]*\]\(([^)]+)\)/);
  if (mdImg) return mdImg[1];
  // Try HTML img tag
  const htmlImg = articleMarkdown.match(/<img[^>]+src=["']([^"']+)["']/i);
  if (htmlImg) return htmlImg[1];
  return "";
}

function firstSelectedImage(article) {
  const candidates = [];
  const selected = Array.isArray(article?.selected_images) ? article.selected_images : [];
  candidates.push(...selected);
  if (article?.first_image && typeof article.first_image === "object") {
    candidates.push(article.first_image);
  }
  if (article?.cover && typeof article.cover === "object") {
    candidates.push({
      path: article.cover.selected_cover_local_path || article.cover.selected_cover_path,
      source_url: article.cover.selected_cover_source_url || article.cover.selected_cover_render_src,
      caption: article.cover.selected_cover_caption,
      role: article.cover.selected_cover_role,
    });
  }

  for (const item of candidates) {
    const imagePath = clean(item?.path || item?.local_path || item?.source_url || item?.url || item?.render_src);
    if (!imagePath) continue;
    return {
      path: imagePath,
      caption: clean(item?.caption),
      role: clean(item?.role || item?.kind || item?.asset_id),
    };
  }

  return { path: "", caption: "", role: "" };
}

function inferHeroReferenceProfile({ imagePath, caption, title, note, role }) {
  const haystack = [imagePath, caption, title, note, role].join(" ").toLowerCase();

  let refStyle = "news-photo";
  if (/(screenshot|截图|screen|tweet|post|x\b|界面|页面|docs|文档|root_post)/.test(haystack)) {
    refStyle = "screenshot";
  } else if (/(chart|图表|k线|走势|数据|统计|曲线|table|表格|price map)/.test(haystack)) {
    refStyle = "chart";
  }

  let refLayout = refStyle === "news-photo" ? "image-dominant" : "split-focus";
  if (/(portrait|人物|现场|路透|ap |afp|photo|照片|摄影)/.test(haystack)) {
    refLayout = "image-dominant";
    refStyle = "news-photo";
  }

  let refPalette = "balanced";
  if (/(dark|深色|夜间|黑底|x screenshot|tweet screenshot)/.test(haystack)) {
    refPalette = "dark";
  } else if (/(light|浅色|白底|docs|文档|chart|图表|table|表格)/.test(haystack)) {
    refPalette = "light";
  }

  return { refStyle, refLayout, refPalette };
}

/** Extract the ## Sources section from article_markdown. */
function extractSources(articleMarkdown) {
  if (!articleMarkdown) return [];
  const match = articleMarkdown.match(/\n## (?:Sources|来源)\n([\s\S]+)$/);
  if (!match) return [];
  return match[1]
    .split("\n")
    .map((l) => l.trim())
    .filter((l) => l.startsWith("-") || l.startsWith("*"));
}

/** Try to derive as_of from various locations in the payload. */
function deriveAsOf(payload, cliAsOf) {
  if (cliAsOf) return cliAsOf;

  // workflow-level analysis_time
  const candidates = [
    payload.analysis_time,
    payload.request?.analysis_time,
    payload.source_summary?.analysis_time,
  ];
  for (const c of candidates) {
    if (c) {
      const d = String(c).slice(0, 10); // YYYY-MM-DD
      if (/^\d{4}-\d{2}-\d{2}$/.test(d)) return d;
    }
  }

  // fallback: today
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}

/** Derive tags from title and topic. */
function deriveTags(title, cliTags) {
  if (cliTags) {
    return cliTags
      .split(",")
      .map((t) => t.trim().toLowerCase())
      .filter(Boolean);
  }
  // Auto-derive from title words
  const words = String(title ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff\s-]/g, " ")
    .split(/\s+/)
    .filter((w) => w.length > 1);
  return [...new Set(words)].slice(0, 6);
}

// ---------------------------------------------------------------------------
// Section mapping: article sections → live-brief sections
// ---------------------------------------------------------------------------

const SECTION_MAP = [
  {
    liveBriefTitle: "一线判断",
    articlePatterns: [/核心判断/i, /bottom\s*line/i, /一线判断/i],
    fallbackToLede: true,
  },
  {
    liveBriefTitle: "已确认进展",
    articlePatterns: [/已确认/i, /confirmed/i, /第一个信号/i, /what\s*changed/i],
  },
  {
    liveBriefTitle: "仍然卡住的点",
    articlePatterns: [/未确认/i, /not\s*confirmed/i, /未证实/i, /仍然卡住/i],
  },
  {
    liveBriefTitle: "对市场最重要的含义",
    articlePatterns: [/为什么.*重要/i, /why\s*this\s*matters/i, /市场.*含义/i],
  },
  {
    liveBriefTitle: "这轮最值得看的变化",
    articlePatterns: [/趋势/i, /trends/i, /core\s*view/i, /最值得看/i, /story\s*angles/i, /可写角度/i],
  },
  {
    liveBriefTitle: "接下来最值得盯的变量",
    articlePatterns: [/边界/i, /open\s*questions/i, /待确认/i, /接下来/i, /what\s*to\s*watch/i, /盯什么/i],
  },
];

function findArticleSection(sections, patterns) {
  for (const pattern of patterns) {
    const found = sections.find((s) => s.title !== "__lede__" && pattern.test(s.title));
    if (found) return found;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Main: build the live-brief markdown
// ---------------------------------------------------------------------------

function buildLiveBrief(payload, cliArgs) {
  // Resolve the final article result — it may be nested
  const article =
    payload.final_article_result || payload.review_rewrite_package?.final_article_result || payload;

  const title = clean(article.title);
  const thesis = clean(article.draft_thesis);
  const bodyMarkdown = clean(article.body_markdown);
  const articleMarkdown = clean(article.article_markdown);

  const asOf = deriveAsOf(payload, cliArgs.asOf);
  const topicSlug = slugifyTopic(title);
  const tags = deriveTags(title, cliArgs.tags);
  const selectedHero = firstSelectedImage(article);
  const heroImage = extractHeroImage(articleMarkdown);
  // Fallback: check payload for image references
  const payloadImages = article.images || article.image_candidates || [];
  const fallbackHeroImage =
    heroImage ||
    selectedHero.path ||
    (payloadImages[0]?.path || payloadImages[0]?.source_url || payloadImages[0]?.url || "");
  const sources = extractSources(articleMarkdown);

  // Parse body sections
  const sections = parseSections(bodyMarkdown);
  const lede = sections.find((s) => s.title === "__lede__");
  const bodySections = sections.filter((s) => s.title !== "__lede__");

  // Build live-brief sections
  const liveBriefSections = [];

  for (const mapping of SECTION_MAP) {
    const matched = findArticleSection(bodySections, mapping.articlePatterns);
    if (matched) {
      liveBriefSections.push({
        title: mapping.liveBriefTitle,
        lines: matched.lines.map(stripInlineMarkdown),
      });
    } else if (mapping.fallbackToLede && lede && lede.lines.length > 0) {
      // For 一线判断: use thesis + lede
      const ledeLines = [];
      if (thesis) ledeLines.push(thesis);
      // Add lede lines that aren't the H1 title
      for (const line of lede.lines) {
        if (line.startsWith("# ")) continue;
        ledeLines.push(stripInlineMarkdown(line));
      }
      if (ledeLines.length > 0) {
        liveBriefSections.push({
          title: mapping.liveBriefTitle,
          lines: ledeLines,
        });
      }
    }
  }

  // If no sections were mapped, dump all body sections as-is
  if (liveBriefSections.length === 0) {
    for (const section of bodySections) {
      liveBriefSections.push({
        title: chineseHeading(section.title),
        lines: section.lines.map(stripInlineMarkdown),
      });
    }
  }

  // Build frontmatter
  const frontmatter = [
    "---",
    "type: live_brief",
    `topic: ${topicSlug}`,
    `as_of: ${asOf}`,
    "status: draft",
  ];
  if (tags.length > 0) {
    frontmatter.push("tags:");
    for (const tag of tags) {
      frontmatter.push(`  - ${tag}`);
    }
  }
  frontmatter.push("---");

  // Build body
  const body = [];

  for (const section of liveBriefSections) {
    body.push("");
    body.push(`## ${section.title}`);
    body.push("");
    for (const line of section.lines) {
      body.push(line);
    }
  }

  // Sources
  if (sources.length > 0) {
    body.push("");
    body.push("## Sources");
    body.push("");
    for (const source of sources) {
      body.push(source);
    }
  }

  // Build metadata for JSON stdout
  const coverTitle = cliArgs.coverTitle || chinesePortion(title);
  const firstJudgment = liveBriefSections[0]?.lines[0] || thesis || "";
  const coverSubtitle = cliArgs.coverSubtitle || firstJudgment;
  const note = coverSubtitle ? `截至北京时间 ${asOf}，${coverSubtitle}` : `截至北京时间 ${asOf}`;
  const heroCaption = clean(selectedHero.caption) || clean(article.cover?.selected_cover_caption);
  const heroRole = clean(selectedHero.role) || clean(article.cover?.selected_cover_role);
  const heroReference = inferHeroReferenceProfile({
    imagePath: fallbackHeroImage || heroImage,
    caption: heroCaption,
    title: coverTitle,
    note,
    role: heroRole,
  });

  const frontmatterPrefix = frontmatter.slice(0, -1);
  if (fallbackHeroImage) {
    frontmatterPrefix.push(`hero_image: ${fallbackHeroImage}`);
  }
  if (heroCaption) {
    frontmatterPrefix.push(`hero_caption: ${heroCaption}`);
  }
  if (heroReference.refStyle) {
    frontmatterPrefix.push(`hero_ref_style: ${heroReference.refStyle}`);
  }
  if (heroReference.refLayout) {
    frontmatterPrefix.push(`hero_ref_layout: ${heroReference.refLayout}`);
  }
  if (heroReference.refPalette) {
    frontmatterPrefix.push(`hero_ref_palette: ${heroReference.refPalette}`);
  }
  frontmatterPrefix.push("---");
  const markdownWithHeroMeta = frontmatterPrefix.join("\n") + "\n" + body.join("\n") + "\n";

  return {
    markdown: markdownWithHeroMeta,
    meta: {
      topic: topicSlug,
      asOf,
      coverTitle,
      coverSubtitle,
      note,
      heroImage: fallbackHeroImage || heroImage,
      heroCaption,
      heroRole,
      heroRefStyle: heroReference.refStyle,
      heroRefLayout: heroReference.refLayout,
      heroRefPalette: heroReference.refPalette,
      sectionCount: liveBriefSections.length,
      sourceCount: sources.length,
      tags,
    },
  };
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv);
  if (!args.input || !args.output) {
    console.error(
      "Usage: node scripts/social-cards/build_live_brief_from_article.mjs --input <final-article-result.json> --output <live-brief.md> [--as-of YYYY-MM-DD] [--tags tag1,tag2] [--cover-title <text>] [--cover-subtitle <text>]"
    );
    process.exit(1);
  }

  const inputPath = path.resolve(args.input);
  const outputPath = path.resolve(args.output);

  const raw = await readFile(inputPath, "utf8");
  // Handle BOM from Python utf-8-sig output
  const cleaned = raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw;

  let payload;
  try {
    payload = JSON.parse(cleaned);
  } catch (parseErr) {
    throw new Error(
      `Failed to parse JSON from ${inputPath}: ${parseErr.message}\nFirst 500 chars: ${cleaned.slice(0, 500)}`
    );
  }

  const result = buildLiveBrief(payload, args);

  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, result.markdown, "utf8");

  console.log(
    JSON.stringify(
      {
        status: "ready",
        inputPath,
        outputPath,
        ...result.meta,
      },
      null,
      2
    )
  );
}

main().catch((error) => {
  console.error(error?.stack || error?.message || String(error));
  process.exit(1);
});
