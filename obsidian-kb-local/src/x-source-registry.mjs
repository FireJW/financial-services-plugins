export function extractXHandleFromUrl(url) {
  let parsed;
  try {
    parsed = new URL(String(url || ""));
  } catch {
    return "";
  }
  const host = parsed.hostname.toLowerCase().replace(/^www\./, "");
  if (host !== "x.com" && host !== "twitter.com") {
    return "";
  }
  const [handle] = parsed.pathname.split("/").filter(Boolean);
  return normalizeXHandle(handle);
}

export function createDefaultXAuthorEntry(params = {}) {
  const handle = normalizeXHandle(params.handle);
  return {
    handle,
    added_at: params.addedAt || params.added_at || "",
    media_policy: params.mediaPolicy || params.media_policy || "remote_only",
    promotion_policy: params.promotionPolicy || params.promotion_policy || "prompt"
  };
}

export function inspectXSourceUrl(url, registry = {}) {
  const handle = extractXHandleFromUrl(url);
  const authors = Array.isArray(registry.authors) ? registry.authors : [];
  const isAllowlisted = authors.some((entry) => normalizeXHandle(entry.handle) === handle);
  return {
    url,
    handle,
    isAllowlisted,
    shouldPromptToWhitelist: Boolean(handle && !isAllowlisted),
    author: authors.find((entry) => normalizeXHandle(entry.handle) === handle) || null,
    policy: registry.default_policy || {}
  };
}

export function upsertXAuthorEntry(registry = {}, author = {}) {
  const normalized = {
    ...author,
    handle: normalizeXHandle(author.handle)
  };
  const authors = (Array.isArray(registry.authors) ? registry.authors : [])
    .filter((entry) => normalizeXHandle(entry.handle) !== normalized.handle)
    .concat(normalized)
    .sort((left, right) => normalizeXHandle(left.handle).localeCompare(normalizeXHandle(right.handle)));
  return {
    ...registry,
    authors
  };
}

export function normalizeXHandle(value) {
  return String(value || "")
    .trim()
    .replace(/^@+/, "")
    .replace(/^\/+|\/+$/g, "")
    .split("/")[0]
    .trim();
}
