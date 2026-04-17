#!/usr/bin/env node

import { readFile } from "fs/promises";
import path from "path";

export const DEFAULT_SUSPECT_PATTERNS = [
  // --- Classic AI filler transitions ---
  "换句话说",
  "总的来说",
  "综上所述",
  "值得注意的是",
  "需要指出的是",
  "不难发现",
  "显而易见",
  "毫无疑问",
  "事实上",
  "从某种程度上说",
  "在这个背景下",
  "从这个角度看",
  "首先",
  "其次",
  "最后",
  "本质上",
  "说白了",
  "归根结底",
  // --- Explainer-tone markers (AI loves to "explain" rather than "state") ---
  "简单来说",
  "具体来说",
  "也就是说",
  "可以说",
  "不得不说",
  "坦率地说",
  "客观来看",
  "总而言之",
  "一言以蔽之",
  // --- Symmetric structure markers (AI defaults to balanced enumeration) ---
  "一方面",
  "另一方面",
  "与此同时",
  "不仅如此",
  "除此之外",
  "在此基础上",
  // --- Generic business/strategy filler ---
  "至关重要",
  "不可忽视",
  "不容小觑",
  "意义深远",
  "深远影响",
  "战略意义",
  "核心竞争力",
  "赋能",
  // --- Overused formal transitions (AI uses these far more than human writers) ---
  "然而",
  "此外",
  "因此",
  "由此可见",
  "进而",
  "从而",
  "鉴于此",
  "有鉴于此",
  "基于此",
  "就此而言",
];

// Structural patterns that indicate AI-generated text when they appear
// in high density. These are checked as regex patterns, not literal strings.
export const STRUCTURAL_SUSPECT_PATTERNS = [
  // Symmetric "first/second/third" enumeration within a single section
  { pattern: "第[一二三四五六]", label: "numbered_enumeration", threshold_per_1k: 3 },
  // Excessive use of "不是X而是Y" contrast frame
  { pattern: "不是.{2,18}而是", label: "contrast_frame", threshold_per_1k: 2 },
  // "从X到Y" parallel structure
  { pattern: "从.{2,12}到.{2,12}", label: "from_to_parallel", threshold_per_1k: 3 },
  // Consecutive rhetorical questions (AI loves stacking "...吗？...吗？")
  { pattern: "[？?]\\s*[^。！？!?.]{4,40}[？?]", label: "stacked_rhetorical_questions", threshold_per_1k: 2 },
  // "无论...都..." universal quantifier (AI overuses this for false authority)
  { pattern: "无论.{2,20}都", label: "universal_quantifier", threshold_per_1k: 2 },
  // "随着...的发展/推进/深入" temporal filler (AI's favorite scene-setting opener)
  { pattern: "随着.{2,20}的(?:发展|推进|深入|演变|变化)", label: "temporal_filler", threshold_per_1k: 2 },
  // "X+Y+Z" triple enumeration with 、 separator (AI defaults to balanced lists)
  { pattern: "[\\u4e00-\\u9fff]{2,8}、[\\u4e00-\\u9fff]{2,8}、[\\u4e00-\\u9fff]{2,8}", label: "triple_enumeration", threshold_per_1k: 4 },
  // "不仅...而且/还..." escalation frame
  { pattern: "不仅.{2,20}(?:而且|还|更)", label: "escalation_frame", threshold_per_1k: 2 },
];

const JUDGMENT_HINTS = [
  "先说结论",
  "核心在于",
  "关键在于",
  "更关键的是",
  "真正值得看",
  "说到底",
  "问题在于",
  "说白了",
  "更重要的是",
];

function clampNumber(value) {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return value;
}

function percentile(sorted, ratio) {
  if (!sorted.length) {
    return 0;
  }
  const index = Math.min(sorted.length - 1, Math.max(0, Math.floor((sorted.length - 1) * ratio)));
  return sorted[index];
}

export function stripMarkdownSurface(content) {
  return String(content ?? "")
    .replace(/^\uFEFF/, "")
    .replace(/^---[\s\S]*?---\s*/m, "")
    .replace(/```[\s\S]*?```/g, "")
    .replace(/^#+\s+.*$/gm, "")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, "")
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/^>\s+/gm, "")
    .replace(/^[-*]\s+/gm, "")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/\*([^*]+)\*/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .trim();
}

export function extractChineseBody(content) {
  return stripMarkdownSurface(content)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => /[\u4e00-\u9fff]/.test(line) && line.length >= 10)
    .join("\n");
}

export function splitParagraphs(text) {
  return String(text ?? "")
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 12);
}

export function splitSentences(text) {
  return String(text ?? "")
    .replace(/\r/g, "")
    .split(/(?<=[。！？!?])/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 6);
}

/**
 * Detect paragraph-opener repetition.
 * Returns an object with:
 * - repeated_openers: array of { opener, count, indices } for openers appearing 3+ times
 * - diversity_ratio: unique openers / total paragraphs (1.0 = fully diverse, <0.5 = repetitive)
 * - flagged: true if diversity_ratio < 0.6
 */
export function detectParagraphOpenerRepetition(text) {
  const paragraphs = splitParagraphs(text);
  if (paragraphs.length < 4) {
    return { repeated_openers: [], diversity_ratio: 1.0, flagged: false };
  }
  const openerMap = new Map();
  for (let i = 0; i < paragraphs.length; i++) {
    const para = paragraphs[i];
    // Extract first 2-4 Chinese characters as the opener pattern
    const zhChars = para.match(/[\u4e00-\u9fff]/g);
    if (!zhChars || zhChars.length < 2) {
      continue;
    }
    const opener = zhChars.slice(0, Math.min(3, zhChars.length)).join("");
    if (!openerMap.has(opener)) {
      openerMap.set(opener, []);
    }
    openerMap.get(opener).push(i);
  }
  const repeated = [];
  for (const [opener, indices] of openerMap) {
    if (indices.length >= 3) {
      repeated.push({ opener, count: indices.length, indices });
    }
  }
  const uniqueOpeners = openerMap.size;
  const diversityRatio = paragraphs.length > 0 ? uniqueOpeners / paragraphs.length : 1.0;
  return {
    repeated_openers: repeated.sort((a, b) => b.count - a.count),
    diversity_ratio: Number(diversityRatio.toFixed(3)),
    flagged: diversityRatio < 0.6,
  };
}

export function summarizeLengths(lengths) {
  if (!lengths.length) {
    return {
      count: 0,
      min: 0,
      max: 0,
      avg: 0,
      median: 0,
      p25: 0,
      p75: 0,
      stdev: 0,
      uniformity: 0,
    };
  }
  const sorted = [...lengths].sort((a, b) => a - b);
  const avg = sorted.reduce((total, value) => total + value, 0) / sorted.length;
  const variance = sorted.reduce((total, value) => total + (value - avg) ** 2, 0) / sorted.length;
  const stdev = Math.sqrt(variance);
  return {
    count: sorted.length,
    min: sorted[0],
    max: sorted.at(-1) ?? 0,
    avg: Math.round(avg),
    median: percentile(sorted, 0.5),
    p25: percentile(sorted, 0.25),
    p75: percentile(sorted, 0.75),
    stdev: Math.round(stdev * 10) / 10,
    uniformity: Number(avg > 0 ? (stdev / avg).toFixed(3) : "0"),
  };
}

export function extractTransitions(text) {
  const candidates = new Map();
  for (const sentence of splitSentences(text)) {
    const firstClause = sentence.split(/[，、：:]/)[0]?.trim() || "";
    if (!/[\u4e00-\u9fff]/.test(firstClause)) {
      continue;
    }
    if (firstClause.length < 2 || firstClause.length > 12) {
      continue;
    }
    candidates.set(firstClause, (candidates.get(firstClause) || 0) + 1);
  }
  return [...candidates.entries()]
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1])
    .map(([phrase, count]) => ({ phrase, count }));
}

export function extractSentenceOpeners(text) {
  const openers = new Map();
  for (const sentence of splitSentences(text)) {
    const opener = sentence.slice(0, Math.min(10, sentence.length)).trim();
    if (!/[\u4e00-\u9fff]/.test(opener)) {
      continue;
    }
    if (opener.length < 2) {
      continue;
    }
    openers.set(opener, (openers.get(opener) || 0) + 1);
  }
  return [...openers.entries()]
    .filter(([, count]) => count >= 2)
    .sort((a, b) => b[1] - a[1])
    .map(([phrase, count]) => ({ phrase, count }));
}

export function extractJudgmentPatterns(text) {
  const candidates = new Map();
  for (const sentence of splitSentences(text)) {
    const firstClause = sentence.split(/[，、：:]/)[0]?.trim() || "";
    const hasJudgmentHint =
      JUDGMENT_HINTS.some((hint) => sentence.includes(hint) || firstClause.includes(hint)) ||
      (/不是.{1,18}而是/.test(sentence) && /[\u4e00-\u9fff]/.test(sentence));
    if (!hasJudgmentHint) {
      continue;
    }
    const key = firstClause || sentence.slice(0, 20);
    if (key.length < 2 || key.length > 24) {
      continue;
    }
    candidates.set(key, (candidates.get(key) || 0) + 1);
  }
  return [...candidates.entries()]
    .sort((a, b) => b[1] - a[1])
    .map(([phrase, count]) => ({ phrase, count }));
}

export function deriveAvoidPatterns(text, patterns = DEFAULT_SUSPECT_PATTERNS) {
  const corpusChars = Math.max(1, String(text ?? "").length);
  const detail = patterns
    .map((pattern) => {
      const escaped = pattern.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const matchCount = (String(text ?? "").match(new RegExp(escaped, "g")) || []).length;
      return {
        pattern,
        count: matchCount,
        density_per_10k_chars: Number(((matchCount * 10000) / corpusChars).toFixed(3)),
        recommended: matchCount <= 1,
      };
    })
    .sort((a, b) => a.count - b.count || a.pattern.localeCompare(b.pattern, "zh-CN"));
  return {
    avoidPatterns: detail.filter((item) => item.recommended).map((item) => item.pattern),
    detail,
  };
}

export function deriveStructuralPatterns(text) {
  const corpusChars = Math.max(1, String(text ?? "").length);
  const kChars = corpusChars / 1000;
  return STRUCTURAL_SUSPECT_PATTERNS.map((spec) => {
    const regex = new RegExp(spec.pattern, "g");
    const matchCount = (String(text ?? "").match(regex) || []).length;
    const density = matchCount / kChars;
    return {
      label: spec.label,
      pattern: spec.pattern,
      count: matchCount,
      density_per_1k_chars: Number(density.toFixed(3)),
      threshold_per_1k: spec.threshold_per_1k,
      flagged: density > spec.threshold_per_1k,
    };
  });
}

export function detectParagraphUniformity(text) {
  const paragraphs = splitParagraphs(text);
  if (paragraphs.length < 3) {
    return { uniform: false, count: paragraphs.length, cv: 0, detail: "too_few_paragraphs" };
  }
  const lengths = paragraphs.map((p) => p.length);
  const avg = lengths.reduce((s, v) => s + v, 0) / lengths.length;
  const stdev = Math.sqrt(lengths.reduce((s, v) => s + (v - avg) ** 2, 0) / lengths.length);
  const cv = avg > 0 ? stdev / avg : 0;
  // CV < 0.25 means paragraphs are suspiciously uniform in length
  return {
    uniform: cv < 0.25,
    count: paragraphs.length,
    avg_length: Math.round(avg),
    stdev: Math.round(stdev * 10) / 10,
    cv: Number(cv.toFixed(3)),
    detail: cv < 0.15 ? "very_uniform_ai_likely" : cv < 0.25 ? "somewhat_uniform" : "natural_variation",
  };
}

export function extractTextProfile(text, { suspectPatterns = DEFAULT_SUSPECT_PATTERNS } = {}) {
  const paragraphs = splitParagraphs(text);
  const sentences = splitSentences(text);
  const paragraphStats = summarizeLengths(paragraphs.map((item) => item.length));
  const sentenceStats = summarizeLengths(sentences.map((item) => item.length));
  const transitions = extractTransitions(text);
  const openers = extractSentenceOpeners(text);
  const judgmentPatterns = extractJudgmentPatterns(text);
  const avoidPatternBundle = deriveAvoidPatterns(text, suspectPatterns);
  const structuralFlags = deriveStructuralPatterns(text);
  const uniformity = detectParagraphUniformity(text);
  const openerDiversity = detectParagraphOpenerRepetition(text);

  return {
    char_count: String(text ?? "").length,
    paragraph_stats: paragraphStats,
    sentence_stats: sentenceStats,
    preferred_transitions: transitions,
    sentence_openers: openers,
    judgment_patterns: judgmentPatterns,
    avoid_patterns: avoidPatternBundle.avoidPatterns,
    avoid_patterns_detail: avoidPatternBundle.detail,
    structural_flags: structuralFlags,
    paragraph_uniformity: uniformity,
    paragraph_opener_diversity: openerDiversity,
  };
}

export async function readTextSource(inputPath) {
  const resolved = path.resolve(inputPath);
  const raw = await readFile(resolved, "utf8");
  const cleaned = raw.charCodeAt(0) === 0xfeff ? raw.slice(1) : raw;
  const ext = path.extname(resolved).toLowerCase();

  if (ext === ".json") {
    const payload = JSON.parse(cleaned);
    const article =
      payload.final_article_result ||
      payload.review_rewrite_package?.final_article_result ||
      payload.publish_package ||
      payload;
    const text =
      article.body_markdown ||
      article.article_markdown ||
      article.content_markdown ||
      article.content_html ||
      cleaned;
    return {
      resolved,
      kind: "json",
      text: extractChineseBody(text),
      rawText: text,
    };
  }

  return {
    resolved,
    kind: ext === ".md" ? "markdown" : "text",
    text: extractChineseBody(cleaned),
    rawText: cleaned,
  };
}

export function diffMetric(beforeValue, afterValue) {
  return clampNumber(afterValue) - clampNumber(beforeValue);
}

// ---------------------------------------------------------------------------
// Trending / high-engagement style extraction utilities
// ---------------------------------------------------------------------------

/**
 * Classify text as primarily Chinese or English.
 * Returns "zh" if CJK chars exceed 30% of non-whitespace, otherwise "en".
 */
export function classifyLanguage(text) {
  const stripped = String(text ?? "").replace(/\s/g, "");
  if (!stripped.length) {
    return "en";
  }
  const cjkCount = (stripped.match(/[\u4e00-\u9fff\u3400-\u4dbf]/g) || []).length;
  return cjkCount / stripped.length > 0.3 ? "zh" : "en";
}

/**
 * Extract the opening hook (first sentence or first line) from a post.
 * For Chinese: split on 。！？ and take the first segment.
 * For English: split on . ! ? and take the first segment.
 */
export function extractHook(text) {
  const trimmed = String(text ?? "").trim();
  if (!trimmed) {
    return "";
  }
  const lang = classifyLanguage(trimmed);
  let hook = "";
  if (lang === "zh") {
    const match = trimmed.match(/^(.+?)[。！？!?]/);
    hook = match ? match[1].trim() : trimmed.split("\n")[0].trim();
  } else {
    const match = trimmed.match(/^(.+?)[.!?]/);
    hook = match ? match[1].trim() : trimmed.split("\n")[0].trim();
  }
  // Cap at 80 chars — hooks should be punchy
  return hook.length > 80 ? hook.slice(0, 80) : hook;
}

/**
 * Extract hook patterns from an array of post texts.
 * Groups hooks by structural similarity and returns the most common patterns.
 * Each post should be { text: string, engagement_score: number }.
 */
export function extractHookPatterns(posts) {
  const zhHooks = [];
  const enHooks = [];

  for (const post of Array.isArray(posts) ? posts : []) {
    const text = String(post?.text ?? "");
    const hook = extractHook(text);
    if (!hook || hook.length < 4) {
      continue;
    }
    const lang = classifyLanguage(text);
    const score = Number(post?.engagement_score ?? 0);
    if (lang === "zh") {
      zhHooks.push({ hook, score });
    } else {
      enHooks.push({ hook, score });
    }
  }

  // Sort by engagement, take top hooks
  zhHooks.sort((a, b) => b.score - a.score);
  enHooks.sort((a, b) => b.score - a.score);

  return {
    hook_patterns_zh: zhHooks.slice(0, 12).map((item) => item.hook),
    hook_patterns_en: enHooks.slice(0, 12).map((item) => item.hook),
  };
}

/**
 * Extract vocabulary that appears disproportionately in high-engagement posts.
 * Compares word frequency in top-engagement posts vs. the full set.
 *
 * @param {Array<{text: string, engagement_score: number}>} posts
 * @param {number} topRatio - fraction of posts considered "high engagement" (default 0.3)
 * @returns {{ zh: string[], en: string[] }}
 */
export function extractDifferentialVocabulary(posts, topRatio = 0.3) {
  const sorted = [...(Array.isArray(posts) ? posts : [])].sort(
    (a, b) => (b.engagement_score ?? 0) - (a.engagement_score ?? 0)
  );
  if (sorted.length < 4) {
    return { zh: [], en: [] };
  }
  const topCount = Math.max(2, Math.floor(sorted.length * topRatio));
  const topPosts = sorted.slice(0, topCount);
  const restPosts = sorted.slice(topCount);

  function buildFreqMap(postList, lang) {
    const freq = new Map();
    for (const post of postList) {
      const text = String(post?.text ?? "");
      if (classifyLanguage(text) !== lang) {
        continue;
      }
      let tokens;
      if (lang === "zh") {
        // Extract 2-4 char Chinese phrases via sliding window
        const chars = text.replace(/[^\u4e00-\u9fff]/g, "");
        tokens = [];
        for (let width = 2; width <= 4; width++) {
          for (let i = 0; i <= chars.length - width; i++) {
            tokens.push(chars.slice(i, i + width));
          }
        }
      } else {
        tokens = text.toLowerCase().split(/\W+/).filter((t) => t.length >= 3);
      }
      const seen = new Set();
      for (const token of tokens) {
        if (!seen.has(token)) {
          seen.add(token);
          freq.set(token, (freq.get(token) || 0) + 1);
        }
      }
    }
    return freq;
  }

  function differential(lang) {
    const topFreq = buildFreqMap(topPosts, lang);
    const restFreq = buildFreqMap(restPosts, lang);
    const topTotal = topPosts.filter((p) => classifyLanguage(p.text ?? "") === lang).length || 1;
    const restTotal = restPosts.filter((p) => classifyLanguage(p.text ?? "") === lang).length || 1;

    const scored = [];
    for (const [token, count] of topFreq) {
      if (count < 2) {
        continue;
      }
      const topRate = count / topTotal;
      const restRate = (restFreq.get(token) || 0) / restTotal;
      // Token must appear at least 2x more frequently in top posts
      if (topRate > restRate * 2 && topRate > 0.15) {
        scored.push({ token, lift: topRate / Math.max(restRate, 0.01), count });
      }
    }
    scored.sort((a, b) => b.lift - a.lift || b.count - a.count);
    return scored.slice(0, 15).map((item) => item.token);
  }

  return {
    zh: differential("zh"),
    en: differential("en"),
  };
}

/**
 * Analyze sentence-length rhythm in a text and classify the dominant pattern.
 *
 * Patterns:
 * - "punch": alternating short-long (high variance between consecutive sentences)
 * - "cascade": gradually increasing sentence lengths
 * - "uniform": metronomic, similar lengths throughout
 * - "natural": no dominant pattern (best for human-like text)
 *
 * @param {string} text
 * @returns {{ dominant: string, avg_first_sentence_chars: number, variance_ratio: number }}
 */
export function extractRhythmSignature(text) {
  const sentences = splitSentences(text);
  if (sentences.length < 4) {
    return { dominant: "natural", avg_first_sentence_chars: 0, variance_ratio: 0 };
  }
  const lengths = sentences.map((s) => s.length);
  const avg = lengths.reduce((s, v) => s + v, 0) / lengths.length;

  // Compute consecutive-pair variance (how much adjacent sentences differ)
  let pairDiffSum = 0;
  for (let i = 1; i < lengths.length; i++) {
    pairDiffSum += Math.abs(lengths[i] - lengths[i - 1]);
  }
  const avgPairDiff = pairDiffSum / (lengths.length - 1);
  const varianceRatio = avg > 0 ? avgPairDiff / avg : 0;

  // Check for cascade (monotonically increasing tendency)
  let increasing = 0;
  for (let i = 1; i < lengths.length; i++) {
    if (lengths[i] > lengths[i - 1]) {
      increasing++;
    }
  }
  const cascadeRatio = increasing / (lengths.length - 1);

  // Compute overall CV
  const stdev = Math.sqrt(lengths.reduce((s, v) => s + (v - avg) ** 2, 0) / lengths.length);
  const cv = avg > 0 ? stdev / avg : 0;

  let dominant;
  if (cv < 0.2) {
    dominant = "uniform";
  } else if (varianceRatio > 0.6) {
    dominant = "punch";
  } else if (cascadeRatio > 0.7) {
    dominant = "cascade";
  } else {
    dominant = "natural";
  }

  // Average length of first sentences (hooks)
  const firstSentences = sentences.filter((_, i) => {
    // First sentence of each "paragraph" (after double newline)
    if (i === 0) return true;
    const preceding = text.indexOf(sentences[i]);
    return preceding > 0 && text.slice(Math.max(0, preceding - 3), preceding).includes("\n\n");
  });
  const avgFirst = firstSentences.length
    ? Math.round(firstSentences.reduce((s, v) => s + v.length, 0) / firstSentences.length)
    : 0;

  return {
    dominant,
    avg_first_sentence_chars: avgFirst,
    variance_ratio: Number(varianceRatio.toFixed(3)),
  };
}

