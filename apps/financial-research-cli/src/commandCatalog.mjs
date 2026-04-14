import { buildWorkflowSurface } from "./runtime/pluginCatalog.mjs";

function getExecutionKind(command) {
  if (command.isBuiltin) {
    return "builtin";
  }
  if (typeof command.resolveDelegate === "function") {
    return "delegated";
  }
  return "wrapper";
}

export function listCommandCatalog(commands) {
  return Object.values(commands)
    .map((command) => ({
      name: command.name,
      description: command.description,
      execution_kind: getExecutionKind(command),
      workflow_surface: buildWorkflowSurface(command),
    }))
    .sort((left, right) => left.name.localeCompare(right.name));
}
