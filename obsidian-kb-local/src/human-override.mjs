const OVERRIDE_RE = /<!-- human-override -->([\s\S]*?)<!-- \/human-override -->/g;

export function extractHumanOverrides(content) {
  if (!content || typeof content !== "string") {
    return [];
  }

  const overrides = [];
  OVERRIDE_RE.lastIndex = 0;

  let match;
  while ((match = OVERRIDE_RE.exec(content)) !== null) {
    overrides.push({
      fullMatch: match[0],
      innerContent: match[1],
      index: match.index
    });
  }

  return overrides;
}

export function mergeWithOverrides(newContent, existingOverrides) {
  if (!existingOverrides || existingOverrides.length === 0) {
    return newContent;
  }

  OVERRIDE_RE.lastIndex = 0;
  if (OVERRIDE_RE.test(newContent)) {
    return newContent;
  }

  const overrideSection = existingOverrides
    .map((override) => override.fullMatch)
    .join("\n\n");

  return `${newContent.trimEnd()}\n\n${overrideSection}\n`;
}

export function hasHumanOverrides(content) {
  if (!content || typeof content !== "string") {
    return false;
  }

  OVERRIDE_RE.lastIndex = 0;
  return OVERRIDE_RE.test(content);
}
