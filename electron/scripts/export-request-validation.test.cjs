
const assert = require("node:assert/strict");
const test = require("node:test");

const {
  validateExportRequest,
} = require("../app_dist/utils/export-request-validation");

test("accepts a valid PDF export request", () => {
  assert.deepEqual(
    validateExportRequest("presentation-123", "My Presentation", "pdf"),
    {
      success: true,
      id: "presentation-123",
      title: "My Presentation",
      format: "pdf",
    },
  );
});

test("accepts a valid PPTX export request", () => {
  assert.deepEqual(
    validateExportRequest("presentation-456", "My Slides", "pptx"),
    {
      success: true,
      id: "presentation-456",
      title: "My Slides",
      format: "pptx",
    },
  );
});

test("trims whitespace from ID and title", () => {
  assert.deepEqual(
    validateExportRequest("  presentation-123  ", "  My Slides  ", "pdf"),
    {
      success: true,
      id: "presentation-123",
      title: "My Slides",
      format: "pdf",
    },
  );
});

test("rejects an empty presentation ID", () => {
  assert.deepEqual(
    validateExportRequest("", "My Presentation", "pdf"),
    { success: false },
  );
});

test("rejects a whitespace-only presentation ID", () => {
  assert.deepEqual(
    validateExportRequest("   ", "My Presentation", "pdf"),
    { success: false },
  );
});

test("rejects a non-string presentation ID", () => {
  assert.deepEqual(
    validateExportRequest(123, "My Presentation", "pdf"),
    { success: false },
  );
});

test("rejects a presentation ID longer than 256 characters", () => {
  assert.deepEqual(
    validateExportRequest("a".repeat(257), "My Presentation", "pdf"),
    { success: false },
  );
});

test("rejects a non-string title", () => {
  assert.deepEqual(
    validateExportRequest("presentation-123", 123, "pdf"),
    { success: false },
  );
});

test("rejects an empty or whitespace-only title", () => {
  assert.deepEqual(
    validateExportRequest("presentation-123", "   ", "pdf"),
    { success: false },
  );
});

test("rejects a title longer than 200 characters", () => {
  assert.deepEqual(
    validateExportRequest("presentation-123", "a".repeat(201), "pdf"),
    { success: false },
  );
});

test("rejects unsupported export formats", () => {
  assert.deepEqual(
    validateExportRequest("presentation-123", "My Presentation", "html"),
    { success: false },
  );
});

test("rejects a non-string export format", () => {
  assert.deepEqual(
    validateExportRequest("presentation-123", "My Presentation", 123),
    { success: false },
  );
});
