export function buildPoliticalEconomyRefreshPlan(options = {}) {
  const includeHealthCheck = options.includeHealthCheck ?? true;
  const steps = [
    { id: "process-political-economy-books" },
    { id: "refresh-wiki-views" }
  ];

  if (includeHealthCheck) {
    steps.push({ id: "health-check" });
  }

  return steps;
}
