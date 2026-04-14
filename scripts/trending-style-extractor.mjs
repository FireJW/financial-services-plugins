#!/usr/bin/env node

/**
 * trending-style-extractor.mjs
 *
 * Extracts writing style patterns from high-engagement X posts and merges
 * them into the corpus style profile as `trending_signals`.
 *
 * Input sources (in priority order):
 *   1. --input <path>   : A JSON file from x-creator-inspiration-fetch.mjs
 *                         or an x-index result JSON
 *   2. --scan-dir <dir> : Scan a directory of x-index result files
 *   3. Default: scan runtime-state/x-index/ for recent results
 *
 * Output:
 *   Merges a `trending_signals` key into the corpus style profile at
 *   --profile <path> (default: profiles/corpus-style-profile.json)
 *
 * Usage:
 *   node scripts/trending-style-extractor.mjs \
 *     --input trending-posts.json \
 *     [--profile profiles/corpus-style-profile.json] \
 *     [--min-engagement 1000] \
 *     [--max-posts 50]
 */

import { mkdir, readdir, readFile, stat, writeFile } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";
import {
  classifyLanguage,
  extractHookPatterns,
  extractDifferentialVocabulary,
  extractRhythmSignature,
  extractTextProfile,
  splitSentences,
} from "./style-profile-utils.mjs";

const SCRIPTS_DIR = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(SCRIPTS_DIR, "..");

const DEFAULT_PROFILE_PATH = path.join(
  REPO_ROOT,
  "financial-analysis",
  "skills",
  "autoresearch-info-index",
  "profiles",
  "corpus-style-profile.json"
);

const DEFAULT_SCAN_DIR = path.join(REPO_ROOT, "runtime-state", "x-index");

function parseArgs(argv) {
  const args = argv.slice(2);
  return args.reduce(
    (result, arg, index) => {
      if (arg === "--input") {
        result.input = args[index + 1] || result.input;
      }
      if (arg === "--scan-dir") {
        result.scanDir = args[index + 1] || result.scanDir;
      }
      if (arg === "--profile") {
        result.profile = args[index + 1] || result.profile;
      }
      if (arg === "--min-engagement") {
        result.minEngagement =
          Number.parseInt(args[index + 1], 10) || result.minEngagement;
      }
      if (arg === "--max-posts") {
        result.maxPosts =
          Number.parseInt(args[index + 1], 10) || result.maxPosts;
      }
      if (arg === "--dry-run") {
        result.dryRun = true;
      }
      return result;
    },
    {
      input: "",
      scanDir: "",
      profile: DEFAULT_PROFILE_PATH,
      minEngagement: 1000,
      maxPosts: 50,
      dryRun: false,
    }
  );
}

/**
 * Load posts from a creator-inspiration-fetch output or x-index result.
 */
async function loadPostsFromFile(filePath) {
  const raw = await readFile(filePath, "utf8");
  const data = JSON.parse(raw);

  // Format 1: x-creator-inspiration-fetch output
  if (Array.isArray(data.posts)) {
    return data.posts;
  }

  // Format 2: x-index result (has x_post_records or post_records)
  const records =
    data.x_post_records ||
    data.post_records ||
    data.kept_posts ||
    data.scored_posts ||
    [];
  if (Array.isArray(records)) {
    return records.map((record) => {
      const engagement = record.engagement || {};
      const engagementScore =
        (engagement.likes || 0) +
        2 * (engagement.reposts || 0) +
        (engagement.replies || 0);
      return {
        text: record.post_text_raw || record.post_text || record.combined_summary || "",
        author: record.author_handle || "",
        language: classifyLanguage(record.post_text_raw || ""),
        engagement,
        engagement_score: engagementScore,
        source_url: record.post_url || "",
      };
    });
  }

  return [];
}

/**
 * Scan a directory for recent x-index result JSON files and collect posts.
 */
async function scanDirectoryForPosts(dirPath, maxFiles = 10) {
  let entries;
  try {
    entries = await readdir(dirPath, { withFileTypes: true });
  } catch {
    return [];
  }

  const jsonFiles = [];
  for (const entry of entries) {
    if (!entry.isFile() || !entry.name.endsWith(".json")) {
      continue;
    }
    const fullPath = path.join(dirPath, entry.name);
    const info = await stat(fullPath);
    jsonFiles.push({ path: fullPath, mtimeMs: info.mtimeMs });
  }

  // Sort by most recent first
  jsonFiles.sort((a, b) => b.mtimeMs - a.mtimeMs);

  const allPosts = [];
  for (const file of jsonFiles.slice(0, maxFiles)) {
    try {
      const posts = await loadPostsFromFile(file.path);
      allPosts.push(...posts);
    } catch {
      // Skip unparseable files
    }
  }
  return allPosts;
}

/**
 * Build the trending_signals object from a collection of posts.
 */
function buildTrendingSignals(posts, minEngagement) {
  // Filter by engagement threshold
  const qualifying = posts.filter(
    (p) => (p.engagement_score || 0) >= minEngagement
  );

  if (qualifying.length === 0) {
    return null;
  }

  // Extract hook patterns
  const hookPatterns = extractHookPatterns(qualifying);

  // Extract differential vocabulary
  const vocabulary = extractDifferentialVocabulary(posts);

  // Analyze rhythm from Chinese high-engagement posts
  const zhPosts = qualifying.filter((p) => classifyLanguage(p.text || "") === "zh");
  const enPosts = qualifying.filter((p) => classifyLanguage(p.text || "") === "en");

  const zhTexts = zhPosts.map((p) => p.text).join("\n\n");
  const enTexts = enPosts.map((p) => p.text).join("\n\n");

  const zhRhythm = zhTexts.length > 100 ? extractRhythmSignature(zhTexts) : null;
  const enRhythm = enTexts.length > 100 ? extractRhythmSignature(enTexts) : null;

  // Extract sentence-level profile from high-engagement Chinese posts
  const zhProfile = zhTexts.length > 200 ? extractTextProfile(zhTexts) : null;

  // Build source post references (top 8 by engagement)
  const topPosts = [...qualifying]
    .sort((a, b) => (b.engagement_score || 0) - (a.engagement_score || 0))
    .slice(0, 8);

  return {
    updated_at: new Date().toISOString(),
    post_count: qualifying.length,
    total_posts_analyzed: posts.length,
    min_engagement_threshold: minEngagement,
    hook_patterns_zh: hookPatterns.hook_patterns_zh,
    hook_patterns_en: hookPatterns.hook_patterns_en,
    high_engagement_vocabulary_zh: vocabulary.zh,
    high_engagement_vocabulary_en: vocabulary.en,
    rhythm_zh: zhRhythm,
    rhythm_en: enRhythm,
    sentence_stats_zh: zhProfile
      ? {
          avg: zhProfile.sentence_stats.avg,
          p25: zhProfile.sentence_stats.p25,
          p75: zhProfile.sentence_stats.p75,
          uniformity: zhProfile.sentence_stats.uniformity,
        }
      : null,
    preferred_openers_zh: zhProfile
      ? zhProfile.sentence_openers.slice(0, 8).map((item) => item.phrase)
      : [],
    source_posts: topPosts.map((p) => ({
      url: p.source_url || "",
      author: p.author || "",
      engagement_score: p.engagement_score || 0,
      hook: p.hook || extractHookFromText(p.text),
      language: classifyLanguage(p.text || ""),
    })),
  };
}

function extractHookFromText(text) {
  const trimmed = String(text || "").trim();
  const firstLine = trimmed.split("\n")[0] || "";
  return firstLine.length > 60 ? firstLine.slice(0, 60) + "..." : firstLine;
}

/**
 * Merge trending_signals into the corpus style profile.
 * Preserves existing profile data; only updates the trending_signals key.
 */
async function mergeIntoProfile(profilePath, trendingSignals) {
  let existing = { _meta: {}, style_memory: {}, analysis: {} };
  try {
    const raw = await readFile(profilePath, "utf8");
    existing = JSON.parse(raw);
  } catch {
    // Start fresh if profile doesn't exist
  }

  // Merge trending hook patterns into style_memory for pipeline consumption
  const styleMemory = existing.style_memory || {};

  // Add trending hooks to corpus_notes (additive, deduplicated)
  const existingNotes = Array.isArray(styleMemory.corpus_notes)
    ? styleMemory.corpus_notes
    : [];
  const trendingHooks = (trendingSignals.hook_patterns_zh || []).slice(0, 4);
  const combinedNotes = [
    ...existingNotes,
    ...trendingHooks.filter((h) => !existingNotes.includes(h)),
  ].slice(0, 14);
  if (combinedNotes.length > existingNotes.length) {
    styleMemory.corpus_notes = combinedNotes;
  }

  // Add high-engagement vocabulary as preferred transitions (if they look like transitions)
  const existingTransitions = Array.isArray(styleMemory.preferred_transitions)
    ? styleMemory.preferred_transitions
    : [];
  const trendingOpeners = (trendingSignals.preferred_openers_zh || []).slice(0, 4);
  const combinedTransitions = [
    ...existingTransitions,
    ...trendingOpeners.filter((t) => !existingTransitions.includes(t)),
  ].slice(0, 14);
  if (combinedTransitions.length > existingTransitions.length) {
    styleMemory.preferred_transitions = combinedTransitions;
  }

  existing.style_memory = styleMemory;
  existing.trending_signals = trendingSignals;

  // Update meta
  existing._meta = existing._meta || {};
  existing._meta.trending_signals_updated_at = trendingSignals.updated_at;
  existing._meta.trending_posts_count = trendingSignals.post_count;

  return existing;
}

async function main() {
  const args = parseArgs(process.argv);

  // Collect posts from input sources
  let posts = [];

  if (args.input) {
    const inputPath = path.resolve(args.input);
    console.error(`Loading posts from: ${inputPath}`);
    posts = await loadPostsFromFile(inputPath);
  } else {
    const scanDir = args.scanDir || DEFAULT_SCAN_DIR;
    console.error(`Scanning for x-index results in: ${scanDir}`);
    posts = await scanDirectoryForPosts(scanDir);
  }

  if (posts.length === 0) {
    console.error("No posts found. Provide --input or ensure runtime-state/x-index/ has results.");
    process.exit(1);
  }

  // Cap at max posts
  posts = posts.slice(0, args.maxPosts);
  console.error(`Analyzing ${posts.length} posts (min engagement: ${args.minEngagement})`);

  // Build trending signals
  const trendingSignals = buildTrendingSignals(posts, args.minEngagement);

  if (!trendingSignals) {
    console.error(
      `No posts met the engagement threshold of ${args.minEngagement}. ` +
        "Try --min-engagement 0 to include all posts."
    );
    process.exit(1);
  }

  if (args.dryRun) {
    console.log(JSON.stringify(trendingSignals, null, 2));
    return;
  }

  // Merge into profile
  const profilePath = path.resolve(args.profile);
  const updatedProfile = await mergeIntoProfile(profilePath, trendingSignals);

  await mkdir(path.dirname(profilePath), { recursive: true });
  await writeFile(profilePath, JSON.stringify(updatedProfile, null, 2), "utf8");

  const summary = {
    status: "ready",
    profile: profilePath,
    posts_analyzed: posts.length,
    qualifying_posts: trendingSignals.post_count,
    zh_hooks: trendingSignals.hook_patterns_zh.length,
    en_hooks: trendingSignals.hook_patterns_en.length,
    zh_vocabulary: trendingSignals.high_engagement_vocabulary_zh.length,
    en_vocabulary: trendingSignals.high_engagement_vocabulary_en.length,
    rhythm_zh: trendingSignals.rhythm_zh?.dominant || "n/a",
  };

  console.log(JSON.stringify(summary, null, 2));
}

main().catch((error) => {
  console.error(error?.stack || error?.message || String(error));
  process.exit(1);
});
