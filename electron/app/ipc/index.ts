import type { BrowserWindow } from "electron";
import { setupExportHandlers } from "./export_handlers";
import { setupReadFile } from "./read_file";
import { createTrustedIpcSenderValidator } from "./ipc-security";

export function setupIpcHandlers(
  getMainWindow: () => BrowserWindow | undefined,
  expectedAppOrigin: string,
) {
  const validateIpcSender = createTrustedIpcSenderValidator(
    getMainWindow,
    expectedAppOrigin,
  );

  setupExportHandlers(validateIpcSender);
  setupReadFile(validateIpcSender);
}