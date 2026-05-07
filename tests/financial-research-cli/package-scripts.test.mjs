import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..", "..");
const packagePath = path.join(repoRoot, "apps", "financial-research-cli", "package.json");

function packageScripts() {
  const payload = JSON.parse(fs.readFileSync(packagePath, "utf8"));
  return payload.scripts || {};
}

test("offline acceptance includes horizon-bridge smoke", () => {
  const scripts = packageScripts();
  assert.match(
    scripts["smoke:offline:horizon-bridge"],
    /node \.\/src\/index\.mjs horizon-bridge --input financial-analysis\/skills\/autoresearch-info-index\/examples\/horizon-bridge-request\.template\.json/,
  );
  assert.match(scripts["smoke:offline:horizon-bridge"], /--output apps\/financial-research-cli\/\.smoke\/horizon-bridge\/horizon-bridge-result\.json/);
  assert.match(scripts["smoke:offline:horizon-bridge"], /--markdown-output apps\/financial-research-cli\/\.smoke\/horizon-bridge\/horizon-bridge-report\.md/);
  assert.match(scripts["acceptance:offline"], /npm run smoke:offline:horizon-bridge/);
});
