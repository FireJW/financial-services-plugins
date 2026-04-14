import { appRoot } from "../config/defaults.mjs";
import { listPluginWorkflowCatalog } from "../pluginWorkflowCatalog.mjs";

export const pluginCatalogCommand = {
  name: "plugin-catalog",
  script: "builtin:plugin-catalog",
  wrapper: "builtin",
  workflowRoot: appRoot,
  pluginId: "financial-research-cli",
  skillId: "",
  isBuiltin: true,
  description: "List repo plugin commands and skills with optional plugin or query filters.",
  validateOptions() {
    return "";
  },
  buildArgs(options) {
    const args = [];
    if (options.plugin) {
      args.push("--plugin", options.plugin);
    }
    if (options.query) {
      args.push("--query", options.query);
    }
    return args;
  },
  executeLocal({ options }) {
    return {
      status: "ok",
      workflow_kind: "plugin_catalog",
      ...listPluginWorkflowCatalog({
        pluginFilter: options.plugin,
        query: options.query,
      }),
    };
  },
  buildSummary(payload) {
    return {
      plugin_filter: payload.plugin_filter || "",
      query: payload.query || "",
      plugin_count: payload.plugin_count ?? 0,
      command_count: payload.command_count ?? 0,
      skill_count: payload.skill_count ?? 0,
    };
  },
  renderSummary(contract) {
    const lines = [
      "Command: plugin-catalog",
      `Status: ${contract.status}`,
      `Workflow: ${contract.workflow_kind}`,
      `Plugin filter: ${contract.summary.plugin_filter || "none"}`,
      `Query: ${contract.summary.query || "none"}`,
      `Plugins: ${contract.summary.plugin_count}`,
      `Commands: ${contract.summary.command_count}`,
      `Skills: ${contract.summary.skill_count}`,
      "Plugins:",
    ];

    for (const plugin of contract.result.plugins || []) {
      lines.push(
        `- ${plugin.plugin_id}: ${plugin.commands.length} commands, ${plugin.skills.length} skills`,
      );
    }

    return lines.join("\n");
  },
};
