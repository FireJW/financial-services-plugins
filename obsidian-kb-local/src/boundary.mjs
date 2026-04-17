function normalizeRelativePath(input, label) {
  if (typeof input !== "string" || input.trim() === "") {
    throw new Error(`Write boundary violation: missing ${label}`);
  }

  const normalized = input.replace(/\\/g, "/").trim();

  if (/^[A-Za-z]:\//.test(normalized) || normalized.startsWith("/")) {
    throw new Error(
      `Write boundary violation: absolute paths are not allowed in ${label} "${input}"`
    );
  }

  const segments = normalized.split("/").filter(Boolean);
  if (segments.length === 0 || segments.some((segment) => segment === "." || segment === "..")) {
    throw new Error(
      `Write boundary violation: path traversal detected in ${label} "${input}"`
    );
  }

  return segments.join("/");
}

export function assertWithinBoundary(notePath, machineRoot) {
  const normalizedPath = normalizeRelativePath(notePath, "path");
  const normalizedRoot = normalizeRelativePath(machineRoot, "machine root");

  if (
    normalizedPath !== normalizedRoot &&
    !normalizedPath.startsWith(`${normalizedRoot}/`)
  ) {
    throw new Error(
      `Write boundary violation: "${notePath}" is outside machine root "${machineRoot}"`
    );
  }
}
