const RAW_SOURCE_TYPES = ["web_article", "paper", "repo", "manual", "article"];
const RAW_STATUSES = ["queued", "compiled", "archived", "error"];
const WIKI_KINDS = ["concept", "entity", "source", "synthesis"];
const WIKI_REVIEW_STATES = ["draft", "reviewed"];

const ISO_8601_TZ_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/;
const DATE_RE = /^\d{4}-\d{2}-\d{2}$/;

export function parseFrontmatter(content) {
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
  if (!match) {
    return null;
  }

  const result = {};
  for (const line of match[1].split(/\r?\n/)) {
    const colonIndex = line.indexOf(":");
    if (colonIndex === -1) {
      continue;
    }

    const key = line.slice(0, colonIndex).trim();
    let value = line.slice(colonIndex + 1).trim();

    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }

    if (value.startsWith("[") && value.endsWith("]")) {
      value = value
        .slice(1, -1)
        .split(",")
        .map((entry) => entry.trim().replace(/^["']|["']$/g, ""))
        .filter(Boolean);
    } else if (/^-?\d+$/.test(value)) {
      value = Number.parseInt(value, 10);
    }

    result[key] = value;
  }

  return result;
}

export function validateRawFrontmatter(frontmatter) {
  assertObject(frontmatter);
  assertField(frontmatter, "kb_type", "raw");
  assertEnum(frontmatter, "source_type", RAW_SOURCE_TYPES);
  assertPresent(frontmatter, "topic");
  assertPresent(frontmatter, "source_url");
  assertIso8601Tz(frontmatter, "captured_at");
  assertDateField(frontmatter, "kb_date");
  assertEnum(frontmatter, "status", RAW_STATUSES);
  assertField(frontmatter, "managed_by", "human");
}

export function validateWikiFrontmatter(frontmatter) {
  assertObject(frontmatter);
  assertField(frontmatter, "kb_type", "wiki");
  assertEnum(frontmatter, "wiki_kind", WIKI_KINDS);
  assertPresent(frontmatter, "topic");
  assertArray(frontmatter, "compiled_from");
  assertIso8601Tz(frontmatter, "compiled_at");
  assertDateField(frontmatter, "kb_date");
  assertEnum(frontmatter, "review_state", WIKI_REVIEW_STATES);
  assertField(frontmatter, "managed_by", "codex");
  assertNumber(frontmatter, "kb_source_count");
  assertPresent(frontmatter, "dedup_key");
}

export function generateFrontmatter(type, fields = {}) {
  const now = formatIso8601Tz(new Date());

  if (type === "raw") {
    const capturedAt = fields.captured_at || now;
    return formatYaml({
      kb_type: "raw",
      source_type: fields.source_type || "manual",
      topic: fields.topic || "",
      source_url: fields.source_url || "",
      captured_at: capturedAt,
      kb_date: fields.kb_date || capturedAt.slice(0, 10),
      status: fields.status || "queued",
      managed_by: "human"
    });
  }

  if (type === "wiki") {
    const compiledAt = fields.compiled_at || now;
    return formatYaml({
      kb_type: "wiki",
      wiki_kind: fields.wiki_kind || "concept",
      topic: fields.topic || "",
      compiled_from: fields.compiled_from || [],
      compiled_at: compiledAt,
      kb_date: fields.kb_date || compiledAt.slice(0, 10),
      review_state: fields.review_state || "draft",
      managed_by: "codex",
      kb_source_count: fields.kb_source_count ?? 0,
      dedup_key: fields.dedup_key || ""
    });
  }

  throw new Error(`Unknown frontmatter type: ${type}`);
}

export function formatIso8601Tz(date, offsetHours = 8) {
  const offsetMinutes = offsetHours * 60;
  const shifted = new Date(date.getTime() + offsetMinutes * 60 * 1000);
  const iso = shifted.toISOString().slice(0, 19);
  const sign = offsetHours >= 0 ? "+" : "-";
  const hours = String(Math.abs(offsetHours)).padStart(2, "0");
  return `${iso}${sign}${hours}:00`;
}

function formatYaml(object) {
  const lines = ["---"];
  for (const [key, value] of Object.entries(object)) {
    if (Array.isArray(value)) {
      lines.push(`${key}: [${value.map((item) => `"${item}"`).join(", ")}]`);
    } else if (typeof value === "number") {
      lines.push(`${key}: ${value}`);
    } else {
      lines.push(`${key}: "${value}"`);
    }
  }
  lines.push("---");
  return lines.join("\n");
}

function assertObject(frontmatter) {
  if (!frontmatter || typeof frontmatter !== "object") {
    throw new Error("Frontmatter is missing or not an object");
  }
}

function assertField(frontmatter, key, expected) {
  if (frontmatter[key] !== expected) {
    throw new Error(
      `Frontmatter field "${key}" must be "${expected}", got "${frontmatter[key]}"`
    );
  }
}

function assertEnum(frontmatter, key, allowedValues) {
  if (!allowedValues.includes(frontmatter[key])) {
    throw new Error(
      `Frontmatter field "${key}" must be one of [${allowedValues.join(", ")}], got "${frontmatter[key]}"`
    );
  }
}

function assertPresent(frontmatter, key) {
  if (frontmatter[key] === undefined || frontmatter[key] === null) {
    throw new Error(`Frontmatter field "${key}" is required but missing`);
  }
}

function assertIso8601Tz(frontmatter, key) {
  assertPresent(frontmatter, key);
  if (typeof frontmatter[key] !== "string" || !ISO_8601_TZ_RE.test(frontmatter[key])) {
    throw new Error(
      `Frontmatter field "${key}" must be ISO 8601 with timezone (YYYY-MM-DDTHH:mm:ss+HH:MM), got "${frontmatter[key]}"`
    );
  }
}

function assertDateField(frontmatter, key) {
  assertPresent(frontmatter, key);
  const value = String(frontmatter[key]);
  if (!DATE_RE.test(value)) {
    throw new Error(`Frontmatter field "${key}" must be YYYY-MM-DD, got "${frontmatter[key]}"`);
  }
}

function assertArray(frontmatter, key) {
  assertPresent(frontmatter, key);
  if (!Array.isArray(frontmatter[key])) {
    throw new Error(`Frontmatter field "${key}" must be an array, got ${typeof frontmatter[key]}`);
  }
}

function assertNumber(frontmatter, key) {
  assertPresent(frontmatter, key);
  if (typeof frontmatter[key] !== "number" || !Number.isFinite(frontmatter[key])) {
    throw new Error(`Frontmatter field "${key}" must be a number, got "${frontmatter[key]}"`);
  }
}
