export function pushCommonOutputArgs(args, options) {
  if (options.output) {
    args.push("--output", options.output);
  }
  if (options.markdownOutput) {
    args.push("--markdown-output", options.markdownOutput);
  }
  return args;
}

export function pushArticleContentArgs(args, options, { includeOutputDir = false } = {}) {
  pushCommonOutputArgs(args, options);
  if (options.titleHint) {
    args.push("--title-hint", options.titleHint);
  }
  if (options.subtitleHint) {
    args.push("--subtitle-hint", options.subtitleHint);
  }
  if (options.angle) {
    args.push("--angle", options.angle);
  }
  if (options.tone) {
    args.push("--tone", options.tone);
  }
  if (options.targetLength) {
    args.push("--target-length", String(options.targetLength));
  }
  if (options.maxImages) {
    args.push("--max-images", String(options.maxImages));
  }
  if (options.humanSignalRatio) {
    args.push("--human-signal-ratio", String(options.humanSignalRatio));
  }
  for (const phrase of options.personalPhrases) {
    args.push("--personal-phrase", phrase);
  }
  if (options.imageStrategy) {
    args.push("--image-strategy", options.imageStrategy);
  }
  if (options.draftMode) {
    args.push("--draft-mode", options.draftMode);
  }
  if (options.headlineHookMode) {
    args.push("--headline-hook-mode", options.headlineHookMode);
  }
  if (options.headlineHookPrefixes.length > 0) {
    args.push("--headline-hook-prefixes", ...options.headlineHookPrefixes);
  }
  if (includeOutputDir && options.outputDir) {
    args.push("--output-dir", options.outputDir);
  }
  return args;
}
