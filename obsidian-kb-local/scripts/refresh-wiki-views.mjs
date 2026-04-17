import { loadConfig } from "../src/config.mjs";
import { refreshWikiViews } from "../src/wiki-views.mjs";

const config = loadConfig();
const args = process.argv.slice(2);
const forceCli = args.includes("--force-cli");
const allowFilesystemFallback = !forceCli;
const cliTimeoutIndex = args.indexOf("--cli-timeout-ms");
const cliRunTimeoutMs =
  cliTimeoutIndex >= 0 && Number.isFinite(Number(args[cliTimeoutIndex + 1]))
    ? Number(args[cliTimeoutIndex + 1])
    : undefined;

const results = refreshWikiViews(config, {
  allowFilesystemFallback,
  preferCli: true,
  cliRunTimeoutMs
});

for (const result of results) {
  console.log(`Wrote ${result.path} via ${result.mode}`);
}
