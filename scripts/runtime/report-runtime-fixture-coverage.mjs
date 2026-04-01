import process from "node:process";
import { buildRuntimeFixtureCoverageReport } from "./runtime-host-reliability-suite-lib.mjs";

const args = process.argv.slice(2);

if (args.includes("--help")) {
  printUsageAndExit(0);
}

const report = buildRuntimeFixtureCoverageReport();

if (args.includes("--list-fixtures")) {
  process.stdout.write(`${report.fixtures.map((fixture) => fixture.fixtureRoot).join("\n")}\n`);
  process.exit(0);
}

const asJson = args.includes("--json");
if (asJson) {
  process.stdout.write(`${JSON.stringify(report, null, 2)}\n`);
} else {
  process.stdout.write(renderCoverageReport(report));
}

if (args.includes("--check") && !report.ok) {
  process.exit(1);
}

process.exit(0);

function renderCoverageReport(report) {
  const lines = [];
  lines.push(`Suite: ${report.suiteName}`);
  lines.push(`Coverage: ${report.ok ? "PASS" : "FAIL"}`);
  lines.push(`Real-task fixtures: ${report.fixtureCount}`);
  lines.push(`Classic cases: ${report.coveredClassicCaseCount}/${report.classicCaseCount}`);
  lines.push("Fixtures:");
  for (const fixture of report.fixtures) {
    lines.push(`- ${fixture.id}: ${fixture.fixtureRoot} [${fixture.exists ? "present" : "missing"}]`);
  }
  lines.push("Classic case coverage:");
  for (const classicCase of report.classicCaseCoverage) {
    lines.push(
      `- ${classicCase.id}: ${classicCase.covered ? `covered by ${classicCase.fixtureId}` : "missing"}`,
    );
  }

  if (report.missingClassicCases.length > 0) {
    lines.push("Missing classic cases:");
    for (const classicCase of report.missingClassicCases) {
      lines.push(`- ${classicCase.id}`);
    }
  }

  if (report.missingFixtureRoots.length > 0) {
    lines.push("Missing fixture roots:");
    for (const fixture of report.missingFixtureRoots) {
      lines.push(`- ${fixture.fixtureRoot}`);
    }
  }

  return `${lines.join("\n")}\n`;
}

function printUsageAndExit(exitCode) {
  process.stderr.write(
    "Usage: node scripts/runtime/report-runtime-fixture-coverage.mjs [--json] [--list-fixtures] [--check]\n",
  );
  process.exit(exitCode);
}
