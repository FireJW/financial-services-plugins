#!/usr/bin/env node

import { mkdir, readFile, writeFile } from "fs/promises";
import path from "path";
import {
  escapeHtml,
  slugify,
  parseSection,
  resolveImageReference,
  renderGallery,
} from "./card-utils.mjs";

const DEFAULT_BRAND = "AI前沿内参";
const DEFAULT_DECK_TITLE = "公众号长图卡片";

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = {
    input: "",
    outputDir: "",
    separator: "\n===\n",
    deckTitle: "",
    brand: DEFAULT_BRAND,
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--input") {
      result.input = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--output-dir") {
      result.outputDir = args[index + 1] || "";
      index += 1;
      continue;
    }
    if (arg === "--separator") {
      result.separator = args[index + 1] || result.separator;
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
    }
  }

  return result;
}

function renderCoverImageDriven(card, options) {
  const imageHtml = card.meta.resolvedImage
    ? `<div class="imgdriven-hero"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>`
    : "";
  const noteHtml = card.meta.note
    ? `<p class="imgdriven-note">${escapeHtml(card.meta.note)}</p>`
    : "";

  return `
    <main class="sheet sheet-cover sheet-cover-imgdriven${card.meta.refPalette === 'dark' ? ' palette-dark' : ''}">
      ${imageHtml}
      <div class="imgdriven-overlay">
        <header class="sheet-top">
          <span class="brand-chip brand-chip-glass">${escapeHtml(options.brand)}</span>
        </header>
        <section class="imgdriven-copy">
          <h1>${escapeHtml(card.title)}</h1>
          ${noteHtml}
        </section>
      </div>
    </main>
  `;
}

function renderCover(card, options) {
  // Image-driven: when reference image is present and layout says image-dominant
  if (card.meta.resolvedImage && (card.meta.refLayout === "image-dominant" || card.meta.refStyle === "news-photo")) {
    return renderCoverImageDriven(card, options);
  }
  const imageHtml = card.meta.resolvedImage
    ? `<div class="wechat-media"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>`
    : `<div class="wechat-media wechat-media-placeholder"><div class="placeholder-label">图片位</div></div>`;
  const note = card.meta.note || card.subtitle || "";
  const noteHtml = note
    ? `<div class="wechat-note"><span class="wechat-note-bar"></span><p>${escapeHtml(note)}</p></div>`
    : "";
  const kicker = card.paragraphs[1] ? `<p class="wechat-kicker">${escapeHtml(card.paragraphs[1])}</p>` : "";

  return `
    <main class="sheet sheet-cover">
      <header class="sheet-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
      </header>
      ${imageHtml}
      <section class="sheet-copy">
        <h1>${escapeHtml(card.title)}</h1>
        ${noteHtml}
        ${kicker}
      </section>
    </main>
  `;
}

function collectContentLines(card) {
  const textLines = [];
  if (card.subtitle) {
    textLines.push(card.subtitle);
  }
  for (const paragraph of card.paragraphs.slice(card.subtitle ? 1 : 0)) {
    textLines.push(paragraph);
  }
  for (const bullet of card.bullets) {
    textLines.push(`- ${bullet}`);
  }
  return textLines;
}

function renderSplitFocusContent(card, options) {
  const paragraphsHtml = collectContentLines(card)
    .map((line) => `<p class="split-focus-paragraph">${escapeHtml(line)}</p>`)
    .join("");
  const highlightHtml = card.meta.highlight
    ? `<p class="split-focus-highlight">${escapeHtml(card.meta.highlight)}</p>`
    : "";

  return `
    <main class="sheet sheet-content sheet-content-split-focus${card.meta.refPalette === "dark" ? " palette-dark" : ""}">
      <header class="sheet-top sheet-top-content">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
        <span class="page-chip">${card.index}</span>
      </header>
      <section class="split-focus-sheet-body">
        <div class="split-focus-sheet-media"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>
        <div class="split-focus-sheet-copy">
          <h2>${escapeHtml(card.title)}</h2>
          <div class="wechat-copy-stack">
            ${paragraphsHtml}
            ${highlightHtml}
          </div>
        </div>
      </section>
    </main>
  `;
}

function renderImageDrivenContent(card, options) {
  const textLines = collectContentLines(card);
  const lead = textLines[0] ? `<p class="imgdriven-content-lead">${escapeHtml(textLines[0])}</p>` : "";
  const restHtml = textLines
    .slice(textLines[0] ? 1 : 0)
    .map((line) => `<p class="imgdriven-content-paragraph">${escapeHtml(line)}</p>`)
    .join("");
  const noteHtml = card.meta.note
    ? `<p class="imgdriven-content-note">${escapeHtml(card.meta.note)}</p>`
    : "";
  const highlightHtml = card.meta.highlight
    ? `<p class="imgdriven-content-highlight">${escapeHtml(card.meta.highlight)}</p>`
    : "";

  return `
    <main class="sheet sheet-content sheet-content-image-dominant${card.meta.refPalette === "dark" ? " palette-dark" : ""}">
      <header class="sheet-top sheet-top-content sheet-top-floating">
        <span class="brand-chip brand-chip-glass">${escapeHtml(options.brand)}</span>
        <span class="page-chip">${card.index}</span>
      </header>
      <section class="imgdriven-sheet-media"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></section>
      <section class="imgdriven-sheet-copy">
        <h2>${escapeHtml(card.title)}</h2>
        ${noteHtml}
        ${lead}
        <div class="wechat-copy-stack">
          ${restHtml}
          ${highlightHtml}
        </div>
      </section>
    </main>
  `;
}

function renderContent(card, options) {
  if (card.meta.resolvedImage && card.meta.refLayout === "split-focus") {
    return renderSplitFocusContent(card, options);
  }
  if (card.meta.resolvedImage && (card.meta.refLayout === "image-dominant" || card.meta.refStyle === "news-photo")) {
    return renderImageDrivenContent(card, options);
  }
  const textLines = [];
  if (card.subtitle) {
    textLines.push(card.subtitle);
  }
  for (const paragraph of card.paragraphs.slice(card.subtitle ? 1 : 0)) {
    textLines.push(paragraph);
  }
  for (const bullet of card.bullets) {
    textLines.push(`• ${bullet}`);
  }

  const paragraphsHtml = textLines
    .map((line) => `<p class="wechat-paragraph">${escapeHtml(line)}</p>`)
    .join("");
  const highlightHtml = card.meta.highlight
    ? `<p class="wechat-highlight">${escapeHtml(card.meta.highlight)}</p>`
    : "";
  const imageHtml = card.meta.resolvedImage
    ? `<div class="content-image"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>`
    : "";

  return `
    <main class="sheet sheet-content">
      <header class="sheet-top sheet-top-content">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
        <span class="page-chip">${card.index}</span>
      </header>
      <section class="sheet-copy">
        ${imageHtml}
        <h2>${escapeHtml(card.title)}</h2>
        <div class="wechat-copy-stack">
          ${paragraphsHtml}
          ${highlightHtml}
        </div>
      </section>
    </main>
  `;
}

function renderEnding(card, options) {
  const lines = [card.subtitle, ...card.paragraphs.slice(card.subtitle ? 1 : 0), ...card.bullets].filter(Boolean);
  const tags = lines
    .slice(0, 4)
    .map((line) => `<span class="ending-tag">${escapeHtml(line)}</span>`)
    .join("");

  return `
    <main class="sheet sheet-ending">
      <header class="sheet-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
      </header>
      <section class="sheet-copy">
        <h2>${escapeHtml(card.title)}</h2>
        <div class="ending-tags">${tags}</div>
      </section>
    </main>
  `;
}

function renderCard(card, options) {
  if (card.type === "cover") {
    return renderCover(card, options);
  }
  if (card.type === "ending") {
    return renderEnding(card, options);
  }
  return renderContent(card, options);
}

function renderHtml(card, options) {
  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(card.title)}</title>
    <style>
      :root {
        --ink: #1f1b18;
        --muted: #6f645d;
        --accent: #ff2442;
        --line: #d9d4ce;
        --highlight: #fff2c8;
        --paper: #fffdf9;
      }

      * { box-sizing: border-box; }

      html, body {
        margin: 0;
        padding: 0;
        width: 1080px;
        height: 1520px;
        overflow: hidden;
        background: var(--paper);
        color: var(--ink);
        font-family: "PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
      }

      .sheet {
        width: 1080px;
        height: 1520px;
        padding: 34px 34px 42px;
        display: flex;
        flex-direction: column;
        background: var(--paper);
      }

      .sheet-top {
        display: flex;
        align-items: center;
        justify-content: flex-start;
      }

      .sheet-top-content {
        justify-content: space-between;
      }

      .brand-chip {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        padding: 14px 22px;
        border-radius: 999px;
        background: rgba(255, 36, 66, 0.1);
        color: var(--accent);
        font-size: 26px;
        font-weight: 700;
        line-height: 1;
      }

      .page-chip {
        width: 54px;
        height: 54px;
        border-radius: 999px;
        background: rgba(31, 27, 24, 0.08);
        color: #6d625b;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        font-weight: 700;
      }

      .wechat-media {
        margin-top: 26px;
        width: 100%;
        height: 680px;
        overflow: hidden;
        background: #e8ecef;
      }

      .wechat-media img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .wechat-media-placeholder {
        position: relative;
        background: linear-gradient(180deg, #dce6ec, #f0f2f4);
      }

      .placeholder-label {
        position: absolute;
        left: 26px;
        top: 24px;
        padding: 8px 14px;
        background: rgba(255,255,255,0.88);
        border-radius: 16px;
        color: #5f6a72;
        font-size: 22px;
        font-weight: 700;
      }

      .sheet-copy {
        margin-top: 30px;
        display: grid;
        gap: 24px;
      }

      .sheet-cover h1,
      .sheet-content h2,
      .sheet-ending h2 {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-weight: 700;
        letter-spacing: -0.04em;
        color: #1f1b18;
      }

      .sheet-cover h1 {
        font-size: 88px;
        line-height: 1.08;
      }

      .sheet-content h2,
      .sheet-ending h2 {
        font-size: 62px;
        line-height: 1.16;
      }

      .wechat-note {
        display: grid;
        grid-template-columns: 8px 1fr;
        gap: 18px;
        align-items: start;
      }

      .wechat-note-bar {
        width: 8px;
        min-height: 90px;
        background: #23201d;
      }

      .wechat-note p {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 28px;
        line-height: 1.55;
        color: #2e2926;
      }

      .wechat-kicker {
        margin: 0;
        color: var(--muted);
        font-size: 22px;
        line-height: 1.4;
        font-weight: 700;
      }

      .wechat-copy-stack {
        display: grid;
        gap: 26px;
      }

      .wechat-paragraph {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 38px;
        line-height: 1.84;
        color: #2f2a28;
      }

      .wechat-highlight {
        margin: 2px 0 0;
        display: inline-block;
        align-self: start;
        padding: 6px 10px 8px;
        background: var(--highlight);
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 38px;
        line-height: 1.7;
        color: #1f1b18;
      }

      .ending-tags {
        display: flex;
        flex-wrap: wrap;
        gap: 14px;
      }

      .ending-tag {
        padding: 16px 20px;
        border-radius: 16px;
        border: 1px solid var(--line);
        background: #fffdfa;
        font-size: 26px;
        line-height: 1.35;
        color: #61544c;
      }
      .sheet-cover-imgdriven {
        padding: 0;
        position: relative;
        overflow: hidden;
      }

      .imgdriven-hero {
        position: absolute;
        inset: 0;
        z-index: 0;
      }

      .imgdriven-hero img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .imgdriven-overlay {
        position: relative;
        z-index: 2;
        width: 100%;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        padding: 34px;
        background: linear-gradient(
          180deg,
          rgba(0, 0, 0, 0.12) 0%,
          rgba(0, 0, 0, 0.02) 40%,
          rgba(0, 0, 0, 0.50) 72%,
          rgba(0, 0, 0, 0.76) 100%
        );
      }

      .brand-chip-glass {
        background: rgba(255, 255, 255, 0.18);
        color: #ffffff;
        backdrop-filter: blur(8px);
      }

      .imgdriven-copy {
        max-width: 960px;
      }

      .imgdriven-copy h1 {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 76px;
        line-height: 1.1;
        letter-spacing: -0.03em;
        font-weight: 700;
        color: #ffffff;
        text-shadow: 0 3px 18px rgba(0, 0, 0, 0.35);
      }

      .imgdriven-note {
        margin: 16px 0 0;
        font-size: 28px;
        line-height: 1.5;
        color: rgba(255, 255, 255, 0.8);
        font-weight: 600;
      }

      .palette-dark .imgdriven-overlay {
        background: linear-gradient(
          180deg,
          rgba(0, 0, 0, 0.22) 0%,
          rgba(0, 0, 0, 0.04) 35%,
          rgba(0, 0, 0, 0.60) 68%,
          rgba(0, 0, 0, 0.85) 100%
        );
      }

      .sheet-top-floating {
        position: absolute;
        top: 34px;
        left: 34px;
        right: 34px;
        z-index: 4;
      }

      .sheet-content-split-focus .split-focus-sheet-body {
        margin-top: 24px;
        display: grid;
        grid-template-columns: 0.82fr 1.18fr;
        gap: 22px;
        align-items: stretch;
      }

      .split-focus-sheet-media {
        min-height: 1180px;
        overflow: hidden;
        border-radius: 28px;
      }

      .split-focus-sheet-media img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .split-focus-sheet-copy {
        border-radius: 26px;
        border: 1px solid rgba(31, 27, 24, 0.08);
        background: rgba(255, 253, 249, 0.96);
        padding: 28px 26px 24px;
        display: grid;
        align-content: start;
        gap: 20px;
      }

      .split-focus-sheet-copy h2 {
        margin: 0;
      }

      .split-focus-paragraph {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 34px;
        line-height: 1.7;
        color: #2f2a28;
      }

      .split-focus-highlight {
        margin: 0;
        display: inline-block;
        align-self: start;
        padding: 6px 10px 8px;
        background: var(--highlight);
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 34px;
        line-height: 1.55;
        color: #1f1b18;
      }

      .sheet-content-image-dominant {
        padding: 0;
        position: relative;
        overflow: hidden;
      }

      .imgdriven-sheet-media {
        position: absolute;
        inset: 0 0 430px;
        z-index: 0;
      }

      .imgdriven-sheet-media img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .imgdriven-sheet-copy {
        position: absolute;
        left: 28px;
        right: 28px;
        bottom: 28px;
        z-index: 3;
        padding: 26px 24px 24px;
        border-radius: 28px;
        background: rgba(255, 253, 249, 0.96);
        box-shadow: 0 14px 30px rgba(0, 0, 0, 0.12);
        display: grid;
        gap: 14px;
      }

      .imgdriven-sheet-copy h2 {
        margin: 0;
      }

      .imgdriven-content-note {
        margin: 0;
        font-size: 24px;
        line-height: 1.45;
        color: #6f645d;
        font-weight: 700;
      }

      .imgdriven-content-lead {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 36px;
        line-height: 1.68;
        color: #2f2a28;
      }

      .imgdriven-content-paragraph {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 30px;
        line-height: 1.58;
        color: #3a3431;
      }

      .imgdriven-content-highlight {
        margin: 0;
        display: inline-block;
        align-self: start;
        padding: 6px 10px 8px;
        background: var(--highlight);
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 30px;
        line-height: 1.48;
        color: #1f1b18;
      }

      .content-image {
        width: 100%;
        height: 380px;
        overflow: hidden;
        margin-bottom: 20px;
      }

      .content-image img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }
    </style>
  </head>
  <body>
    ${renderCard(card, options)}
  </body>
</html>`;
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.input || !args.outputDir) {
    console.error("Usage: node render_wechat_longform_cards.mjs --input <txt> --output-dir <dir> [--separator <text>] [--deck-title <title>] [--brand <name>]");
    process.exit(1);
  }

  const inputPath = path.resolve(args.input);
  const outputDir = path.resolve(args.outputDir);
  const raw = await readFile(inputPath, "utf8");
  const sections = raw
    .split(args.separator)
    .map((section) => section.trim())
    .filter(Boolean);

  if (sections.length === 0) {
    throw new Error("No card sections found. Check the separator.");
  }

  const cards = sections.map((section, index) => parseSection(section, index));
  const deckTitle = args.deckTitle || cards[0]?.title || DEFAULT_DECK_TITLE;
  const options = {
    deckTitle,
    brand: args.brand,
  };

  await mkdir(outputDir, { recursive: true });

  for (const card of cards) {
    card.meta.resolvedImage = resolveImageReference(card.meta.image, inputPath, outputDir);
    const html = renderHtml(card, options);
    await writeFile(path.join(outputDir, `${card.id}.html`), html, "utf8");
  }

  await writeFile(path.join(outputDir, "index.html"), renderGallery(cards, { ...options, defaultDeckTitle: DEFAULT_DECK_TITLE, galleryBackground: "#f7f4ef", galleryCardBackground: "rgba(255,255,255,0.85)", galleryPadding: 36, galleryCardRadius: 18 }), "utf8");
  await writeFile(
    path.join(outputDir, "manifest.json"),
    JSON.stringify(
      {
        status: "ready",
        deckTitle,
        brand: args.brand,
        separator: args.separator,
        inputPath,
        outputDir,
        platform: "wechat",
        cards: cards.map((card) => ({
          id: card.id,
          index: card.index,
          type: card.type,
          title: card.title,
          html: `${card.id}.html`,
          suggestedPng: `${slugify(card.id)}.png`,
        })),
      },
      null,
      2
    ),
    "utf8"
  );

  console.log(
    JSON.stringify(
      {
        status: "ready",
        deckTitle,
        outputDir,
        count: cards.length,
        platform: "wechat",
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
