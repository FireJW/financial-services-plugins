export function buildTradingRefreshPlan(options = {}) {
  const includeHealthCheck = options.includeHealthCheck ?? true;
  const steps = [
    "refresh-oneil-core-notes",
    "refresh-trading-core-notes",
    "refresh-trading-extension-notes",
    "refresh-trading-synthesis-notes",
    "refresh-trading-playbook-notes",
    "refresh-trading-template-notes",
    "refresh-trading-risk-notes",
    "refresh-trading-card-notes",
    "refresh-wiki-views"
  ].map((id) => ({ id }));

  if (includeHealthCheck) {
    steps.push({ id: "health-check" });
  }

  return steps;
}
