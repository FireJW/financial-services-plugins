#!/usr/bin/env node

import { mkdir, readFile, writeFile } from "fs/promises";
import path from "path";
import {
  extractTextProfile,
  readTextSource,
  extractHook,
  classifyLanguage,
} from "./style-profile-utils.mjs";

function parseArgs(argv) {
  const args = argv.slice(2);
  return args.reduce(
    (result, arg, index) => {
      if (arg === "--input") {
        result.input = args[index + 1] || result.input;
      }
      if (arg === "--profile") {
        result.profile = args[index + 1] || result.profile;
      }
      return result;
    },
    {
      input: "",
      profile: "",
    }
  );
}

function mergeUnique(primary, secondary, limit = 24) {
  const merged = [];
  for (const item of [...primary, ...secondary]) {
    const cleaned = String(item ?? "").trim();
    if (!cleaned || merged.includes(cleaned)) {
      continue;
    }
    merged.push(cleaned);
    if (limit && merged.length >= limit) {
      break;
    }
  }
  return merged;
}

function readJsonSafe(rawText, fallback) {
  try {
    return JSON.parse(rawText);
  } catch {
    return fallback;
  }
}

function buildStyleDelta(previousProfile, nextProfile, articleProfile) {
  const previousMemory = previousProfile.style_memory || {};
  const nextMemory = nextProfile.style_memory || {};
  const previousTransitions = previousMemory.preferred_transitions || [];
  const nextTransitions = nextMemory.preferred_transitions || [];
  const previousAvoid = previousMemory.avoid_patterns || [];
  const nextAvoid = nextMemory.avoid_patterns || [];
  const addedTransitions = nextTransitions.filter((item) => !previousTransitions.includes(item));
  const addedAvoid = nextAvoid.filter((item) => !previousAvoid.includes(item));
  const articleJudgments = articleProfile.judgment_patterns.slice(0, 5).map((item) => item.phrase);

  return {
    generated_at: new Date().toISOString(),
    added_transitions: addedTransitions,
    added_avoid_patterns: addedAvoid,
    judgment_patterns: articleJudgments,
    target_band_before: previousMemory.target_band || "",
    target_band_after: nextMemory.target_band || "",
    change_summary: [
      addedTransitions.length ? `Added ${addedTransitions.length} new transition cues.` : "No new transition cues were added.",
      addedAvoid.length ? `Expanded avoid-pattern list by ${addedAvoid.length}.` : "Avoid-pattern list stayed stable.",
      articleJudgments.length ? `Tracked ${articleJudgments.length} high-signal judgment patterns from the published piece.` : "",
    ].filter(Boolean),
  };
}

function mergeTrendingSignals(existingTrending, articleProfile, source) {
  const trending = { ...existingTrending };
  trending.updated_at = new Date().toISOString();
  trending.post_count = (trending.post_count || 0) + 1;
  trending.total_posts_analyzed = (trending.total_posts_analyzed || 0) + 1;

  // Extract hook from the new article
  const hook = extractHook(source.text);
  const lang = classifyLanguage(source.text);

  // Merge hook patterns
  if (hook && lang === "zh") {
    const existingHooks = Array.isArray(trending.hook_patterns_zh) ? trending.hook_patterns_zh : [];
    if (!existingHooks.includes(hook)) {
      trending.hook_patterns_zh = [...existingHooks, hook].slice(0, 16);
    }
  } else if (hook && lang === "en") {
    const existingHooks = Array.isArray(trending.hook_patterns_en) ? trending.hook_patterns_en : [];
    if (!existingHooks.includes(hook)) {
      trending.hook_patterns_en = [...existingHooks, hook].slice(0, 16);
    }
  }

  // Merge preferred openers from the article's sentence openers
  const articleOpeners = (articleProfile.sentence_openers || []).slice(0, 4).map((item) => item.phrase);
  if (articleOpeners.length && lang === "zh") {
    const existingOpeners = Array.isArray(trending.preferred_openers_zh) ? trending.preferred_openers_zh : [];
    trending.preferred_openers_zh = mergeUnique(existingOpeners, articleOpeners, 12);
  }

  // Update sentence stats from the latest article
  if (lang === "zh" && articleProfile.sentence_stats) {
    trending.sentence_stats_zh = {
      avg: articleProfile.sentence_stats.avg,
      p25: articleProfile.sentence_stats.p25,
      p75: articleProfile.sentence_stats.p75,
      uniformity: articleProfile.sentence_stats.uniformity,
    };
  }

  return trending;
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.input || !args.profile) {
    console.error("Usage: node scripts/corpus-style-append.mjs --input <publish-package.json|article-result.json|markdown> --profile <corpus-style-profile.json>");
    process.exit(1);
  }

  const source = await readTextSource(args.input);
  if (source.text.length < 160) {
    throw new Error(`Not enough Chinese text in ${source.resolved} to append into the corpus profile.`);
  }

  const profilePath = path.resolve(args.profile);
  const profileRaw = await readFile(profilePath, "utf8").catch(() => "");
  const previousProfile = readJsonSafe(profileRaw, { _meta: {}, style_memory: {}, analysis: {} });
  const previousMemory = previousProfile.style_memory || {};
  const articleProfile = extractTextProfile(source.text);

  const nextProfile = {
    _meta: {
      ...(previousProfile._meta || {}),
      last_appended: new Date().toISOString(),
      last_input_path: source.resolved,
      append_count: Number(previousProfile._meta?.append_count || 0) + 1,
    },
    style_memory: {
      ...previousMemory,
      preferred_transitions: mergeUnique(
        previousMemory.preferred_transitions || [],
        articleProfile.preferred_transitions.map((item) => item.phrase),
        24
      ),
      avoid_patterns: mergeUnique(previousMemory.avoid_patterns || [], articleProfile.avoid_patterns, 32),
      corpus_notes: mergeUnique(
        previousMemory.corpus_notes || [],
        articleProfile.judgment_patterns.map((item) => item.phrase),
        12
      ),
    },
    analysis: {
      ...(previousProfile.analysis || {}),
      last_article_profile: articleProfile,
    },
    trending_signals: mergeTrendingSignals(
      previousProfile.trending_signals || {},
      articleProfile,
      source
    ),
  };

  const delta = buildStyleDelta(previousProfile, nextProfile, articleProfile);
  const historyDir = path.join(path.dirname(profilePath), "history", path.basename(profilePath, ".json"));
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  await mkdir(historyDir, { recursive: true });
  const snapshotPath = path.join(historyDir, `${stamp}-before.json`);
  const deltaPath = path.join(historyDir, `${stamp}-delta.json`);
  if (profileRaw) {
    await writeFile(snapshotPath, JSON.stringify(previousProfile, null, 2), "utf8");
  }
  await writeFile(deltaPath, JSON.stringify(delta, null, 2), "utf8");
  await writeFile(profilePath, JSON.stringify(nextProfile, null, 2), "utf8");

  console.log(
    JSON.stringify(
      {
        status: "appended",
        input: source.resolved,
        profile: profilePath,
        snapshot_path: profileRaw ? snapshotPath : "",
        delta_path: deltaPath,
        change_summary: delta.change_summary,
        added_transitions: delta.added_transitions,
        added_avoid_patterns: delta.added_avoid_patterns,
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

