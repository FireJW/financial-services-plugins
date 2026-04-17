#!/usr/bin/env node

import { mkdir, readFile } from "fs/promises";
import { existsSync } from "fs";
import path from "path";
import { execFile } from "child_process";
import { promisify } from "util";

const execFileAsync = promisify(execFile);

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = {
    inputDir: "",
    outputDir: "",
    browserExecutable: "",
    width: 1242,
    height: 1660,
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--input-dir") {
      result.inputDir = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--output-dir") {
      result.outputDir = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--browser-executable") {
      result.browserExecutable = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--width") {
      result.width = Number(args[index + 1] || result.width);
      index += 1;
      continue;
    }
    if (arg === "--height") {
      result.height = Number(args[index + 1] || result.height);
      index += 1;
    }
  }

  return result;
}

function resolveBrowserExecutable(explicitPath) {
  const candidates = explicitPath
    ? [path.resolve(explicitPath)]
    : [
        "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
        "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
        path.join(process.env.LOCALAPPDATA || "", "Microsoft", "Edge", "Application", "msedge.exe"),
        "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
        "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        path.join(process.env.LOCALAPPDATA || "", "Google", "Chrome", "Application", "chrome.exe"),
      ];

  for (const candidate of candidates) {
    if (existsSync(candidate)) {
      return candidate;
    }
  }

  throw new Error("No local Edge/Chrome executable was found.");
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.inputDir || !args.outputDir) {
    console.error("Usage: node capture_xiaohongshu_cards_with_edge.mjs --input-dir <dir> --output-dir <dir> [--browser-executable <path>] [--width <n>] [--height <n>]");
    process.exit(1);
  }

  const inputDir = path.resolve(args.inputDir);
  const outputDir = path.resolve(args.outputDir);
  const manifestPath = path.join(inputDir, "manifest.json");
  const browserExecutable = resolveBrowserExecutable(args.browserExecutable);
  const manifest = JSON.parse(await readFile(manifestPath, "utf8"));

  await mkdir(outputDir, { recursive: true });

  const results = [];
  for (const card of manifest.cards) {
    const htmlPath = path.join(inputDir, card.html);
    const pngPath = path.join(outputDir, `${card.id}.png`);
    const fileUrl = `file:///${htmlPath.replace(/\\/g, "/")}`;

    await execFileAsync(browserExecutable, [
      "--headless=new",
      "--disable-gpu",
      "--hide-scrollbars",
      "--run-all-compositor-stages-before-draw",
      "--virtual-time-budget=1500",
      `--window-size=${args.width},${args.height}`,
      `--screenshot=${pngPath}`,
      fileUrl,
    ]);

    results.push({
      id: card.id,
      htmlPath,
      pngPath,
    });
  }

  console.log(
    JSON.stringify(
      {
        status: "ready",
        browserExecutable,
        outputDir,
        count: results.length,
        results,
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
