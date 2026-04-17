import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..", "..");
const sourceRoot = path.join(
  repoRoot,
  "financial-analysis",
  "skills",
  "decision-journal-publishing",
  "examples",
);
const fixtureRoot = path.join(
  repoRoot,
  "apps",
  "financial-research-cli",
  ".smoke",
  "benchmark-refresh-fixture",
);

fs.rmSync(fixtureRoot, { recursive: true, force: true });
fs.mkdirSync(fixtureRoot, { recursive: true });

const fileMap = [
  ["benchmark-refresh-demo-library.json", "benchmark-refresh-library.json"],
  ["benchmark-refresh-demo-candidates.json", "benchmark-refresh-candidates.json"],
  ["benchmark-refresh-demo-seeds.json", "benchmark-refresh-seeds.json"],
  ["benchmark-refresh-demo-observations.jsonl", "benchmark-refresh-observations.jsonl"],
];

for (const [fromName, toName] of fileMap) {
  fs.copyFileSync(path.join(sourceRoot, fromName), path.join(fixtureRoot, toName));
}

const requestPayload = {
  analysis_time: "2026-03-24T22:00:00+08:00",
  library_path: "apps/financial-research-cli/.smoke/benchmark-refresh-fixture/benchmark-refresh-library.json",
  candidate_library_path: "apps/financial-research-cli/.smoke/benchmark-refresh-fixture/benchmark-refresh-candidates.json",
  seeds_path: "apps/financial-research-cli/.smoke/benchmark-refresh-fixture/benchmark-refresh-seeds.json",
  observations_path: "apps/financial-research-cli/.smoke/benchmark-refresh-fixture/benchmark-refresh-observations.jsonl",
  output_dir: "apps/financial-research-cli/.smoke/benchmark-refresh",
  benchmark_index_request: {
    output_dir: "apps/financial-research-cli/.smoke/benchmark-refresh/benchmark-index-nested",
  },
  refresh_existing_cases: true,
  discover_new_cases: true,
  auto_add_new_cases: true,
  allow_reference_url_fallback: false,
  run_benchmark_index_after_refresh: true,
};

fs.writeFileSync(
  path.join(fixtureRoot, "benchmark-refresh-request.json"),
  `${JSON.stringify(requestPayload, null, 2)}\n`,
  "utf8",
);
