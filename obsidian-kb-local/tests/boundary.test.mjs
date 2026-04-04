import assert from "node:assert/strict";
import { describe, it } from "node:test";
import { assertWithinBoundary } from "../src/boundary.mjs";

const MACHINE_ROOT = "08-AI知识库";

describe("assertWithinBoundary", () => {
  it("allows paths within machine root", () => {
    assert.doesNotThrow(() =>
      assertWithinBoundary("08-AI知识库/10-raw/web/test.md", MACHINE_ROOT)
    );
  });

  it("allows exact machine root path", () => {
    assert.doesNotThrow(() => assertWithinBoundary("08-AI知识库", MACHINE_ROOT));
  });

  it("normalizes Windows separators", () => {
    assert.doesNotThrow(() =>
      assertWithinBoundary("08-AI知识库\\10-raw\\test.md", MACHINE_ROOT)
    );
  });

  it("rejects paths outside machine root", () => {
    assert.throws(
      () => assertWithinBoundary("00-收件箱/test.md", MACHINE_ROOT),
      /Write boundary violation/
    );
  });

  it("rejects empty path", () => {
    assert.throws(() => assertWithinBoundary("", MACHINE_ROOT), /Write boundary violation/);
  });

  it("rejects relative traversal", () => {
    assert.throws(
      () => assertWithinBoundary("08-AI知识库/../00-收件箱/test.md", MACHINE_ROOT),
      /Write boundary violation/
    );
  });

  it("rejects absolute paths", () => {
    assert.throws(
      () => assertWithinBoundary("D:/OneDrive - zn/文档/Obsidian Vault/08-AI知识库/test.md", MACHINE_ROOT),
      /Write boundary violation/
    );
  });

  it("rejects prefix spoofing", () => {
    assert.throws(
      () => assertWithinBoundary("08-AI知识库-fake/test.md", MACHINE_ROOT),
      /Write boundary violation/
    );
  });
});
