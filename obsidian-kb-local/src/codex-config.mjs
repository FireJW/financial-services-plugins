import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1";

export function resolveCodexHome(options = {}) {
  const env = options.env ?? process.env;
  const home = options.homedir ?? os.homedir();
  const configuredHome = firstNonEmptyString(env.CODEX_HOME);
  return path.resolve(configuredHome || path.join(home, ".codex"));
}

export function getCodexPaths(options = {}) {
  const env = options.env ?? process.env;
  const codexHome = options.codexHome || resolveCodexHome(options);

  return {
    codexHome,
    configPath: path.resolve(
      firstNonEmptyString(env.CODEX_CONFIG_PATH) || path.join(codexHome, "config.toml")
    ),
    authPath: path.resolve(
      firstNonEmptyString(env.CODEX_AUTH_PATH) || path.join(codexHome, "auth.json")
    )
  };
}

export function parseTomlConfig(input) {
  const root = {};
  let currentTarget = root;

  for (const rawLine of String(input ?? "").split(/\r?\n/)) {
    const line = stripTomlComment(rawLine).trim();
    if (!line) {
      continue;
    }

    const sectionMatch = line.match(/^\[([^\]]+)\]$/);
    if (sectionMatch) {
      currentTarget = ensureObjectPath(root, sectionMatch[1].split(".").map((part) => part.trim()));
      continue;
    }

    const keyValueMatch = line.match(/^([A-Za-z0-9_.-]+)\s*=\s*(.+)$/);
    if (!keyValueMatch) {
      continue;
    }

    currentTarget[keyValueMatch[1]] = parseTomlValue(keyValueMatch[2].trim());
  }

  return root;
}

export function loadCodexLlmProvider(options = {}) {
  const env = options.env ?? process.env;
  const requireApiKey = options.requireApiKey !== false;
  const { codexHome, configPath, authPath } = getCodexPaths({
    ...options,
    env
  });

  const configExists = fs.existsSync(configPath);
  if (!configExists && !hasEnvironmentProviderOverride(env)) {
    throw new Error(`Missing Codex config.toml: ${configPath}`);
  }

  const parsedConfig = configExists
    ? parseTomlConfig(fs.readFileSync(configPath, "utf8"))
    : {};
  const providerConfig = resolveProviderConfig(parsedConfig, env);
  const auth = loadOpenAiAuthDetails(authPath, env);

  if (
    providerConfig.requiresOpenAiAuth &&
    requireApiKey &&
    !auth.apiKey &&
    !auth.canUseChatGptSession
  ) {
    throw new Error(
      `LLM provider requires OPENAI_API_KEY, but no key was found in env or ${authPath}`
    );
  }

  return {
    codexHome,
    configPath,
    authPath,
    providerName: providerConfig.providerName,
    model: providerConfig.model,
    baseUrl: providerConfig.baseUrl,
    wireApi: providerConfig.wireApi,
    reasoningEffort: providerConfig.reasoningEffort,
    requiresOpenAiAuth: providerConfig.requiresOpenAiAuth,
    disableResponseStorage: providerConfig.disableResponseStorage,
    apiKey: auth.apiKey,
    authMode: auth.authMode,
    canUseChatGptSession: auth.canUseChatGptSession
  };
}

export function summarizeLlmProvider(provider) {
  const parts = [
    provider.providerName || "openai",
    provider.model || "unknown-model",
    provider.wireApi || "unknown-wire-api",
    provider.baseUrl || DEFAULT_OPENAI_BASE_URL
  ];
  return parts.join(" | ");
}

export function describeCodexProviderRoute(provider = {}) {
  const authMode = provider.authMode || (provider.apiKey ? "api_key" : "api_key");
  const flags = [
    `route:${providerRoute(provider)}`,
    `auth-mode:${authMode}`,
    provider.requiresOpenAiAuth === false
      ? "api-key:not-required"
      : provider.apiKey
        ? "api-key:present"
        : "api-key:missing"
  ];
  const canUseChatGptFallback =
    provider.providerName === "openai" &&
    authMode === "chatgpt" &&
    provider.canUseChatGptSession === true &&
    !provider.apiKey;

  if (provider.requiresOpenAiAuth === false || provider.apiKey || canUseChatGptFallback) {
    return {
      ok: true,
      route: canUseChatGptFallback ? "codex-exec-fallback" : "direct",
      flags: canUseChatGptFallback
        ? ["route:codex-exec-fallback", `auth-mode:${authMode}`, "api-key:missing"]
        : flags
    };
  }

  if (authMode === "chatgpt" && provider.providerName !== "openai") {
    flags.push("chatgpt-session:openai-only");
  }

  return {
    ok: false,
    route: "blocked",
    flags: flags.map((flag) => (flag.startsWith("route:") ? "route:blocked" : flag))
  };
}

export function formatCodexProviderRouteDetail(provider = {}) {
  const route = describeCodexProviderRoute(provider);
  return `${summarizeLlmProvider(provider)} (${route.flags.join(", ")})`;
}

function resolveProviderConfig(parsedConfig, env) {
  const configuredProviders = parsedConfig.model_providers;
  const providers =
    configuredProviders && typeof configuredProviders === "object" ? configuredProviders : {};
  const selectedProviderName =
    firstNonEmptyString(env.CODEX_MODEL_PROVIDER) ||
    firstNonEmptyString(parsedConfig.model_provider) ||
    "openai";
  const selectedProvider =
    providers[selectedProviderName] && typeof providers[selectedProviderName] === "object"
      ? providers[selectedProviderName]
      : {};

  const model =
    firstNonEmptyString(env.OPENAI_MODEL) ||
    firstNonEmptyString(env.CODEX_MODEL) ||
    firstNonEmptyString(parsedConfig.model) ||
    "gpt-5.4";
  const baseUrl = normalizeBaseUrl(
    firstNonEmptyString(env.OPENAI_BASE_URL) ||
      firstNonEmptyString(env.CODEX_BASE_URL) ||
      firstNonEmptyString(selectedProvider.base_url) ||
      DEFAULT_OPENAI_BASE_URL
  );
  const wireApi =
    firstNonEmptyString(env.CODEX_WIRE_API) ||
    firstNonEmptyString(selectedProvider.wire_api) ||
    "responses";
  const reasoningEffort =
    firstNonEmptyString(env.CODEX_REASONING_EFFORT) ||
    firstNonEmptyString(parsedConfig.model_reasoning_effort) ||
    "";
  const requiresOpenAiAuth = parseBooleanOverride(
    env.CODEX_REQUIRES_OPENAI_AUTH,
    selectedProvider.requires_openai_auth,
    true
  );
  const disableResponseStorage = parseBooleanOverride(
    env.CODEX_DISABLE_RESPONSE_STORAGE,
    parsedConfig.disable_response_storage,
    true
  );

  return {
    providerName: selectedProviderName,
    model,
    baseUrl,
    wireApi,
    reasoningEffort,
    requiresOpenAiAuth,
    disableResponseStorage
  };
}

function hasEnvironmentProviderOverride(env) {
  return Boolean(
    firstNonEmptyString(env.OPENAI_API_KEY) ||
      firstNonEmptyString(env.OPENAI_BASE_URL) ||
      firstNonEmptyString(env.OPENAI_MODEL)
  );
}

function loadOpenAiAuthDetails(authPath, env) {
  const envKey = firstNonEmptyString(env.OPENAI_API_KEY);
  if (envKey) {
    return {
      apiKey: envKey,
      authMode: "api_key",
      canUseChatGptSession: false
    };
  }

  if (!fs.existsSync(authPath)) {
    return {
      apiKey: null,
      authMode: "api_key",
      canUseChatGptSession: false
    };
  }

  const auth = JSON.parse(fs.readFileSync(authPath, "utf8"));
  const apiKey = firstNonEmptyString(auth.OPENAI_API_KEY) || null;
  const authMode = firstNonEmptyString(auth.auth_mode) || (apiKey ? "api_key" : "api_key");
  const canUseChatGptSession =
    authMode === "chatgpt" &&
    Boolean(auth.tokens && typeof auth.tokens === "object" && firstNonEmptyString(auth.tokens.access_token));
  return {
    apiKey,
    authMode,
    canUseChatGptSession
  };
}

function providerRoute(provider) {
  if (
    provider.providerName === "openai" &&
    provider.authMode === "chatgpt" &&
    provider.canUseChatGptSession === true &&
    !provider.apiKey
  ) {
    return "codex-exec-fallback";
  }
  if (provider.requiresOpenAiAuth !== false && !provider.apiKey) {
    return "blocked";
  }
  return "direct";
}

function normalizeBaseUrl(input) {
  const trimmed = String(input ?? "").trim();
  if (!trimmed) {
    return DEFAULT_OPENAI_BASE_URL;
  }
  return trimmed.replace(/\/+$/, "");
}

function firstNonEmptyString(value) {
  return typeof value === "string" && value.trim() !== "" ? value.trim() : "";
}

function parseBooleanOverride(candidate, fallback, defaultValue) {
  if (typeof candidate === "string") {
    const normalized = candidate.trim().toLowerCase();
    if (normalized === "true") {
      return true;
    }
    if (normalized === "false") {
      return false;
    }
  }

  if (typeof fallback === "boolean") {
    return fallback;
  }

  return defaultValue;
}

function stripTomlComment(line) {
  let inString = false;
  let quote = "";
  let result = "";

  for (let index = 0; index < line.length; index += 1) {
    const character = line[index];
    const previous = index > 0 ? line[index - 1] : "";

    if ((character === '"' || character === "'") && previous !== "\\") {
      if (!inString) {
        inString = true;
        quote = character;
      } else if (quote === character) {
        inString = false;
        quote = "";
      }
    }

    if (character === "#" && !inString) {
      break;
    }

    result += character;
  }

  return result;
}

function ensureObjectPath(root, parts) {
  let current = root;
  for (const part of parts) {
    if (!part) {
      continue;
    }
    if (!current[part] || typeof current[part] !== "object" || Array.isArray(current[part])) {
      current[part] = {};
    }
    current = current[part];
  }
  return current;
}

function parseTomlValue(value) {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return parseTomlString(value);
  }

  if (value.startsWith("[") && value.endsWith("]")) {
    return splitTomlArray(value.slice(1, -1)).map((entry) => parseTomlValue(entry));
  }

  if (value === "true") {
    return true;
  }

  if (value === "false") {
    return false;
  }

  if (/^-?\d+$/.test(value)) {
    return Number.parseInt(value, 10);
  }

  if (/^-?\d+\.\d+$/.test(value)) {
    return Number.parseFloat(value);
  }

  return value;
}

function parseTomlString(value) {
  if (value.startsWith('"')) {
    return JSON.parse(value);
  }

  return value.slice(1, -1);
}

function splitTomlArray(content) {
  const values = [];
  let current = "";
  let inString = false;
  let quote = "";

  for (let index = 0; index < content.length; index += 1) {
    const character = content[index];
    const previous = index > 0 ? content[index - 1] : "";

    if ((character === '"' || character === "'") && previous !== "\\") {
      if (!inString) {
        inString = true;
        quote = character;
      } else if (quote === character) {
        inString = false;
        quote = "";
      }
    }

    if (character === "," && !inString) {
      pushTomlArrayEntry(values, current);
      current = "";
      continue;
    }

    current += character;
  }

  pushTomlArrayEntry(values, current);
  return values;
}

function pushTomlArrayEntry(values, entry) {
  const trimmed = entry.trim();
  if (trimmed) {
    values.push(trimmed);
  }
}
