import fs from "node:fs";
import path from "node:path";
import {
  applyCompileOutput,
  buildCompilePrompt,
  parseCompileNotes,
  updateRawNoteStatus
} from "./compile-pipeline.mjs";
import { formatCodexProviderRouteDetail } from "./codex-config.mjs";
import { formatIso8601Tz } from "./frontmatter.mjs";
import { callResponsesApi } from "./llm-provider.mjs";

export async function executeCompileForRawNote(config, params, options = {}) {
  const { rawNote, existingWikiNotes, templateContent, provider } = params;
  const promptVariants = normalizePromptVariants(params, templateContent, rawNote, existingWikiNotes);
  const attempts = [];
  let lastError = null;

  for (const variant of promptVariants) {
    try {
      const response = await callResponsesApi(provider, variant.prompt, {
        fetchImpl: options.fetchImpl,
        signal: options.signal,
        timeoutMs: options.timeoutMs,
        maxAttempts: options.maxAttempts,
        retryBaseDelayMs: options.retryBaseDelayMs,
        sleepImpl: options.sleepImpl,
        spawnSyncImpl: options.spawnSyncImpl
      });
      const notes = parseCompileNotes(response.outputText);
      const applyResult = applyCompileOutput(
        config,
        {
          rawPath: rawNote.relativePath,
          notes
        },
        {
          allowFilesystemFallback: options.allowFilesystemFallback ?? true,
          preferCli: options.preferCli ?? true,
          timestamp: options.timestamp,
          logContext: buildLogContext(provider, response, options)
        }
      );

      attempts.push({ label: variant.label, status: "success", endpoint: response.endpoint });
      return {
        ok: true,
        prompt: variant.prompt,
        promptVariant: { label: variant.label },
        attempts,
        response,
        notes,
        applyResult
      };
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error));
      attempts.push({ label: variant.label, status: "failed", error: lastError.message });
    }
  }

  const rawWriteResult = updateRawNoteStatus(config, rawNote.relativePath, "error", {
    allowFilesystemFallback: options.allowFilesystemFallback ?? true,
    preferCli: options.preferCli ?? true
  });
  const timestamp = options.timestamp || formatIso8601Tz(new Date());
  const logFile = appendCompileErrorLog(config.projectRoot, timestamp, {
    timestamp,
    raw_path: rawNote.relativePath,
    provider: provider.providerName,
    model: provider.model,
    provider_route: providerRouteDetail(provider),
    timeout_ms: options.timeoutMs,
    attempts,
    error: lastError ? lastError.message : "Unknown compile error"
  });

  return {
    ok: false,
    prompt: promptVariants[0]?.prompt || "",
    promptVariant: promptVariants[0] ? { label: promptVariants[0].label } : null,
    attempts,
    error: lastError || new Error("Unknown compile error"),
    rawWriteMode: rawWriteResult.mode,
    logFile
  };
}

export function appendCompileErrorLog(projectRoot, timestamp, entry) {
  const today = String(timestamp).slice(0, 10);
  const logDirectory = path.join(projectRoot, "logs");
  fs.mkdirSync(logDirectory, { recursive: true });

  const logFile = path.join(logDirectory, `compile-errors-${today}.jsonl`);
  fs.appendFileSync(logFile, `${JSON.stringify(entry)}\n`, "utf8");
  return logFile;
}

function normalizePromptVariants(params, templateContent, rawNote, existingWikiNotes) {
  if (Array.isArray(params.promptVariants) && params.promptVariants.length > 0) {
    return params.promptVariants.map((variant) => ({
      label: variant.label || "variant",
      prompt: buildCompilePrompt(
        templateContent,
        {
          ...rawNote,
          promptContent: variant.promptContent
        },
        existingWikiNotes
      )
    }));
  }

  return [
    {
      label: "default",
      prompt: buildCompilePrompt(templateContent, rawNote, existingWikiNotes)
    }
  ];
}

function buildLogContext(provider, response, options) {
  return {
    provider: provider.providerName,
    model: provider.model,
    provider_route: providerRouteDetail(provider),
    provider_endpoint: response.endpoint,
    timeout_ms: options.timeoutMs
  };
}

function providerRouteDetail(provider) {
  return formatCodexProviderRouteDetail(provider).replace("route:direct", "route:responses-api");
}
