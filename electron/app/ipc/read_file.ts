import { ipcMain } from "electron";
import type { IpcMainInvokeEvent } from "electron";
import { readReadableLocalFile } from "../utils/readable-file-access";

export function setupReadFile(
  validateIpcSender: (event: IpcMainInvokeEvent) => void,
) {
  ipcMain.handle("read-file", async (event, filePath: unknown) => {
    validateIpcSender(event);

    try {
      const content = readReadableLocalFile(filePath);
      return { content };
    } catch (error) {
      console.error("Error reading file:", error);
      throw error;
    }
  });
}