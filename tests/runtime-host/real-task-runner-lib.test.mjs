import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildRealTaskRunnerPreview,
  materializeRealTaskRunnerInputs,
} from "../../scripts/runtime/real-task-runner-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");

test("real-task runner preview routes feedback-workflow tasks into worker and verifier commands", () => {
  const outputDir = path.join(os.tmpdir(), "runtime-real-task-preview");
  const preview = buildRealTaskRunnerPreview({
    requestText:
      "Collect what Jenny Wen said in interviews and podcasts about feedback, then turn it into a workflow cadence.",
    taskId: "jenny-feedback-run",
    outputDir,
    sessionInput: {
      goal: "Turn evidence into a reusable workflow.",
    },
    contextFiles: [
      path.join(
        "tests",
        "fixtures",
        "runtime-real-tasks",
        "jenny-feedback-workflow",
        "evidence.md",
      ),
    ],
    structuredVerifier: true,
  });

  assert.equal(preview.schemaVersion, "real-task-runner-v1");
  assert.equal(preview.taskId, "jenny-feedback-run");
  assert.equal(preview.routePlan.routeId, "feedback_workflow");
  assert.equal(preview.structuredVerifier, true);
  assert.equal(preview.outputDir, outputDir);
  assert.ok(
    preview.routePlan.pluginDirs.some((pluginDir) => /financial-analysis$/i.test(pluginDir)),
    JSON.stringify(preview, null, 2),
  );
  assert.match(preview.commands.worker.displayCommand, /run-worker-task\.mjs/);
  assert.match(preview.commands.verifier.displayCommand, /run-verifier-task\.mjs/);
  assert.match(preview.commands.verifierPreflight.displayCommand, /--local-only/);
  assert.match(preview.generatedState.routeGuidanceMarkdown, /feedback_workflow/);
  assert.equal(preview.artifacts.contextFiles.length, 1);
  assert.match(
    preview.artifacts.verifierStructuredOutputPath,
    /verifier-output\.json$/,
  );
});

test("real-task runner materialization writes route, state, and copied context artifacts", () => {
  const tempDir = mkdtempSync(path.join(os.tmpdir(), "runtime-real-task-"));

  try {
    const requestText = readFileSync(
      path.join(
        repoRoot,
        "tests",
        "fixtures",
        "runtime-real-tasks",
        "jenny-feedback-workflow",
        "task.md",
      ),
      "utf8",
    ).trim();
    const sessionInput = JSON.parse(
      readFileSync(
        path.join(
          repoRoot,
          "tests",
          "fixtures",
          "runtime-state",
          "sample-session-input.json",
        ),
        "utf8",
      ),
    );
    const preview = buildRealTaskRunnerPreview({
      requestText,
      outputDir: tempDir,
      taskId: "jenny-feedback-pack",
      sessionInput,
      contextFiles: [
        path.join(
          "tests",
          "fixtures",
          "runtime-real-tasks",
          "jenny-feedback-workflow",
          "evidence.md",
        ),
      ],
      approachText: "Preserve evidence tiers and reconstruct only the supported workflow.",
      filesChangedText: "docs/runtime/README.md",
    });

    materializeRealTaskRunnerInputs(preview);

    assert.ok(existsSync(preview.artifacts.rawRequestPath));
    assert.ok(existsSync(preview.artifacts.routePlanPath));
    assert.ok(existsSync(preview.artifacts.routeGuidancePath));
    assert.ok(existsSync(preview.artifacts.intentPath));
    assert.ok(existsSync(preview.artifacts.intentCompactPath));
    assert.ok(existsSync(preview.artifacts.nowPath));
    assert.ok(existsSync(preview.artifacts.approachPath));
    assert.ok(existsSync(preview.artifacts.filesChangedPath));
    assert.ok(existsSync(preview.artifacts.runPlanPath));
    assert.ok(existsSync(preview.artifacts.contextFiles[0].materializedPath));

    const routePlan = JSON.parse(readFileSync(preview.artifacts.routePlanPath, "utf8"));
    assert.equal(routePlan.routeId, "feedback_workflow");

    const intentMarkdown = readFileSync(preview.artifacts.intentPath, "utf8");
    assert.match(intentMarkdown, /## User Intent/);

    const nowMarkdown = readFileSync(preview.artifacts.nowPath, "utf8");
    assert.match(nowMarkdown, /## Goal/);
    assert.match(nowMarkdown, /Deploy the P0\/P1 runtime hardening layer/);

    const routeGuidance = readFileSync(preview.artifacts.routeGuidancePath, "utf8");
    assert.match(routeGuidance, /## Native Workflow/);
    assert.match(routeGuidance, /feedback-iteration-workflow/);

    const copiedContext = readFileSync(
      preview.artifacts.contextFiles[0].materializedPath,
      "utf8",
    );
    assert.match(copiedContext, /Jenny Wen Feedback Workflow Evidence Pack/);
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
});
