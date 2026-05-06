import { buildWorkflowSurface, wrapperPath } from "../runtime/pluginCatalog.mjs";

export function buildCliContract(commandName, payload, options, plan, command) {
  const summary = typeof command.buildSummary === "function" ? command.buildSummary(payload) : {};
  return {
    cli_command: commandName,
    status: payload.status || "ok",
    workflow_kind: payload.workflow_kind || commandName.replaceAll("-", "_"),
    input_path: options.input || options.file || options.basePublishResult || "",
    plugin_surface: buildWorkflowSurface(command),
    execution_target: {
      script: command.script || "",
      wrapper: plan?.wrapper || wrapperPath(command),
      args: plan?.args || command.buildArgs(options),
    },
    summary,
    result: payload,
  };
}
