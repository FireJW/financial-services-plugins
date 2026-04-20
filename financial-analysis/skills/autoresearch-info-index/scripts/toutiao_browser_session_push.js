#!/usr/bin/env node

/**
 * Push a toutiao-fast-card manifest to Toutiao weitoutiao (micro-headline)
 * via CDP remote debugging.
 *
 * Usage:
 *   node toutiao_browser_session_push.js \
 *     --manifest <path-to-manifest.json> \
 *     [--endpoint http://127.0.0.1:9222] \
 *     [--wait-ms 8000] \
 *     [--draft-only]
 *
 * The manifest JSON must contain:
 *   { title, plain_text, segments[], keywords[] }
 *
 * --draft-only: click "存草稿" instead of "发布" (safe for dry-runs).
 */

const fs = require("node:fs");
const path = require("node:path");
const WebSocketImpl = globalThis.WebSocket;

// ---------------------------------------------------------------------------
// CLI args
// ---------------------------------------------------------------------------

function parseArgs(argv) {
  const result = {
    manifest: "",
    endpoint: "http://127.0.0.1:9222",
    waitMs: 8000,
    draftOnly: false,
  };
  for (let i = 0; i < argv.length; i += 1) {
    const v = argv[i];
    if (v === "--manifest" && i + 1 < argv.length) {
      result.manifest = argv[++i];
    } else if (v === "--endpoint" && i + 1 < argv.length) {
      result.endpoint = argv[++i];
    } else if (v === "--wait-ms" && i + 1 < argv.length) {
      result.waitMs = Number.parseInt(argv[++i], 10) || 8000;
    } else if (v === "--draft-only") {
      result.draftOnly = true;
    }
  }
  if (!result.manifest) {
    throw new Error(
      "Usage: toutiao_browser_session_push.js --manifest <path> " +
        "[--endpoint http://127.0.0.1:9222] [--wait-ms 8000] [--draft-only]",
    );
  }
  return result;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function cleanText(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function joinUrl(base, suffix) {
  return `${String(base || "").replace(/\/+$/, "")}${suffix}`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
  return response.json();
}

async function fetchText(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
  return response.text();
}

function parseJsonValue(value, fallback = {}) {
  try {
    return JSON.parse(value || "{}");
  } catch {
    return fallback;
  }
}

// ---------------------------------------------------------------------------
// CDP target management
// ---------------------------------------------------------------------------

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
  if (!targetId) return;
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

// ---------------------------------------------------------------------------
// CDP helpers
// ---------------------------------------------------------------------------

async function navigateAndSettle(send, url, waitMs) {
  await send("Page.navigate", { url });
  await sleep(Math.max(2000, waitMs));
}

async function evaluateJson(send, expression) {
  const result = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  return parseJsonValue(result?.result?.value, {});
}

function manifestScreenshotPath(manifestPath) {
  const parsed = path.parse(manifestPath);
  return path.join(parsed.dir, `${parsed.name}-editor.png`);
}

async function captureScreenshot(send, screenshotPath) {
  const screenshot = await send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: true,
  });
  if (screenshot?.data) {
    fs.mkdirSync(path.dirname(screenshotPath), { recursive: true });
    fs.writeFileSync(screenshotPath, Buffer.from(screenshot.data, "base64"));
    return screenshotPath;
  }
  return "";
}

// ---------------------------------------------------------------------------
// ProseMirror content setter
// ---------------------------------------------------------------------------

/**
 * Set plain text content in the ProseMirror editor used by Toutiao weitoutiao.
 * The editor is a contentEditable div with class "ProseMirror" inside ".syl-editor".
 */
function buildProseMirrorSetterExpression(plainText) {
  return `JSON.stringify((() => {
    const text = ${JSON.stringify(plainText)};
    const editor = document.querySelector('.syl-editor .ProseMirror[contenteditable="true"]')
                || document.querySelector('.ProseMirror[contenteditable="true"]')
                || document.querySelector('[contenteditable="true"]');
    if (!editor) {
      return { ok: false, message: 'ProseMirror editor not found' };
    }

    // ProseMirror expects paragraph nodes, not raw text.
    // Split by double-newline to create paragraphs.
    const paragraphs = text.split(/\\n\\n+/).filter(Boolean);
    const html = paragraphs.map(p => '<p>' + p.replace(/\\n/g, '<br>') + '</p>').join('');

    editor.focus();
    editor.innerHTML = html;

    // Dispatch input events so ProseMirror picks up the change.
    editor.dispatchEvent(new InputEvent('input', {
      bubbles: true,
      inputType: 'insertFromPaste',
      data: text,
    }));
    editor.dispatchEvent(new Event('change', { bubbles: true }));

    // Also try the clipboard approach as a fallback for ProseMirror state sync.
    // ProseMirror sometimes ignores direct innerHTML changes.
    const charCount = (editor.innerText || '').length;
    return {
      ok: charCount > 10,
      charCount,
      method: 'innerHTML_paragraphs',
      paragraphCount: paragraphs.length,
    };
  })())`;
}

/**
 * Alternative: use execCommand-based paste simulation for ProseMirror.
 */
function buildProseMirrorPasteExpression(plainText) {
  return `JSON.stringify((() => {
    const text = ${JSON.stringify(plainText)};
    const editor = document.querySelector('.syl-editor .ProseMirror[contenteditable="true"]')
                || document.querySelector('.ProseMirror[contenteditable="true"]')
                || document.querySelector('[contenteditable="true"]');
    if (!editor) {
      return { ok: false, message: 'ProseMirror editor not found' };
    }

    editor.focus();
    // Clear existing content
    document.execCommand('selectAll', false, null);
    document.execCommand('delete', false, null);

    // Insert text line by line
    const lines = text.split(/\\n/);
    for (let i = 0; i < lines.length; i++) {
      if (i > 0) {
        document.execCommand('insertParagraph', false, null);
      }
      if (lines[i].trim()) {
        document.execCommand('insertText', false, lines[i]);
      }
    }

    const charCount = (editor.innerText || '').length;
    return {
      ok: charCount > 10,
      charCount,
      method: 'execCommand_insertText',
    };
  })())`;
}

// ---------------------------------------------------------------------------
// Button clickers
// ---------------------------------------------------------------------------

function buildClickButtonExpression(buttonTexts) {
  return `JSON.stringify((() => {
    const targets = ${JSON.stringify(buttonTexts)};
    const buttons = Array.from(document.querySelectorAll('button, [role="button"], a, span'));
    let best = null;
    for (const el of buttons) {
      const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
      if (!text) continue;
      let score = -1;
      for (const target of targets) {
        if (!target) continue;
        if (text === target) score = Math.max(score, 20 + target.length);
        else if (text.includes(target)) score = Math.max(score, 8 + target.length);
      }
      if (score < 0) continue;
      const rect = el.getBoundingClientRect ? el.getBoundingClientRect() : { width: 0, height: 0 };
      if (rect.width < 8 || rect.height < 8) continue;
      if (!best || score > best.score) {
        best = { el, score, text };
      }
    }
    if (!best) return { ok: false, matchedText: '' };
    best.el.click();
    return { ok: true, matchedText: best.text, score: best.score };
  })())`;
}

function buildPageStateExpression() {
  return `JSON.stringify((() => ({
    href: location.href,
    title: document.title || '',
    text: (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').trim().substring(0, 500),
    charCount: (() => {
      const editor = document.querySelector('.ProseMirror');
      return editor ? (editor.innerText || '').length : 0;
    })(),
  }))())`;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!WebSocketImpl) {
    throw new Error(
      "toutiao_browser_session_push.js requires Node.js with global WebSocket support.",
    );
  }

  const manifest = JSON.parse(fs.readFileSync(args.manifest, "utf8"));
  const plainText = cleanText(manifest.plain_text) || "";
  const screenshotPath = manifestScreenshotPath(args.manifest);

  if (!plainText) {
    throw new Error("Manifest plain_text is empty — nothing to publish.");
  }

  const publishUrl =
    "https://mp.toutiao.com/profile_v4/weitoutiao/publish";

  // --- Open a fresh CDP tab ---
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
        current.reject(
          new Error(message.error.message || JSON.stringify(message.error)),
        );
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

    // --- Navigate to weitoutiao publish page ---
    await navigateAndSettle(send, publishUrl, args.waitMs);

    // --- Check login state ---
    const pageState = await evaluateJson(send, buildPageStateExpression());
    if (
      /登录|扫码|scan|login/i.test(
        `${pageState.title || ""} ${pageState.text || ""}`,
      )
    ) {
      throw new Error(
        "Toutiao backend does not look logged in. " +
          "Reuse a signed-in browser profile first.",
      );
    }

    // --- Set content in ProseMirror editor ---
    // Try execCommand approach first (better ProseMirror state sync).
    let contentResult = await evaluateJson(
      send,
      buildProseMirrorPasteExpression(manifest.plain_text),
    );

    if (!contentResult.ok) {
      // Fallback to innerHTML approach.
      contentResult = await evaluateJson(
        send,
        buildProseMirrorSetterExpression(manifest.plain_text),
      );
    }

    await sleep(1000);

    // --- Take a pre-publish screenshot ---
    const preScreenshot = await captureScreenshot(send, screenshotPath);

    // --- Click publish or save-draft ---
    let actionResult;
    if (args.draftOnly) {
      actionResult = await evaluateJson(
        send,
        buildClickButtonExpression(["存草稿"]),
      );
    } else {
      actionResult = await evaluateJson(
        send,
        buildClickButtonExpression(["发布"]),
      );
    }

    await sleep(Math.max(3000, args.waitMs));

    // --- Check post-action state ---
    const finalState = await evaluateJson(send, buildPageStateExpression());

    // Try to detect success indicators.
    const successIndicators = ["发布成功", "已发布", "草稿保存成功", "已保存", "保存成功"];
    const finalText = `${finalState.title || ""} ${finalState.text || ""}`;
    const looksSuccessful =
      actionResult.ok &&
      (successIndicators.some((s) => finalText.includes(s)) ||
        finalState.href !== publishUrl ||
        // If editor char count dropped significantly, content was likely submitted.
        (contentResult.charCount > 50 && finalState.charCount < 30));

    const payload = {
      status: looksSuccessful ? "ok" : actionResult.ok ? "uncertain" : "error",
      message: looksSuccessful
        ? args.draftOnly
          ? "Draft saved successfully."
          : "Published successfully."
        : actionResult.ok
          ? "Action was clicked but success confirmation not detected."
          : "Could not find the action button.",
      draft_only: args.draftOnly,
      article_url: finalState.href !== publishUrl ? finalState.href : "",
      screenshot_path: preScreenshot,
      content_result: contentResult,
      action_result: actionResult,
      final_state: {
        href: finalState.href,
        title: finalState.title,
        editor_char_count: finalState.charCount,
      },
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
  const payload = {
    status: "error",
    message:
      cleanText(error && (error.stack || error.message || String(error))) ||
      "toutiao browser-session push failed",
  };
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
  process.exit(1);
});
