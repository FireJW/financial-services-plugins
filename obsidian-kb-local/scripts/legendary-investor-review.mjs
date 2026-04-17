import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadConfig } from "../src/config.mjs";
import {
  buildLegendaryInvestorReview,
  renderLegendaryInvestorReview
} from "../src/legendary-investor-review.mjs";
import { writeLegendaryArtifactSynthesis } from "../src/legendary-investor-writeback.mjs";

export function parseLegendaryInvestorReviewArgs(args = []) {
  const list = Array.isArray(args) ? args : [];
  return {
    json: list.includes("--json"),
    jsonFile: String(getArg(list, "json-file") || "").trim(),
    writeJson: list.includes("--write-json"),
    outputJsonFile: String(getArg(list, "output-json-file") || "").trim(),
    factsFile: String(getArg(list, "facts-file") || "").trim(),
    facts: collectFactArgs(list),
    writeSynthesis: list.includes("--write-synthesis"),
    skipLinks: list.includes("--skip-links"),
    skipViews: list.includes("--skip-views")
  };
}

export function runLegendaryInvestorReview(args = process.argv.slice(2), runtime = {}) {
  const command = parseLegendaryInvestorReviewArgs(args);
  if (command.json && command.writeSynthesis) {
    throw new Error("--write-synthesis cannot be combined with --json.");
  }
  const config = runtime.config || loadConfig();
  const writer = runtime.writer || console;
  const sourcePath = resolveLegendaryInvestorReviewSourcePath(command, config);
  const exportData = JSON.parse(fs.readFileSync(sourcePath, "utf8"));
  const facts = loadLegendaryReviewFacts(command);
  const report = buildLegendaryInvestorReview(exportData, facts);
  const rendered = renderLegendaryInvestorReview(report, { sourcePath });
  let jsonWritePath = null;

  if (command.writeJson) {
    jsonWritePath = resolveLegendaryInvestorReviewOutputPath(command, config);
    writeLegendaryInvestorReviewJson(jsonWritePath, report);
  }

  if (command.json) {
    writer.log(JSON.stringify(report, null, 2));
    if (jsonWritePath) {
      writer.log("");
      writer.log(`json: ${path.relative(config.projectRoot, jsonWritePath)}`);
    }
    return {
      ...report,
      jsonWritePath
    };
  }

  writer.log(rendered);
  if (jsonWritePath) {
    writer.log("");
    writer.log(`json: ${path.relative(config.projectRoot, jsonWritePath)}`);
  }

  let synthesisResult = null;
  if (command.writeSynthesis) {
    synthesisResult = writeLegendaryArtifactSynthesis(
      config,
      {
        kindLabel: "Review",
        query: "Legendary Investor Review",
        topic: "legendary investor review",
        answer: rendered,
        exportData
      },
      {
        skipLinks: command.skipLinks,
        skipViews: command.skipViews,
        allowFilesystemFallback: true,
        preferCli: true
      }
    );
    writer.log("");
    writer.log(
      `${synthesisResult.writeResult.action}: ${synthesisResult.writeResult.path} (mode: ${synthesisResult.writeResult.mode}, dedup_key: ${synthesisResult.writeResult.dedupKey})`
    );
    if (synthesisResult.linkResult) {
      writer.log(
        `Rebuilt automatic links for ${synthesisResult.linkResult.updated} note(s) out of ${synthesisResult.linkResult.scanned} scanned.`
      );
    }
    if (synthesisResult.viewResults.length > 0) {
      writer.log(
        `Refreshed wiki views: ${synthesisResult.viewResults.map((result) => `${result.path} (${result.mode})`).join(", ")}`
      );
    }
  }

  return {
    ...report,
    jsonWritePath,
    synthesisResult
  };
}

export function resolveLegendaryInvestorReviewSourcePath(command, config) {
  const requested = String(command.jsonFile || "").trim();
  if (requested) {
    return path.resolve(config.projectRoot, requested);
  }
  return path.join(config.projectRoot, "handoff", "legendary-investor-last-run.json");
}

export function loadLegendaryReviewFacts(command) {
  const fileFacts = command.factsFile
    ? JSON.parse(fs.readFileSync(path.resolve(command.factsFile), "utf8"))
    : {};
  return {
    ...fileFacts,
    ...command.facts
  };
}

export function resolveLegendaryInvestorReviewOutputPath(command, config) {
  const requested = String(command.outputJsonFile || "").trim();
  if (requested) {
    return path.resolve(config.projectRoot, requested);
  }
  return path.join(config.projectRoot, "handoff", "legendary-investor-last-review.json");
}

export function writeLegendaryInvestorReviewJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
  return filePath;
}

function printUsage(writer = console.error) {
  writer("Usage: node scripts/legendary-investor-review.mjs [--json] [--json-file <path>] [--facts-file <path>] [--fact key=value] [--write-json] [--output-json-file <path>] [--write-synthesis] [--skip-links] [--skip-views]");
}

async function main(args = process.argv.slice(2)) {
  try {
    runLegendaryInvestorReview(args);
  } catch (error) {
    printUsage(console.error);
    console.error("");
    console.error(error instanceof Error ? error.message : String(error));
    process.exit(1);
  }
}

function getArg(args, name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }
  return args[index + 1];
}

function collectFactArgs(args) {
  const facts = {};
  for (let index = 0; index < args.length; index += 1) {
    if (args[index] !== "--fact" || index + 1 >= args.length) {
      continue;
    }
    const raw = String(args[index + 1] || "");
    const separator = raw.indexOf("=");
    if (separator === -1) {
      continue;
    }
    const key = raw.slice(0, separator).trim();
    const value = raw.slice(separator + 1).trim();
    if (key) {
      facts[key] = value;
    }
  }
  return facts;
}

function isDirectExecution() {
  if (!process.argv[1]) {
    return false;
  }
  try {
    return pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url;
  } catch {
    return false;
  }
}

if (isDirectExecution()) {
  await main();
}
