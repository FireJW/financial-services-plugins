#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const WebSocketImpl = globalThis.WebSocket;

function parseArgs(argv) {
  const result = {
    endpoint: "http://127.0.0.1:9222",
    url: "",
    screenshot: "",
    waitMs: 8000,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--endpoint" && index + 1 < argv.length) {
      result.endpoint = argv[index + 1];
      index += 1;
    } else if (value === "--url" && index + 1 < argv.length) {
      result.url = argv[index + 1];
      index += 1;
    } else if (value === "--screenshot" && index + 1 < argv.length) {
      result.screenshot = argv[index + 1];
      index += 1;
    } else if (value === "--wait-ms" && index + 1 < argv.length) {
      result.waitMs = Number.parseInt(argv[index + 1], 10) || 8000;
      index += 1;
    }
  }
  if (!result.url) {
    throw new Error("Usage: browser_session_fetch.js --url <url> [--endpoint <http://127.0.0.1:9222>] [--screenshot <path>] [--wait-ms 8000]");
  }
  return result;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function joinUrl(base, suffix) {
  return `${String(base || "").replace(/\/+$/, "")}${suffix}`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.json();
}

async function fetchText(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} for ${url}`);
  }
  return response.text();
}

async function openTarget(endpoint) {
  const blankUrl = encodeURIComponent("about:blank");
  const targetUrl = joinUrl(endpoint, `/json/new?${blankUrl}`);
  try {
    return await fetchJson(targetUrl, { method: "PUT" });
  } catch {
    return fetchJson(targetUrl);
  }
}

async function closeTarget(endpoint, targetId) {
  if (!targetId) {
    return;
  }
  const closeUrl = joinUrl(endpoint, `/json/close/${targetId}`);
  try {
    await fetchText(closeUrl, { method: "PUT" });
  } catch {
    try {
      await fetchText(closeUrl);
    } catch {
      // Ignore close errors.
    }
  }
}

function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
}

function uniqueMediaCandidates(items) {
  const seen = new Set();
  const result = [];
  for (const item of Array.isArray(items) ? items : []) {
    const src = cleanText(item?.source_url || item?.src);
    if (!src || seen.has(src)) {
      continue;
    }
    seen.add(src);
    result.push({
      source_url: src,
      alt_text: cleanText(item?.alt_text || item?.alt),
      display_width: Number(item?.display_width || item?.displayWidth || 0),
      display_height: Number(item?.display_height || item?.displayHeight || 0),
      x: Number(item?.x || 0),
      y: Number(item?.y || 0),
      natural_width: Number(item?.natural_width || item?.naturalWidth || 0),
      natural_height: Number(item?.natural_height || item?.naturalHeight || 0),
    });
  }
  return result;
}

function deriveMediaPath(rootScreenshotPath, index) {
  if (!rootScreenshotPath) {
    return "";
  }
  const parsed = path.parse(rootScreenshotPath);
  return path.join(parsed.dir, `${parsed.name}-media-${index}.png`);
}

async function captureMediaScreenshots(send, rootScreenshotPath, mediaCandidates) {
  const localized = [];
  const candidates = uniqueMediaCandidates(mediaCandidates).slice(0, 6);
  for (let index = 0; index < candidates.length; index += 1) {
    const candidate = candidates[index];
    let localArtifactPath = "";
    const width = Math.round(candidate.display_width || 0);
    const height = Math.round(candidate.display_height || 0);
    if (rootScreenshotPath && width >= 120 && height >= 120) {
      try {
        const mediaPath = deriveMediaPath(rootScreenshotPath, index + 1);
        const screenshot = await send("Page.captureScreenshot", {
          format: "png",
          captureBeyondViewport: true,
          clip: {
            x: Math.max(0, Number(candidate.x || 0)),
            y: Math.max(0, Number(candidate.y || 0)),
            width,
            height,
            scale: 1,
          },
        });
        if (screenshot?.data) {
          fs.mkdirSync(path.dirname(mediaPath), { recursive: true });
          fs.writeFileSync(mediaPath, Buffer.from(screenshot.data, "base64"));
          localArtifactPath = mediaPath;
        }
      } catch {
        // Keep the source URL even if clipping fails.
      }
    }
    localized.push({
      media_type: "image",
      source_url: candidate.source_url,
      local_artifact_path: localArtifactPath,
      ocr_source: localArtifactPath ? "screenshot_crop" : "image",
      alt_text: candidate.alt_text,
      capture_method: localArtifactPath ? "dom_clip" : "dom_reference",
      display_width: width,
      display_height: height,
    });
  }
  return localized;
}

function collectAxText(nodes) {
  if (!Array.isArray(nodes)) {
    return "";
  }
  const lines = [];
  for (const node of nodes) {
    const role = cleanText(node?.role?.value);
    const name = cleanText(node?.name?.value);
    if (!name) {
      continue;
    }
    const line = role && role !== "StaticText" ? `${role}: ${name}` : name;
    if (line && !lines.includes(line)) {
      lines.push(line);
    }
  }
  return lines.join("\n");
}

async function readMediaCandidates(send) {
  const mediaCandidates = await send("Runtime.evaluate", {
    expression: `JSON.stringify(Array.from(document.images || []).map((img) => {
      const src = img.currentSrc || img.src || '';
      const rect = img.getBoundingClientRect();
      const nearestLabel = img.getAttribute('aria-label')
        || img.alt
        || img.getAttribute('title')
        || img.closest('[aria-label]')?.getAttribute('aria-label')
        || '';
      return {
        source_url: src,
        alt_text: nearestLabel,
        display_width: rect.width || 0,
        display_height: rect.height || 0,
        natural_width: img.naturalWidth || 0,
        natural_height: img.naturalHeight || 0,
        x: rect.left + window.scrollX,
        y: rect.top + window.scrollY
      };
    }).filter((item) => item.source_url.includes('pbs.twimg.com/media/') && item.display_width >= 120 && item.display_height >= 120))`,
    returnByValue: true,
  });
  try {
    return uniqueMediaCandidates(JSON.parse(mediaCandidates?.result?.value || "[]"));
  } catch {
    return [];
  }
}

async function waitForMeaningfulContent(send, waitMs) {
  const deadline = Date.now() + Math.max(1000, Number(waitMs) || 8000);
  let lastProbe = {
    readyState: "",
    primaryText: "",
    hasTweetText: false,
    mediaCount: 0,
    looksReady: false,
  };

  while (Date.now() < deadline) {
    const probeResult = await send("Runtime.evaluate", {
      expression: `JSON.stringify((() => {
        const primary = document.querySelector('[data-testid="primaryColumn"]') || document.querySelector('main');
        const primaryText = ((primary && primary.innerText) || '').replace(/\\s+/g, ' ').trim();
        const mediaCount = Array.from((primary || document).querySelectorAll ? (primary || document).querySelectorAll('img') : []).filter((img) => {
          const src = img.currentSrc || img.src || '';
          const rect = img.getBoundingClientRect();
          return src.includes('pbs.twimg.com/media/') && rect.width >= 120 && rect.height >= 120;
        }).length;
        const hasTweetText = Boolean((primary || document).querySelector?.('[data-testid="tweetText"]'));
        const shortcutsOnlyNormalized = /(?:keyboard shortcuts|查看键盘快捷键|要查看键盘快捷键)/i.test(primaryText) && primaryText.length < 80;
        const shortcutsOnly = /(?:keyboard shortcuts|查看键盘快捷键|要查看键盘快捷键)/i.test(primaryText) && primaryText.length < 80;
        const looksReady = hasTweetText || mediaCount > 0 || (document.readyState === 'complete' && primaryText.length > 160 && !shortcutsOnlyNormalized);
        return {
          readyState: document.readyState,
          primaryText,
          hasTweetText,
          mediaCount,
          looksReady
        };
      })())`,
      returnByValue: true,
    });

    try {
      lastProbe = JSON.parse(probeResult?.result?.value || "{}");
    } catch {
      lastProbe = {
        readyState: "",
        primaryText: "",
        hasTweetText: false,
        mediaCount: 0,
        looksReady: false,
      };
    }

    if (lastProbe.looksReady) {
      return lastProbe;
    }
    await sleep(750);
  }
  return lastProbe;
}

async function waitForStableMediaCandidates(send, waitMs) {
  const deadline = Date.now() + Math.max(2500, Number(waitMs) || 8000);
  let best = [];
  let lastSignature = "";
  let stablePasses = 0;

  while (Date.now() < deadline) {
    const candidates = await readMediaCandidates(send);
    if (candidates.length > best.length) {
      best = candidates;
    }

    const signature = candidates
      .map((item) => `${cleanText(item.source_url)}|${Math.round(Number(item.display_width || 0))}x${Math.round(Number(item.display_height || 0))}`)
      .join("||");

    if (signature && signature === lastSignature) {
      stablePasses += 1;
    } else {
      stablePasses = 0;
      lastSignature = signature;
    }

    if (best.length > 0 && stablePasses >= 2) {
      return best;
    }
    await sleep(500);
  }

  return best;
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!WebSocketImpl) {
    throw new Error("browser_session_fetch.js requires a Node.js runtime with global WebSocket support.");
  }
  const target = await openTarget(args.endpoint);
  const ws = new WebSocketImpl(target.webSocketDebuggerUrl);
  let nextId = 0;
  const pending = new Map();

  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = ++nextId;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });

  ws.onmessage = (event) => {
    const message = JSON.parse(event.data.toString());
    if (message.id && pending.has(message.id)) {
      const current = pending.get(message.id);
      pending.delete(message.id);
      if (message.error) {
        current.reject(new Error(message.error.message || JSON.stringify(message.error)));
      } else {
        current.resolve(message.result || {});
      }
    }
  };

  try {
    await new Promise((resolve, reject) => {
      ws.onopen = resolve;
      ws.onerror = reject;
    });

    await send("Page.enable");
    await send("Runtime.enable");
    await send("Accessibility.enable");
    await send("Page.navigate", { url: args.url });
    await waitForMeaningfulContent(send, args.waitMs);
    const parsedMediaCandidates = await waitForStableMediaCandidates(send, Math.max(3000, args.waitMs));

    const [finalUrl, visibleText, html, linksText, axTree, screenshot] = await Promise.all([
      send("Runtime.evaluate", {
        expression: "location.href",
        returnByValue: true,
      }),
      send("Runtime.evaluate", {
        expression: "document.body ? document.body.innerText : ''",
        returnByValue: true,
      }),
      send("Runtime.evaluate", {
        expression: "document.documentElement ? document.documentElement.outerHTML : ''",
        returnByValue: true,
      }),
      send("Runtime.evaluate", {
        expression: "Array.from(document.links || []).map(item => item.href).join('\\n')",
        returnByValue: true,
      }),
      send("Accessibility.getFullAXTree"),
      send("Page.captureScreenshot", {
        format: "png",
        captureBeyondViewport: true,
      }),
    ]);

    let screenshotPath = "";
    if (args.screenshot && screenshot?.data) {
      fs.mkdirSync(path.dirname(args.screenshot), { recursive: true });
      fs.writeFileSync(args.screenshot, Buffer.from(screenshot.data, "base64"));
      screenshotPath = args.screenshot;
    }
    const localizedMediaItems = await captureMediaScreenshots(send, screenshotPath, parsedMediaCandidates);

    const payload = {
      final_url: cleanText(finalUrl?.result?.value) || args.url,
      visible_text: String(visibleText?.result?.value || ""),
      accessibility_text: collectAxText(axTree?.nodes) || String(visibleText?.result?.value || ""),
      html: String(html?.result?.value || ""),
      links_text: String(linksText?.result?.value || ""),
      screenshot_path: screenshotPath,
      media_items: localizedMediaItems,
      error: "",
      session_note: `attached to ${args.endpoint}`,
    };
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
  } finally {
    try {
      ws.close();
    } catch {
      // Ignore websocket close errors.
    }
    await closeTarget(args.endpoint, target.id);
  }
}

main().catch((error) => {
  process.stderr.write(`${error.stack || String(error)}\n`);
  process.exit(1);
});
