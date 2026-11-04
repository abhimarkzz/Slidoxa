
export type ExportFormat = "pdf" | "pptx";

export type ExportRequestResult =
  | {
      success: true;
      id: string;
      title: string;
      format: ExportFormat;
    }
  | {
      success: false;
    };

export function validateExportRequest(
  id: unknown,
  title: unknown,
  format: unknown,
): ExportRequestResult {
  if (
    typeof id !== "string" ||
    typeof title !== "string" ||
    (format !== "pdf" && format !== "pptx")
  ) {
    return { success: false };
  }

  const validatedId = id.trim();
  const validatedTitle = title.trim();

  if (
    !validatedId ||
    validatedId.length > 256 ||
    !validatedTitle ||
    validatedTitle.length > 200
  ) {
    return { success: false };
  }

  return {
    success: true,
    id: validatedId,
    title: validatedTitle,
    format,
  };
}
