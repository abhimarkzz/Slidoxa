
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

type ExportFormat = "pdf" | "pptx";

interface ExportResponse {
  path?: unknown;
  url?: unknown;
}

function isInsideDirectory(root: string, candidate: string): boolean {
  const relative = path.relative(root, candidate);

  return (
    relative !== "" &&
    relative !== ".." &&
    !relative.startsWith(`..${path.sep}`) &&
    !path.isAbsolute(relative)
  );
}

function getCandidatePath(
  response: ExportResponse,
  appDataDirectory: string,
): string | null {
  if (typeof response.path === "string" && response.path.trim()) {
    return path.isAbsolute(response.path)
      ? path.resolve(response.path)
      : path.resolve(appDataDirectory, response.path);
  }

  if (typeof response.url === "string") {
    try {
      const parsed = new URL(response.url);

      if (parsed.protocol !== "file:") {
        return null;
      }

      return path.resolve(fileURLToPath(parsed));
    } catch {
      return null;
    }
  }

  return null;
}

export async function resolveTrustedExportFilePath(
  response: unknown,
  appDataDirectory: string,
  format: ExportFormat,
): Promise<string | null> {
  if (!response || typeof response !== "object" || Array.isArray(response)) {
    return null;
  }

  if (format !== "pdf" && format !== "pptx") {
    return null;
  }

  const candidate = getCandidatePath(
    response as ExportResponse,
    appDataDirectory,
  );

  if (!candidate) {
    return null;
  }

  const exportsDirectory = await fs.realpath(
    path.join(appDataDirectory, "exports"),
  );

  // Reject a symbolic link at the output-file location.
  const candidateStats = await fs.lstat(candidate);

  if (candidateStats.isSymbolicLink() || !candidateStats.isFile()) {
    throw new Error("Export output must be a regular, non-symlink file.");
  }

  // Resolve parent-directory symlinks before checking containment.
  const resolvedCandidate = await fs.realpath(candidate);

  if (!isInsideDirectory(exportsDirectory, resolvedCandidate)) {
    throw new Error("Export output is outside the permitted exports directory.");
  }

  const expectedExtension = `.${format}`;
  if (path.extname(resolvedCandidate).toLowerCase() !== expectedExtension) {
    throw new Error(`Export output must have the ${expectedExtension} extension.`);
  }

  return resolvedCandidate;
}
