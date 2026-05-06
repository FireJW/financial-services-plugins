const SURFACE_ALIASES = {
  x: "x-index",
  twitter: "x-index",
  "x-index": "x-index",
  reddit: "reddit-bridge",
  last30days: "last30days-bridge",
  "last30days-bridge": "last30days-bridge",
  opencli: "opencli-index",
  "opencli-index": "opencli-index",
  "agent-reach": "agent-reach-bridge",
  "agent-reach-bridge": "agent-reach-bridge",
  fieldtheory: "fieldtheory-index",
  "fieldtheory-index": "fieldtheory-index",
};

export const sourceIntakeCommand = {
  name: "source-intake",
  script: "builtin:source-intake",
  wrapper: "builtin",
  description: "Route source intake aliases to the native evidence workflow.",
  validateOptions(options) {
    const target = SURFACE_ALIASES[String(options.surface || "").toLowerCase()];
    return target ? "" : "source-intake requires --surface <x|reddit|last30days|opencli|agent-reach|fieldtheory>.";
  },
  buildArgs(options) {
    return [options.surface, options.input || options.file || options.topic || ""].filter(Boolean);
  },
  resolveDelegate(options, commands) {
    const targetName = SURFACE_ALIASES[String(options.surface || "").toLowerCase()];
    return { command: commands[targetName] };
  },
  buildSummary(payload) {
    return { routed_to: payload.routed_to || "" };
  },
  renderSummary(contract) {
    return `Command: source-intake\nStatus: ${contract.status}\nWorkflow: ${contract.workflow_kind}`;
  },
};
