import { contextBridge, ipcRenderer } from 'electron';

contextBridge.exposeInMainWorld('env', {
  NEXT_PUBLIC_FAST_API: process.env.NEXT_PUBLIC_FAST_API || '',
  APP_VERSION: process.env.APP_VERSION || '',
  DISABLE_AUTH: process.env.DISABLE_AUTH || '',
  PRESENTON_ELECTRON: process.env.PRESENTON_ELECTRON || '',
});


contextBridge.exposeInMainWorld('electron', {
  exportPresentation: (id: string, title: string, format: "pptx" | "pdf") =>
    ipcRenderer.invoke("export-presentation", id, title, format),
  readFile: (filePath: string) => ipcRenderer.invoke("read-file", filePath),
});
