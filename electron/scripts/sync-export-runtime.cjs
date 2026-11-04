/** Copy the architecture-independent export-core runtime into Electron resources. */
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const electronRoot = path.join(__dirname, "..");
const repoRoot = path.join(electronRoot, "..");
const sourceRoot = path.join(repoRoot, "presentation-export");
const targetRoot = path.join(electronRoot, "resources", "export");
const rootSyncScript = path.join(repoRoot, "scripts", "sync-presentation-export.cjs");
const { validateExportRuntime } = require(rootSyncScript);
const packageJson = JSON.parse(
  fs.readFileSync(path.join(electronRoot, "package.json"), "utf8"),
);
const expectedVersion = String(packageJson.exportVersion || "").replace(/^v/, "");
const cliArgs = new Set(process.argv.slice(2));

function rebaseAbsoluteSymlinks(targetRoot, sourceRoot) {
  // fs.cpSync preserves symlink targets verbatim. Absolute links that point
  // inside the source tree become machine-specific in the copy, so rewrite
  // them to relative paths within targetRoot.
  const sourcePrefix = path.resolve(sourceRoot) + path.sep;
  const resolvedSourceRoot = path.resolve(sourceRoot);
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isSymbolicLink()) {
        const target = fs.readlinkSync(full);
        if (!path.isAbsolute(target)) continue;
        if (target !== resolvedSourceRoot && !target.startsWith(sourcePrefix)) continue;
        const relFromSource = path.relative(resolvedSourceRoot, target);
        const rebased = path.join(targetRoot, relFromSource);
        const newTarget = path.relative(path.dirname(full), rebased);
        fs.unlinkSync(full);
        fs.symlinkSync(newTarget, full);
      } else if (entry.isDirectory()) {
        walk(full);
      }
    }
  };
  walk(targetRoot);
}

function installedVersion(root) {
  const packagePath = path.join(
    root,
    "node_modules",
    "@presenton",
    "export-core",
    "package.json",
  );
  const runnerPath = path.join(root, "runner.mjs");
  if (!fs.existsSync(packagePath) || !fs.existsSync(runnerPath)) return null;
  try {
    return JSON.parse(fs.readFileSync(packagePath, "utf8")).version || null;
  } catch {
    return null;
  }
}

function validateTarget(expected = expectedVersion) {
  const version = installedVersion(targetRoot);
  if (version !== expected) {
    throw new Error(
      `Expected export-core ${expected} in Electron resources, found ${version || "nothing"}.`,
    );
  }
  const sharpRuntime = validateExportRuntime(targetRoot);
  if (!sharpRuntime.ok) {
    throw new Error(`Invalid Electron export dependencies: ${sharpRuntime.reason}`);
  }
  return version;
}

function main() {
  if (cliArgs.has("--check-only")) {
    console.log(`[export-runtime] OK (${validateTarget()})`);
    return;
  }

  const syncArgs = [];
  if (cliArgs.has("--force")) syncArgs.push("--force");
  if (cliArgs.has("--allow-version-override")) {
    syncArgs.push("--allow-version-override");
  }
  execFileSync(process.execPath, [rootSyncScript, ...syncArgs], {
    cwd: repoRoot,
    env: process.env,
    stdio: "inherit",
  });

  fs.rmSync(targetRoot, { recursive: true, force: true });
  fs.mkdirSync(path.dirname(targetRoot), { recursive: true });
  fs.cpSync(sourceRoot, targetRoot, { recursive: true, force: true });
  rebaseAbsoluteSymlinks(targetRoot, sourceRoot);
  const sourceVersion = installedVersion(sourceRoot);
  if (!sourceVersion) {
    throw new Error("The synced export-core package is missing from presentation-export.");
  }
  console.log(`[export-runtime] Installed export-core ${validateTarget(sourceVersion)}`);
}

try {
  main();
} catch (error) {
  console.error(`[export-runtime] ${error.message}`);
  process.exit(1);
}
