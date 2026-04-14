#!/usr/bin/env node

import { execFile } from "child_process";
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
    xhsCoverStyle: "auto",
    xhsDeckStyle: "auto",
    xhsEyebrow: "",
    wechatWidth: "1080",
    wechatHeight: "1520",
    browserExecutable: "",
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
    if (arg === "--wechat-width") {
      result.wechatWidth = args[index + 1] || result.wechatWidth;
      index += 1;
      continue;
    }
    if (arg === "--wechat-height") {
      result.wechatHeight = args[index + 1] || result.wechatHeight;
      index += 1;
      continue;
    }
    if (arg === "--browser-executable") {
      result.browserExecutable = args[index + 1] || "";
      index += 1;
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

function maybeBrowserArgs(browserExecutable) {
  return browserExecutable ? ["--browser-executable", browserExecutable] : [];
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
    console.error("Usage: node scripts/social-cards/build_social_image_sets.mjs --input <source.txt> --output-root <dir> [--deck-title <title>] [--brand <name>] [--xhs-cover-style <style>] [--xhs-deck-style <style>] [--xhs-eyebrow <text>] [--wechat-width <n>] [--wechat-height <n>] [--browser-executable <path>]");
    process.exit(1);
  }

  const cwd = process.cwd();
  const input = path.resolve(cwd, args.input);
  const outputRoot = path.resolve(cwd, args.outputRoot);

  const xhsHtmlDir = path.join(outputRoot, "xiaohongshu", "html");
  const xhsPngDir = path.join(outputRoot, "xiaohongshu", "png");
  const wechatHtmlDir = path.join(outputRoot, "wechat", "html");
  const wechatPngDir = path.join(outputRoot, "wechat", "png");

  const renderXhs = await runNodeScript(
    path.join("scripts", "social-cards", "render_xiaohongshu_cards.mjs"),
    [
      "--input",
      input,
      "--output-dir",
      xhsHtmlDir,
      "--deck-title",
      args.deckTitle,
      "--brand",
      args.brand,
      "--cover-style",
      args.xhsCoverStyle,
      "--deck-style",
      args.xhsDeckStyle,
      ...(args.xhsEyebrow ? ["--eyebrow", args.xhsEyebrow] : []),
    ],
    cwd
  );

  const captureXhs = await runNodeScript(
    path.join("scripts", "social-cards", "capture_xiaohongshu_cards_with_edge.mjs"),
    [
      "--input-dir",
      xhsHtmlDir,
      "--output-dir",
      xhsPngDir,
      ...maybeBrowserArgs(args.browserExecutable),
    ],
    cwd
  );

  const renderWechat = await runNodeScript(
    path.join("scripts", "social-cards", "render_wechat_longform_cards.mjs"),
    [
      "--input",
      input,
      "--output-dir",
      wechatHtmlDir,
      "--deck-title",
      args.deckTitle,
      "--brand",
      args.brand,
    ],
    cwd
  );

  const captureWechat = await runNodeScript(
    path.join("scripts", "social-cards", "capture_xiaohongshu_cards_with_edge.mjs"),
    [
      "--input-dir",
      wechatHtmlDir,
      "--output-dir",
      wechatPngDir,
      "--width",
      args.wechatWidth,
      "--height",
      args.wechatHeight,
      ...maybeBrowserArgs(args.browserExecutable),
    ],
    cwd
  );

  console.log(
    JSON.stringify(
      {
        status: "ready",
        input,
        outputRoot,
        xiaohongshu: {
          htmlDir: xhsHtmlDir,
          pngDir: xhsPngDir,
          render: parseJsonWithContext("render_xiaohongshu_cards.mjs", renderXhs.stdout),
          capture: parseJsonWithContext("capture_xiaohongshu_cards_with_edge.mjs (xiaohongshu)", captureXhs.stdout),
        },
        wechat: {
          htmlDir: wechatHtmlDir,
          pngDir: wechatPngDir,
          render: parseJsonWithContext("render_wechat_longform_cards.mjs", renderWechat.stdout),
          capture: parseJsonWithContext("capture_xiaohongshu_cards_with_edge.mjs (wechat)", captureWechat.stdout),
        },
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
