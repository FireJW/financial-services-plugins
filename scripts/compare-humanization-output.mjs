#!/usr/bin/env node

import { mkdir, writeFile } from "fs/promises";
import path from "path";
import {
  diffMetric,
  extractTextProfile,
  readTextSource,
} from "./style-profile-utils.mjs";

function parseArgs(argv) {
  const args = argv.slice(2);
  return args.reduce(
    (result, arg, index) => {
      if (arg === "--low") {
        result.low = args[index + 1] || result.low;
      }
      if (arg === "--high") {
        result.high = args[index + 1] || result.high;
      }
      if (arg === "--output") {
        result.output = args[index + 1] || result.output;
      }
      if (arg === "--json-output") {
        result.jsonOutput = args[index + 1] || result.jsonOutput;
      }
      return result;
    },
    {
      low: "",
      high: "",
      output: "",
      jsonOutput: "",
    }
  );
}

function summarizeSuspectHits(profile) {
  return profile.avoid_patterns_detail.reduce((total, item) => total + Number(item.count || 0), 0);
}

function buildMarkdownReport(lowSource, highSource, lowProfile, highProfile) {
  const lowSuspects = summarizeSuspectHits(lowProfile);
  const highSuspects = summarizeSuspectHits(highProfile);
  const paragraphUniformityDelta = diffMetric(lowProfile.paragraph_stats.uniformity, highProfile.paragraph_stats.uniformity);
  const sentenceUniformityDelta = diffMetric(lowProfile.sentence_stats.uniformity, highProfile.sentence_stats.uniformity);
  const likelyWins = [];

  if (highSuspects < lowSuspects) {
    likelyWins.push(`模板短语命中从 ${lowSuspects} 降到 ${highSuspects}`);
  }
  if (highProfile.paragraph_stats.uniformity > lowProfile.paragraph_stats.uniformity) {
    likelyWins.push(`段落长度波动更自然（uniformity ${lowProfile.paragraph_stats.uniformity} -> ${highProfile.paragraph_stats.uniformity}）`);
  }
  if (Math.abs(sentenceUniformityDelta) > 0.03) {
    likelyWins.push(`句长分布更松弛（uniformity ${lowProfile.sentence_stats.uniformity} -> ${highProfile.sentence_stats.uniformity}）`);
  }

  // Check structural pattern improvements
  const lowFlagged = (lowProfile.structural_flags || []).filter((f) => f.flagged);
  const highFlagged = (highProfile.structural_flags || []).filter((f) => f.flagged);
  if (lowFlagged.length > highFlagged.length) {
    likelyWins.push(`结构性 AI 模式从 ${lowFlagged.length} 个降到 ${highFlagged.length} 个`);
  }

  // Check paragraph uniformity improvement
  const lowUnif = lowProfile.paragraph_uniformity || {};
  const highUnif = highProfile.paragraph_uniformity || {};
  if (lowUnif.uniform && !highUnif.uniform) {
    likelyWins.push(`段落均匀度从”${lowUnif.detail}”改善为”${highUnif.detail}”`);
  }

  // Check paragraph opener diversity improvement
  const lowOpenerDiv = lowProfile.paragraph_opener_diversity || {};
  const highOpenerDiv = highProfile.paragraph_opener_diversity || {};
  if ((lowOpenerDiv.diversity_ratio || 1) < (highOpenerDiv.diversity_ratio || 1)) {
    likelyWins.push(`段首多样性从 ${lowOpenerDiv.diversity_ratio || “n/a”} 提升到 ${highOpenerDiv.diversity_ratio || “n/a”}`);
  }
  if (lowOpenerDiv.flagged && !highOpenerDiv.flagged) {
    likelyWins.push(`段首重复问题已修复`);
  }

  // Check sentence opener diversity
  const lowOpeners = lowProfile.sentence_openers || [];
  const highOpeners = highProfile.sentence_openers || [];
  const lowOpenerCount = lowOpeners.length;
  const highOpenerCount = highOpeners.length;
  if (highOpenerCount > lowOpenerCount) {
    likelyWins.push(`句首词汇多样性从 ${lowOpenerCount} 种提升到 ${highOpenerCount} 种`);
  }

  return [
    “# Humanization Comparison”,
    “”,
    `- Low source: ${lowSource}`,
    `- High source: ${highSource}`,
    “”,
    “## Scorecard”,
    “”,
    `- Paragraph count: ${lowProfile.paragraph_stats.count} -> ${highProfile.paragraph_stats.count}`,
    `- Paragraph avg chars: ${lowProfile.paragraph_stats.avg} -> ${highProfile.paragraph_stats.avg}`,
    `- Paragraph uniformity: ${lowProfile.paragraph_stats.uniformity} -> ${highProfile.paragraph_stats.uniformity}`,
    `- Paragraph CV: ${lowUnif.cv || “n/a”} -> ${highUnif.cv || “n/a”} (< 0.25 = AI-like)`,
    `- Paragraph opener diversity: ${lowOpenerDiv.diversity_ratio || “n/a”} -> ${highOpenerDiv.diversity_ratio || “n/a”} (< 0.6 = repetitive)`,
    `- Paragraph opener repeats: ${(lowOpenerDiv.repeated_openers || []).length} -> ${(highOpenerDiv.repeated_openers || []).length}`,
    `- Sentence avg chars: ${lowProfile.sentence_stats.avg} -> ${highProfile.sentence_stats.avg}`,
    `- Sentence uniformity: ${lowProfile.sentence_stats.uniformity} -> ${highProfile.sentence_stats.uniformity}`,
    `- Sentence opener types: ${lowOpenerCount} -> ${highOpenerCount}`,
    `- Suspect phrase hits: ${lowSuspects} -> ${highSuspects}`,
    `- Structural flags: ${lowFlagged.length} -> ${highFlagged.length}`,
    “”,
    “## Likely Improvements”,
    “”,
    ...(likelyWins.length ? likelyWins.map((item) => `- ${item}`) : [“- 没看到明显的”更像人”提升，需要继续调规则。”]),
    “”,
    “## Top Suspect Phrases Still Firing”,
    “”,
    ...highProfile.avoid_patterns_detail
      .filter((item) => item.count > 0)
      .slice(0, 5)
      .map((item) => `- ${item.pattern}: ${item.count}`),
    “”,
    ...(highFlagged.length
      ? [
          “## Structural Patterns Still Flagged”,
          “”,
          ...highFlagged.map((f) => `- ${f.label}: ${f.count} hits (${f.density_per_1k_chars}/1k, threshold ${f.threshold_per_1k})`),
          “”,
        ]
      : []),
    ...((highOpenerDiv.repeated_openers || []).length
      ? [
          “## Repeated Paragraph Openers”,
          “”,
          ...(highOpenerDiv.repeated_openers || []).map((r) => `- “${r.opener}”: ${r.count} times`),
          “”,
        ]
      : []),
  ].join(“\n”);
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.low || !args.high) {
    console.error("Usage: node scripts/compare-humanization-output.mjs --low <draft-a> --high <draft-b> [--output report.md] [--json-output metrics.json]");
    process.exit(1);
  }

  const [lowSource, highSource] = await Promise.all([readTextSource(args.low), readTextSource(args.high)]);
  const lowProfile = extractTextProfile(lowSource.text);
  const highProfile = extractTextProfile(highSource.text);
  const report = buildMarkdownReport(lowSource.resolved, highSource.resolved, lowProfile, highProfile);
  const result = {
    status: "ready",
    low: {
      path: lowSource.resolved,
      ...lowProfile,
    },
    high: {
      path: highSource.resolved,
      ...highProfile,
    },
    deltas: {
      paragraph_count: diffMetric(lowProfile.paragraph_stats.count, highProfile.paragraph_stats.count),
      paragraph_uniformity: diffMetric(lowProfile.paragraph_stats.uniformity, highProfile.paragraph_stats.uniformity),
      sentence_uniformity: diffMetric(lowProfile.sentence_stats.uniformity, highProfile.sentence_stats.uniformity),
      suspect_hits: summarizeSuspectHits(highProfile) - summarizeSuspectHits(lowProfile),
      structural_flags: (highProfile.structural_flags || []).filter((f) => f.flagged).length - (lowProfile.structural_flags || []).filter((f) => f.flagged).length,
      paragraph_opener_diversity: diffMetric(
        (lowProfile.paragraph_opener_diversity || {}).diversity_ratio || 0,
        (highProfile.paragraph_opener_diversity || {}).diversity_ratio || 0
      ),
      sentence_opener_types: (highProfile.sentence_openers || []).length - (lowProfile.sentence_openers || []).length,
    },
    report_markdown: report,
  };

  if (args.output) {
    const outputPath = path.resolve(args.output);
    await mkdir(path.dirname(outputPath), { recursive: true });
    await writeFile(outputPath, report, "utf8");
  }
  if (args.jsonOutput) {
    const outputPath = path.resolve(args.jsonOutput);
    await mkdir(path.dirname(outputPath), { recursive: true });
    await writeFile(outputPath, JSON.stringify(result, null, 2), "utf8");
  }

  console.log(JSON.stringify(result, null, 2));
}

main().catch((error) => {
  console.error(error?.stack || error?.message || String(error));
  process.exit(1);
});

