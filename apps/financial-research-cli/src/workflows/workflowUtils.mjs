export function requireInput(commandName, options) {
  return options.input ? "" : `Missing required --input <path> for ${commandName}.`;
}

export function pushOutputArgs(args, options, { markdown = true, outputDir = false } = {}) {
  if (options.output) {
    args.push("--output", options.output);
  }
  if (markdown && options.markdownOutput) {
    args.push("--markdown-output", options.markdownOutput);
  }
  if (outputDir && options.outputDir) {
    args.push("--output-dir", options.outputDir);
  }
  return args;
}
