
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const { moveExportFile } = require("../app_dist/utils/export-file-transfer");

let root;
let sourceDirectory;
let destinationDirectory;

test.beforeEach(() => {
    root = fs.mkdtempSync(path.join(os.tmpdir(), "slidoxa-export-transfer-"));
    sourceDirectory = path.join(root, "source");
    destinationDirectory = path.join(root, "downloads");

    fs.mkdirSync(sourceDirectory);
    fs.mkdirSync(destinationDirectory);
});

test.afterEach(() => {
    fs.rmSync(root, { recursive: true, force: true });
});

test("moves an export into the destination directory", async () => {
    const source = path.join(sourceDirectory, "report.pdf");
    const destination = path.join(destinationDirectory, "report.pdf");

    fs.writeFileSync(source, "PDF CONTENT");

    assert.equal(await moveExportFile(source, destination), destination);
    assert.equal(fs.readFileSync(destination, "utf8"), "PDF CONTENT");
    assert.equal(fs.existsSync(source), false);
});

test("preserves an existing download and creates a numbered filename", async () => {
    const source = path.join(sourceDirectory, "report.pdf");
    const destination = path.join(destinationDirectory, "report.pdf");
    const numbered = path.join(destinationDirectory, "report (1).pdf");

    fs.writeFileSync(source, "NEW PDF");
    fs.writeFileSync(destination, "EXISTING PDF");

    assert.equal(await moveExportFile(source, destination), numbered);
    assert.equal(fs.readFileSync(destination, "utf8"), "EXISTING PDF");
    assert.equal(fs.readFileSync(numbered, "utf8"), "NEW PDF");
    assert.equal(fs.existsSync(source), false);
});

test("uses the next available numbered filename", async () => {
    const source = path.join(sourceDirectory, "report.pdf");
    const destination = path.join(destinationDirectory, "report.pdf");
    const first = path.join(destinationDirectory, "report (1).pdf");
    const second = path.join(destinationDirectory, "report (2).pdf");

    fs.writeFileSync(source, "NEW PDF");
    fs.writeFileSync(destination, "ORIGINAL");
    fs.writeFileSync(first, "FIRST");

    assert.equal(await moveExportFile(source, destination), second);
    assert.equal(fs.readFileSync(second, "utf8"), "NEW PDF");
    assert.equal(fs.readFileSync(first, "utf8"), "FIRST");
});

test("does not create a destination when the source is missing", async () => {
    const source = path.join(sourceDirectory, "missing.pdf");
    const destination = path.join(destinationDirectory, "missing.pdf");

    await assert.rejects(moveExportFile(source, destination));
    assert.equal(fs.existsSync(destination), false);
});
