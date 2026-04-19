#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");
const WebSocketImpl = globalThis.WebSocket;

function cleanText(value) {
  return String(value ?? "").replace(/\u200b/g, " ").replace(/\s+/g, " ").trim();
}

function escapeHtml(text) {
  return String(text ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
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

function renderInlineImageBlock(image) {
  const src = cleanText(image?.src);
  if (!src) return "";
  const caption = cleanText(image?.caption);
  return [
    `<figure data-role="toutiao-inline-image" style="margin:28px 0 24px;">`,
    `<img src="${escapeHtml(src)}" alt="${escapeHtml(caption || "article image")}" style="display:block;max-width:100%;width:100%;border-radius:6px;" />`,
    caption
      ? `<figcaption style="margin-top:10px;font-size:14px;line-height:1.6;color:#6b7280;text-align:center;">${escapeHtml(caption)}</figcaption>`
      : "",
    `</figure>`,
  ].join("");
}

function normalizeMarkdown(markdown) {
  const text = String(markdown ?? "").replace(/\r\n/g, "\n").trim();
  if (!text) return "";
  const blocks = text.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  if (blocks.length && /^#\s+/.test(blocks[0])) {
    blocks.shift();
  }
  return blocks.join("\n\n");
}

function buildToutiaoBodyHtml(markdown, inlineImages = []) {
  const normalized = normalizeMarkdown(markdown);
  const blocks = normalized.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean);
  const afterLedeImages = inlineImages.filter((item) => cleanText(item?.placement) === "after_lede");
  const otherImages = inlineImages.filter((item) => cleanText(item?.placement) !== "after_lede");
  const html = [];
  let insertedAfterLede = false;

  for (const block of blocks) {
    if (block === "---") continue;
    const h2 = block.match(/^##\s+(.+)$/);
    if (h2) {
      html.push(renderToutiaoSectionHeading(h2[1], 2));
      continue;
    }
    const h3 = block.match(/^###\s+(.+)$/);
    if (h3) {
      html.push(renderToutiaoSectionHeading(h3[1], 3));
      continue;
    }
    const paragraph = escapeHtml(block).replace(/\n/g, "<br>");
    html.push(`<p style="margin:0 0 22px;line-height:1.9;font-size:18px;color:#1f2329;">${paragraph}</p>`);
    if (!insertedAfterLede && afterLedeImages.length) {
      html.push(...afterLedeImages.map(renderInlineImageBlock).filter(Boolean));
      insertedAfterLede = true;
    }
  }

  if (!insertedAfterLede && afterLedeImages.length) {
    html.push(...afterLedeImages.map(renderInlineImageBlock).filter(Boolean));
  }
  if (otherImages.length) {
    html.push(...otherImages.map(renderInlineImageBlock).filter(Boolean));
  }

  return html.join("\n");
}

function parseArgs(argv) {
  const args = {
    manifest: "",
    output: "",
    endpoint: "http://127.0.0.1:9222",
    waitMs: 10000,
    prepareOnly: false,
  };
  for (let index = 2; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--manifest") args.manifest = argv[index + 1] || "";
    else if (token === "--output") args.output = argv[index + 1] || "";
    else if (token === "--endpoint") args.endpoint = argv[index + 1] || args.endpoint;
    else if (token === "--wait-ms") args.waitMs = Number.parseInt(argv[index + 1] || "", 10) || args.waitMs;
    else if (token === "--prepare-only") args.prepareOnly = true;
  }
  if (!args.manifest) {
    throw new Error("Missing required --manifest argument.");
  }
  args.output = args.output || path.join(path.dirname(args.manifest), "result.json");
  return args;
}

function parseJsonValue(value) {
  try {
    return JSON.parse(value || "{}");
  } catch {
    return {};
  }
}

function writeOutput(outputPath, payload) {
  fs.writeFileSync(outputPath, JSON.stringify(payload, null, 2), "utf8");
  process.stdout.write(JSON.stringify(payload));
}

async function fetchJson(url, opts = {}) {
  const response = await fetch(url, opts);
  if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
  return response.json();
}

async function fetchText(url, opts = {}) {
  const response = await fetch(url, opts);
  if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
  return response.text();
}

function joinUrl(base, suffix) {
  return `${String(base || "").replace(/\/+$/, "")}${suffix}`;
}

async function openTarget(endpoint) {
  const url = joinUrl(endpoint, `/json/new?${encodeURIComponent("about:blank")}`);
  try {
    return await fetchJson(url, { method: "PUT" });
  } catch {
    return fetchJson(url);
  }
}

async function closeTarget(endpoint, id) {
  if (!id) return;
  const url = joinUrl(endpoint, `/json/close/${id}`);
  try {
    await fetchText(url, { method: "PUT" });
  } catch {
    try {
      await fetchText(url);
    } catch {}
  }
}

async function connect(endpoint) {
  const target = await openTarget(endpoint);
  const ws = new WebSocketImpl(target.webSocketDebuggerUrl);
  let nextId = 0;
  const pending = new Map();
  const send = (method, params = {}) => new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data.toString());
    if (msg.id && pending.has(msg.id)) {
      const entry = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) entry.reject(new Error(msg.error.message || JSON.stringify(msg.error)));
      else entry.resolve(msg.result || {});
    }
  };
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });
  return {
    target,
    send,
    close() {
      try {
        ws.close();
      } catch {}
    },
  };
}

async function uploadCover(session, coverImagePath) {
  if (!coverImagePath) return { attempted: false, uploaded: false, matchedSelector: "" };
  const triggerResult = await session.send("Runtime.evaluate", {
    expression: `JSON.stringify((() => {
      const add = document.querySelector('.article-cover-add');
      if (add) { add.click(); return { ok: true, mode: 'add' }; }
      const replace = document.querySelector('.article-cover-img-replace');
      if (replace) { replace.click(); return { ok: true, mode: 'replace' }; }
      const edit = document.querySelector('.article-cover-img-modify');
      if (edit) { edit.click(); return { ok: true, mode: 'edit' }; }
      return { ok: false, mode: '' };
    })())`,
    returnByValue: true,
  });
  const trigger = parseJsonValue(triggerResult?.result?.value);
  await new Promise((resolve) => setTimeout(resolve, 1000));

  const documentRoot = await session.send("DOM.getDocument", { depth: -1, pierce: true });
  const selectors = [
    ".btn-upload-handle input[type='file']",
    ".upload-handler input[type='file']",
    "input[type='file'][accept*='image']",
    "input[type='file']",
  ];
  let nodeId = 0;
  let matchedSelector = "";
  for (const selector of selectors) {
    const found = await session.send("DOM.querySelector", { nodeId: documentRoot.root.nodeId, selector });
    if (found?.nodeId) {
      nodeId = found.nodeId;
      matchedSelector = selector;
      break;
    }
  }
  if (!nodeId) {
    return { attempted: true, uploaded: false, matchedSelector: "", trigger };
  }

  await session.send("DOM.setFileInputFiles", {
    nodeId,
    files: [path.resolve(coverImagePath)],
  });
  await new Promise((resolve) => setTimeout(resolve, 5000));

  const uploadedCheck = await session.send("Runtime.evaluate", {
    expression: `JSON.stringify((() => {
      const previewImg = document.querySelector('.article-cover-images img, .article-cover img, .upload-image-wrapper img');
      return {
        hasPreviewImage: !!previewImg,
        previewSrc: previewImg ? (previewImg.getAttribute('src') || '') : '',
      };
    })())`,
    returnByValue: true,
  });
  const uploaded = parseJsonValue(uploadedCheck?.result?.value);
  return {
    attempted: true,
    uploaded: Boolean(uploaded.hasPreviewImage),
    matchedSelector,
    trigger,
    previewSrc: cleanText(uploaded.previewSrc),
  };
}

async function main() {
  const args = parseArgs(process.argv);
  const manifest = JSON.parse(fs.readFileSync(args.manifest, "utf8"));
  if (!WebSocketImpl) {
    throw new Error("Requires Node.js with global WebSocket.");
  }

  const prepared = {
    status: "prepared",
    title: cleanText(manifest.title),
    subtitle: cleanText(manifest.subtitle),
    body_html: buildToutiaoBodyHtml(manifest.body_markdown || manifest.content_markdown, Array.isArray(manifest.inline_images) ? manifest.inline_images : []),
    cover_image_path: cleanText(manifest.cover_image_path),
    save_mode: cleanText(manifest.save_mode) || "draft",
    inline_images: Array.isArray(manifest.inline_images) ? manifest.inline_images : [],
  };

  if (args.prepareOnly) {
    writeOutput(args.output, prepared);
    return;
  }

  const publishUrl = "https://mp.toutiao.com/profile_v4/graphic/publish";
  const session = await connect(args.endpoint);
  try {
    await session.send("Page.enable");
    await session.send("Runtime.enable");
    await session.send("DOM.enable");
    await session.send("Page.navigate", { url: publishUrl });
    await new Promise((resolve) => setTimeout(resolve, Math.max(3000, args.waitMs)));

    const stateCheck = await session.send("Runtime.evaluate", {
      expression: `JSON.stringify({ title: document.title, text: (document.body?.innerText || '').substring(0, 300) })`,
      returnByValue: true,
    });
    const state = parseJsonValue(stateCheck?.result?.value);
    if (/登录|扫码|scan|login/i.test(`${state.title} ${state.text}`)) {
      throw new Error("Toutiao backend not logged in. Use a signed-in browser profile.");
    }

    const titleResult = await session.send("Runtime.evaluate", {
      expression: `JSON.stringify((() => {
        const titleInput = document.querySelector('textarea[placeholder*="标题"]')
          || document.querySelector('input[placeholder*="标题"]')
          || document.querySelector('.article-title textarea')
          || document.querySelector('.article-title input')
          || document.querySelector('[class*="title"] textarea')
          || document.querySelector('[class*="title"] input');
        if (!titleInput) return { ok: false, message: 'Title input not found' };
        const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set
          || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        if (setter) setter.call(titleInput, ${JSON.stringify(prepared.title)});
        else titleInput.value = ${JSON.stringify(prepared.title)};
        titleInput.dispatchEvent(new Event('input', { bubbles: true }));
        titleInput.dispatchEvent(new Event('change', { bubbles: true }));
        return { ok: true, value: titleInput.value };
      })())`,
      returnByValue: true,
    });

    const bodyResult = await session.send("Runtime.evaluate", {
      expression: `JSON.stringify((() => {
        const editor = document.querySelector('.ProseMirror[contenteditable="true"]')
          || document.querySelector('[contenteditable="true"][class*="editor"]')
          || document.querySelector('[contenteditable="true"]');
        if (!editor) return { ok: false, message: 'Body editor not found' };
        editor.focus();
        editor.innerHTML = ${JSON.stringify(prepared.body_html)};
        editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste' }));
        editor.dispatchEvent(new Event('change', { bubbles: true }));
        const charCount = (editor.innerText || '').length;
        return { ok: charCount > 20, charCount };
      })())`,
      returnByValue: true,
    });

    const coverResult = await uploadCover(session, prepared.cover_image_path);
    const buttonTexts = prepared.save_mode === "publish" ? ["预览并发布", "发布", "发表"] : ["存草稿", "保存草稿"];
    const clickResult = await session.send("Runtime.evaluate", {
      expression: `JSON.stringify((() => {
        const targets = ${JSON.stringify(buttonTexts)};
        const buttons = Array.from(document.querySelectorAll('button, [role="button"]'));
        let best = null;
        for (const el of buttons) {
          const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
          if (!text) continue;
          for (const target of targets) {
            if (text.includes(target)) {
              const rect = el.getBoundingClientRect();
              if (rect.width < 8 || rect.height < 8) continue;
              const score = text === target ? 20 : 8;
              if (!best || score > best.score) best = { el, score, text };
            }
          }
        }
        if (!best) return { ok: false, matchedText: '' };
        best.el.click();
        return { ok: true, matchedText: best.text };
      })())`,
      returnByValue: true,
    });

    await new Promise((resolve) => setTimeout(resolve, Math.max(4000, args.waitMs)));

    const finalCheck = await session.send("Runtime.evaluate", {
      expression: `JSON.stringify({ href: location.href, title: document.title, text: (document.body?.innerText || '').substring(0, 500) })`,
      returnByValue: true,
    });
    const finalState = parseJsonValue(finalCheck?.result?.value);
    const titleRes = parseJsonValue(titleResult?.result?.value);
    const bodyRes = parseJsonValue(bodyResult?.result?.value);
    const clickRes = parseJsonValue(clickResult?.result?.value);
    const successIndicators = ["发布成功", "已发布", "草稿保存成功", "已保存", "保存成功"];
    const finalText = `${finalState.title || ""} ${finalState.text || ""}`;
    const looksSuccessful = clickRes.ok && (
      successIndicators.some((item) => finalText.includes(item)) ||
      finalState.href !== publishUrl
    );

    const payload = {
      status: looksSuccessful ? "ok" : clickRes.ok ? "uncertain" : "error",
      save_mode: prepared.save_mode,
      title_result: titleRes,
      body_result: bodyRes,
      cover_result: coverResult,
      click_result: clickRes,
      final_state: { href: cleanText(finalState.href), title: cleanText(finalState.title) },
      article_url: cleanText(finalState.href) !== publishUrl ? cleanText(finalState.href) : "",
    };
    writeOutput(args.output, payload);
  } finally {
    session.close();
    await closeTarget(args.endpoint, session.target.id);
  }
}

main().catch((error) => {
  const payload = {
    status: "error",
    message: String(error?.stack || error?.message || error).replace(/\s+/g, " ").trim(),
  };
  writeOutput(process.argv.includes("--output") ? parseArgs(process.argv).output : path.join(process.cwd(), "result.json"), payload);
  process.exit(1);
});
