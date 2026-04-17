import test from "node:test";
import assert from "node:assert/strict";
import {
  existsSync,
  mkdirSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildStoryLoopStatus,
  confirmStoryLoopGitReady,
  executeStoryLoop,
  initializeStoryLoop,
  resolveStoryLoopDir,
} from "../../scripts/runtime/story-loop-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const fixtureRoot = path.join(repoRoot, "tests", "fixtures", "runtime-story-loop");

test("story-loop runner advances on PASS, waits for git gate, then blocks on verifier failure", () => {
  const tempPlanPath = createApprovedPlanCopy("english-plan.md");
  const publishHandoffPath = path.join(
    repoRoot,
    ".claude",
    "handoff",
    `story-loop-publish-${Date.now()}.md`,
  );
  const loopId = `story-loop-runner-${Date.now()}`;
  const loopDir = resolveStoryLoopDir(loopId);

  try {
    initializeStoryLoop({
      planFile: tempPlanPath,
      loopId,
      publishHandoffPath,
    });

    const passResult = executeStoryLoop({
      loopDir,
      executeRealTask: createExecutorStub({
        ok: true,
        stage: "completed",
        verdict: "PASS",
      }),
    });

    assert.equal(passResult.state, "waiting_for_git_gate");
    assert.equal(passResult.activeStory?.status, "passed_pending_git");
    assert.equal(passResult.activeStory?.lastVerifierVerdict, "PASS");
    assert.ok(passResult.latestRunPath);
    assert.ok(existsSync(publishHandoffPath));

    const nextStoryNote = readFileSync(path.join(loopDir, "next-story.md"), "utf8");
    assert.match(nextStoryNote, /Manual Git Gate/);

    const afterGate = confirmStoryLoopGitReady({ loopDir });
    assert.equal(afterGate.state, "ready");
    assert.equal(afterGate.activeStory?.title, "Add runner");
    assert.equal(
      JSON.parse(readFileSync(path.join(loopDir, "story-queue.json"), "utf8")).stories[1].status,
      "done",
    );

    const failResult = executeStoryLoop({
      loopDir,
      executeRealTask: createExecutorStub({
        ok: false,
        stage: "verifier_rejected",
        verdict: "FAIL",
      }),
    });

    assert.equal(failResult.state, "blocked");
    assert.equal(failResult.activeStory?.title, "Add runner");
    assert.equal(failResult.activeStory?.status, "blocked");
    assert.equal(failResult.activeStory?.lastVerifierVerdict, "FAIL");

    const handoff = readFileSync(path.join(loopDir, "latest-handoff.md"), "utf8");
    assert.match(handoff, /Story Loop Handoff/);
    assert.match(handoff, /Latest run:/);
    assert.match(handoff, /State: `blocked`/);

    const mirroredHandoff = readFileSync(publishHandoffPath, "utf8");
    assert.equal(mirroredHandoff, handoff);

    const hydrated = buildStoryLoopStatus(loopDir);
    assert.equal(hydrated.counts.done, 1);
    assert.equal(hydrated.counts.blocked, 1);
  } finally {
    rmSync(loopDir, { recursive: true, force: true });
    rmSync(tempPlanPath, { force: true });
    rmSync(publishHandoffPath, { force: true });
  }
});

function createExecutorStub({ ok, stage, verdict }) {
  return (options = {}) => {
    mkdirSync(options.outputDir, { recursive: true });
    const summary = {
      stage,
      results: {
        verifier: {
          semanticGate: {
            ok,
            verdict,
            detail: `structured verdict=${verdict}`,
          },
        },
      },
    };
    writeFileSync(
      path.join(options.outputDir, "run-summary.json"),
      `${JSON.stringify(summary, null, 2)}\n`,
      "utf8",
    );

    return {
      ok,
      exitCode: ok ? 0 : 2,
      summary,
    };
  };
}

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
