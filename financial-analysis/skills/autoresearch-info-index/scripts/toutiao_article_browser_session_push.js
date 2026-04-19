#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

function cleanText(value) {
  return String(value ?? "").replace(/\u200b/g, " ").replace(/\s+/g, " ").trim();
}

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderToutiaoSectionHeading(rawText, level = 2) {
  const heading = cleanText(rawText);
  if (!heading) return "";
  const fontSize = level >= 3 ? 22 : 26;
  return [
    `<section data-role="toutiao-heading" style="margin:30px 0 18px;">`,
    `<p style="margin:0;line-height:1.4;font-size:${fontSize}px;font-weight:700;color:#1f2329;">`,
    `<span style="display:inline-block;margin-right:10px;color:#ff4d4f;font-weight:800;">/</span>${escapeHtml(heading)}`,
    `</p>`,
    `</section>`,
  ].join("");
}

function buildToutiaoBodyHtml(markdown) {
  const lines = String(markdown ?? "").replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) {
      blocks.push(`<p style="margin:18px 0;"></p>`);
      continue;
    }
    const h2 = line.match(/^##\s+(.+)$/);
    if (h2) {
      blocks.push(renderToutiaoSectionHeading(h2[1], 2));
      continue;
    }
    const h3 = line.match(/^###\s+(.+)$/);
    if (h3) {
      blocks.push(renderToutiaoSectionHeading(h3[1], 3));
      continue;
    }
    blocks.push(`<p style="margin:0 0 22px;line-height:1.9;font-size:18px;color:#1f2329;">${escapeHtml(line)}</p>`);
  }
  return blocks.join("\n");
}

function parseArgs(argv) {
  const args = { manifest: "", output: "" };
  for (let index = 2; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--manifest") args.manifest = argv[index + 1] || "";
    if (token === "--output") args.output = argv[index + 1] || "";
  }
  if (!args.manifest) {
    throw new Error("Missing required --manifest argument.");
  }
  args.output = args.output || path.join(path.dirname(args.manifest), "result.json");
  return args;
}

function main() {
  const args = parseArgs(process.argv);
  const manifest = JSON.parse(fs.readFileSync(args.manifest, "utf8"));
  const result = {
    status: "prepared",
    title: cleanText(manifest.title),
    subtitle: cleanText(manifest.subtitle),
    content_html: buildToutiaoBodyHtml(manifest.content_markdown),
    selected_images: Array.isArray(manifest.selected_images) ? manifest.selected_images : [],
    cover_plan: manifest.cover_plan || {},
    platform_hints: manifest.platform_hints || {},
  };
  fs.writeFileSync(args.output, JSON.stringify(result, null, 2), "utf8");
  process.stdout.write(JSON.stringify(result));
}

if (require.main === module) {
  main();
}
