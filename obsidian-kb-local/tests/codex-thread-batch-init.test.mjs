import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import {
  buildCodexThreadBatchInitPlan,
  loadCodexThreadNameIndex
} from "../scripts/init-codex-thread-batch.mjs";

test("batch init uses Codex session_index thread names for manifest titles and bodies", () => {
  const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "codex-thread-name-"));
  try {
    const sessionIndexPath = path.join(tempRoot, "session_index.jsonl");
    fs.writeFileSync(
      sessionIndexPath,
      [
        JSON.stringify({
          id: "019dfe10-7cc1-71b1-b507-a7674a74aa68",
          thread_name: "多内容平台互转",
          updated_at: "2026-05-06T16:13:24.7392599Z"
        }),
        ""
      ].join("\n"),
      "utf8"
    );

    const plan = buildCodexThreadBatchInitPlan({
      outputDir: path.join(tempRoot, "out"),
      sessionIndexPath,
      threadIds: ["019dfe10-7cc1-71b1-b507-a7674a74aa68"],
      threadUris: [],
      topic: "历史 Codex 线程沉淀",
      titlePrefix: "历史线程",
      sourceLabel: "Codex batch import",
      compile: true
    });

    assert.equal(
      loadCodexThreadNameIndex(sessionIndexPath).get("019dfe10-7cc1-71b1-b507-a7674a74aa68")
        .threadName,
      "多内容平台互转"
    );
    assert.equal(plan.entries[0].threadName, "多内容平台互转");
    assert.equal(plan.manifest.entries[0].thread_name, "多内容平台互转");
    assert.equal(plan.manifest.entries[0].title, "历史线程 - 多内容平台互转");
    assert.match(plan.entries[0].bodyTemplate, /Thread name: 多内容平台互转/);
    assert.match(plan.entries[0].bodyTemplate, /# Codex Thread Capture\n\nThread URI:/);
    assert.match(plan.entries[0].bodyTemplate, /Topic: 历史 Codex 线程沉淀\n\n## User Request/);
  } finally {
    fs.rmSync(tempRoot, { recursive: true, force: true });
  }
});
