const assert = require("node:assert/strict");
const test = require("node:test");

const {
  createTrustedIpcSenderValidator,
} = require("../app_dist/ipc/ipc-security");

const APP_ORIGIN = "http://127.0.0.1:3000";

function createFixture(overrides = {}) {
  const mainFrame = {
    url: APP_ORIGIN + "/upload",
  };

  const webContents = {
    isDestroyed: () => false,
    mainFrame,
  };

  const mainWindow = {
    isDestroyed: () => false,
    webContents,
  };

  const event = {
    sender: webContents,
    senderFrame: mainFrame,
  };

  return {
    mainWindow,
    webContents,
    mainFrame,
    event: { ...event, ...overrides.event },
    getMainWindow: () => mainWindow,
  };
}

test("accepts the trusted main window and its main frame", () => {
  const fixture = createFixture();

  const validate = createTrustedIpcSenderValidator(
    fixture.getMainWindow,
    APP_ORIGIN,
  );

  assert.doesNotThrow(() => validate(fixture.event));
});

test("rejects a different BrowserWindow", () => {
  const fixture = createFixture();

  const validate = createTrustedIpcSenderValidator(
    fixture.getMainWindow,
    APP_ORIGIN,
  );

  fixture.event.sender = {};

  assert.throws(() => validate(fixture.event), /Unauthorized IPC sender/);
});

test("rejects a destroyed main window", () => {
  const fixture = createFixture();
  fixture.mainWindow.isDestroyed = () => true;

  const validate = createTrustedIpcSenderValidator(
    fixture.getMainWindow,
    APP_ORIGIN,
  );

  assert.throws(() => validate(fixture.event), /Unauthorized IPC sender/);
});

test("rejects destroyed webContents", () => {
  const fixture = createFixture();
  fixture.webContents.isDestroyed = () => true;

  const validate = createTrustedIpcSenderValidator(
    fixture.getMainWindow,
    APP_ORIGIN,
  );

  assert.throws(() => validate(fixture.event), /Unauthorized IPC sender/);
});

test("rejects a missing sender frame", () => {
  const fixture = createFixture();
  fixture.event.senderFrame = null;

  const validate = createTrustedIpcSenderValidator(
    fixture.getMainWindow,
    APP_ORIGIN,
  );

  assert.throws(() => validate(fixture.event), /Unauthorized IPC frame/);
});

test("rejects a subframe", () => {
  const fixture = createFixture();

  fixture.event.senderFrame = {
    url: APP_ORIGIN + "/iframe",
  };

  const validate = createTrustedIpcSenderValidator(
    fixture.getMainWindow,
    APP_ORIGIN,
  );

  assert.throws(() => validate(fixture.event), /Unauthorized IPC frame/);
});

test("rejects an incorrect sender origin", () => {
  const fixture = createFixture();
  fixture.mainFrame.url = "https://attacker.example/";

  const validate = createTrustedIpcSenderValidator(
    fixture.getMainWindow,
    APP_ORIGIN,
  );

  assert.throws(() => validate(fixture.event), /Unauthorized IPC origin/);
});

test("rejects an invalid application origin during initialization", () => {
  const fixture = createFixture();

  assert.throws(
    () => createTrustedIpcSenderValidator(
      fixture.getMainWindow,
      "javascript:alert(1)",
    ),
    /invalid application origin/i,
  );
});
