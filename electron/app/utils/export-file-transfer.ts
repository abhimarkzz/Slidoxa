import fs from "node:fs/promises";
import { constants } from "node:fs";
import path from "node:path";

export async function moveExportFile(
  sourcePath: string,
  destinationPath: string,
): Promise<string> {
  const destinationDirectory = path.dirname(destinationPath);
  const extension = path.extname(destinationPath);
  const basename = path.basename(destinationPath, extension);

  await fs.mkdir(destinationDirectory, { recursive: true });

  for (let attempt = 0; attempt < 1000; attempt++) {
    const candidate =
      attempt === 0
        ? destinationPath
        : path.join(
          destinationDirectory,
          `${basename} (${attempt})${extension}`,
        );

    try {
      await fs.copyFile(
        sourcePath,
        candidate,
        // Never overwrite an existing download.
        constants.COPYFILE_EXCL,
      );

      try {
        await fs.unlink(sourcePath);
      } catch (error) {
        await fs.unlink(candidate).catch(() => { });
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
