import test from "node:test";
import assert from "node:assert/strict";
import {
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { resolveStoryLoopDir } from "../../scripts/runtime/story-loop-lib.mjs";
import { runInitStoryLoopCli } from "../../scripts/runtime/init-story-loop.mjs";
import { runStoryLoopCli } from "../../scripts/runtime/run-story-loop.mjs";
import { runStoryLoopStatusCli } from "../../scripts/runtime/story-loop-status.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const fixtureRoot = path.join(repoRoot, "tests", "fixtures", "runtime-story-loop");
test("init-story-loop entrypoint emits stable JSON and story-loop-status reads it back", () => {
  const tempPlanPath = createApprovedPlanCopy("english-plan.md");
  const loopId = `story-loop-entry-${Date.now()}`;
  const loopDir = resolveStoryLoopDir(loopId);

  try {
    const initResult = runInitStoryLoopCli([
      "--plan-file",
      tempPlanPath,
      "--loop-id",
      loopId,
      "--json",
    ]);

    assert.equal(initResult.exitCode, 0, initResult.stderr || initResult.stdout);
    const initPayload = JSON.parse(initResult.stdout);
    assert.equal(initPayload.schemaVersion, "story-loop-v1");
    assert.equal(initPayload.state, "ready");
    assert.equal(initPayload.counts.skipped, 1);

    const statusResult = runStoryLoopStatusCli(["--loop-dir", loopDir, "--json"]);

    assert.equal(statusResult.exitCode, 0, statusResult.stderr || statusResult.stdout);
    const statusPayload = JSON.parse(statusResult.stdout);
    assert.equal(statusPayload.activeStory.title, "Build parser");
  } finally {
    rmSync(loopDir, { recursive: true, force: true });
    rmSync(tempPlanPath, { force: true });
  }
});

test("run-story-loop entrypoint confirm-git-ready only advances local loop state", () => {
  const tempPlanPath = createApprovedPlanCopy("english-plan.md");
  const loopId = `story-loop-confirm-${Date.now()}`;
  const loopDir = resolveStoryLoopDir(loopId);

  try {
    const initResult = runInitStoryLoopCli([
      "--plan-file",
      tempPlanPath,
      "--loop-id",
      loopId,
      "--json",
    ]);
    assert.equal(initResult.exitCode, 0, initResult.stderr || initResult.stdout);

    const queuePath = path.join(loopDir, "story-queue.json");
    const queue = JSON.parse(readFileSync(queuePath, "utf8"));
    queue.stories[1].status = "passed_pending_git";
    queue.stories[1].lastRunPath = path.join(loopDir, "stories", queue.stories[1].id, "runs", "pass");
    queue.stories[1].lastVerifierVerdict = "PASS";
    writeFileSync(queuePath, `${JSON.stringify(queue, null, 2)}\n`, "utf8");

    const confirmResult = runStoryLoopCli([
      "--loop-dir",
      loopDir,
      "--confirm-git-ready",
      "--json",
    ]);

    assert.equal(confirmResult.exitCode, 0, confirmResult.stderr || confirmResult.stdout);
    const payload = JSON.parse(confirmResult.stdout);
    assert.equal(payload.action, "confirm_git_ready");
    assert.equal(payload.state, "ready");
    assert.equal(payload.activeStory.title, "Add runner");

    const updatedQueue = JSON.parse(readFileSync(queuePath, "utf8"));
    assert.equal(updatedQueue.stories[1].status, "done");
    assert.equal(updatedQueue.stories[2].status, "queued");
  } finally {
    rmSync(loopDir, { recursive: true, force: true });
    rmSync(tempPlanPath, { force: true });
  }
});

function createApprovedPlanCopy(fixtureName) {
  const targetPath = path.join(
    repoRoot,
    ".claude",
    "plan",
    `story-loop-test-${Date.now()}-${Math.random().toString(16).slice(2)}.md`,
  );
  writeFileSync(targetPath, readFileSync(path.join(fixtureRoot, fixtureName), "utf8"), "utf8");
  return targetPath;
}
