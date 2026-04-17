import { loadConfig } from "../src/config.mjs";
import { ingestRawNote } from "../src/ingest.mjs";

async function main() {
  const args = process.argv.slice(2);
  const topic = getArg(args, "topic");
  const url = getArg(args, "url") || "";
  const title = getArg(args, "title");

  if (!topic || !title) {
    printUsage();
    process.exit(1);
  }

  const body = await readBodyFromStdin();
  const config = loadConfig();
  const result = ingestRawNote(
    config,
    {
      sourceType: "web_article",
      topic,
      sourceUrl: url,
      title,
      body
    },
    {
      allowFilesystemFallback: true,
      preferCli: true
    }
  );

  console.log(`Ingested: ${result.path} (mode: ${result.mode})`);
}

function getArg(args, name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return null;
  }

  return args[index + 1];
}

async function readBodyFromStdin() {
  if (process.stdin.isTTY) {
    return "";
  }

  const chunks = [];
  for await (const chunk of process.stdin) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

function printUsage() {
  console.error("Usage: node scripts/ingest-web.mjs --topic <topic> --title <title> [--url <url>]");
  console.error("  --topic  Required topic name");
  console.error("  --title  Required note title");
  console.error("  --url    Optional source URL");
  console.error("");
  console.error("Body content is read from stdin when provided.");
}

await main();
