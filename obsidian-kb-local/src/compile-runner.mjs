import fs from "node:fs";
import path from "node:path";
import {
  applyCompileOutput,
  buildCompilePrompt,
  parseCompileNotes,
  updateRawNoteStatus
} from "./compile-pipeline.mjs";
import { formatIso8601Tz } from "./frontmatter.mjs";
import { callResponsesApi } from "./llm-provider.mjs";

export async function executeCompileForRawNote(config, params, options = {}) {
  const {
    rawNote,
    existingWikiNotes,
    templateContent,
    provider
  } = params;
  const prompt = buildCompilePrompt(templateContent, rawNote, existingWikiNotes);

  try {
    const response = await callResponsesApi(provider, prompt, {
      fetchImpl: options.fetchImpl,
      signal: options.signal
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
        timestamp: options.timestamp
      }
    );

    return {
      ok: true,
      prompt,
      response,
      notes,
      applyResult
    };
  } catch (error) {
    const rawWriteResult = updateRawNoteStatus(
      config,
      rawNote.relativePath,
      "error",
      {
        allowFilesystemFallback: options.allowFilesystemFallback ?? true,
        preferCli: options.preferCli ?? true
      }
    );
    const timestamp = options.timestamp || formatIso8601Tz(new Date());
    const logFile = appendCompileErrorLog(config.projectRoot, timestamp, {
      timestamp,
      raw_path: rawNote.relativePath,
      model: provider.model,
      provider: provider.providerName,
      error: error instanceof Error ? error.message : String(error)
    });

    return {
      ok: false,
      prompt,
      error: error instanceof Error ? error : new Error(String(error)),
      rawWriteMode: rawWriteResult.mode,
      logFile
    };
  }
}

export function appendCompileErrorLog(projectRoot, timestamp, entry) {
  const today = String(timestamp).slice(0, 10);
  const logDirectory = path.join(projectRoot, "logs");
  fs.mkdirSync(logDirectory, { recursive: true });

  const logFile = path.join(logDirectory, `compile-errors-${today}.jsonl`);
  fs.appendFileSync(logFile, `${JSON.stringify(entry)}\n`, "utf8");
  return logFile;
}
