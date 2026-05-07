export function parseTradingPsychologyMentorArgs(args = []) {
  const parsed = {
    query: "",
    template: "",
    dryRun: false,
    execute: false,
    writeSession: false,
    contextNote: ""
  };

  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === "--query") {
      parsed.query = String(args[++index] || "");
    } else if (arg === "--template") {
      parsed.template = String(args[++index] || "");
    } else if (arg === "--context-note") {
      parsed.contextNote = String(args[++index] || "");
    } else if (arg === "--dry-run") {
      parsed.dryRun = true;
    } else if (arg === "--execute") {
      parsed.execute = true;
      parsed.dryRun = false;
    } else if (arg === "--write-session") {
      parsed.writeSession = true;
    }
  }

  if (parsed.writeSession && !parsed.execute) {
    throw new Error("--write-session requires --execute");
  }

  return parsed;
}

if (import.meta.url === `file://${process.argv[1]}`) {
  try {
    console.log(JSON.stringify(parseTradingPsychologyMentorArgs(process.argv.slice(2)), null, 2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
