export function renderExecutionPlan(plan, asJson = false) {
  if (asJson) {
    return `${JSON.stringify({ dry_run: true, execution_plan: plan }, null, 2)}\n`;
  }
  return [
    `Command: ${plan.cli_command}`,
    `Wrapper: ${plan.wrapper || "n/a"}`,
    `Args: ${(plan.args || []).join(" ")}`,
  ].join("\n") + "\n";
}

export function renderHelp(commands) {
  const lines = ["Financial research commands:", ""];
  for (const command of Object.values(commands).sort((left, right) => left.name.localeCompare(right.name))) {
    lines.push(`- ${command.name}: ${command.description || ""}`);
  }
  return `${lines.join("\n")}\n`;
}

export function renderSummary(command, contract) {
  if (typeof command.renderSummary === "function") {
    return `${command.renderSummary(contract)}\n`;
  }
  return `${JSON.stringify(contract, null, 2)}\n`;
}
