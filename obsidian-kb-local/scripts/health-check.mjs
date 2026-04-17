import { loadConfig } from "../src/config.mjs";
import { buildHealthCheckReport } from "../src/compile-pipeline.mjs";

function main() {
  const jsonOutput = process.argv.includes("--json");
  const config = loadConfig();
  const { rawNotes, wikiNotes, report } = buildHealthCheckReport(config);

  if (jsonOutput) {
    console.log(JSON.stringify(report, null, 2));
    return;
  }

  const totalIssues =
    report.orphan_wiki.length +
    report.stale_wiki.length +
    report.missing_source.length +
    report.contract_violations.length +
    report.dedup_conflicts.length;

  console.log("KB Health Check\n");
  console.log(`Raw notes:  ${rawNotes.length}`);
  console.log(`Wiki notes: ${wikiNotes.length}`);
  console.log(`Issues:     ${totalIssues}`);
  console.log("");

  printSection("orphan_wiki", report.orphan_wiki, (item) => `${item.path}`);
  printSection(
    "stale_wiki",
    report.stale_wiki,
    (item) => `${item.path} compiled_at=${item.compiled_at} newest_raw_at=${item.newest_raw_at}`
  );
  printSection(
    "missing_source",
    report.missing_source,
    (item) => `${item.wiki_path} missing=${item.missing_raw}`
  );
  printSection(
    "contract_violations",
    report.contract_violations,
    (item) => `${item.path} ${item.issue}`
  );
  printSection(
    "dedup_conflicts",
    report.dedup_conflicts,
    (item) => `${item.dedup_key} -> ${item.files.join(", ")}`
  );

  console.log(`Summary: ${report.summary}`);
}

function printSection(name, items, formatter) {
  if (!items || items.length === 0) {
    return;
  }

  console.log(`## ${name} (${items.length})`);
  for (const item of items) {
    console.log(`- [${item.severity}] ${formatter(item)}`);
  }
  console.log("");
}

main();
