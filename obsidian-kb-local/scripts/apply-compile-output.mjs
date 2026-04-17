import { loadConfig } from "../src/config.mjs";
import { applyCompileOutput, parseCompileNotes } from "../src/compile-pipeline.mjs";

const args = process.argv.slice(2);

function getArg(name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }

  return args[index + 1];
}

async function main() {
  const rawPath = getArg("raw-path");
  if (!rawPath) {
    console.error(
      "Usage: node scripts/apply-compile-output.mjs --raw-path <raw-note-path> < llm-output.json"
    );
    process.exit(1);
  }

  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }

  const input = Buffer.concat(chunks).toString("utf8").trim();
  if (!input) {
    console.error("No JSON was provided on stdin.");
    process.exit(1);
  }

  const notes = parseCompileNotes(input);
  const config = loadConfig();
  const result = applyCompileOutput(
    config,
    {
      rawPath,
      notes
    },
    {
      allowFilesystemFallback: true,
      preferCli: true
    }
  );

  console.log(`Applied ${result.results.length} compile note(s).`);
  console.log(`Raw note status: ${result.rawStatus} (mode: ${result.rawWriteMode})`);
  console.log(`Compile log: ${result.logFile}`);

  for (const entry of result.results) {
    if (entry.path) {
      console.log(`- ${entry.action}: ${entry.path} (${entry.mode})`);
    } else {
      console.log(`- ${entry.action}: ${entry.title}`);
    }
  }
}

await main();
