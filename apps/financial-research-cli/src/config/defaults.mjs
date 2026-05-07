import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);

export const repoRoot = path.resolve(path.dirname(__filename), "..", "..", "..", "..");
export const appRoot = path.join(repoRoot, "apps", "financial-research-cli");
export const autoresearchScriptsRoot = path.join(
  repoRoot,
  "financial-analysis",
  "skills",
  "autoresearch-info-index",
  "scripts",
);
