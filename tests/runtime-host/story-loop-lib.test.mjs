import test from "node:test";
import assert from "node:assert/strict";
import {
  existsSync,
  readFileSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  buildStoryLoopStatus,
  initializeStoryLoop,
  parseStoryLoopPlan,
  resolveStoryLoopDir,
} from "../../scripts/runtime/story-loop-lib.mjs";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..", "..");
const fixtureRoot = path.join(repoRoot, "tests", "fixtures", "runtime-story-loop");

test("story-loop parser extracts skipped and queued stories from an English plan", () => {
  const parsed = parseStoryLoopPlan(
    readFileSync(path.join(fixtureRoot, "english-plan.md"), "utf8"),
    {
      planPath: "tests/fixtures/runtime-story-loop/english-plan.md",
    },
  );

  assert.equal(parsed.title, "feat: Story loop sample plan");
  assert.match(parsed.summary, /machine-readable implementation units/i);
  assert.equal(parsed.stories.length, 3);
  assert.equal(parsed.stories[0].completedInPlan, true);
  assert.equal(parsed.stories[1].title, "Build parser");
  assert.match(parsed.stories[1].objective, /Parse the plan into loop stories/i);
  assert.equal(parsed.stories[1].executionNote, "test-first");
  assert.equal(parsed.stories[1].acceptanceHints.length, 2);
  assert.match(parsed.stories[2].objective, /Drive one story per fresh session/i);
});

test("story-loop parser supports Chinese implementation-unit labels", () => {
  const parsed = parseStoryLoopPlan(
    readFileSync(path.join(fixtureRoot, "chinese-plan.md"), "utf8"),
    {
      planPath: "tests/fixtures/runtime-story-loop/chinese-plan.md",
    },
  );

  assert.equal(parsed.title, "feat: 中文 story loop 示例");
  assert.equal(parsed.stories.length, 1);
  assert.equal(parsed.stories[0].title, "建立状态机");
  assert.match(parsed.stories[0].objective, /固定集合/);
  assert.match(parsed.stories[0].executionNote, /状态转换清晰/);
  assert.equal(parsed.stories[0].acceptanceHints.length, 2);
});

test("story-loop parser fails when Implementation Units is missing", () => {
  assert.throws(
    () =>
      parseStoryLoopPlan(
        readFileSync(path.join(fixtureRoot, "missing-units-plan.md"), "utf8"),
        {
          planPath: "tests/fixtures/runtime-story-loop/missing-units-plan.md",
        },
      ),
    /Implementation Units/i,
  );
});

test("story-loop parser fails when a story objective is missing", () => {
  assert.throws(
    () =>
      parseStoryLoopPlan(
        readFileSync(path.join(fixtureRoot, "missing-objective-plan.md"), "utf8"),
        {
          planPath: "tests/fixtures/runtime-story-loop/missing-objective-plan.md",
        },
      ),
    /missing an objective/i,
  );
});

test("story-loop parser keeps acceptance hints empty when Verification is absent", () => {
  const parsed = parseStoryLoopPlan(
    readFileSync(path.join(fixtureRoot, "missing-verification-plan.md"), "utf8"),
    {
      planPath: "tests/fixtures/runtime-story-loop/missing-verification-plan.md",
    },
  );

  assert.equal(parsed.stories.length, 1);
  assert.equal(parsed.stories[0].acceptanceHints.length, 0);
});

test("story-loop initialization writes queue, progress, and handoff artifacts", () => {
  const tempPlanPath = createApprovedPlanCopy("english-plan.md");
  const loopId = `story-loop-bootstrap-${Date.now()}`;
  const loopDir = resolveStoryLoopDir(loopId);

  try {
    const status = initializeStoryLoop({
      planFile: tempPlanPath,
      loopId,
    });

    assert.equal(status.state, "ready");
    assert.equal(status.counts.skipped, 1);
    assert.equal(status.counts.queued, 2);
    assert.ok(existsSync(path.join(loopDir, "loop-config.json")));
    assert.ok(existsSync(path.join(loopDir, "story-queue.json")));
    assert.ok(existsSync(path.join(loopDir, "progress.json")));
    assert.ok(existsSync(path.join(loopDir, "next-story.md")));
    assert.ok(existsSync(path.join(loopDir, "latest-handoff.md")));

    const queue = JSON.parse(readFileSync(path.join(loopDir, "story-queue.json"), "utf8"));
    assert.equal(queue.stories[0].status, "skipped");
    assert.equal(queue.stories[1].status, "queued");

    const hydratedStatus = buildStoryLoopStatus(loopDir);
    assert.equal(hydratedStatus.activeStory?.title, "Build parser");
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
