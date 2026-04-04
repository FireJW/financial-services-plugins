import fs from "node:fs";
import { loadConfig } from "../src/config.mjs";
import { loadCodexLlmProvider, summarizeLlmProvider } from "../src/codex-config.mjs";
import { resolveObsidianEnvironment } from "../src/obsidian-cli.mjs";

const config = loadConfig();
const env = resolveObsidianEnvironment(config);
const providerCheck = resolveProviderCheck();

const checks = [
  {
    label: "Vault path exists",
    ok: fs.existsSync(config.vaultPath),
    detail: config.vaultPath
  },
  {
    label: "Machine root configured",
    ok: typeof config.machineRoot === "string" && config.machineRoot.length > 0,
    detail: config.machineRoot
  },
  {
    label: "Desktop app candidate configured",
    ok: Boolean(env.exePath),
    detail: env.exePath ?? "not configured"
  },
  {
    label: "Obsidian CLI registered",
    ok: Boolean(env.cliCommand),
    detail: env.cliCommand ?? "not found"
  },
  {
    label: "Codex LLM provider ready",
    ok: providerCheck.ok,
    detail: providerCheck.detail
  }
];

console.log("Obsidian KB Local doctor\n");
for (const check of checks) {
  console.log(`[${check.ok ? "OK" : "FAIL"}] ${check.label}: ${check.detail}`);
}

if (!env.cliCommand) {
  if (env.exePath) {
    console.log("\nNote:");
    console.log("Desktop app path is configured. The remaining blocker is CLI registration.");
  }

  console.log("\nNext step:");
  console.log("1. 打开 Obsidian");
  console.log("2. 进入 Settings -> General");
  console.log("3. 启用并注册 Command line interface");
  console.log("4. 重新打开终端，再运行 cmd /c npm run doctor");
}

const failed = checks.some((check) => !check.ok);
process.exit(failed ? 1 : 0);

function resolveProviderCheck() {
  try {
    const provider = loadCodexLlmProvider({
      requireApiKey: false
    });
    const keyState = provider.requiresOpenAiAuth
      ? provider.apiKey
        ? "api-key:present"
        : "api-key:missing"
      : "api-key:not-required";
    return {
      ok: provider.requiresOpenAiAuth ? Boolean(provider.apiKey) : true,
      detail: `${summarizeLlmProvider(provider)} (${keyState})`
    };
  } catch (error) {
    return {
      ok: false,
      detail: error instanceof Error ? error.message : String(error)
    };
  }
}
