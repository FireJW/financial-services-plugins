import fs from "node:fs";
import { loadConfig } from "../src/config.mjs";
import {
  describeCodexProviderRoute,
  formatCodexProviderRouteDetail,
  loadCodexLlmProvider,
  summarizeLlmProvider
} from "../src/codex-config.mjs";
import { resolveObsidianEnvironment } from "../src/obsidian-cli.mjs";

export { describeCodexProviderRoute as describeProviderRoute };

export function parseDoctorArgs(args = []) {
  return {
    json: args.includes("--json"),
    probeProvider: args.includes("--probe-provider"),
    timeoutMs: normalizePositiveInteger(getArgFrom(args, "timeout-ms"), 240000)
  };
}

export function buildDoctorChecks(config = loadConfig()) {
  const env = resolveObsidianEnvironment(config);
  const providerCheck = resolveProviderCheck();
  return {
    env,
    checks: [
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
        label: "Obsidian command entrypoint",
        ok: Boolean(env.cliCommand),
        detail: formatCliDetail(env)
      },
      {
        label: "Codex LLM provider ready",
        ok: providerCheck.ok,
        detail: providerCheck.detail
      }
    ]
  };
}

export function runDoctor(options = {}) {
  const config = options.config || loadConfig();
  const writer = options.writer || console;
  const { env, checks } = buildDoctorChecks(config);

  writer.log("Obsidian KB Local doctor\n");
  for (const check of checks) {
    writer.log(`[${check.ok ? "OK" : "FAIL"}] ${check.label}: ${check.detail}`);
  }

  if (!env.cliCommand) {
    if (env.exePath) {
      writer.log("\nNote:");
      writer.log("Desktop app path is configured. The remaining blocker is command entrypoint detection.");
    }

    writer.log("\nNext step:");
    writer.log("1. 打开 Obsidian");
    writer.log("2. 进入 Settings -> General");
    writer.log("3. 启用并注册 Command line interface");
    writer.log("4. 重新打开终端，再运行 cmd /c npm run doctor");
  }

  return {
    ok: !checks.some((check) => !check.ok),
    checks
  };
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const result = runDoctor();
  process.exit(result.ok ? 0 : 1);
}

function resolveProviderCheck() {
  try {
    const provider = loadCodexLlmProvider({
      requireApiKey: false
    });
    const route = describeCodexProviderRoute(provider);
    return {
      ok: route.ok,
      detail: formatCodexProviderRouteDetail(provider)
    };
  } catch (error) {
    return {
      ok: false,
      detail: error instanceof Error ? error.message : String(error)
    };
  }
}

function formatCliDetail(env) {
  if (!env.cliCommand) {
    return "not found";
  }

  if (env.cliMode === "desktop-executable") {
    return `${env.cliCommand} (desktop executable fallback)`;
  }

  if (env.cliMode === "registered-shim") {
    return `${env.cliCommand} (registered shim)`;
  }

  if (env.cliMode === "path-candidate") {
    return `${env.cliCommand} (configured path candidate)`;
  }

  return env.cliCommand;
}

function getArgFrom(args, name) {
  const index = args.indexOf(`--${name}`);
  if (index === -1 || index + 1 >= args.length) {
    return undefined;
  }
  return args[index + 1];
}

function normalizePositiveInteger(value, fallback) {
  const parsed = Number.parseInt(String(value ?? ""), 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback;
}
