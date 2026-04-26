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

async function openTarget(endpoint, initialUrl = "about:blank") {
  const encodedUrl = encodeURIComponent(cleanText(initialUrl) || "about:blank");
  const targetUrl = joinUrl(endpoint, `/json/new?${encodedUrl}`);
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

function extractToken(url) {
  const match = String(url || "").match(/[?&]token=(\d+)/);
  return match ? match[1] : "";
}

function isWechatBackendTarget(tab) {
  if (!tab || tab.type !== "page") {
    return false;
  }
  const url = cleanText(tab.url);
  if (!url.includes("mp.weixin.qq.com")) {
    return false;
  }
  return !/\/s\//.test(url);
}

function shouldNavigateExistingTarget(targetUrl, editorUrl, homeUrl) {
  const cleanTargetUrl = cleanText(targetUrl);
  const cleanEditorUrl = cleanText(editorUrl);
  if (
    cleanEditorUrl &&
    /cgi-bin\/appmsg/i.test(cleanTargetUrl) &&
    /(?:[?&](?:appmsgid|timestamp|reprint_confirm)=)/i.test(cleanTargetUrl)
  ) {
    return true;
  }
  if (!cleanEditorUrl) {
    return !/cgi-bin\/appmsg/i.test(cleanTargetUrl) && Boolean(cleanText(homeUrl));
  }
  const targetToken = extractToken(cleanTargetUrl);
  const desiredToken = extractToken(cleanEditorUrl) || extractToken(homeUrl);
  if (/cgi-bin\/appmsg/i.test(cleanTargetUrl)) {
    if (!desiredToken) {
      return false;
    }
    if (targetToken && targetToken === desiredToken) {
      return false;
    }
  }
  return cleanTargetUrl !== cleanEditorUrl;
}

function chooseWechatTarget(tabs, options = {}) {
  const editorUrl = cleanText(options.editorUrl);
  const homeUrl = cleanText(options.homeUrl);
  const desiredToken = extractToken(editorUrl) || extractToken(homeUrl);
  let best = null;
  for (const tab of Array.isArray(tabs) ? tabs : []) {
    if (!isWechatBackendTarget(tab)) {
      continue;
    }
    const url = cleanText(tab.url);
    const title = cleanText(tab.title);
    const token = extractToken(url);
    let score = 0;
    const reasons = [];
    if (/cgi-bin\/appmsg/i.test(url)) {
      score += 140;
      reasons.push("editor");
    } else if (/cgi-bin\/home/i.test(url)) {
      score += 90;
      reasons.push("home");
    } else {
      score += 45;
      reasons.push("backend");
    }
    if (/appmsgid=/.test(url)) {
      score += 30;
      reasons.push("draft");
    }
    if (desiredToken && token === desiredToken) {
      score += 45;
      reasons.push("token-match");
    } else if (token) {
      score += 10;
      reasons.push("token");
    }
    if (/公众号/.test(title)) {
      score += 8;
      reasons.push("title");
    }
    if (/login|scan|qrcode/i.test(`${title} ${url}`)) {
      score -= 100;
    }
    if (!best || score > best.score) {
      best = { target: tab, score, reasons };
    }
  }
  if (!best) {
    return {
      target: null,
      reusedExisting: false,
      shouldNavigate: false,
      navigateUrl: "",
      shouldClose: false,
      matchedBy: "",
    };
  }
  const shouldNavigate = shouldNavigateExistingTarget(
    best.target.url,
    editorUrl,
    homeUrl,
  );
  const navigateUrl = shouldNavigate ? editorUrl || homeUrl : "";
  return {
    target: best.target,
    reusedExisting: true,
    shouldNavigate,
    navigateUrl,
    shouldClose: false,
    matchedBy: best.reasons.join(","),
  };
}

async function attachWechatTarget(endpoint, options = {}) {
  const tabs = await fetchJson(joinUrl(endpoint, "/json"));
  const selected = chooseWechatTarget(tabs, options);
  if (selected.target) {
    return {
      ...selected,
      openedNew: false,
      sessionNote: `reused ${selected.target.id}`,
    };
  }
  const initialUrl =
    cleanText(options.editorUrl) ||
    cleanText(options.homeUrl) ||
    "https://mp.weixin.qq.com/";
  const target = await openTarget(endpoint, initialUrl);
  return {
    target,
    reusedExisting: false,
    shouldNavigate: false,
    navigateUrl: "",
    shouldClose: false,
    openedNew: true,
    matchedBy: "new-target",
    sessionNote: `opened ${initialUrl}`,
  };
}

function buildPageStateExpression() {
  return `JSON.stringify((() => ({
    href: location.href,
    title: document.title || '',
    text: (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ').trim(),
  }))())`;
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

    function scoreElement(element) {
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
      if (text.length === 0) {
        score -= 2;
      }
      return { score, text, tagName };
    }

    function setValue(element, value) {
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
      if (element.isContentEditable) {
        element.focus();
        element.textContent = '';
        element.appendChild(element.ownerDocument.createTextNode(value));
        try {
          element.dispatchEvent(new InputEvent('input', { bubbles: true, data: value, inputType: 'insertText' }));
        } catch {
          element.dispatchEvent(new Event('input', { bubbles: true }));
        }
        element.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      }
      return false;
    }

    let best = null;
    for (const doc of candidateDocs) {
      const elements = Array.from(doc.querySelectorAll('input, textarea, [contenteditable="true"]'));
      for (const element of elements) {
        const info = scoreElement(element);
        if (!best || info.score > best.score) {
          best = { element, score: info.score, text: info.text, tagName: info.tagName };
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

    function visible(element) {
      if (!element || !element.getBoundingClientRect) {
        return false;
      }
      const rect = element.getBoundingClientRect();
      return rect.width > 40 && rect.height > 40;
    }

    function scoreEditable(doc, element) {
      const rect = element.getBoundingClientRect ? element.getBoundingClientRect() : { width: 0, height: 0 };
      const area = Math.max(0, Number(rect.width || 0)) * Math.max(0, Number(rect.height || 0));
      const selectorHints = [
        element.id ? ('#' + element.id) : '',
        element.className || '',
        element.getAttribute?.('data-testid') || '',
      ].join(' ');
      const containerText = ((element.closest?.('section,div,article,main') || element.parentElement)?.innerText || '').replace(/\\s+/g, ' ').trim();
      let score = area;
      if (/ProseMirror/.test(selectorHints)) {
        score += 90000;
      }
      if (element.isContentEditable) {
        score += 40000;
      }
      if (/正文|文章|内容/.test(containerText)) {
        score += 20000;
      }
      if (/标题|摘要|作者/.test(containerText)) {
        score -= 15000;
      }
      if (/original_primary_tips_input/.test(selectorHints)) {
        score -= 50000;
      }
      return {
        score,
        selector: selectorHints.trim(),
        containerText: containerText.slice(0, 240),
      };
    }

    let best = null;
    for (const doc of candidateDocs) {
      const preferred = [
        ...Array.from(doc.querySelectorAll('.ProseMirror[contenteditable="true"]')),
        ...Array.from(doc.querySelectorAll('.ql-editor[contenteditable="true"]')),
        ...Array.from(doc.querySelectorAll('.cke_editable[contenteditable="true"]')),
        ...Array.from(doc.querySelectorAll('[contenteditable="true"]')),
        ...(doc.body && doc.body.isContentEditable ? [doc.body] : []),
      ];
      for (const element of preferred) {
        if (!visible(element)) {
          continue;
        }
        const info = scoreEditable(doc, element);
        if (!best || info.score > best.score) {
          best = { doc, element, score: info.score, selector: info.selector, containerText: info.containerText };
        }
      }
    }

    if (!best || best.score < 1000) {
      return { ok: false, score: best ? best.score : -1, message: 'editor not found' };
    }

    const doc = best.doc;
    const element = best.element;
    const win = doc.defaultView || window;
    const selection = (win.getSelection && win.getSelection()) || (doc.getSelection && doc.getSelection());

    element.focus?.();

    const clearRange = doc.createRange();
    clearRange.selectNodeContents(element);
    if (selection && selection.removeAllRanges) {
      selection.removeAllRanges();
      selection.addRange(clearRange);
    }

    try {
      element.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, inputType: 'deleteByCut', data: null }));
    } catch {
      element.dispatchEvent(new Event('beforeinput', { bubbles: true }));
    }

    let usedExecCommand = false;
    if (typeof doc.execCommand === 'function') {
      try {
        doc.execCommand('delete', false, null);
      } catch {
        // Ignore execCommand delete failures.
      }
      try {
        usedExecCommand = !!doc.execCommand('insertHTML', false, html);
      } catch {
        usedExecCommand = false;
      }
    }

    if (!usedExecCommand) {
      element.replaceChildren();
      const insertRange = doc.createRange();
      insertRange.selectNodeContents(element);
      insertRange.collapse(true);
      const fragment = insertRange.createContextualFragment(html);
      insertRange.insertNode(fragment);
    }

    if (selection && selection.removeAllRanges) {
      const endRange = doc.createRange();
      endRange.selectNodeContents(element);
      endRange.collapse(false);
      selection.removeAllRanges();
      selection.addRange(endRange);
    }

    try {
      element.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste', data: null }));
    } catch {
      element.dispatchEvent(new Event('input', { bubbles: true }));
    }
    element.dispatchEvent(new Event('change', { bubbles: true }));

    return {
      ok: true,
      score: best.score,
      selector: best.selector,
      containerText: best.containerText,
      bodyLength: (element.innerText || '').length,
      method: usedExecCommand ? 'execCommand_insertHTML' : 'fragment_insert',
    };
  })())`;
}

function buildButtonClickExpression(texts, options = {}) {
  const preferSendWording = Boolean(options.preferSendWording);
  return `JSON.stringify((() => {
    const targets = ${JSON.stringify(texts || [])};
    const preferSendWording = ${preferSendWording ? "true" : "false"};
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

    function visible(element) {
      if (!element || !element.getBoundingClientRect) {
        return false;
      }
      const rect = element.getBoundingClientRect();
      const style = element.ownerDocument?.defaultView?.getComputedStyle
        ? element.ownerDocument.defaultView.getComputedStyle(element)
        : null;
      return rect.width >= 8 && rect.height >= 8 && (!style || (style.display !== 'none' && style.visibility !== 'hidden'));
    }

    function normalizedText(element) {
      return (element?.innerText || element?.textContent || '').replace(/\\s+/g, ' ').trim();
    }

    let best = null;
    for (const doc of candidateDocs) {
      const seen = new Set();
      const candidates = [];
      if (preferSendWording) {
        for (const wording of Array.from(doc.querySelectorAll('.send_wording'))) {
          candidates.push({
            clickTarget: wording.closest('button') || wording,
            text: normalizedText(wording) || normalizedText(wording.closest('button') || wording),
            viaSendWording: true,
          });
        }
      }
      for (const element of Array.from(doc.querySelectorAll('button, [role="button"], a, span, div'))) {
        const clickTarget = element.matches?.('span, div')
          ? (element.closest('button, [role="button"], a') || element)
          : element;
        candidates.push({
          clickTarget,
          text: normalizedText(element) || normalizedText(clickTarget),
          viaSendWording: false,
        });
      }
      for (const candidate of candidates) {
        const clickTarget = candidate.clickTarget;
        if (!clickTarget || seen.has(clickTarget) || !visible(clickTarget)) {
          continue;
        }
        seen.add(clickTarget);
        const text = candidate.text;
        if (!text) {
          continue;
        }
        let score = -1;
        for (const target of targets) {
          if (!target) {
            continue;
          }
          if (text === target) {
            score = Math.max(score, 30 + target.length);
          } else if (text.includes(target)) {
            score = Math.max(score, 15 + target.length);
          }
        }
        if (score < 0) {
          continue;
        }
        if (candidate.viaSendWording) {
          score += 25;
        }
        if (String(clickTarget.tagName || '').toLowerCase() === 'button') {
          score += 10;
        }
        if (!best || score > best.score) {
          best = {
            clickTarget,
            text,
            score,
            viaSendWording: candidate.viaSendWording,
          };
        }
      }
    }
    if (!best) {
      return { ok: false, matchedText: '' };
    }
    best.clickTarget.click();
    return {
      ok: true,
      matchedText: best.text,
      score: best.score,
      viaSendWording: best.viaSendWording,
    };
  })())`;
}

function buildClickByTextExpression(texts) {
  return buildButtonClickExpression(texts, { preferSendWording: false });
}

function buildSaveDraftClickExpression() {
  return buildButtonClickExpression(
    ["保存为草稿", "保存草稿", "保存"],
    { preferSendWording: true },
  );
}

function buildCoverDialogResetExpression() {
  return `JSON.stringify((() => {
    const dialog = document.querySelector('.weui-desktop-dialog_img-picker, .weui-desktop-dialog__wrp.weui-desktop-dialog_img-picker');
    if (!dialog) {
      return { ok: true, reset: false };
    }
    const resetButton = Array.from(dialog.querySelectorAll('button, a, .weui-desktop-btn')).find((element) => {
      const text = (element.innerText || element.textContent || '').replace(/\\s+/g, ' ').trim();
      const rect = element.getBoundingClientRect ? element.getBoundingClientRect() : { width: 0, height: 0 };
      return ['取消', '关闭'].includes(text) && rect.width >= 8 && rect.height >= 8;
    });
    resetButton?.click?.();
    return {
      ok: true,
      reset: Boolean(resetButton),
      dialogSelector: '.weui-desktop-dialog_img-picker',
    };
  })())`;
}

function buildCoverPickerPreparationExpression() {
  return `JSON.stringify((() => {
    const coverArea = document.querySelector('#js_cover_area')
      || document.querySelector('#js_cover_description_area .js_cover_btn_area')
      || document.querySelector('.setting-group__cover_primary .js_cover_btn_area');
    coverArea?.click?.();
    const imageDialogButton = document.querySelector('#js_cover_null .js_imagedialog')
      || document.querySelector('#js_cover_area .js_imagedialog')
      || document.querySelector('.js_cover_opr .js_imagedialog');
    if (!imageDialogButton) {
      return {
        ok: false,
        step: 'cover-picker-button-not-found',
        coverSelector: coverArea ? '#js_cover_area' : '',
      };
    }
    imageDialogButton.click();
    return {
      ok: true,
      step: 'cover-picker-opened',
      coverSelector: '#js_cover_area',
      dialogSelector: '.weui-desktop-dialog_img-picker',
      buttonSelector: '#js_cover_null .js_imagedialog',
      inputSelector: '.weui-desktop-dialog_img-picker .js_upload_btn_container input[type="file"]',
    };
  })())`;
}

function buildCoverDialogInputMarkerExpression() {
  return `JSON.stringify((() => {
    for (const item of Array.from(document.querySelectorAll('[data-codex-cover-upload]'))) {
      item.removeAttribute('data-codex-cover-upload');
    }
    const dialog = document.querySelector('.weui-desktop-dialog_img-picker, .weui-desktop-dialog__wrp.weui-desktop-dialog_img-picker');
    if (!dialog) {
      return { ok: false, step: 'dialog-not-found' };
    }
    const input = dialog.querySelector('.js_upload_btn_container input[type="file"]')
      || dialog.querySelector('.weui-desktop-upload_global-media input[type="file"]')
      || dialog.querySelector('input[type="file"][accept*="image"]');
    if (!input) {
      return { ok: false, step: 'input-not-found' };
    }
    input.setAttribute('data-codex-cover-upload', '1');
    return {
      ok: true,
      step: 'input-marked',
      accept: input.getAttribute('accept') || '',
    };
  })())`;
}

function buildCoverDialogStateExpression() {
  return `JSON.stringify((() => {
    const dialog = document.querySelector('.weui-desktop-dialog_img-picker, .weui-desktop-dialog__wrp.weui-desktop-dialog_img-picker');
    const coverArea = document.querySelector('#js_cover_area');
    const preview = coverArea
      ? (coverArea.querySelector('.js_cover_preview_new') || coverArea.querySelector('.js_cover_preview_square'))
      : null;
    const placeholderText = coverArea ? (coverArea.innerText || '').replace(/\\s+/g, ' ').trim() : '';
    const previewStyle = preview
      ? ((preview.style && preview.style.backgroundImage) || (preview.ownerDocument?.defaultView?.getComputedStyle(preview)?.backgroundImage || ''))
      : '';
    const previewRect = preview && preview.getBoundingClientRect ? preview.getBoundingClientRect() : { width: 0, height: 0 };
    const hasPreviewImage = Boolean(previewStyle)
      && previewStyle !== 'none'
      && previewStyle !== 'url("")'
      && previewStyle !== "url('')";
    const buttons = dialog
      ? Array.from(dialog.querySelectorAll('button, a, .weui-desktop-btn')).map((element) => ({
          text: (element.innerText || element.textContent || '').replace(/\\s+/g, ' ').trim(),
          cls: String(element.className || ''),
          w: element.getBoundingClientRect ? element.getBoundingClientRect().width : 0,
          h: element.getBoundingClientRect ? element.getBoundingClientRect().height : 0,
        }))
      : [];
    const enabledButtons = buttons.filter((item) => item.text && item.w >= 8 && item.h >= 8 && !/disabled/.test(item.cls));
    const nextAction = enabledButtons.find((item) => ['下一步', '完成', '确定'].includes(item.text));
    return {
      dialogOpen: Boolean(dialog),
      coverReady: Boolean(preview && previewRect.width > 8 && previewRect.height > 8 && hasPreviewImage)
        || Boolean(coverArea && !placeholderText.includes('拖拽或选择封面') && !placeholderText.includes('选择封面') && !placeholderText.includes('请勿上传空文件')),
      nextActionText: nextAction ? nextAction.text : '',
      buttons: enabledButtons,
      placeholderText,
      previewStyle,
    };
  })())`;
}

function buildCoverDialogAdvanceExpression(actionText) {
  return `JSON.stringify((() => {
    const dialog = document.querySelector('.weui-desktop-dialog_img-picker, .weui-desktop-dialog__wrp.weui-desktop-dialog_img-picker');
    if (!dialog) {
      return { ok: false, step: 'dialog-not-found', actionText: ${JSON.stringify(actionText)} };
    }
    const target = Array.from(dialog.querySelectorAll('button, a, .weui-desktop-btn')).find((element) => {
      const text = (element.innerText || element.textContent || '').replace(/\\s+/g, ' ').trim();
      const rect = element.getBoundingClientRect ? element.getBoundingClientRect() : { width: 0, height: 0 };
      return text === ${JSON.stringify(actionText)} && rect.width >= 8 && rect.height >= 8 && !/disabled/.test(String(element.className || ''));
    });
    if (!target) {
      return { ok: false, step: 'action-not-found', actionText: ${JSON.stringify(actionText)} };
    }
    target.click();
    return {
      ok: true,
      matchedText: (target.innerText || target.textContent || '').replace(/\\s+/g, ' ').trim(),
      cls: String(target.className || ''),
    };
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

async function markCoverDialogInput(send) {
  return evaluateJson(send, buildCoverDialogInputMarkerExpression());
}

async function setCoverFile(send, coverPath) {
  const documentNode = await send("DOM.getDocument", { depth: -1, pierce: true });
  const nodeId = await send("DOM.querySelector", {
    nodeId: documentNode.root.nodeId,
    selector: 'input[data-codex-cover-upload="1"]',
  });
  if (!nodeId?.nodeId) {
    return { ok: false, message: "cover dialog file input was not found" };
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

async function finalizeCoverSelection(send, waitMs) {
  const actions = [];
  const deadline = Date.now() + Math.max(15000, waitMs + 12000);
  while (Date.now() < deadline) {
    const state = await evaluateJson(send, buildCoverDialogStateExpression());
    if (state.coverReady) {
      return { ok: true, actions, state };
    }
    if (!state.dialogOpen && actions.length === 0) {
      return { ok: false, actions, state, message: "cover dialog did not open" };
    }
    if (!state.dialogOpen) {
      return {
        ok: Boolean(state.coverReady),
        actions,
        state,
        message: state.coverReady ? "" : "cover dialog closed before preview updated",
      };
    }
    if (state.nextActionText) {
      const clickResult = await evaluateJson(
        send,
        buildCoverDialogAdvanceExpression(state.nextActionText),
      );
      if (clickResult.ok) {
        actions.push(clickResult.matchedText);
        await sleep(1200);
        continue;
      }
    }
    await sleep(800);
  }
  const lastState = await evaluateJson(send, buildCoverDialogStateExpression());
  return {
    ok: false,
    actions,
    state: lastState,
    message: "cover upload confirmation timed out",
  };
}

async function waitForAnyText(send, patterns, waitMs) {
  const deadline = Date.now() + Math.max(2500, waitMs);
  while (Date.now() < deadline) {
    const state = await evaluateJson(send, buildPageStateExpression());
    const joined = `${state.title || ""} ${state.text || ""} ${state.href || ""}`;
    if ((patterns || []).some((pattern) => pattern && joined.includes(pattern))) {
      return { ok: true, matched: joined };
    }
    await sleep(700);
  }
  return { ok: false, matched: "" };
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

  const targetContext = await attachWechatTarget(args.endpoint, {
    editorUrl: editorUrlFromManifest,
    homeUrl,
  });
  const ws = new WebSocketImpl(targetContext.target.webSocketDebuggerUrl);
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

    if (targetContext.shouldNavigate && targetContext.navigateUrl) {
      await navigateAndSettle(send, targetContext.navigateUrl, args.waitMs);
    }

    let pageState = await evaluateJson(send, buildPageStateExpression());
    if (/登录|扫码|scan|login/i.test(`${pageState.title || ""} ${pageState.text || ""}`)) {
      throw new Error("The WeChat Official Account backend does not look logged in. Reuse a signed-in browser profile first.");
    }

    let editorUrl = editorUrlFromManifest;
    let createResult = { ok: false, matchedText: "" };
    if (!/cgi-bin\/appmsg/i.test(cleanText(pageState.href))) {
      if (editorUrl) {
        await navigateAndSettle(send, editorUrl, args.waitMs);
      } else {
        createResult = await evaluateJson(
          send,
          buildClickByTextExpression(["新建图文消息", "图文消息", "写新图文", "写文章"]),
        );
        if (createResult.ok) {
          await sleep(Math.max(2500, args.waitMs));
        }
      }
      pageState = await evaluateJson(send, buildPageStateExpression());
      if (!editorUrl) {
        editorUrl = cleanText(pageState.href);
      }
    }

    const editorState = await evaluateJson(send, buildPageStateExpression());
    const token =
      extractToken(editorState.href) ||
      extractToken(editorUrl) ||
      extractToken(pageState.href);

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
    const contentResult = await evaluateJson(
      send,
      buildContentSetterExpression(String(article.content_html || "")),
    );

    let coverUploadResult = { ok: false, message: "cover image path missing" };
    if (cleanText(manifest.cover_image_path)) {
      const dialogReset = await evaluateJson(
        send,
        buildCoverDialogResetExpression(),
      );
      if (dialogReset.reset) {
        await sleep(350);
      }
      const pickerPreparation = await evaluateJson(
        send,
        buildCoverPickerPreparationExpression(),
      );
      if (pickerPreparation.ok) {
        await sleep(Math.max(1000, Math.floor(args.waitMs / 3)));
        const inputMarker = await markCoverDialogInput(send);
        if (inputMarker.ok) {
          const fileResult = await setCoverFile(send, cleanText(manifest.cover_image_path));
          await sleep(Math.max(1200, Math.floor(args.waitMs / 2)));
          const finalizeResult = await finalizeCoverSelection(send, args.waitMs);
          coverUploadResult = {
            ok: Boolean(fileResult.ok && finalizeResult.ok),
            picker_preparation: pickerPreparation,
            input_marker: inputMarker,
            file_result: fileResult,
            finalize_result: finalizeResult,
            message: finalizeResult.message || "",
          };
        } else {
          coverUploadResult = {
            ok: false,
            picker_preparation: pickerPreparation,
            input_marker: inputMarker,
            message: "cover dialog file input not found",
          };
        }
      } else {
        coverUploadResult = {
          ok: false,
          picker_preparation: pickerPreparation,
          message: "cover picker could not be opened",
        };
      }
    }

    const saveClickResult = await evaluateJson(
      send,
      buildSaveDraftClickExpression(),
    );
    const saveState = await waitForAnyText(
      send,
      ["保存成功", "草稿", "已保存", "手动保存"],
      Math.max(4000, args.waitMs + 3000),
    );
    const finalState = await evaluateJson(send, buildPageStateExpression());
    const screenshot = await captureScreenshot(send, screenshotPath);

    const payload = {
      status: saveClickResult.ok ? "ok" : "saved",
      message: saveState.ok
        ? "Browser-session draft save flow completed."
        : "Browser-session draft flow reached the editor, but save confirmation was not strongly detected.",
      editor_url: cleanText(editorUrl) || cleanText(editorState.href),
      final_url: cleanText(finalState.href) || cleanText(editorState.href),
      draft_url: cleanText(finalState.href) || cleanText(editorState.href),
      draft_media_id: "",
      cover_media_id: "",
      detected_token: token,
      screenshot_path: screenshot,
      session_note: `${targetContext.sessionNote} via ${args.endpoint}`,
      target_selection: {
        reused_existing: targetContext.reusedExisting,
        matched_by: targetContext.matchedBy,
        opened_new: targetContext.openedNew,
      },
      create_result: createResult,
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
    if (targetContext.shouldClose) {
      await closeTarget(args.endpoint, targetContext.target.id);
    }
  }
}

module.exports = {
  parseArgs,
  cleanText,
  extractToken,
  chooseWechatTarget,
  buildContentSetterExpression,
  buildCoverPickerPreparationExpression,
  buildSaveDraftClickExpression,
};

if (require.main === module) {
  main().catch((error) => {
    const payload = {
      status: "error",
      message: cleanText(error && (error.stack || error.message || String(error))) || "browser-session push failed",
    };
    process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
    process.exit(1);
  });
}
