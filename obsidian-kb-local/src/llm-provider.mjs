import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

export function buildResponseEndpointCandidates(baseUrl, wireApi) {
  if (wireApi !== "responses") {
    throw new Error(`Unsupported wire_api: ${wireApi}`);
  }

  const normalizedBase = normalizeBaseUrl(baseUrl);
  const candidates = [joinUrl(normalizedBase, "responses")];

  if (!/\/v\d+$/i.test(normalizedBase)) {
    candidates.push(joinUrl(normalizedBase, "v1/responses"));
  }

  return uniqueStrings(candidates);
}

export function extractResponseOutputText(payload, options = {}) {
  const fragments = [];
  collectTextFragments(payload, fragments);
  const joined = uniqueStrings(fragments.map((fragment) => fragment.trim()).filter(Boolean)).join(
    "\n"
  );

  if (!joined) {
    const endpoint = options.endpoint || "unknown endpoint";
    const outputTokens = payload?.usage?.output_tokens ?? "unknown";
    const error = new Error(
      `Responses API completed at ${endpoint} but returned no textual output (output_tokens=${outputTokens}). Auth appears accepted; inspect the model response payload.`
    );
    error.code = "EMPTY_RESPONSE_TEXT";
    throw error;
  }

  return joined;
}

export async function callResponsesApi(provider, prompt, options = {}) {
  if (shouldUseCodexExec(provider)) {
    return callCodexExec(prompt, options);
  }

  const fetchImpl = options.fetchImpl ?? globalThis.fetch;
  if (typeof fetchImpl !== "function") {
    throw new Error("A fetch implementation is required to call the LLM provider");
  }

  const requestBody = {
    model: provider.model,
    input: prompt
  };
  const endpoints = buildResponseEndpointCandidates(provider.baseUrl, provider.wireApi);
  const maxAttempts = normalizePositiveInteger(options.maxAttempts, 2);
  let lastError = null;

  for (let index = 0; index < endpoints.length; index += 1) {
    const endpoint = endpoints[index];

    for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
      const abortController = createAbortController(options.timeoutMs);
      try {
        const response = await fetchImpl(endpoint, {
          method: "POST",
          headers: buildHeaders(provider),
          body: JSON.stringify(requestBody),
          signal: options.signal || abortController?.signal
        });
        abortController?.clear();

        const responseText = await response.text();
        if (!response.ok) {
          lastError = new Error(
            `Responses API ${response.status} at ${endpoint}: ${truncate(responseText, 240)}`
          );
          if (isTransientStatus(response.status) && attempt < maxAttempts) {
            await sleep(options.retryBaseDelayMs || 25, options.sleepImpl);
            continue;
          }
          if (response.status === 404 && index < endpoints.length - 1) {
            break;
          }
          throw lastError;
        }

        let payload;
        try {
          payload = JSON.parse(responseText);
        } catch (error) {
          throw new Error(
            `Responses API returned non-JSON content at ${endpoint}: ${truncate(responseText, 240)}`
          );
        }

        return {
          endpoint,
          requestBody,
          payload,
          outputText: extractResponseOutputText(payload, { endpoint })
        };
      } catch (error) {
        abortController?.clear();
        lastError = error instanceof Error ? error : new Error(String(error));
        if (lastError.name === "AbortError" || /aborted/i.test(lastError.message)) {
          throw new Error(`Responses API timed out after ${options.timeoutMs}ms at ${endpoint}`);
        }
        if (index < endpoints.length - 1 && !isTransientError(lastError)) {
          break;
        }
        if (isTransientError(lastError) && attempt < maxAttempts) {
          await sleep(options.retryBaseDelayMs || 25, options.sleepImpl);
          continue;
        }
        break;
      }
    }
  }

  throw lastError || new Error("Responses API request failed");
}

function buildHeaders(provider) {
  const headers = {
    "content-type": "application/json"
  };

  if (provider.apiKey) {
    headers.authorization = `Bearer ${provider.apiKey}`;
  }

  return headers;
}

function collectTextFragments(node, fragments) {
  if (typeof node === "string") {
    fragments.push(node);
    return;
  }

  if (!node || typeof node !== "object") {
    return;
  }

  if (typeof node.output_text === "string") {
    fragments.push(node.output_text);
  }

  if (
    typeof node.text === "string" &&
    (!node.type || node.type === "text" || node.type === "output_text")
  ) {
    fragments.push(node.text);
  }

  if (Array.isArray(node.output)) {
    for (const item of node.output) {
      collectTextFragments(item, fragments);
    }
  }

  if (Array.isArray(node.content)) {
    for (const item of node.content) {
      collectTextFragments(item, fragments);
    }
  }
}

function shouldUseCodexExec(provider) {
  return (
    provider?.providerName === "openai" &&
    provider?.authMode === "chatgpt" &&
    provider?.canUseChatGptSession === true &&
    !provider?.apiKey
  );
}

function callCodexExec(prompt, options = {}) {
  const spawnSyncImpl = options.spawnSyncImpl || spawnSync;
  const outputPath = path.join(
    options.tmpdir || os.tmpdir(),
    `codex-exec-output-${Date.now()}-${Math.random().toString(16).slice(2)}.txt`
  );
  const codexArgs = [
    "exec",
    "--ephemeral",
    "--skip-git-repo-check",
    "--output-last-message",
    outputPath,
    "-"
  ];
  let command = "codex";
  let args = codexArgs;
  if (process.platform === "win32") {
    command = process.env.ComSpec || "C:\\Windows\\System32\\cmd.exe";
    args = ["/d", "/s", "/c", `codex ${codexArgs.map(quoteCmdArg).join(" ")}`];
  }

  const result = spawnSyncImpl(command, args, {
    input: prompt,
    encoding: "utf8",
    timeout: options.timeoutMs
  });
  if (result.status !== 0) {
    throw new Error(`codex exec failed: ${result.stderr || result.stdout || result.status}`);
  }
  const outputText = fs.existsSync(outputPath) ? fs.readFileSync(outputPath, "utf8") : "";
  fs.rmSync(outputPath, { force: true });
  return {
    endpoint: "codex exec",
    requestBody: { input: prompt },
    payload: null,
    outputText
  };
}

function quoteCmdArg(value) {
  const text = String(value);
  return /[\s"]/g.test(text) ? `"${text.replace(/"/g, '\\"')}"` : text;
}

function createAbortController(timeoutMs) {
  const timeout = normalizePositiveInteger(timeoutMs, 0);
  if (!timeout || typeof AbortController !== "function") {
    return null;
  }
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  return {
    signal: controller.signal,
    clear() {
      clearTimeout(timer);
    }
  };
}

function isTransientStatus(status) {
  return [408, 409, 429, 500, 502, 503, 504, 524].includes(Number(status));
}

function isTransientError(error) {
  return /timeout|temporar|network|fetch failed/i.test(error?.message || "");
}

async function sleep(baseDelayMs, sleepImpl) {
  const delay = normalizePositiveInteger(baseDelayMs, 25) * 4;
  if (typeof sleepImpl === "function") {
    await sleepImpl(delay);
    return;
  }
  await new Promise((resolve) => setTimeout(resolve, delay));
}

function normalizeBaseUrl(baseUrl) {
  return String(baseUrl ?? "").trim().replace(/\/+$/, "");
}

function joinUrl(baseUrl, suffix) {
  const normalizedBase = `${normalizeBaseUrl(baseUrl)}/`;
  return new URL(suffix.replace(/^\/+/, ""), normalizedBase).toString();
}

function truncate(value, maxLength) {
  const text = String(value ?? "").replace(/\s+/g, " ").trim();
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}

function uniqueStrings(values) {
  return [...new Set(values)];
}

function normalizePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
