import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { mkdir, readFile, rm, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const workspaceRoot = path.resolve(__dirname, "..", "..");
const fixturePath = path.join(
  workspaceRoot,
  "financial-analysis",
  "skills",
  "autoresearch-info-index",
  "tests",
  "fixtures",
  "article-publish-canonical",
  "claude_code_deep_analysis_prefer_images_2800_snapshot.json"
);
const tempRoot = path.join(workspaceRoot, "tests", ".tmp-social-cards-image-driven");

const TINY_PNG_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9WnSUs8AAAAASUVORK5CYII=";

function replaceTokens(value, mapping) {
  if (typeof value === "string") {
    let replaced = value;
    for (const [needle, replacement] of Object.entries(mapping)) {
      replaced = replaced.replaceAll(needle, replacement);
    }
    return replaced;
  }
  if (Array.isArray(value)) {
    return value.map((item) => replaceTokens(item, mapping));
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, replaceTokens(item, mapping)])
    );
  }
  return value;
}

async function runScript(relativeScriptPath, args) {
  const scriptPath = path.join(workspaceRoot, relativeScriptPath);
  const result = await execFileAsync(process.execPath, [scriptPath, ...args], {
    cwd: workspaceRoot,
    windowsHide: true,
    maxBuffer: 20 * 1024 * 1024,
  });
  return {
    stdout: result.stdout,
    stderr: result.stderr,
    json: JSON.parse(result.stdout),
  };
}

await rm(tempRoot, { recursive: true, force: true });
await mkdir(tempRoot, { recursive: true });

try {
  const screenshotPath = path.join(tempRoot, "root-post.png");
  const inputPath = path.join(tempRoot, "article-result.json");
  const liveBriefPath = path.join(tempRoot, "live-brief.md");
  const sourcePath = path.join(tempRoot, "source.txt");
  const xhsDir = path.join(tempRoot, "xhs");
  const wechatDir = path.join(tempRoot, "wechat");

  await writeFile(screenshotPath, Buffer.from(TINY_PNG_BASE64, "base64"));

  const fixture = JSON.parse(await readFile(fixturePath, "utf8"));
  const resolvedFixture = replaceTokens(fixture, {
    "__ROOT_POST_SCREENSHOT_PATH__": screenshotPath,
    "__WORKSPACE_ROOT__": workspaceRoot,
  });
  await writeFile(inputPath, `${JSON.stringify(resolvedFixture, null, 2)}\n`, "utf8");

  const liveBriefResult = await runScript("scripts/social-cards/build_live_brief_from_article.mjs", [
    "--input",
    inputPath,
    "--output",
    liveBriefPath,
  ]);
  assert.equal(liveBriefResult.json.heroRefStyle, "screenshot");
  assert.equal(liveBriefResult.json.heroRefLayout, "split-focus");

  const liveBriefMarkdown = await readFile(liveBriefPath, "utf8");
  assert.match(liveBriefMarkdown, /hero_ref_style:\s*screenshot/);
  assert.match(liveBriefMarkdown, /hero_ref_layout:\s*split-focus/);

  await runScript("scripts/social-cards/build_social_source_from_live_brief.mjs", [
    "--input",
    liveBriefPath,
    "--output",
    sourcePath,
  ]);

  const sourceText = await readFile(sourcePath, "utf8");
  assert.match(sourceText, /@image:\s+/);
  assert.match(sourceText, /@ref-style:\s*screenshot/);
  assert.match(sourceText, /@ref-layout:\s*split-focus/);

  const sections = sourceText.trim().split("\n===\n");
  assert.match(sections[1], /@image:\s+/);
  assert.match(sections[1], /@ref-layout:\s*split-focus/);

  await runScript("scripts/social-cards/render_xiaohongshu_cards.mjs", [
    "--input",
    sourcePath,
    "--output-dir",
    xhsDir,
  ]);
  await runScript("scripts/social-cards/render_wechat_longform_cards.mjs", [
    "--input",
    sourcePath,
    "--output-dir",
    wechatDir,
  ]);

  const xhsFirstContent = await readFile(path.join(xhsDir, "card-02.html"), "utf8");
  const wechatFirstContent = await readFile(path.join(wechatDir, "card-02.html"), "utf8");
  assert.match(xhsFirstContent, /card-content-split-focus|card-content-image-dominant/);
  assert.match(wechatFirstContent, /sheet-content-split-focus|sheet-content-image-dominant/);
  assert.match(xhsFirstContent, /root-post\.png/);
  assert.match(wechatFirstContent, /root-post\.png/);
} finally {
  await rm(tempRoot, { recursive: true, force: true });
}
