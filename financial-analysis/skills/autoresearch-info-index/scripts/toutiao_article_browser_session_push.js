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
  const args = { manifest: "", output: "", endpoint: "http://127.0.0.1:9222", waitMs: 10000 };
  for (let index = 2; index < argv.length; index += 1) {
    const token = argv[index];
    if (token === "--manifest") args.manifest = argv[index + 1] || "";
    if (token === "--output") args.output = argv[index + 1] || "";
    if (token === "--endpoint") args.endpoint = argv[index + 1] || args.endpoint;
    if (token === "--wait-ms") args.waitMs = Number.parseInt(argv[index + 1] || "", 10) || args.waitMs;
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
  if (!WebSocketImpl) {
    throw new Error("Requires Node.js with global WebSocket.");
  }

  const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
  const joinUrl = (base, suffix) => `${String(base || "").replace(/\/+$/, "")}${suffix}`;
  const fetchJson = async (url, opts = {}) => {
    const response = await fetch(url, opts);
    if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
    return response.json();
  };
  const fetchText = async (url, opts = {}) => {
    const response = await fetch(url, opts);
    if (!response.ok) throw new Error(`HTTP ${response.status} for ${url}`);
    return response.text();
  };
  const openTarget = async (endpoint) => {
    const url = joinUrl(endpoint, `/json/new?${encodeURIComponent("about:blank")}`);
    try {
      return await fetchJson(url, { method: "PUT" });
    } catch {
      return fetchJson(url);
    }
  };
  const closeTarget = async (endpoint, id) => {
    if (!id) return;
    const url = joinUrl(endpoint, `/json/close/${id}`);
    try {
      await fetchText(url, { method: "PUT" });
    } catch {
      try { await fetchText(url); } catch {}
    }
  };
  const parseJsonValue = (value) => {
    try { return JSON.parse(value || "{}"); } catch { return {}; }
  };

  (async () => {
    const publishUrl = "https://mp.toutiao.com/profile_v4/graphic/publish";
    const target = await openTarget(args.endpoint);
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
        const ctx = pending.get(msg.id);
        pending.delete(msg.id);
        if (msg.error) ctx.reject(new Error(msg.error.message || JSON.stringify(msg.error)));
        else ctx.resolve(msg.result || {});
      }
    };

    try {
      await new Promise((resolve, reject) => { ws.onopen = resolve; ws.onerror = reject; });
      await send("Page.enable");
      await send("Runtime.enable");
      await send("Page.navigate", { url: publishUrl });
      await sleep(Math.max(3000, args.waitMs));

      const titleResult = await send("Runtime.evaluate", {
        expression: `JSON.stringify((() => {
          const titleInput = document.querySelector('textarea[placeholder*="标题"]')
            || document.querySelector('input[placeholder*="标题"]')
            || document.querySelector('.article-title textarea')
            || document.querySelector('.article-title input')
            || document.querySelector('[class*="title"] textarea')
            || document.querySelector('[class*="title"] input');
          if (!titleInput) return { ok: false, message: 'Title input not found' };
          const nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value')?.set
            || Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
          if (nativeInputValueSetter) nativeInputValueSetter.call(titleInput, ${JSON.stringify(cleanText(manifest.title))});
          else titleInput.value = ${JSON.stringify(cleanText(manifest.title))};
          titleInput.dispatchEvent(new Event('input', { bubbles: true }));
          titleInput.dispatchEvent(new Event('change', { bubbles: true }));
          return { ok: true, value: titleInput.value };
        })())`,
        returnByValue: true,
      });
      const bodyHtml = buildToutiaoBodyHtml(manifest.content_markdown);
      const bodyResult = await send("Runtime.evaluate", {
        expression: `JSON.stringify((() => {
          const editor = document.querySelector('.ProseMirror[contenteditable="true"]')
            || document.querySelector('[contenteditable="true"][class*="editor"]')
            || document.querySelector('[contenteditable="true"]');
          if (!editor) return { ok: false, message: 'Body editor not found' };
          editor.focus();
          editor.innerHTML = ${JSON.stringify(bodyHtml)};
          editor.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste' }));
          editor.dispatchEvent(new Event('change', { bubbles: true }));
          return { ok: (editor.innerText || '').length > 20, charCount: (editor.innerText || '').length };
        })())`,
        returnByValue: true,
      });

      await sleep(Math.max(3000, args.waitMs));
      const payload = {
        status: "ok",
        title_result: parseJsonValue(titleResult?.result?.value),
        body_result: parseJsonValue(bodyResult?.result?.value),
        article_url: publishUrl,
      };
      fs.writeFileSync(args.output, JSON.stringify(payload, null, 2), "utf8");
      process.stdout.write(JSON.stringify(payload));
    } finally {
      try { ws.close(); } catch {}
      await closeTarget(args.endpoint, target.id);
    }
  })().catch((error) => {
    const payload = { status: "error", message: String(error?.stack || error?.message || error).replace(/\s+/g, " ").trim() };
    fs.writeFileSync(args.output, JSON.stringify(payload, null, 2), "utf8");
    process.stdout.write(JSON.stringify(payload));
    process.exit(1);
  });
}

if (require.main === module) {
  main();
}
