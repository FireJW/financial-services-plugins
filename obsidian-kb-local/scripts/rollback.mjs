import path from "node:path";
import { loadConfig } from "../src/config.mjs";
import {
  collectRollbackCandidates,
  executeRollback,
  writeRollbackLog
} from "../src/rollback.mjs";

const args = process.argv.slice(2);

function getArg(name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }

  return args[index + 1];
}

function hasFlag(name) {
  return args.includes(`--${name}`);
}

function main() {
  const dryRun = hasFlag("dry-run");
  const execute = hasFlag("execute");
  const topic = getArg("topic");

  if (!dryRun && !execute) {
    console.error("Usage:");
    console.error("  node scripts/rollback.mjs --dry-run");
    console.error("  node scripts/rollback.mjs --execute");
    console.error("  node scripts/rollback.mjs --execute --topic <topic>");
    process.exit(1);
  }

  const config = loadConfig();
  const candidates = collectRollbackCandidates(config, { topic });
  const kbRoot = path.join(config.vaultPath, config.machineRoot);

  console.log(`Rollback ${dryRun ? "(DRY RUN)" : "(EXECUTE)"}`);
  console.log(`KB root: ${kbRoot}`);
  console.log(`Topic filter: ${topic || "(all)"}`);
  console.log(`Candidates: ${candidates.length}`);
  console.log("");

  if (candidates.length === 0) {
    console.log("No machine-generated files found.");
    return;
  }

  for (const candidate of candidates) {
    const label = `[${candidate.kb_type}/${candidate.wiki_kind || candidate.managed_by}] ${candidate.relativePath}`;
    console.log(`${dryRun ? "WOULD DELETE" : "DELETING"}: ${label}`);
  }

  if (dryRun) {
    console.log("");
    console.log(`Preview complete. ${candidates.length} file(s) would be deleted.`);
    return;
  }

  const logFile = writeRollbackLog(config.projectRoot, {
    topic,
    candidates
  });
  const deleted = executeRollback(config, candidates);

  console.log("");
  console.log(`Rollback log: ${logFile}`);
  console.log(`Deleted ${deleted}/${candidates.length} file(s).`);
}

main();
