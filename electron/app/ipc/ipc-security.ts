import type {
    BrowserWindow,
    IpcMainInvokeEvent,
} from "electron";

type MainWindowGetter = () => BrowserWindow | undefined;

export function createTrustedIpcSenderValidator(
    getMainWindow: MainWindowGetter,
    expectedAppOrigin: string,
): (event: IpcMainInvokeEvent) => void {
    let expectedOrigin: string;

    try {
        const parsed = new URL(expectedAppOrigin);

        if (
            !["http:", "https:"].includes(parsed.protocol) ||
            parsed.username ||
            parsed.password
        ) {
            throw new Error("Invalid application origin");
        }

        expectedOrigin = parsed.origin;
    } catch {
        throw new Error(
            "Cannot initialize IPC security: invalid application origin.",
        );
    }

    return (event: IpcMainInvokeEvent): void => {
        const mainWindow = getMainWindow();

        if (
            !mainWindow ||
            mainWindow.isDestroyed() ||
            mainWindow.webContents.isDestroyed() ||
            event.sender !== mainWindow.webContents
        ) {
            throw new Error("Unauthorized IPC sender.");
        }

        const frame = event.senderFrame;

        if (
            !frame ||
            frame !== event.sender.mainFrame
        ) {
            throw new Error("Unauthorized IPC frame.");
        }

        try {
            const senderOrigin = new URL(frame.url).origin;

            if (senderOrigin !== expectedOrigin) {
                throw new Error("Unauthorized IPC origin.");
            }
        } catch {
            throw new Error("Unauthorized IPC origin.");
        }
    };
}