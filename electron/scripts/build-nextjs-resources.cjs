const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const electronRoot = path.join(__dirname, "..");
const nextjsDir = path.join(electronRoot, "..", "packages", "frontend");
const outDir = path.join(electronRoot, "resources", "nextjs");
const nextBuildDir = path.join(nextjsDir, ".next-build");
const standaloneDir = path.join(nextBuildDir, "standalone");

function rm(p) {
  fs.rmSync(p, { recursive: true, force: true });
}

function cpDir(src, dest) {
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.cpSync(src, dest, { recursive: true });
}

console.log("Running shared Next.js production build for Electron…");

rm(outDir);
rm(nextBuildDir);

const npmCmd = process.platform === "win32" ? "npm.cmd" : "npm";
const build = spawnSync(npmCmd, ["run", "build"], {
  cwd: nextjsDir,
  env: {
    ...process.env,
    PRESENTON_ELECTRON_BUILD: "true",
    NEXT_PUBLIC_PRESENTON_ELECTRON_PLATFORM: process.platform,
  },
  stdio: "inherit",
  // Windows: cmd is required to run npm.cmd; without shell, spawnSync can throw EINVAL.
  shell: process.platform === "win32",
});

if (build.error) {
  console.error(build.error);
  process.exit(1);
}
if (build.status !== 0) {
  process.exit(build.status ?? 1);
}

if (!fs.existsSync(standaloneDir)) {
  console.error("Expected standalone output at:", standaloneDir);
  process.exit(1);
}

fs.mkdirSync(path.join(outDir, ".next-build"), { recursive: true });

for (const name of fs.readdirSync(standaloneDir)) {
  fs.cpSync(
    path.join(standaloneDir, name),
    path.join(outDir, name),
    { recursive: true }
  );
}

// Next.js standalone traces the application under packages/frontend after migration.
// Keep assets beside server.js and retain the legacy destination for older bundles.
const packageStandaloneDir = path.join(outDir, "packages", "frontend");
const legacyNestedStandaloneDir = path.join(outDir, "servers", "nextjs");

// The standalone trace may contain an absolute node_modules symlink back to
// the build directory. Rebase it so the packaged app uses its bundled modules.
const packageServer = path.join(packageStandaloneDir, "server.js");
const packageNodeModules = path.join(packageStandaloneDir, "node_modules");
const bundledNodeModules = path.join(legacyNestedStandaloneDir, "node_modules");

if (fs.existsSync(packageServer)) {
  if (!fs.existsSync(bundledNodeModules)) {
    throw new Error(`Bundled Next.js dependencies not found: ${bundledNodeModules}`);
  }

  let existingNodeModules;
  try {
    existingNodeModules = fs.lstatSync(packageNodeModules);
  } catch (error) {
    if (error.code !== "ENOENT") throw error;
  }

  if (existingNodeModules && !existingNodeModules.isSymbolicLink()) {
    throw new Error(
      `Refusing to replace a real node_modules directory: ${packageNodeModules}`
    );
  }

  if (existingNodeModules) {
    fs.unlinkSync(packageNodeModules);
  }

  const relativeNodeModules = path.relative(
    packageStandaloneDir,
    bundledNodeModules
  );
  fs.symlinkSync(relativeNodeModules, packageNodeModules, "dir");
  console.log("Rebased standalone node_modules link:", relativeNodeModules);
}

const staticSrc = path.join(nextBuildDir, "static");
const staticDestinations = [
  path.join(outDir, ".next-build", "static"),
  ...(fs.existsSync(path.join(packageStandaloneDir, "server.js"))
    ? [path.join(packageStandaloneDir, ".next-build", "static")]
    : []),
  ...(fs.existsSync(path.join(legacyNestedStandaloneDir, "server.js"))
    ? [path.join(legacyNestedStandaloneDir, ".next-build", "static")]
    : []),
];
if (fs.existsSync(staticSrc)) {
  for (const staticDest of staticDestinations) {
    cpDir(staticSrc, staticDest);
  }
} else {
  console.error("Expected Next.js static output at:", staticSrc);
  process.exit(1);
}

const publicDir = path.join(nextjsDir, "public");
if (fs.existsSync(publicDir)) {
  cpDir(publicDir, path.join(outDir, "public"));
  if (fs.existsSync(path.join(packageStandaloneDir, "server.js"))) {
    cpDir(publicDir, path.join(packageStandaloneDir, "public"));
  }
  if (fs.existsSync(path.join(legacyNestedStandaloneDir, "server.js"))) {
    cpDir(publicDir, path.join(legacyNestedStandaloneDir, "public"));
  }
}

console.log("Next.js bundle copied to:", outDir);
