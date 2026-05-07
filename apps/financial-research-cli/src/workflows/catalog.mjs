import { listCommandCatalog } from "../commandCatalog.mjs";

export const catalogCommand = {
  name: "catalog",
  script: "builtin:catalog",
  wrapper: "builtin",
  isBuiltin: true,
  description: "List supported financial-research CLI commands.",
  validateOptions() {
    return "";
  },
  buildArgs() {
    return [];
  },
  executeLocal({ commands }) {
    return {
      status: "ok",
      workflow_kind: "command_catalog",
      commands: listCommandCatalog(commands),
    };
  },
  buildSummary(payload) {
    return { command_count: Array.isArray(payload.commands) ? payload.commands.length : 0 };
  },
  renderSummary(contract) {
    return `Command: catalog\nStatus: ${contract.status}\nCommands: ${contract.summary.command_count}`;
  },
};
