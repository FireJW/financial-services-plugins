#!/usr/bin/env node

import { execFile } from "child_process";
import { rm } from "fs/promises";
import { promisify } from "util";
import path from "path";

const execFileAsync = promisify(execFile);

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = {
    input: "",
    outputRoot: "",
    deckTitle: "",
    brand: "AI前沿内参",
    coverTitle: "",
    coverSubtitle: "",
    image: "",
    heroCaption: "",
    heroRefStyle: "",
    heroRefLayout: "",
    heroRefPalette: "",
    note: "",
    xhsCoverStyle: "auto",
    xhsDeckStyle: "auto",
    xhsEyebrow: "",
    browserExecutable: "",
    keepSource: "false",
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--input") {
      result.input = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--output-root") {
      result.outputRoot = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--deck-title") {
      result.deckTitle = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--brand") {
      result.brand = args[index + 1] || result.brand;
      index += 1;
      continue;
    }
    if (arg === "--cover-title") {
      result.coverTitle = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--cover-subtitle") {
      result.coverSubtitle = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--image") {
      result.image = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--hero-caption") {
      result.heroCaption = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--hero-ref-style") {
      result.heroRefStyle = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--hero-ref-layout") {
      result.heroRefLayout = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--hero-ref-palette") {
      result.heroRefPalette = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--note") {
      result.note = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--xhs-cover-style") {
      result.xhsCoverStyle = args[index + 1] || result.xhsCoverStyle;
      index += 1;
      continue;
    }
    if (arg === "--xhs-deck-style") {
      result.xhsDeckStyle = args[index + 1] || result.xhsDeckStyle;
      index += 1;
      continue;
    }
    if (arg === "--xhs-eyebrow") {
      result.xhsEyebrow = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--browser-executable") {
      result.browserExecutable = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--keep-source") {
      result.keepSource = "true";
    }
  }

  return result;
}

async function runNodeScript(scriptPath, args, cwd) {
  return execFileAsync(process.execPath, [scriptPath, ...args], {
    cwd,
    windowsHide: true,
    maxBuffer: 20 * 1024 * 1024,
  });
}

function parseJsonWithContext(scriptName, stdout) {
  try {
    return JSON.parse(stdout);
  } catch (parseErr) {
    throw new Error(
      `Failed to parse JSON from ${scriptName}: ${parseErr.message}\nstdout (first 500 chars):\n${String(stdout).slice(0, 500)}`
    );
  }
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.input || !args.outputRoot) {
    console.error("Usage: node scripts/social-cards/build_social_images_from_live_brief.mjs --input <live-brief.md> --output-root <dir> [--deck-title <title>] [--brand <name>] [--cover-title <text>] [--cover-subtitle <text>] [--image <path-or-url>] [--hero-caption <text>] [--hero-ref-style <style>] [--hero-ref-layout <layout>] [--hero-ref-palette <palette>] [--note <text>] [--xhs-cover-style <style>] [--xhs-deck-style <style>] [--xhs-eyebrow <text>] [--browser-executable <path>] [--keep-source]");
    process.exit(1);
  }

  const cwd = process.cwd();
  const input = path.resolve(cwd, args.input);
  const outputRoot = path.resolve(cwd, args.outputRoot);
  const bridgeDir = path.join(outputRoot, "_bridge");
  const sourcePath = path.join(bridgeDir, "source.txt");

  const bridgeArgs = [
    "--input",
    input,
    "--output",
    sourcePath,
  ];

  if (args.coverTitle) {
    bridgeArgs.push("--cover-title", args.coverTitle);
  }
  if (args.coverSubtitle) {
    bridgeArgs.push("--cover-subtitle", args.coverSubtitle);
  }
  if (args.image) {
    bridgeArgs.push("--image", args.image);
  }
  if (args.heroCaption) {
    bridgeArgs.push("--hero-caption", args.heroCaption);
  }
  if (args.heroRefStyle) {
    bridgeArgs.push("--hero-ref-style", args.heroRefStyle);
  }
  if (args.heroRefLayout) {
    bridgeArgs.push("--hero-ref-layout", args.heroRefLayout);
  }
  if (args.heroRefPalette) {
    bridgeArgs.push("--hero-ref-palette", args.heroRefPalette);
  }
  if (args.note) {
    bridgeArgs.push("--note", args.note);
  }

  const bridge = await runNodeScript(
    path.join("scripts", "social-cards", "build_social_source_from_live_brief.mjs"),
    bridgeArgs,
    cwd
  );

  const exportArgs = [
    "--input",
    sourcePath,
    "--output-root",
    outputRoot,
    "--deck-title",
    args.deckTitle || path.basename(outputRoot),
    "--brand",
    args.brand,
    "--xhs-cover-style",
    args.xhsCoverStyle,
    "--xhs-deck-style",
    args.xhsDeckStyle,
    ...(args.xhsEyebrow ? ["--xhs-eyebrow", args.xhsEyebrow] : []),
  ];

  if (args.browserExecutable) {
    exportArgs.push("--browser-executable", args.browserExecutable);
  }

  const exportResult = await runNodeScript(
    path.join("scripts", "social-cards", "build_social_image_sets.mjs"),
    exportArgs,
    cwd
  );

  if (args.keepSource !== "true") {
    await rm(bridgeDir, { recursive: true, force: true });
  }

  console.log(
    JSON.stringify(
      {
        status: "ready",
        input,
        outputRoot,
        bridge: parseJsonWithContext("build_social_source_from_live_brief.mjs", bridge.stdout),
        export: parseJsonWithContext("build_social_image_sets.mjs", exportResult.stdout),
        sourcePath,
        keepSource: args.keepSource === "true",
        bridgeRemoved: args.keepSource !== "true",
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
