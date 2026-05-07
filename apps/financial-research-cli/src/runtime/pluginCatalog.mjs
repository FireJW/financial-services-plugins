import path from "node:path";

import { autoresearchScriptsRoot } from "../config/defaults.mjs";

export function buildWorkflowSurface(command) {
  return {
    plugin_id: command.pluginId || "financial-analysis",
    skill_id: command.skillId || "autoresearch-info-index",
    workflow_root: command.workflowRoot || autoresearchScriptsRoot,
    script: command.script || "",
    wrapper: command.wrapper || "",
  };
}

export function wrapperPath(command) {
  const root = command.workflowRoot || autoresearchScriptsRoot;
  if (!command.wrapper || command.wrapper === "builtin") {
    return command.wrapper || "";
  }
  return path.join(root, command.wrapper);
}
