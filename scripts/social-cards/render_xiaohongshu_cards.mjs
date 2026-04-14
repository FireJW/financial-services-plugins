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
const DEFAULT_DECK_TITLE = "小红书信息差卡片";

function parseArgs(argv) {
  const args = argv.slice(2);
  const result = {
    input: "",
    outputDir: "",
    separator: "\n===\n",
    deckTitle: "",
    brand: DEFAULT_BRAND,
    coverStyle: "auto",
    deckStyle: "auto",
    eyebrow: "",
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
      continue;
    }
    if (arg === "--cover-style") {
      result.coverStyle = args[index + 1] || result.coverStyle;
      index += 1;
      continue;
    }
    if (arg === "--deck-style") {
      result.deckStyle = args[index + 1] || result.deckStyle;
      index += 1;
      continue;
    }
    if (arg === "--eyebrow") {
      result.eyebrow = args[index + 1] || "";
      index += 1;
    }
  }

  return result;
}

function renderCoverStatement(card, options) {
  const subtitle = card.paragraphs[0] ? `<p class="cover-subtitle">${escapeHtml(card.paragraphs[0])}</p>` : "";
  const kicker = card.paragraphs[1] ? `<p class="cover-kicker">${escapeHtml(card.paragraphs[1])}</p>` : "";

  return `
    <main class="card card-cover card-cover-statement">
      <div class="grain"></div>
      <div class="cover-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
        <span class="save-chip">建议收藏</span>
      </div>
      <section class="cover-body">
        ${options.eyebrow ? `<p class="eyebrow">${escapeHtml(options.eyebrow)}</p>` : ""}
        <h1>${escapeHtml(card.title)}</h1>
        ${subtitle}
        ${kicker}
      </section>
    </main>
  `;
}

function renderCoverAlert(card, options) {
  const subtitle = card.paragraphs[0] ? `<p class="cover-subtitle">${escapeHtml(card.paragraphs[0])}</p>` : "";
  const kicker = card.paragraphs[1] ? `<p class="cover-kicker">${escapeHtml(card.paragraphs[1])}</p>` : "";

  return `
    <main class="card card-cover card-cover-alert">
      <div class="grain"></div>
      <div class="alert-glow alert-glow-a"></div>
      <div class="alert-glow alert-glow-b"></div>
      <div class="cover-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
        <span class="save-chip">建议收藏</span>
      </div>
      <section class="cover-body cover-body-panel">
        ${options.eyebrow ? `<p class="eyebrow">${escapeHtml(options.eyebrow)}</p>` : ""}
        <h1>${escapeHtml(card.title)}</h1>
        ${subtitle}
        ${kicker}
      </section>
    </main>
  `;
}

function extractNumericBadge(card) {
  const match = `${card.title} ${card.subtitle} ${card.paragraphs.join(" ")}`.match(/(\d+\s*[条点步招个])/);
  if (match) {
    return match[1];
  }
  return "3条";
}

function renderCoverNumber(card, options) {
  const subtitle = card.paragraphs[0] ? `<p class="cover-subtitle">${escapeHtml(card.paragraphs[0])}</p>` : "";
  const kicker = card.paragraphs[1] ? `<p class="cover-kicker">${escapeHtml(card.paragraphs[1])}</p>` : "";
  const badge = extractNumericBadge(card);

  return `
    <main class="card card-cover card-cover-number">
      <div class="grain"></div>
      <div class="number-ribbon">${escapeHtml(badge)}</div>
      <div class="cover-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
        <span class="save-chip">建议收藏</span>
      </div>
      <section class="cover-body cover-body-panel">
        ${options.eyebrow ? `<p class="eyebrow">${escapeHtml(options.eyebrow)}</p>` : ""}
        <h1>${escapeHtml(card.title)}</h1>
        ${subtitle}
        ${kicker}
      </section>
    </main>
  `;
}

function renderCover(card, options) {
  // Image-driven: when reference image is present and layout says image-dominant
  if (card.meta.resolvedImage && (card.meta.refLayout === "image-dominant" || card.meta.refStyle === "news-photo")) {
    return renderCoverImageDriven(card, options);
  }
  if (options.deckStyle === "editorial") {
    return renderCoverEditorial(card, options);
  }
  if (options.coverStyle === "alert" || options.coverStyle === "contrast") {
    return renderCoverAlert(card, options);
  }
  if (options.coverStyle === "number") {
    return renderCoverNumber(card, options);
  }
  return renderCoverStatement(card, options);
}

function renderCoverEditorial(card, options) {
  if (options.coverStyle === "contrast") {
    return renderCoverEditorialContrast(card, options);
  }

  const note = card.meta.note || card.subtitle || "";
  const kicker = card.paragraphs[1] ? `<p class="editorial-cover-kicker">${escapeHtml(card.paragraphs[1])}</p>` : "";
  const imageHtml = card.meta.resolvedImage
    ? `<div class="editorial-media"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>`
    : `<div class="editorial-media editorial-media-placeholder"><div class="placeholder-label">图片位</div></div>`;
  const noteHtml = note
    ? `<div class="editorial-note"><span class="editorial-note-bar"></span><p>${escapeHtml(note)}</p></div>`
    : "";

  return `
    <main class="card card-editorial-cover">
      <div class="grain"></div>
      <header class="editorial-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
      </header>
      <section class="editorial-cover-stack">
        ${imageHtml}
        <div class="editorial-cover-copy">
          <h1>${escapeHtml(card.title)}</h1>
          ${noteHtml}
          ${kicker}
        </div>
      </section>
    </main>
  `;
}

function renderCoverEditorialContrast(card, options) {
  const note = card.meta.note || card.subtitle || "";
  const kicker = card.paragraphs[1] ? `<p class="editorial-cover-kicker">${escapeHtml(card.paragraphs[1])}</p>` : "";
  const imageHtml = card.meta.resolvedImage
    ? `<div class="editorial-media editorial-media-tall"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>`
    : `<div class="editorial-media editorial-media-placeholder editorial-media-tall"><div class="placeholder-label">图片位</div></div>`;
  const noteHtml = note
    ? `<div class="editorial-note editorial-note-contrast"><span class="editorial-note-bar"></span><p>${escapeHtml(note)}</p></div>`
    : "";
  const contrastLabel = card.subtitle
    ? `<p class="editorial-contrast-line">${escapeHtml(card.subtitle)}</p>`
    : "";

  return `
    <main class="card card-editorial-cover card-editorial-cover-contrast">
      <div class="grain"></div>
      <header class="editorial-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
      </header>
      <section class="editorial-cover-stack">
        ${imageHtml}
        <div class="editorial-cover-copy editorial-cover-copy-contrast">
          <h1>${escapeHtml(card.title)}</h1>
          ${contrastLabel}
          ${noteHtml}
          ${kicker}
        </div>
      </section>
    </main>
  `;
}

function resolveImageCoverVariant(card, options) {
  const requested = String(options.coverStyle || "").trim().toLowerCase();

  if (["poster", "photo-poster", "image-poster"].includes(requested)) {
    return "poster";
  }
  if (["split", "split-band", "editorial-split"].includes(requested)) {
    return "split-band";
  }
  if (["window", "window-card", "image-window"].includes(requested)) {
    return "window-card";
  }
  if (card.meta.refLayout === "split-focus") {
    return "split-band";
  }
  if (card.meta.refStyle === "news-photo" || card.meta.refLayout === "image-dominant") {
    return "poster";
  }
  return "window-card";
}

function renderCoverImagePoster(card, options) {
  const imageHtml = card.meta.resolvedImage
    ? `<img src="${escapeHtml(card.meta.resolvedImage)}" alt="" />`
    : "";
  const noteHtml = card.meta.note
    ? `<p class="imgposter-note">${escapeHtml(card.meta.note)}</p>`
    : "";

  return `
    <main class="card card-cover card-cover-imgdriven card-cover-imgposter${card.meta.refPalette === 'dark' ? ' palette-dark' : ''}">
      <section class="imgposter-media">${imageHtml}</section>
      <div class="imgposter-vignette"></div>
      <div class="imgposter-bottomfade"></div>
      <div class="grain"></div>
      <div class="cover-top imgposter-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
        <span class="save-chip">建议收藏</span>
      </div>
      <section class="imgposter-copy">
        ${options.eyebrow ? `<p class="eyebrow">${escapeHtml(options.eyebrow)}</p>` : ""}
        <h1>${escapeHtml(card.title)}</h1>
        ${noteHtml}
      </section>
    </main>
  `;
}

function renderCoverImageSplitBand(card, options) {
  const imageHtml = card.meta.resolvedImage
    ? `<img src="${escapeHtml(card.meta.resolvedImage)}" alt="" />`
    : "";
  const noteHtml = card.meta.note
    ? `<p class="imgsplit-note">${escapeHtml(card.meta.note)}</p>`
    : "";

  return `
    <main class="card card-cover card-cover-imgdriven card-cover-imgsplit${card.meta.refPalette === 'dark' ? ' palette-dark' : ''}">
      <section class="imgsplit-media">${imageHtml}</section>
      <div class="imgsplit-wash"></div>
      <div class="imgsplit-band"></div>
      <div class="grain"></div>
      <div class="cover-top imgsplit-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
        <span class="save-chip">建议收藏</span>
      </div>
      <section class="imgsplit-panel">
        ${options.eyebrow ? `<p class="eyebrow">${escapeHtml(options.eyebrow)}</p>` : ""}
        <span class="imgsplit-rule"></span>
        <h1>${escapeHtml(card.title)}</h1>
        ${noteHtml}
      </section>
    </main>
  `;
}

function renderCoverImageWindowCard(card, options) {
  const imageHtml = card.meta.resolvedImage
    ? `<div class="imgdriven-frame"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>`
    : "";
  const noteHtml = card.meta.note
    ? `<p class="imgdriven-note">${escapeHtml(card.meta.note)}</p>`
    : "";

  return `
    <main class="card card-cover card-cover-imgdriven card-cover-imgwindow${card.meta.refPalette === 'dark' ? ' palette-dark' : ''}">
      <div class="grain"></div>
      <div class="cover-top">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
        <span class="save-chip">建议收藏</span>
      </div>
      <section class="imgdriven-stage">
        ${imageHtml}
      </section>
      <section class="imgdriven-copy-card">
        ${options.eyebrow ? `<p class="eyebrow">${escapeHtml(options.eyebrow)}</p>` : ""}
        <h1>${escapeHtml(card.title)}</h1>
        ${noteHtml}
      </section>
    </main>
  `;
}

function renderCoverImageDriven(card, options) {
  const variant = resolveImageCoverVariant(card, options);
  if (variant === "split-band") {
    return renderCoverImageSplitBand(card, options);
  }
  if (variant === "window-card") {
    return renderCoverImageWindowCard(card, options);
  }
  return renderCoverImagePoster(card, options);
}

function detectAutoCoverStyle(cards, deckTitle) {
  const cover = cards.find((card) => card.type === "cover") ?? cards[0];
  const haystack = [deckTitle, cover?.title, cover?.subtitle, ...(cover?.paragraphs ?? []), ...(cover?.bullets ?? [])]
    .join(" ")
    .trim();

  if (/\d+\s*(条|点|步|招|个|类|件)/.test(haystack) || /(一图看懂|规则|清单|步骤|变化|重点)/.test(haystack)) {
    return "number";
  }

  if (/(不是.+而是|为什么不是|真相|其实是|别再|别把|误区)/.test(haystack)) {
    return "contrast";
  }

  if (/(尚未|未公布|还没有|仍未|暂停|但.+没|远不到|不能放心|没谈成|没结果)/.test(haystack)) {
    return "contrast";
  }

  if (/(焦虑|警告|停止|别再|危险|崩了|失控|救命|解药|马上)/.test(haystack)) {
    return "alert";
  }

  return "statement";
}

function detectAutoDeckStyle(cards, deckTitle) {
  const joined = [
    deckTitle,
    ...cards.flatMap((card) => [card.title, card.subtitle, ...card.paragraphs, ...card.bullets, card.meta.note, card.meta.highlight]),
  ]
    .join(" ")
    .trim();

  const hasEditorialHints = cards.some((card) => card.meta.image || card.meta.note || card.meta.highlight);
  if (hasEditorialHints) {
    return "editorial";
  }

  if (/(谈判|停火|战线|会谈|最新进展|报道|据.+报道|现场|调查|专访|人物|叙事|长文)/.test(joined)) {
    return "editorial";
  }

  return "cards";
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
  const textLines = collectContentLines(card);
  const paragraphsHtml = textLines
    .map((line) => `<p class="split-focus-paragraph">${escapeHtml(line)}</p>`)
    .join("");
  const highlightHtml = card.meta.highlight
    ? `<p class="split-focus-highlight">${escapeHtml(card.meta.highlight)}</p>`
    : "";

  return `
    <main class="card card-content card-content-split-focus${card.meta.refPalette === "dark" ? " palette-dark" : ""}">
      <div class="grain"></div>
      <header class="content-header">
        <div class="header-left">
          <span class="brand-chip">${escapeHtml(options.brand)}</span>
          <span class="deck-title">${escapeHtml(options.deckTitle || DEFAULT_DECK_TITLE)}</span>
        </div>
        <span class="page-chip">${card.index}</span>
      </header>
      <section class="split-focus-body">
        <div class="split-focus-media"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>
        <div class="split-focus-copy">
          <h2>${escapeHtml(card.title)}</h2>
          <div class="split-focus-stack">
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
    <main class="card card-content card-content-image-dominant${card.meta.refPalette === "dark" ? " palette-dark" : ""}">
      <div class="grain"></div>
      <header class="content-header content-header-floating">
        <div class="header-left">
          <span class="brand-chip">${escapeHtml(options.brand)}</span>
        </div>
        <span class="page-chip">${card.index}</span>
      </header>
      <section class="imgdriven-content-media"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></section>
      <section class="imgdriven-content-copy">
        <h2>${escapeHtml(card.title)}</h2>
        ${noteHtml}
        ${lead}
        <div class="imgdriven-content-stack">
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
  if (options.deckStyle === "editorial") {
    return renderEditorialContent(card, options);
  }
  const bulletsHtml =
    card.bullets.length > 0
      ? `<ul class="bullet-list">${card.bullets.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>`
      : "";
  const paragraphsHtml = card.paragraphs
    .slice(card.subtitle ? 1 : 0)
    .map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`)
    .join("");
  const subtitle = card.subtitle ? `<p class="subtitle">${escapeHtml(card.subtitle)}</p>` : "";
  const imageHtml = card.meta.resolvedImage
    ? `<div class="content-image"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>`
    : "";

  return `
    <main class="card card-content">
      <div class="grain"></div>
      <header class="content-header">
        <div class="header-left">
          <span class="brand-chip">${escapeHtml(options.brand)}</span>
          <span class="deck-title">${escapeHtml(options.deckTitle || DEFAULT_DECK_TITLE)}</span>
        </div>
        <span class="page-chip">${card.index}</span>
      </header>
      <section class="content-body">
        ${imageHtml}
        <h2>${escapeHtml(card.title)}</h2>
        ${subtitle}
        ${bulletsHtml}
        <div class="paragraph-stack">${paragraphsHtml}</div>
      </section>
      <footer class="content-footer">
        <span>别急着下结论，先抓住最硬变化</span>
      </footer>
    </main>
  `;
}

function renderEditorialContent(card, options) {
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
    .map((line) => `<p class="editorial-paragraph">${escapeHtml(line)}</p>`)
    .join("");
  const highlightHtml = card.meta.highlight
    ? `<p class="editorial-highlight">${escapeHtml(card.meta.highlight)}</p>`
    : "";
  const imageHtml = card.meta.resolvedImage
    ? `<div class="editorial-inline-image"><img src="${escapeHtml(card.meta.resolvedImage)}" alt="" /></div>`
    : "";

  return `
    <main class="card card-editorial-content">
      <div class="grain"></div>
      <header class="content-header editorial-content-header">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
        <span class="page-chip">${card.index}</span>
      </header>
      <section class="editorial-article">
        ${imageHtml}
        <h2>${escapeHtml(card.title)}</h2>
        <div class="editorial-copy-stack">
          ${paragraphsHtml}
          ${highlightHtml}
        </div>
      </section>
    </main>
  `;
}

function renderEnding(card, options) {
  const lines = [...card.paragraphs, ...card.bullets];
  const tags = lines.length
    ? lines.map((line) => `<span class="ending-tag">${escapeHtml(line)}</span>`).join("")
    : `<span class="ending-tag">关注后续更新</span>`;

  return `
    <main class="card card-ending">
      <div class="grain"></div>
      <header class="ending-header">
        <span class="brand-chip">${escapeHtml(options.brand)}</span>
      </header>
      <section class="ending-body">
        <p class="eyebrow">看完这组卡片，你至少该记住</p>
        <h2>${escapeHtml(card.title)}</h2>
        <div class="ending-tags">${tags}</div>
      </section>
      <footer class="ending-footer">
        <span class="footer-pill">适合小红书</span>
        <span class="footer-pill">也可做公众号插图</span>
      </footer>
    </main>
  `;
}

function renderCardHtml(card, options) {
  const body =
    card.type === "cover"
      ? renderCover(card, options)
      : card.type === "ending"
        ? renderEnding(card, options)
        : renderContent(card, options);

  return `<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>${escapeHtml(card.title)}</title>
    <style>
      :root {
        --ink: #241914;
        --muted: #7b6258;
        --accent: #ff2442;
        --shadow: rgba(92, 46, 35, 0.12);
        --border: rgba(115, 75, 64, 0.12);
        --font-body: "PingFang SC", "Microsoft YaHei UI", "Microsoft YaHei", sans-serif;
      }

      * { box-sizing: border-box; }

      html, body {
        margin: 0;
        padding: 0;
        width: 1242px;
        height: 1660px;
        overflow: hidden;
        background: radial-gradient(circle at top left, #fff7f2 0%, #f6ece4 42%, #eeded2 100%);
        font-family: var(--font-body);
        color: var(--ink);
      }

      body { position: relative; }

      .card {
        position: relative;
        width: 1242px;
        height: 1660px;
        padding: 56px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        background:
          linear-gradient(180deg, rgba(255,255,255,0.82), rgba(255,248,242,0.92)),
          linear-gradient(135deg, rgba(255,212,220,0.42), rgba(246,191,121,0.28));
      }

      .grain {
        position: absolute;
        inset: 0;
        background-image:
          linear-gradient(rgba(255,255,255,0.14) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.14) 1px, transparent 1px);
        background-size: 28px 28px;
        opacity: 0.35;
        pointer-events: none;
      }

      .brand-chip, .save-chip, .page-chip, .footer-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        border-radius: 999px;
        font-size: 28px;
        line-height: 1;
        letter-spacing: 0.02em;
      }

      .brand-chip {
        padding: 16px 28px;
        background: rgba(255, 36, 66, 0.1);
        color: var(--accent);
        font-weight: 700;
      }

      .save-chip {
        padding: 16px 28px;
        background: var(--accent);
        color: #ffffff;
        font-weight: 700;
        box-shadow: 0 16px 30px rgba(255, 36, 66, 0.22);
      }

      .cover-top, .content-header, .ending-header {
        position: relative;
        z-index: 2;
        display: flex;
        justify-content: space-between;
        align-items: center;
      }

      .cover-body, .content-body, .ending-body {
        position: relative;
        z-index: 2;
      }

      .eyebrow {
        margin: 0 0 18px;
        color: var(--accent);
        font-size: 34px;
        font-weight: 700;
        letter-spacing: 0.06em;
      }

      .card-cover h1 {
        margin: 0;
        max-width: 980px;
        font-size: 88px;
        line-height: 1.06;
        letter-spacing: -0.03em;
        font-weight: 900;
      }

      .cover-subtitle {
        margin: 28px 0 0;
        max-width: 920px;
        font-size: 42px;
        line-height: 1.42;
        color: var(--muted);
        font-weight: 600;
      }

      .cover-kicker {
        margin: 22px 0 0;
        max-width: 880px;
        font-size: 32px;
        line-height: 1.48;
        color: #5d463e;
      }

      .cover-body-panel {
        padding: 56px 54px 60px;
        border-radius: 44px;
        background: linear-gradient(160deg, rgba(255,255,255,0.92), rgba(255,240,232,0.88));
        box-shadow: 0 28px 80px rgba(135, 67, 54, 0.12);
        border: 1px solid rgba(255,255,255,0.7);
      }

      .alert-glow {
        position: absolute;
        border-radius: 999px;
        filter: blur(24px);
        opacity: 0.45;
        pointer-events: none;
      }

      .alert-glow-a {
        width: 280px;
        height: 280px;
        top: 180px;
        right: 100px;
        background: rgba(255, 36, 66, 0.14);
      }

      .alert-glow-b {
        width: 320px;
        height: 320px;
        bottom: 140px;
        left: 48px;
        background: rgba(246, 191, 121, 0.18);
      }

      .number-ribbon {
        position: absolute;
        right: 56px;
        top: 220px;
        z-index: 2;
        min-width: 172px;
        padding: 18px 24px;
        border-radius: 30px;
        background: rgba(36, 25, 20, 0.92);
        color: #fff7f0;
        font-size: 54px;
        line-height: 1;
        font-weight: 900;
        text-align: center;
        box-shadow: 0 20px 40px rgba(36, 25, 20, 0.2);
      }

      .card-cover-number h1 {
        max-width: 860px;
        font-size: 92px;
        line-height: 1.04;
      }

      .card-cover-number .cover-subtitle {
        margin-top: 22px;
        font-size: 48px;
        line-height: 1.2;
        font-weight: 900;
        color: #4d352d;
      }

      .card-cover-number .cover-kicker {
        margin-top: 18px;
        font-size: 30px;
        line-height: 1.42;
        font-weight: 700;
      }

      .card-cover-alert h1 {
        max-width: 900px;
        font-size: 98px;
        line-height: 1.02;
      }

      .card-cover-alert .cover-subtitle {
        margin-top: 24px;
        font-size: 54px;
        line-height: 1.18;
        font-weight: 900;
        color: #4d352d;
      }

      .card-cover-alert .cover-kicker {
        margin-top: 14px;
        display: inline-flex;
        align-self: flex-start;
        padding: 12px 18px;
        border-radius: 18px;
        background: rgba(255, 36, 66, 0.08);
        color: #6e5146;
        font-size: 28px;
        line-height: 1.35;
        font-weight: 700;
      }

      .header-left {
        display: flex;
        align-items: center;
        gap: 16px;
      }

      .deck-title {
        font-size: 28px;
        color: var(--muted);
        font-weight: 700;
      }

      .page-chip {
        min-width: 72px;
        height: 72px;
        background: rgba(36, 25, 20, 0.08);
        color: #533a31;
        font-weight: 800;
      }

      .card-content h2,
      .card-ending h2 {
        margin: 0;
        font-size: 72px;
        line-height: 1.16;
        letter-spacing: -0.03em;
        font-weight: 900;
      }

      .subtitle {
        margin: 28px 0 0;
        max-width: 1020px;
        font-size: 42px;
        line-height: 1.48;
        color: var(--muted);
        font-weight: 600;
      }

      .bullet-list {
        margin: 34px 0 0;
        padding: 0;
        list-style: none;
        display: grid;
        gap: 18px;
      }

      .bullet-list li {
        padding: 24px 28px;
        border-radius: 32px;
        background: rgba(255, 255, 255, 0.78);
        box-shadow: 0 18px 40px var(--shadow);
        font-size: 38px;
        line-height: 1.45;
        font-weight: 700;
      }

      .paragraph-stack {
        margin-top: 28px;
        display: grid;
        gap: 18px;
      }

      .paragraph-stack p {
        margin: 0;
        font-size: 36px;
        line-height: 1.62;
        color: #4f3a32;
      }

      .content-footer {
        position: relative;
        z-index: 1;
        padding-top: 22px;
        border-top: 2px dashed rgba(111, 81, 70, 0.2);
        color: var(--muted);
        font-size: 28px;
        font-weight: 700;
      }

      .ending-tags {
        margin-top: 34px;
        display: flex;
        flex-wrap: wrap;
        gap: 18px;
      }

      .ending-tag {
        padding: 20px 28px;
        border-radius: 26px;
        background: rgba(255, 255, 255, 0.82);
        border: 1px solid var(--border);
        font-size: 34px;
        line-height: 1.35;
        color: #5d463e;
        font-weight: 700;
      }

      .ending-footer {
        position: relative;
        z-index: 1;
        display: flex;
        gap: 16px;
        flex-wrap: wrap;
      }

      .footer-pill {
        padding: 16px 26px;
        background: rgba(255, 255, 255, 0.72);
        color: #6f5146;
        border: 1px solid var(--border);
        font-size: 24px;
      }

      .card-editorial-cover,
      .card-editorial-content {
        background: #fbfaf7;
        justify-content: flex-start;
        gap: 36px;
      }

      .card-editorial-cover {
        padding-top: 28px;
        gap: 22px;
      }

      .editorial-top {
        position: relative;
        z-index: 2;
        display: flex;
        align-items: center;
      }

      .editorial-cover-stack {
        position: relative;
        z-index: 2;
        display: grid;
        gap: 22px;
        align-content: start;
      }

      .editorial-media {
        width: 100%;
        height: 760px;
        overflow: hidden;
        background: #e9edf1;
      }

      .editorial-media-tall {
        height: 800px;
      }

      .editorial-media img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .editorial-media-placeholder {
        position: relative;
        background:
          linear-gradient(180deg, #bfd1df 0%, #dfe7ee 46%, #c9b8a2 46%, #d3c4b5 100%);
      }

      .editorial-media-placeholder::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        width: 220px;
        height: 220px;
        background: #1b6847;
      }

      .editorial-media-placeholder::after {
        content: "";
        position: absolute;
        right: 130px;
        bottom: 110px;
        width: 220px;
        height: 120px;
        background: rgba(255,255,255,0.82);
        box-shadow: 0 18px 36px rgba(0,0,0,0.1);
      }

      .placeholder-label {
        position: absolute;
        left: 42px;
        top: 34px;
        z-index: 2;
        padding: 10px 16px;
        border-radius: 18px;
        background: rgba(255,255,255,0.88);
        font-size: 24px;
        font-weight: 700;
        color: #41535f;
      }

      .editorial-cover-copy h1 {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 96px;
        line-height: 1.08;
        letter-spacing: -0.04em;
        font-weight: 700;
      }

      .editorial-cover-copy-contrast h1 {
        font-size: 90px;
        line-height: 1.04;
      }

      .editorial-contrast-line {
        margin: 18px 0 0;
        display: inline-block;
        align-self: flex-start;
        padding: 8px 14px 10px;
        background: #fff1c9;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 52px;
        line-height: 1.18;
        color: #201b19;
        font-weight: 700;
      }

      .editorial-note {
        margin-top: 28px;
        display: grid;
        grid-template-columns: 8px 1fr;
        gap: 18px;
        align-items: start;
      }

      .editorial-note-bar {
        width: 8px;
        height: 100%;
        min-height: 96px;
        background: #2a2a2a;
      }

      .editorial-note p {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 32px;
        line-height: 1.5;
        color: #2f2a27;
      }

      .editorial-note-contrast {
        margin-top: 24px;
      }

      .editorial-cover-kicker {
        margin: 28px 0 0;
        font-size: 24px;
        line-height: 1.4;
        color: #76675f;
        font-weight: 700;
      }

      .editorial-content-header {
        justify-content: space-between;
      }

      .editorial-article {
        position: relative;
        z-index: 2;
        display: grid;
        gap: 22px;
        align-content: start;
      }

      .editorial-article h2 {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 70px;
        line-height: 1.16;
        font-weight: 700;
        letter-spacing: -0.03em;
      }

      .editorial-copy-stack {
        display: grid;
        gap: 28px;
      }

      .editorial-paragraph {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 44px;
        line-height: 1.78;
        color: #2d2b29;
      }

      .editorial-highlight {
        margin: 6px 0 0;
        display: inline-block;
        align-self: start;
        padding: 4px 10px 6px;
        background: #fff1c9;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 44px;
        line-height: 1.6;
        color: #24201e;
      }

      .card-cover-imgdriven {
        position: relative;
        overflow: hidden;
      }

      .card-cover-imgdriven .grain {
        z-index: 3;
        opacity: 0.18;
      }

      .card-cover-imgwindow {
        padding: 44px 38px 38px;
        background:
          linear-gradient(180deg, rgba(255,255,255,0.9), rgba(255,248,242,0.96)),
          radial-gradient(circle at 78% 18%, rgba(255,173,167,0.22), transparent 20%),
          radial-gradient(circle at 26% 62%, rgba(255,210,140,0.14), transparent 24%);
      }

      .imgdriven-stage {
        position: absolute;
        left: 50px;
        right: 50px;
        top: 188px;
        height: 980px;
        z-index: 1;
        display: flex;
        align-items: center;
        justify-content: center;
      }

      .imgdriven-frame {
        width: 100%;
        height: 100%;
        border-radius: 38px;
        overflow: hidden;
        box-shadow: 0 26px 50px rgba(56, 36, 30, 0.16);
        background: #dfe8f1;
      }

      .imgdriven-frame img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: 50% 42%;
        display: block;
      }

      .imgdriven-copy-card {
        position: absolute;
        left: 54px;
        right: 54px;
        bottom: 86px;
        z-index: 3;
        margin-top: 0;
        border-radius: 34px;
        padding: 28px 32px 28px;
        background: rgba(255, 251, 247, 0.94);
        box-shadow: 0 18px 38px rgba(92, 46, 35, 0.08);
        border: 1px solid rgba(115, 75, 64, 0.08);
      }

      .imgdriven-copy-card h1 {
        margin: 0;
        font-size: 72px;
        line-height: 1.04;
        letter-spacing: -0.03em;
        font-weight: 900;
        color: #241914;
      }

      .imgdriven-copy-card .eyebrow {
        color: #ff2442;
      }

      .imgdriven-note {
        margin: 12px 0 0;
        font-size: 28px;
        line-height: 1.4;
        color: #6e6058;
        font-weight: 700;
      }

      .palette-dark .imgdriven-frame {
        box-shadow: 0 28px 54px rgba(10, 10, 10, 0.22);
      }

      .card-cover-imgposter {
        padding: 0;
        background: #11243c;
      }

      .imgposter-media {
        position: absolute;
        inset: 0;
        z-index: 1;
        background: #dfe8f1;
      }

      .imgposter-media img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: 50% 40%;
        display: block;
      }

      .imgposter-vignette {
        position: absolute;
        inset: 0;
        z-index: 2;
        background:
          linear-gradient(180deg, rgba(5, 18, 36, 0.24), rgba(5, 18, 36, 0.02) 28%, rgba(5, 18, 36, 0.02) 56%, rgba(5, 18, 36, 0.36) 100%),
          linear-gradient(0deg, rgba(10, 18, 30, 0.12), rgba(10, 18, 30, 0.12));
      }

      .imgposter-bottomfade {
        position: absolute;
        left: 0;
        right: 0;
        bottom: 0;
        height: 640px;
        z-index: 2;
        background: linear-gradient(180deg, rgba(8, 17, 31, 0) 0%, rgba(8, 17, 31, 0.24) 34%, rgba(8, 17, 31, 0.88) 100%);
      }

      .imgposter-top {
        position: relative;
        z-index: 4;
        padding: 44px 38px 0;
      }

      .card-cover-imgposter .brand-chip {
        background: rgba(255, 255, 255, 0.16);
        color: #fff;
        backdrop-filter: blur(12px);
      }

      .card-cover-imgposter .save-chip {
        background: rgba(255, 36, 66, 0.94);
      }

      .imgposter-copy {
        position: absolute;
        left: 54px;
        right: 54px;
        bottom: 76px;
        z-index: 4;
        padding: 34px 36px 30px;
        border-radius: 36px;
        background: linear-gradient(180deg, rgba(9, 20, 38, 0.22), rgba(9, 20, 38, 0.58));
        border: 1px solid rgba(255, 255, 255, 0.14);
        box-shadow: 0 32px 64px rgba(5, 12, 24, 0.22);
        backdrop-filter: blur(14px);
      }

      .card-cover-imgposter h1 {
        max-width: 100%;
        font-size: 82px;
        line-height: 1.02;
        color: #fffaf6;
        text-shadow: 0 12px 24px rgba(0, 0, 0, 0.24);
      }

      .card-cover-imgposter .eyebrow {
        color: rgba(255, 223, 228, 0.96);
      }

      .imgposter-note {
        margin: 18px 0 0;
        max-width: 920px;
        font-size: 30px;
        line-height: 1.36;
        color: rgba(247, 238, 232, 0.92);
        font-weight: 700;
      }

      .card-cover-imgsplit {
        padding: 0;
        background: #f5efe9;
      }

      .imgsplit-media {
        position: absolute;
        inset: 0 0 0 248px;
        z-index: 1;
        background: #dfe8f1;
      }

      .imgsplit-media img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        object-position: 58% 42%;
        display: block;
      }

      .imgsplit-wash {
        position: absolute;
        inset: 0;
        z-index: 2;
        background:
          linear-gradient(90deg, rgba(255, 247, 240, 0.8) 0%, rgba(255, 247, 240, 0.28) 30%, rgba(255, 247, 240, 0) 48%),
          linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.08));
      }

      .imgsplit-band {
        position: absolute;
        left: 52px;
        top: 204px;
        bottom: 78px;
        width: 26px;
        z-index: 3;
        border-radius: 999px;
        background: linear-gradient(180deg, rgba(255, 51, 82, 0.96), rgba(255, 185, 102, 0.88));
        box-shadow: 0 22px 40px rgba(255, 87, 88, 0.18);
      }

      .imgsplit-top {
        position: absolute;
        left: 38px;
        right: 38px;
        top: 44px;
        z-index: 5;
      }

      .card-cover-imgsplit .brand-chip {
        background: rgba(255, 255, 255, 0.82);
        backdrop-filter: blur(10px);
      }

      .imgsplit-panel {
        position: absolute;
        left: 88px;
        bottom: 82px;
        width: 700px;
        z-index: 5;
        padding: 32px 34px 34px;
        border-radius: 38px;
        background: rgba(255, 250, 244, 0.95);
        box-shadow: 0 28px 64px rgba(92, 46, 35, 0.12);
        border: 1px solid rgba(115, 75, 64, 0.08);
      }

      .imgsplit-rule {
        display: block;
        width: 118px;
        height: 12px;
        border-radius: 999px;
        background: #ff2442;
        margin-bottom: 24px;
      }

      .card-cover-imgsplit h1 {
        max-width: 100%;
        font-size: 78px;
        line-height: 1.04;
        color: #241914;
      }

      .card-cover-imgsplit .eyebrow {
        margin-bottom: 16px;
      }

      .imgsplit-note {
        margin: 16px 0 0;
        max-width: 560px;
        font-size: 30px;
        line-height: 1.4;
        color: #63564e;
        font-weight: 700;
      }

      .content-header-floating {
        position: absolute;
        top: 56px;
        left: 56px;
        right: 56px;
        z-index: 4;
      }

      .card-content-split-focus .split-focus-body {
        position: relative;
        z-index: 2;
        margin-top: 18px;
        display: grid;
        grid-template-columns: 0.88fr 1.12fr;
        gap: 28px;
        align-items: stretch;
      }

      .split-focus-media {
        min-height: 1180px;
        overflow: hidden;
        border-radius: 36px;
        box-shadow: 0 24px 46px rgba(0, 0, 0, 0.12);
      }

      .split-focus-media img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .split-focus-copy {
        border-radius: 32px;
        background: rgba(255, 252, 248, 0.9);
        border: 1px solid rgba(115, 75, 64, 0.1);
        padding: 38px 36px 34px;
        display: grid;
        align-content: start;
        gap: 26px;
        box-shadow: 0 18px 36px rgba(92, 46, 35, 0.08);
      }

      .split-focus-copy h2 {
        margin: 0;
        font-size: 64px;
        line-height: 1.12;
      }

      .split-focus-stack {
        display: grid;
        gap: 22px;
      }

      .split-focus-paragraph {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 38px;
        line-height: 1.72;
        color: #2d2b29;
      }

      .split-focus-highlight {
        margin: 0;
        display: inline-block;
        align-self: start;
        padding: 8px 12px;
        background: #fff1c9;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 36px;
        line-height: 1.58;
        color: #24201e;
      }

      .card-content-image-dominant {
        padding: 0;
        overflow: hidden;
      }

      .imgdriven-content-media {
        position: absolute;
        inset: 0 0 480px;
        z-index: 0;
      }

      .imgdriven-content-media img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .imgdriven-content-copy {
        position: absolute;
        left: 40px;
        right: 40px;
        bottom: 40px;
        z-index: 3;
        padding: 36px 34px 34px;
        border-radius: 34px;
        background: rgba(255, 252, 248, 0.94);
        box-shadow: 0 18px 38px rgba(0, 0, 0, 0.12);
        display: grid;
        gap: 18px;
      }

      .imgdriven-content-copy h2 {
        margin: 0;
        font-size: 62px;
        line-height: 1.12;
      }

      .imgdriven-content-note {
        margin: 0;
        font-size: 28px;
        line-height: 1.45;
        color: #72655d;
        font-weight: 700;
      }

      .imgdriven-content-lead {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 40px;
        line-height: 1.7;
        color: #2d2b29;
      }

      .imgdriven-content-stack {
        display: grid;
        gap: 16px;
      }

      .imgdriven-content-paragraph {
        margin: 0;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 34px;
        line-height: 1.62;
        color: #3b3532;
      }

      .imgdriven-content-highlight {
        margin: 0;
        display: inline-block;
        align-self: start;
        padding: 8px 12px;
        background: #fff1c9;
        font-family: "Songti SC", "STSong", "SimSun", serif;
        font-size: 34px;
        line-height: 1.5;
        color: #24201e;
      }

      .content-image {
        width: 100%;
        height: 420px;
        overflow: hidden;
        border-radius: 24px;
        margin-bottom: 22px;
      }

      .content-image img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }

      .editorial-inline-image {
        width: 100%;
        height: 480px;
        overflow: hidden;
        margin-bottom: 18px;
      }

      .editorial-inline-image img {
        width: 100%;
        height: 100%;
        object-fit: cover;
        display: block;
      }
    </style>
  </head>
  <body>
    ${body}
  </body>
</html>`;
}

async function main() {
  const args = parseArgs(process.argv);
  if (!args.input || !args.outputDir) {
    console.error("Usage: node render_xiaohongshu_cards.mjs --input <txt> --output-dir <dir> [--separator <text>] [--deck-title <title>] [--brand <name>] [--cover-style statement|alert|contrast|number|poster|split-band|window-card] [--deck-style cards|editorial] [--eyebrow <text>]");
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
  const resolvedDeckStyle = args.deckStyle === "auto" ? detectAutoDeckStyle(cards, deckTitle) : args.deckStyle;
  const resolvedCoverStyle = args.coverStyle === "auto" ? detectAutoCoverStyle(cards, deckTitle) : args.coverStyle;
  const options = {
    deckTitle,
    brand: args.brand,
    coverStyle: resolvedCoverStyle,
    deckStyle: resolvedDeckStyle,
    eyebrow: args.eyebrow,
  };

  await mkdir(outputDir, { recursive: true });

  for (const card of cards) {
    card.meta.resolvedImage = resolveImageReference(card.meta.image, inputPath, outputDir);
  }

  for (const card of cards) {
    const html = renderCardHtml(card, options);
    await writeFile(path.join(outputDir, `${card.id}.html`), html, "utf8");
  }

  const coverCard = cards.find((card) => card.type === "cover") ?? cards[0];
  const resolvedImageCoverVariant =
    coverCard?.meta?.resolvedImage && (coverCard.meta.refLayout === "image-dominant" || coverCard.meta.refStyle === "news-photo")
      ? resolveImageCoverVariant(coverCard, options)
      : "";

  await writeFile(path.join(outputDir, "index.html"), renderGallery(cards, { ...options, defaultDeckTitle: DEFAULT_DECK_TITLE }), "utf8");
  await writeFile(
    path.join(outputDir, "manifest.json"),
    JSON.stringify(
      {
        status: "ready",
        deckTitle,
        brand: args.brand,
        requestedCoverStyle: args.coverStyle,
        resolvedCoverStyle,
        resolvedImageCoverVariant,
        requestedDeckStyle: args.deckStyle,
        resolvedDeckStyle,
        separator: args.separator,
        inputPath,
        outputDir,
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
        coverStyle: resolvedCoverStyle,
        imageCoverVariant: resolvedImageCoverVariant,
        deckStyle: resolvedDeckStyle,
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
