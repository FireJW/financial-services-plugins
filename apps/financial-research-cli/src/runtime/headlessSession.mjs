import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";

import { repoRoot } from "../config/defaults.mjs";
import { buildWorkflowSurface, wrapperPath } from "./pluginCatalog.mjs";

export function buildExecutionPlan(commandName, command, options, commands = {}) {
  if (typeof command.resolveDelegate === "function") {
    const delegated = command.resolveDelegate(options, commands);
    const delegateCommand = delegated.command;
    return {
      cli_command: commandName,
      delegated_command: delegateCommand.name,
      routed_via: commandName,
      args: delegateCommand.buildArgs(options),
      wrapper: wrapperPath(delegateCommand),
      workflow_surface: buildWorkflowSurface(delegateCommand),
    };
  }

  return {
    cli_command: commandName,
    args: command.buildArgs(options),
    wrapper: wrapperPath(command),
    workflow_surface: buildWorkflowSurface(command),
  };
}

function pythonInvocation(command, plan) {
  if (!String(command.script || "").endsWith(".py")) {
    return null;
  }
  const scriptPath = path.join(plan.workflow_surface.workflow_root, command.script);
  const username = process.env.USERNAME || "rickylu";
  const candidates = [
    `D:\\Users\\${username}\\.codex\\vendor\\python312\\python.exe`,
    path.join(process.env.USERPROFILE || "", ".cache", "codex-runtimes", "codex-primary-runtime", "dependencies", "python", "python.exe"),
  ].filter(Boolean);
  const pythonExe = candidates.find((candidate) => fs.existsSync(candidate));
  if (pythonExe) {
    return { target: pythonExe, args: [scriptPath, ...plan.args] };
  }
  const pyLauncher = path.join(process.env.LOCALAPPDATA || "", "Programs", "Python", "Launcher", "py.exe");
  if (fs.existsSync(pyLauncher)) {
    return { target: pyLauncher, args: ["-3", scriptPath, ...plan.args] };
  }
  return null;
}

export function runWorkflowCommand(commandName, command, options, { spawnSyncImpl = spawnSync } = {}) {
  const plan = buildExecutionPlan(commandName, command, options);
  if (!plan.wrapper || plan.wrapper === "builtin") {
    return { ok: false, error: `Command ${commandName} is not executable through a wrapper.`, plan };
  }

  const invocation = pythonInvocation(command, plan) || { target: plan.wrapper, args: plan.args };
  const result = spawnSyncImpl(invocation.target, invocation.args, {
    cwd: repoRoot,
    encoding: "utf8",
    windowsHide: true,
    env: {
      ...process.env,
      PYTHONDONTWRITEBYTECODE: "1",
    },
  });
  if (result.error) {
    return { ok: false, error: result.error.message, plan };
  }
  if (result.status !== 0) {
    return {
      ok: false,
      error: result.stderr || result.stdout || `Command exited with status ${result.status}`,
      plan,
    };
  }

  if (!String(result.stdout || "").trim()) {
    return { ok: false, error: `Command ${commandName} produced no JSON stdout.`, plan };
  }

  try {
    return { ok: true, payload: JSON.parse(result.stdout), plan };
  } catch (error) {
    return { ok: false, error: `Could not parse JSON stdout: ${error.message}`, plan };
  }
}
