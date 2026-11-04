
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const test = require("node:test");

const {
  resolveTrustedExportFilePath,
} = require("../app_dist/utils/export-file-security");

let root;
let appData;
let exportsDirectory;
let userDirectory;

test.before(() => {
  root = fs.mkdtempSync(path.join(os.tmpdir(), "presenton-export-security-"));
  appData = path.join(root, "app-data");
  exportsDirectory = path.join(appData, "exports");
  userDirectory = path.join(exportsDirectory, "users", "test-user");

  fs.mkdirSync(userDirectory, { recursive: true });
});

test.after(() => {
  fs.rmSync(root, { recursive: true, force: true });
});

test("accepts a valid PDF export", async () => {
  const file = path.join(exportsDirectory, "presentation.pdf");
  fs.writeFileSync(file, "pdf");

  assert.equal(
    await resolveTrustedExportFilePath(
      { path: file },
      appData,
      "pdf",
    ),
    fs.realpathSync(file),
  );
});

test("accepts a valid user-specific PPTX export", async () => {
  const file = path.join(userDirectory, "presentation.pptx");
  fs.writeFileSync(file, "pptx");

  assert.equal(
    await resolveTrustedExportFilePath(
      { path: file },
      appData,
      "pptx",
    ),
    fs.realpathSync(file),
  );
});

test("accepts a relative path inside app data exports", async () => {
  const file = path.join(exportsDirectory, "relative.pdf");
  fs.writeFileSync(file, "pdf");

  assert.equal(
    await resolveTrustedExportFilePath(
      { path: path.relative(appData, file) },
      appData,
      "pdf",
    ),
    fs.realpathSync(file),
  );
});

test("accepts a file URL inside exports", async () => {
  const file = path.join(exportsDirectory, "url.pdf");
  fs.writeFileSync(file, "pdf");

  assert.equal(
    await resolveTrustedExportFilePath(
      { url: pathToFileURL(file).href },
      appData,
      "pdf",
    ),
    fs.realpathSync(file),
  );
});

test("rejects paths outside exports", async () => {
  const file = path.join(root, "private.pdf");
  fs.writeFileSync(file, "private");

  await assert.rejects(
    resolveTrustedExportFilePath({ path: file }, appData, "pdf"),
    /outside the permitted exports directory/,
  );
});

test("rejects traversal paths", async () => {
  const file = path.join(root, "outside.pdf");
  fs.writeFileSync(file, "private");

  await assert.rejects(
    resolveTrustedExportFilePath(
      { path: path.relative(appData, file) },
      appData,
      "pdf",
    ),
    /outside the permitted exports directory/,
  );
});

test("rejects symbolic links to files outside exports", async (t) => {
  const outside = path.join(root, "outside.pdf");
  const link = path.join(exportsDirectory, "linked.pdf");

  fs.writeFileSync(outside, "private");

  try {
    fs.symlinkSync(outside, link);
  } catch (error) {
    if (["EPERM", "EACCES", "ENOTSUP"].includes(error.code)) {
      return t.skip("Symbolic links are unavailable in this environment");
    }
    throw error;
  }

  await assert.rejects(
    resolveTrustedExportFilePath({ path: link }, appData, "pdf"),
    /regular, non-symlink file/,
  );
});

test("rejects directories", async () => {
  const directory = path.join(exportsDirectory, "directory.pdf");
  fs.mkdirSync(directory);

  await assert.rejects(
    resolveTrustedExportFilePath({ path: directory }, appData, "pdf"),
    /regular, non-symlink file/,
  );
});

test("rejects missing files", async () => {
  const missing = path.join(exportsDirectory, "missing.pdf");

  await assert.rejects(
    resolveTrustedExportFilePath({ path: missing }, appData, "pdf"),
  );
});

test("rejects an extension that does not match the requested format", async () => {
  const file = path.join(exportsDirectory, "wrong-format.pptx");
  fs.writeFileSync(file, "pptx");

  await assert.rejects(
    resolveTrustedExportFilePath({ path: file }, appData, "pdf"),
    /\.pdf extension/,
  );
});

test("rejects invalid response objects", async () => {
  assert.equal(
    await resolveTrustedExportFilePath(null, appData, "pdf"),
    null,
  );

  assert.equal(
    await resolveTrustedExportFilePath([], appData, "pdf"),
    null,
  );

  assert.equal(
    await resolveTrustedExportFilePath({}, appData, "pdf"),
    null,
  );
});
