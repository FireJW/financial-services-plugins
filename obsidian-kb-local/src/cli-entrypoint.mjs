import path from "node:path";
import { pathToFileURL } from "node:url";

export function isCliEntrypoint(moduleUrl, argvPath = process.argv[1]) {
  if (!moduleUrl || !argvPath) {
    return false;
  }

  return pathToFileURL(path.resolve(argvPath)).href === moduleUrl;
}
