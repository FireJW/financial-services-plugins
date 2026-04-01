import path from "node:path";
import process from "node:process";
import { existsSync } from "node:fs";
import { repoRoot } from "./runtime-report-lib.mjs";

export const RUNTIME_HOST_RELIABILITY_SUITE_NAME = "runtime-host-reliability";

export const RUNTIME_HOST_RELIABILITY_TESTS = Object.freeze([
  path.join("tests", "runtime-host", "runtime-real-task-fixtures.test.mjs"),
  path.join("tests", "runtime-host", "real-task-runner-lib.test.mjs"),
  path.join("tests", "runtime-host", "real-task-runner-entrypoint.test.mjs"),
  path.join("tests", "runtime-host", "runtime-prompt-budget.test.mjs"),
  path.join("tests", "runtime-host", "runtime-attempt-ledger.test.mjs"),
  path.join("tests", "runtime-host", "worker-verifier-entrypoints.test.mjs"),
  path.join("tests", "runtime-host", "structured-verifier-contract.test.mjs"),
  path.join("tests", "runtime-host", "structured-verifier-entrypoints.test.mjs"),
  path.join("tests", "runtime-host", "verification-pass.test.mjs"),
  path.join("tests", "runtime-host", "intent-preservation.test.mjs"),
  path.join("tests", "runtime-host", "session-memory-state.test.mjs"),
  path.join("tests", "runtime-host", "runtime-fixture-coverage-entrypoint.test.mjs"),
  path.join("tests", "runtime-host", "runtime-host-reliability-suite-entrypoint.test.mjs"),
]);

export const RUNTIME_REAL_TASK_FIXTURE_MANIFEST = Object.freeze([
  {
    id: "feedback-workflow",
    label: "Jenny feedback workflow",
    fixtureRoot: path.join("tests", "fixtures", "runtime-real-tasks", "jenny-feedback-workflow"),
    classicCase: null,
  },
  {
    id: "macro-shock-chain-map",
    label: "A-share macro shock chain map",
    fixtureRoot: path.join("tests", "fixtures", "runtime-real-tasks", "a-share-macro-shock-chain-map"),
    classicCase: "macro-shock-chain-map",
  },
  {
    id: "latest-event-verification",
    label: "Latest event verification",
    fixtureRoot: path.join("tests", "fixtures", "runtime-real-tasks", "latest-event-verification"),
    classicCase: "latest-event-verification",
  },
  {
    id: "x-post-evidence",
    label: "X post evidence",
    fixtureRoot: path.join("tests", "fixtures", "runtime-real-tasks", "x-post-evidence"),
    classicCase: "x-post-evidence",
  },
  {
    id: "evidence-to-article",
    label: "Evidence to article",
    fixtureRoot: path.join("tests", "fixtures", "runtime-real-tasks", "evidence-to-article"),
    classicCase: "evidence-to-article",
  },
  {
    id: "workflow-improvement-loop",
    label: "Workflow improvement loop",
    fixtureRoot: path.join("tests", "fixtures", "runtime-real-tasks", "workflow-improvement-loop"),
    classicCase: "workflow-improvement-loop",
  },
]);

export const RUNTIME_CLASSIC_CASES = Object.freeze([
  {
    id: "latest-event-verification",
    label: "Latest event verification",
  },
  {
    id: "x-post-evidence",
    label: "X post evidence",
  },
  {
    id: "macro-shock-chain-map",
    label: "Macro shock chain map",
  },
  {
    id: "evidence-to-article",
    label: "Evidence to article",
  },
  {
    id: "workflow-improvement-loop",
    label: "Workflow improvement loop",
  },
]);

export function buildRuntimeFixtureCoverageReport() {
  const fixtures = RUNTIME_REAL_TASK_FIXTURE_MANIFEST.map((fixture) => {
    const absoluteFixtureRoot = path.join(repoRoot, fixture.fixtureRoot);
    return {
      ...fixture,
      absoluteFixtureRoot,
      exists: existsSync(absoluteFixtureRoot),
    };
  });

  const classicCaseCoverage = RUNTIME_CLASSIC_CASES.map((classicCase) => {
    const matchingFixture = fixtures.find((fixture) => fixture.classicCase === classicCase.id) ?? null;
    return {
      ...classicCase,
      covered: Boolean(matchingFixture?.exists),
      fixtureId: matchingFixture?.id ?? null,
      fixtureRoot: matchingFixture?.fixtureRoot ?? null,
    };
  });

  const missingClassicCases = classicCaseCoverage.filter((entry) => !entry.covered);
  const missingFixtureRoots = fixtures.filter((fixture) => !fixture.exists);

  return {
    suiteName: RUNTIME_HOST_RELIABILITY_SUITE_NAME,
    fixtureCount: fixtures.length,
    coveredClassicCaseCount: classicCaseCoverage.filter((entry) => entry.covered).length,
    classicCaseCount: classicCaseCoverage.length,
    fixtures,
    classicCaseCoverage,
    missingClassicCases,
    missingFixtureRoots,
    ok: missingClassicCases.length === 0 && missingFixtureRoots.length === 0,
  };
}

export function buildRuntimeHostReliabilitySuitePreview(options = {}) {
  const forwardedArgs = [...(options.forwardedArgs ?? [])];
  const command = options.command ?? process.execPath;
  const args = ["--test", ...forwardedArgs, ...RUNTIME_HOST_RELIABILITY_TESTS];
  const coverage = buildRuntimeFixtureCoverageReport();

  return {
    suiteName: RUNTIME_HOST_RELIABILITY_SUITE_NAME,
    cwd: repoRoot,
    testCount: RUNTIME_HOST_RELIABILITY_TESTS.length,
    testFiles: [...RUNTIME_HOST_RELIABILITY_TESTS],
    realTaskFixtureCount: coverage.fixtureCount,
    coveredClassicCaseCount: coverage.coveredClassicCaseCount,
    classicCaseCount: coverage.classicCaseCount,
    invocation: {
      command,
      args,
      forwardedArgs,
      displayCommand: ["node", "--test", ...forwardedArgs, ...RUNTIME_HOST_RELIABILITY_TESTS].join(
        " ",
      ),
    },
  };
}
