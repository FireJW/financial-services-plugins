export function buildGraphifyRefreshRequest(topic, options = {}) {
  return {
    topic: String(topic || ""),
    execute: options.execute ?? true,
    buildWiki: options.buildWiki ?? true,
    includeArtifacts: options.includeArtifacts ?? false,
    buildSvg: options.buildSvg ?? false,
    noViz: options.noViz ?? false,
    syncVault: options.syncVault ?? true
  };
}

export function runGraphifyTopicRefresh(config, topic, options = {}) {
  const request = buildGraphifyRefreshRequest(topic, options);
  const runner = typeof options.runner === "function" ? options.runner : defaultRunner;
  return runner(config, request);
}

function defaultRunner() {
  throw new Error("runGraphifyTopicRefresh requires a runner");
}
