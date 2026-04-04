#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const WebSocketImpl = globalThis.WebSocket;

function parseArgs(argv) {
  const result = {
    manifest: "",
    endpoint: "http://127.0.0.1:9222",
    waitMs: 8000,
  };
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index];
    if (value === "--manifest" && index + 1 < argv.length) {
      result.manifest = argv[index + 1];
      index += 1;
    } else if (value === "--endpoint" && index + 1 < argv.length) {
      result.endpoint = argv[index + 1];
      index += 1;
    } else if (value === "--wait-ms" && index + 1 < argv.length) {
      result.waitMs = Number.parseInt(argv[index + 1], 10) || 8000;
      index += 1;
    }
  }
  if (!result.manifest) {
    throw new Error("Usage: wechat_browser_session_push.js --manifest <path> [--endpoint <http://127.0.0.1:9222>] [--wait-ms 8000]");
  }
  return result;
}

function cleanText(value) {
  return String(value || "").replace(/\s+/g, " ").trim();
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

function parseJsonValue(value, fallback = {}) {
  try {
    return JSON.parse(value || "{}");
  } catch {
    return fallback;
  }
}

function manifestScreenshotPath(manifestPath) {
  const parsed = path.parse(manifestPath);
  return path.join(parsed.dir, `${parsed.name}-editor.png`);
}

function buildFieldSetterExpression(payload) {
  return `JSON.stringify((() => {
    const payload = ${JSON.stringify(payload)};
    const keywords = Array.isArray(payload.keywords) ? payload.keywords : [];
    const preferredTags = new Set(Array.isArray(payload.preferredTags) ? payload.preferredTags : []);
    const candidateDocs = [document];
    for (const frame of Array.from(document.querySelectorAll('iframe'))) {
      try {
        if (frame.contentDocument) {
          candidateDocs.push(frame.contentDocument);
        }
      } catch {
        // Ignore cross-origin iframe access failures.
      }
    }

    function scoreElement(doc, element) {
      const own = [
        element.getAttribute?.('placeholder') || '',
        element.getAttribute?.('aria-label') || '',
        element.getAttribute?.('title') || '',
        element.name || '',
        element.id || '',
        element.className || '',
        element.innerText || '',
      ].join(' ');
      const container = element.closest?.('label,section,div,li,td,tr,form') || element.parentElement;
      const nearby = container ? (container.innerText || '') : '';
      const text = (own + ' ' + nearby).replace(/\\s+/g, ' ').trim();
      let score = 0;
      for (const keyword of keywords) {
        if (keyword && text.includes(keyword)) {
          score += 8;
        }
      }
      const tagName = String(element.tagName || '').toLowerCase();
      if (preferredTags.has(tagName)) {
        score += 3;
      }
      if (element.isContentEditable) {
        score += 2;
      }
      if (text.length === 0) {
        score -= 2;
      }
      return { score, text, tagName };
    }

    function setValue(element, value) {
      if (element.isContentEditable) {
        element.focus();
        element.innerHTML = '';
        element.textContent = value;
        element.dispatchEvent(new InputEvent('input', { bubbles: true, data: value, inputType: 'insertText' }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      }
      const tagName = String(element.tagName || '').toLowerCase();
      if (tagName === 'textarea' || tagName === 'input') {
        const descriptor = Object.getOwnPropertyDescriptor(Object.getPrototypeOf(element), 'value');
        if (descriptor && descriptor.set) {
          descriptor.set.call(element, value);
        } else {
          element.value = value;
        }
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      }
      return false;
    }

    let best = null;
    for (const doc of candidateDocs) {
      const elements = Array.from(doc.querySelectorAll('input, textarea, [contenteditable="true"]'));
      for (const element of elements) {
        const info = scoreElement(doc, element);
        if (!best || info.score > best.score) {
          best = { doc, element, score: info.score, text: info.text, tagName: info.tagName };
        }
      }
    }

    if (!best || best.score < 3) {
      return { ok: false, score: best ? best.score : -1, matchedText: best ? best.text : '' };
    }
    const ok = setValue(best.element, payload.value || '');
    return {
      ok,
      score: best.score,
      tagName: best.tagName,
      matchedText: best.text,
    };
  })())`;
}

function buildContentSetterExpression(contentHtml) {
  return `JSON.stringify((() => {
    const html = ${JSON.stringify(contentHtml)};
    const candidateDocs = [document];
    for (const frame of Array.from(document.querySelectorAll('iframe'))) {
      try {
        if (frame.contentDocument) {
          candidateDocs.push(frame.contentDocument);
        }
      } catch {
        // Ignore cross-origin iframe access failures.
      }
    }

    let best = null;
    for (const doc of candidateDocs) {
      const elements = Array.from(doc.querySelectorAll('[contenteditable="true"], .ql-editor, .cke_editable, body'));
      for (const element of elements) {
        const rect = element.getBoundingClientRect ? element.getBoundingClientRect() : { width: 0, height: 0 };
        const area = Math.max(0, Number(rect.width || 0)) * Math.max(0, Number(rect.height || 0));
        const ownText = (element.innerText || '').replace(/\\s+/g, ' ').trim();
        const containerText = ((element.closest?.('section,div,article,main') || element.parentElement)?.innerText || '').replace(/\\s+/g, ' ').trim();
        let score = area;
        if (element.isContentEditable) {
          score += 50000;
        }
        if (/正文|文章|内容/.test(containerText)) {
          score += 30000;
        }
        if (/标题|摘要|作者/.test(containerText)) {
          score -= 12000;
        }
        if (ownText.length > 800) {
          score += 4000;
        }
        if (!best || score > best.score) {
          best = { doc, element, score, containerText };
        }
      }
    }

    if (!best || best.score < 1000) {
      return { ok: false, score: best ? best.score : -1 };
    }

    best.element.focus?.();
    if (String(best.element.tagName || '').toLowerCase() === 'body' || best.element.isContentEditable) {
      best.element.innerHTML = html;
    } else {
      best.element.textContent = '';
      best.element.innerHTML = html;
    }
    best.element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste' }));
    best.element.dispatchEvent(new Event('change', { bubbles: true }));
    return {
      ok: true,
      score: best.score,
      containerText: best.containerText,
      bodyLength: (best.element.innerText || '').length,
    };
  })())`;
}

function buildCoverInputMarkerExpression() {
  return `JSON.stringify((() => {
    for (const item of Array.from(document.querySelectorAll('[data-codex-cover-upload]'))) {
      item.removeAttribute('data-codex-cover-upload');
    }
    const inputs = Array.from(document.querySelectorAll('input[type="file"]'));
    let best = null;
    for (const input of inputs) {
      const container = input.closest('label,section,div,li,form') || input.parentElement;
      const text = ((container && container.innerText) || '').replace(/\\s+/g, ' ').trim();
      let score = 0;
      if (/封面|题图|摘要图/.test(text)) {
        score += 10;
      }
      if (/正文|图片|插图/.test(text)) {
        score -= 3;
      }
      if (!best || score > best.score) {
        best = { input, score, text };
      }
    }
    if (!best || best.score < 1) {
      return { ok: false, score: best ? best.score : -1, matchedText: best ? best.text : '' };
    }
    best.input.setAttribute('data-codex-cover-upload', '1');
    return { ok: true, score: best.score, matchedText: best.text };
  })())`;
}

function buildClickByTextExpression(texts) {
  return `JSON.stringify((() => {
    const targets = ${JSON.stringify(texts || [])};
    const elements = Array.from(document.querySelectorAll('button, [role="button"], a, span, div'));
    let best = null;
    for (const element of elements) {
      const text = (element.innerText || element.textContent || '').replace(/\\s+/g, ' ').trim();
      if (!text) {
        continue;
      }
      let score = -1;
      for (const target of targets) {
        if (!target) {
          continue;
        }
        if (text === target) {
          score = Math.max(score, 20 + target.length);
        } else if (text.includes(target)) {
          score = Math.max(score, 8 + target.length);
        }
      }
      if (score < 0) {
        continue;
      }
      const rect = element.getBoundingClientRect ? element.getBoundingClientRect() : { width: 0, height: 0 };
      if (rect.width < 8 || rect.height < 8) {
        continue;
      }
      if (!best || score > best.score) {
        best = { element, score, text };
      }
    }
    if (!best) {
      return { ok: false, matchedText: '' };
    }
    best.element.click();
    return { ok: true, matchedText: best.text };
  })())`;
}

async function navigateAndSettle(send, url, waitMs) {
  await send("Page.navigate", { url });
  await sleep(Math.max(1500, waitMs));
}

async function evaluateJson(send, expression) {
  const result = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  return parseJsonValue(result?.result?.value, {});
}

async function markCoverInput(send) {
  return evaluateJson(send, buildCoverInputMarkerExpression());
}

async function setCoverFile(send, coverPath) {
  const documentNode = await send("DOM.getDocument", { depth: -1, pierce: true });
  const nodeId = await send("DOM.querySelector", {
    nodeId: documentNode.root.nodeId,
    selector: 'input[data-codex-cover-upload="1"]',
  });
  if (!nodeId?.nodeId) {
    return { ok: false, message: "cover file input was not found" };
  }
  await send("DOM.setFileInputFiles", {
    nodeId: nodeId.nodeId,
    files: [coverPath],
  });
  await send("Runtime.evaluate", {
    expression: `(() => {
      const input = document.querySelector('input[data-codex-cover-upload="1"]');
      if (!input) return false;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })()`,
    returnByValue: true,
  });
  return { ok: true };
}

async function waitForAnyText(send, patterns, waitMs) {
  const deadline = Date.now() + Math.max(2500, waitMs);
  while (Date.now() < deadline) {
    const state = await evaluateJson(
      send,
      `JSON.stringify((() => {
        const text = (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').trim();
        return { text, href: location.href, title: document.title || '' };
      })())`,
    );
    const joined = `${state.title || ''} ${state.text || ''} ${state.href || ''}`;
    if ((patterns || []).some((pattern) => pattern && joined.includes(pattern))) {
      return { ok: true, matched: joined };
    }
    await sleep(700);
  }
  return { ok: false, matched: "" };
}

function extractToken(url) {
  const match = String(url || "").match(/[?&]token=(\d+)/);
  return match ? match[1] : "";
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

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (!WebSocketImpl) {
    throw new Error("wechat_browser_session_push.js requires a Node.js runtime with global WebSocket support.");
  }

  const manifest = JSON.parse(fs.readFileSync(args.manifest, "utf8"));
  const article = manifest.article || {};
  const browserSession = manifest.browser_session || {};
  const homeUrl = cleanText(browserSession.home_url) || "https://mp.weixin.qq.com/";
  const editorUrlFromManifest = cleanText(browserSession.editor_url);
  const screenshotPath = manifestScreenshotPath(args.manifest);

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
    await send("DOM.enable");

    await navigateAndSettle(send, homeUrl, args.waitMs);
    const homeState = await evaluateJson(
      send,
      `JSON.stringify((() => ({ href: location.href, title: document.title || '', text: (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').trim() }))())`,
    );
    if (/登录|扫码|scan|login/i.test(`${homeState.title || ""} ${homeState.text || ""}`)) {
      throw new Error("The WeChat Official Account backend does not look logged in. Reuse a signed-in browser profile first.");
    }

    let editorUrl = editorUrlFromManifest;
    if (!editorUrl) {
      const createResult = await evaluateJson(
        send,
        buildClickByTextExpression(["新建图文消息", "图文消息", "写新图文", "写文章"]),
      );
      if (createResult.ok) {
        await sleep(Math.max(2500, args.waitMs));
        const stateAfterClick = await evaluateJson(
          send,
          `JSON.stringify((() => ({ href: location.href, title: document.title || '' }))())`,
        );
        editorUrl = cleanText(stateAfterClick.href);
      }
    }

    if (editorUrl) {
      await navigateAndSettle(send, editorUrl, args.waitMs);
    }

    const editorState = await evaluateJson(
      send,
      `JSON.stringify((() => ({ href: location.href, title: document.title || '', text: (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').trim() }))())`,
    );
    const token = extractToken(editorState.href) || extractToken(editorUrl) || extractToken(homeState.href);

    const titleResult = await evaluateJson(
      send,
      buildFieldSetterExpression({
        keywords: ["标题", "请在这里输入标题", "文章标题"],
        preferredTags: ["textarea", "input"],
        value: cleanText(article.title),
      }),
    );
    const authorResult = await evaluateJson(
      send,
      buildFieldSetterExpression({
        keywords: ["作者"],
        preferredTags: ["input", "textarea"],
        value: cleanText(article.author),
      }),
    );
    const digestResult = await evaluateJson(
      send,
      buildFieldSetterExpression({
        keywords: ["摘要", "选填", "描述"],
        preferredTags: ["textarea", "input"],
        value: cleanText(article.digest),
      }),
    );
    const contentResult = await evaluateJson(send, buildContentSetterExpression(String(article.content_html || "")));

    const coverMarker = await markCoverInput(send);
    let coverUploadResult = { ok: false, message: "cover file input not found" };
    if (coverMarker.ok && cleanText(manifest.cover_image_path)) {
      coverUploadResult = await setCoverFile(send, cleanText(manifest.cover_image_path));
      await sleep(Math.max(1500, args.waitMs));
    }

    const saveClickResult = await evaluateJson(
      send,
      buildClickByTextExpression(["保存为草稿", "保存草稿", "保存"]),
    );
    const saveState = await waitForAnyText(send, ["保存成功", "草稿", "已保存"], Math.max(4000, args.waitMs + 3000));
    const finalState = await evaluateJson(
      send,
      `JSON.stringify((() => ({ href: location.href, title: document.title || '', text: (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').trim() }))())`,
    );
    const screenshot = await captureScreenshot(send, screenshotPath);

    const payload = {
      status: saveClickResult.ok ? "ok" : "saved",
      message: saveState.ok ? "Browser-session draft save flow completed." : "Browser-session draft flow reached the editor, but save confirmation was not strongly detected.",
      editor_url: cleanText(editorUrl) || cleanText(editorState.href),
      final_url: cleanText(finalState.href) || cleanText(editorState.href),
      draft_url: cleanText(finalState.href) || cleanText(editorState.href),
      draft_media_id: "",
      cover_media_id: "",
      detected_token: token,
      screenshot_path: screenshot,
      session_note: `attached to ${args.endpoint}`,
      title_result: titleResult,
      author_result: authorResult,
      digest_result: digestResult,
      content_result: contentResult,
      cover_upload_result: coverUploadResult,
      save_click_result: saveClickResult,
      save_state: saveState,
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
    message: cleanText(error && (error.stack || error.message || String(error))) || "browser-session push failed",
  };
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
  process.exit(1);
});
