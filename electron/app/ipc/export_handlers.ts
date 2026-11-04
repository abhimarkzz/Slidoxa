import { ipcMain } from "electron";
import {
  getAppDataDir,
  getCacheDir,
  getDownloadsDir,
  getTempDir,
  resourceBaseDir,
  isDev,
} from "../utils/constants";
import fs from "fs";
import path from "path";
import type { IpcMainInvokeEvent } from "electron";
import { showFileDownloadedDialog } from "../utils/dialog";
import { ChildProcess, spawn } from "child_process";
import { safeError, safeLog } from "../utils/safe-console";
import { addMainBreadcrumb } from "../sentry/main";
import { BoundedTextBuffer, memorySnapshotMb } from "../utils/memory";
import { destroyChildProcessStdio, terminateChildProcess } from "../utils/lifecycle";
import { killProcess } from "../utils";
import {
  isExportChromiumAvailable,
  removeBrokenExportChromiumCaches,
  resolveLaunchableExportChromiumPath,
} from "../utils/export-chromium";
import { moveExportFile } from "../utils/export-file-transfer";
import { resolveExportSpawnTarget } from "../utils/export-msix-runtime";
import { desktopCookieHeader } from "../utils/desktop-auth";
import { resolveTrustedExportFilePath } from "../utils/export-file-security";
import { validateExportRequest } from "../utils/export-request-validation";

type RuntimeCandidate = {
  command: string;
  label: string;
  useElectronRunAsNode?: boolean;
};

const activeExportProcesses = new Set<ChildProcess>();

function showFileDownloadedDialogInBackground(filePath: string): void {
  setImmediate(() => {
    void showFileDownloadedDialog(filePath).catch((error) => {
      safeError("[Export] Failed to show downloaded-file dialog:", error);
    });
  });
}

export async function stopActiveExportProcesses(): Promise<void> {
  const processes = Array.from(activeExportProcesses);
  activeExportProcesses.clear();
  await Promise.all(
    processes.map((process) =>
      terminateChildProcess(process, "Export", killProcess).catch((error) => {
        safeError("[Export] Failed to stop active export process:", error);
      }),
    ),
  );
}


export function setupExportHandlers(
  validateIpcSender: (event: IpcMainInvokeEvent) => void,
) {
  ipcMain.handle(
    "export-presentation",
    async (
      event,
      id: unknown,
      title: unknown,
      exportAs: unknown,
    ) => {
      // Verify the IPC sender before processing any arguments.
      validateIpcSender(event);

      // Validate all renderer-controlled arguments.
      const validation = validateExportRequest(id, title, exportAs);

      if (!validation.success) {
        return {
          success: false,
          message: "Invalid export request.",
        };
      }

      // Only use validated values from this point onwards.
      const validatedId = validation.id;
      const validatedTitle = validation.title;
      const validatedFormat = validation.format;

      let exportTempDir: string | undefined;

      try {
        await removeBrokenExportChromiumCaches();

        if (!isExportChromiumAvailable()) {
          return {
            success: false,
            message: isDev
              ? "The export runtime is missing. Run npm run setup:desktop-runtime in the electron directory, then restart the desktop development app."
              : "The export browser is missing from this installation. Reinstall Presenton to restore export support.",
          };
        }

        addMainBreadcrumb(
          "export",
          "electron.ipc_export.start",
          {
            id: validatedId,
            title: validatedTitle,
            exportAs: validatedFormat,
            memory: memorySnapshotMb(),
          },
        );

        const params = new URLSearchParams({
          id: validatedId,
        });

        if (process.env.NEXT_PUBLIC_FAST_API) {
          params.set(
            "fastapiUrl",
            process.env.NEXT_PUBLIC_FAST_API,
          );
        }

        const pptUrl = `${process.env.NEXT_PUBLIC_URL}/pdf-maker?${params.toString()}`;

        const exportTask = {
          type: "export",
          url: pptUrl,
          format: validatedFormat,
          title: validatedTitle,
          fastapiUrl: process.env.NEXT_PUBLIC_FAST_API,
          cookieHeader: desktopCookieHeader(),
        };

        const tempDir = getTempDir();
        const appDataDir = getAppDataDir();

        exportTempDir = await fs.promises.mkdtemp(
          path.join(tempDir, "export-"),
        );

        const exportTaskPath = path.join(
          exportTempDir,
          "export_task.json",
        );

        await fs.promises.writeFile(
          exportTaskPath,
          JSON.stringify(exportTask),
          {
            flag: "wx",
            mode: 0o600,
          },
        );

        const packagedExportRoot = path.join(
          resourceBaseDir,
          "resources",
          "export",
        );

        const packagedExportScriptPath = path.join(
          packagedExportRoot,
          "runner.mjs",
        );

        const { scriptPath: exportScriptPath } =
          await resolveExportSpawnTarget(
            packagedExportRoot,
            packagedExportScriptPath,
          );

        safeLog(
          "[Export] Spawning export task with config:",
          {
            exportAs: validatedFormat,
            id: validatedId,
            title: validatedTitle,
            pptUrl,
            exportTaskPath,
            exportScriptPath,
            NEXT_PUBLIC_URL: process.env.NEXT_PUBLIC_URL,
            NEXT_PUBLIC_FAST_API:
              process.env.NEXT_PUBLIC_FAST_API,
          },
        );

        const chromiumExecutablePath =
          await resolveLaunchableExportChromiumPath();

        if (!chromiumExecutablePath) {
          return {
            success: false,
            message:
              "Export could not prepare Chromium for this Microsoft Store install. Restart Presenton and try again.",
          };
        }

        const puppeteerTempDir = path.join(
          tempDir,
          "puppeteer",
        );

        const puppeteerCacheDir = path.join(
          getCacheDir(),
          "puppeteer",
        );

        await Promise.all([
          fs.promises.mkdir(puppeteerTempDir, {
            recursive: true,
          }),
          fs.promises.mkdir(puppeteerCacheDir, {
            recursive: true,
          }),
        ]);

        const baseExportEnv = {
          ...process.env,
          TEMP_DIRECTORY: tempDir,
          APP_DATA_DIRECTORY: appDataDir,
          NODE_ENV: "development",
          PUPPETEER_EXECUTABLE_PATH:
            chromiumExecutablePath,
          PUPPETEER_CACHE_DIR: puppeteerCacheDir,
          PUPPETEER_TMP_DIR: puppeteerTempDir,
        };

        const responsePath = exportTaskPath.replace(
          ".json",
          ".response.json",
        );

        const responseRaw =
          await runExportTaskAndReadResponse(
            exportScriptPath,
            exportTaskPath,
            responsePath,
            baseExportEnv,
          );

        const responseData: unknown = JSON.parse(responseRaw);

        const exportFilePath =
          await resolveTrustedExportFilePath(
            responseData,
            appDataDir,
            validatedFormat,
          );

        if (!exportFilePath) {
          return {
            success: false,
            message:
              "Export finished but output file was not found.",
          };
        }

        const requestedDestination = path.join(
          getDownloadsDir(),
          path.basename(exportFilePath),
        );

        const destinationPath = await moveExportFile(
          exportFilePath,
          requestedDestination,
        );

        showFileDownloadedDialogInBackground(
          destinationPath,
        );

        addMainBreadcrumb(
          "export",
          "electron.ipc_export.finish",
          {
            id: validatedId,
            exportAs: validatedFormat,
            success: true,
            memory: memorySnapshotMb(),
          },
        );

        return {
          success: true,
          message: "Export completed.",
        };
      } catch (error: any) {
        safeError(
          "[Export] Error exporting presentation:",
          error,
        );

        addMainBreadcrumb(
          "export",
          "electron.ipc_export.error",
          {
            id: validatedId,
            exportAs: validatedFormat,
            message: error?.message,
            memory: memorySnapshotMb(),
          },
        );

        return {
          success: false,
          message: error?.message ?? "Export failed.",
        };
      } finally {
        if (exportTempDir) {
          await fs.promises
            .rm(exportTempDir, {
              recursive: true,
              force: true,
            })
            .catch(() => { });
        }
      }
    },
  );
}


function getExportRuntimeCandidates(): RuntimeCandidate[] {
  const candidates: RuntimeCandidate[] = [];
  const push = (command: string | undefined, label: string, useElectronRunAsNode?: boolean) => {
    if (!command) return;
    const trimmed = command.trim();
    if (!trimmed) return;
    candidates.push({ command: trimmed, label, useElectronRunAsNode });
  };

  // Explicit overrides first.
  push(process.env.EXPORT_NODE_BINARY, "EXPORT_NODE_BINARY");
  push(process.env.NODE_BINARY, "NODE_BINARY");

  // Match the older stable export approach: `spawn("node", ...)` first.
  push("node", "node");

  // Additional system node entries.
  if (process.platform === "win32") {
    push("node.exe", "node.exe");
    push("node.cmd", "node.cmd");
  } else {
    push("/usr/bin/node", "/usr/bin/node");
    push("/usr/local/bin/node", "/usr/local/bin/node");
  }

  // Fallback: Electron runtime in Node mode.
  push(process.execPath, "process.execPath (electron-as-node)", true);

  const deduped: RuntimeCandidate[] = [];
  const seen = new Set<string>();
  for (const candidate of candidates) {
    const key = `${candidate.command}|${candidate.useElectronRunAsNode ? "electron-node" : "plain"}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push(candidate);
  }
  return deduped;
}

function isRetryableRuntimeError(error: any): boolean {
  const code = String(error?.code || "");
  // Try another runtime when binary is missing or cannot be spawned.
  return ["ENOENT", "EACCES", "EPERM", "EAGAIN"].includes(code);
}

async function runExportTaskWithRuntimeFallback(
  exportScriptPath: string,
  exportTaskPath: string,
  baseEnv: NodeJS.ProcessEnv
): Promise<void> {
  const runtimeCandidates = getExportRuntimeCandidates();
  const failures: string[] = [];

  for (const runtime of runtimeCandidates) {
    let repairedBrowserCache = false;
    while (true) {
      safeLog(`[Export] Trying runtime: ${runtime.label} -> ${runtime.command}`);
      try {
        await runExportTaskOnce(
          runtime,
          exportScriptPath,
          exportTaskPath,
          baseEnv
        );
        return;
      } catch (error: any) {
        if (!repairedBrowserCache && (await repairBrokenPuppeteerCache(error))) {
          repairedBrowserCache = true;
          safeLog(`[Export] Retrying runtime ${runtime.label} after repairing Puppeteer cache.`);
          continue;
        }

        const details = [
          `${runtime.label}: ${error?.message || "Unknown error"}`,
          error?.code ? `code=${error.code}` : "",
        ]
          .filter(Boolean)
          .join(" ");
        failures.push(details);
        safeError(`[Export] Runtime failed (${runtime.label})`, error);

        if (!isRetryableRuntimeError(error)) {
          throw error;
        }

        break;
      }
    }
  }

  throw new Error(
    `Export failed to start with all runtimes.\n${failures.map((f) => `- ${f}`).join("\n")}`
  );
}

async function runExportTaskAndReadResponse(
  exportScriptPath: string,
  exportTaskPath: string,
  responsePath: string,
  baseEnv: NodeJS.ProcessEnv
): Promise<string> {
  const maxAttempts = 2;
  let lastError: unknown;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    await runExportTaskWithRuntimeFallback(exportScriptPath, exportTaskPath, baseEnv);
    try {
      return await fs.promises.readFile(responsePath, "utf8");
    } catch (error: any) {
      if (error?.code === "ENOENT" && attempt < maxAttempts) {
        safeError(
          `[Export] Response file missing after successful export process. Retrying (${attempt}/${maxAttempts}).`,
          error
        );
        lastError = error;
        continue;
      }
      throw error;
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new Error("Export task completed without creating a response file.");
}

function extractMissingChromeFolderFromError(error: unknown): string | null {
  const message = String((error as any)?.message ?? "");
  const match = message.match(/browser folder \(([^)]+)\) exists but the executable \(([^)]+)\) is missing/i);
  if (!match) return null;
  const browserFolder = path.normalize(match[1]);
  const missingExecutablePath = path.normalize(match[2]);
  if (!browserFolder || !missingExecutablePath.startsWith(browserFolder)) return null;
  const normalized = browserFolder.toLowerCase().replace(/\\/g, "/");
  if (!normalized.includes("/.cache/puppeteer/chrome/")) return null;
  return browserFolder;
}

async function repairBrokenPuppeteerCache(error: unknown): Promise<boolean> {
  const browserFolder = extractMissingChromeFolderFromError(error);
  if (!browserFolder) return false;
  try {
    await fs.promises.rm(browserFolder, { recursive: true, force: true });
    safeLog(`[Export] Removed broken Puppeteer browser cache: ${browserFolder}`);
    return true;
  } catch (rmError) {
    safeError(`[Export] Failed to remove broken Puppeteer cache at ${browserFolder}`, rmError);
    return false;
  }
}

async function runExportTaskOnce(
  runtime: RuntimeCandidate,
  exportScriptPath: string,
  exportTaskPath: string,
  baseEnv: NodeJS.ProcessEnv
): Promise<void> {
  const runtimeEnv = {
    ...baseEnv,
    ...(runtime.useElectronRunAsNode ? { ELECTRON_RUN_AS_NODE: "1" } : {}),
  };

  const exportTaskProcess = spawn(runtime.command, [exportScriptPath, exportTaskPath], {
    stdio: ["ignore", "pipe", "pipe"],
    cwd: path.dirname(exportScriptPath),
    windowsHide: process.platform === "win32",
    env: runtimeEnv,
  });
  activeExportProcesses.add(exportTaskProcess);

  safeLog("[Export] Child process started:", {
    runtime: runtime.label,
    pid: exportTaskProcess.pid,
    memory: memorySnapshotMb(),
  });
  addMainBreadcrumb("export", "electron.export_child.start", {
    runtime: runtime.label,
    pid: exportTaskProcess.pid,
    memory: memorySnapshotMb(),
  });

  const stdoutTail = new BoundedTextBuffer();
  const stderrTail = new BoundedTextBuffer();

  const onStdoutData = (data: Buffer) => {
    const text = data.toString();
    stdoutTail.append(text);
    safeLog(`[Export] ${text}`);
  };
  const onStderrData = (data: Buffer) => {
    const text = data.toString();
    stderrTail.append(text);
    safeError(`[Export] ${text}`);
  };
  exportTaskProcess.stdout?.on("data", onStdoutData);
  exportTaskProcess.stderr?.on("data", onStderrData);

  let settled = false;
  let resolvePromise: (() => void) | null = null;
  let rejectPromise: ((error: Error) => void) | null = null;

  const cleanup = () => {
    exportTaskProcess.stdout?.removeListener("data", onStdoutData);
    exportTaskProcess.stderr?.removeListener("data", onStderrData);
    exportTaskProcess.removeListener("error", onError);
    exportTaskProcess.removeListener("close", onClose);
    activeExportProcesses.delete(exportTaskProcess);
  };

  const finish = (callback: () => void) => {
    if (settled) {
      return;
    }
    settled = true;
    cleanup();
    callback();
  };

  const onError = (error: Error) => {
    finish(() => rejectPromise?.(error));
  };

  const onClose = (code: number | null, signal: NodeJS.Signals | null) => {
    finish(() => {
      safeLog("[Export] Child process exited:", {
        runtime: runtime.label,
        pid: exportTaskProcess.pid,
        code,
        signal,
        memory: memorySnapshotMb(),
      });
      addMainBreadcrumb("export", "electron.export_child.exit", {
        runtime: runtime.label,
        pid: exportTaskProcess.pid,
        code,
        signal,
        memory: memorySnapshotMb(),
      });
      if (code === 0) {
        resolvePromise?.();
      } else {
        const stderrText = stderrTail.toString() || "(no stderr)";
        const stdoutText = stdoutTail.toString();
        const detail =
          stderrText !== "(no stderr)"
            ? stderrText
            : stdoutText
              ? `stdout: ${stdoutText}`
              : "";
        const error: NodeJS.ErrnoException = new Error(
          `Export process exited with code ${code ?? "unknown"}${signal ? ` signal ${signal}` : ""}${detail ? `. ${detail}` : ""}`
        );
        error.code = `EXIT_${code ?? "UNKNOWN"}`;
        rejectPromise?.(error);
      }
    });
  };

  try {
    await new Promise<void>((resolve, reject) => {
      resolvePromise = resolve;
      rejectPromise = reject;
      exportTaskProcess.once("error", onError);
      exportTaskProcess.once("close", onClose);
    });
  } finally {
    cleanup();
    destroyChildProcessStdio(exportTaskProcess);
  }
}




async function moveFile(sourcePath: string, destinationPath: string): Promise<string> {
  const destinationDirectory = path.dirname(destinationPath);
  const extension = path.extname(destinationPath);
  const basename = path.basename(destinationPath, extension);

  await fs.promises.mkdir(destinationDirectory, { recursive: true });

  // Exclusive creation prevents overwriting existing downloads.
  for (let attempt = 0; attempt < 1000; attempt++) {
    const candidate =
      attempt === 0
        ? destinationPath
        : path.join(
          destinationDirectory,
          `${basename} (${attempt})${extension}`,
        );

    try {
      await fs.promises.copyFile(
        sourcePath,
        candidate,
        fs.constants.COPYFILE_EXCL,
      );

      try {
        await fs.promises.unlink(sourcePath);
      } catch (error) {
        await fs.promises.unlink(candidate).catch(() => { });
        throw error;
      }

      return candidate;
    } catch (error: any) {
      if (error?.code === "EEXIST") {
        continue;
      }

      throw error;
    }
  }

  throw new Error("Unable to find an available export filename.");
}
