import fs from "node:fs";
import path from "node:path";

export function appendRebuildTopicLog(projectRoot, timestamp, entry) {
  const date = String(timestamp || new Date().toISOString()).slice(0, 10);
  const logDir = path.join(projectRoot, "logs");
  fs.mkdirSync(logDir, { recursive: true });
  const logFile = path.join(logDir, `rebuild-topic-${date}.jsonl`);
  fs.appendFileSync(logFile, `${JSON.stringify(entry)}\n`, "utf8");
  return logFile;
}

export function buildTopicRebuildPromptVariants(templateContent, params = {}) {
  const fullPrompt = buildPrompt(templateContent, params, { compact: false, maxChars: Infinity });
  if (fullPrompt.length <= 42000) {
    return [{ label: "full", prompt: fullPrompt }];
  }

  return [
    {
      label: "compact-42000",
      prompt: buildPrompt(templateContent, params, { compact: true, maxChars: 42000 })
    },
    {
      label: "compact-24000",
      prompt: buildPrompt(templateContent, params, { compact: true, maxChars: 24000 })
    }
  ];
}

function buildPrompt(templateContent, params, options) {
  const rawSection = formatNotes("Raw Notes", params.rawNotes || [], options);
  const wikiSection = formatNotes("Wiki Notes", params.wikiNotes || [], options);
  return [
    String(templateContent || ""),
    "",
    `Topic: ${params.topic || ""}`,
    "",
    rawSection,
    "",
    wikiSection
  ].join("\n");
}

function formatNotes(label, notes, options) {
  const lines = [`## ${label}`];
  for (const note of notes) {
    lines.push("");
    lines.push(`### ${note.title || note.relativePath || "(untitled)"}`);
    lines.push(`Path: ${note.relativePath || ""}`);
    const content = String(note.content || "");
    if (options.compact) {
      lines.push(content.slice(0, 1200));
      if (content.length > 1200) {
        lines.push("[compact snapshot truncated]");
      }
    } else {
      lines.push(content);
    }
  }
  const output = lines.join("\n");
  if (Number.isFinite(options.maxChars) && output.length > options.maxChars) {
    return `${output.slice(0, Math.max(0, options.maxChars - 32))}\n[compact snapshot truncated]`;
  }
  return output;
}
