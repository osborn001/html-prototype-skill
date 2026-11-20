const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const { createRequire } = require("node:module");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { parseArgs } = require("node:util");

function loadPlaywright() {
  try {
    return require("playwright");
  } catch (error) {
    if (error.code !== "MODULE_NOT_FOUND") throw error;
  }
  const fromProject = createRequire(path.join(process.cwd(), "package.json"));
  try {
    return fromProject("playwright");
  } catch (error) {
    if (error.code !== "MODULE_NOT_FOUND") throw error;
    throw new Error("Playwright is unavailable. Install it in your project or use the browser tools you already have.");
  }
}

function isLocalResource(requestURL, documentURL) {
  if (/^(data:|blob:|about:)/.test(requestURL)) return true;
  const parsed = new URL(requestURL);
  parsed.hash = "";
  parsed.search = "";
  return parsed.href === documentURL;
}

async function verifyBrowser({
  file, viewport, dpr = 1, executablePath, screenshot, flow, anchors = [], allowOverflow = false,
}) {
  const { chromium } = loadPlaywright();
  const folder = await fs.mkdtemp(path.join(os.tmpdir(), "html-prototype-"));
  let browser;
  try {
    const copy = path.join(folder, "prototype.html");
    await fs.copyFile(file, copy);
    const documentURL = pathToFileURL(copy).href;
    const unexpectedRequests = new Set();
    const browserErrors = new Set();
    browser = await chromium.launch({ executablePath });
    const context = await browser.newContext({
      viewport, deviceScaleFactor: dpr, offline: true, serviceWorkers: "block", acceptDownloads: true,
    });
    context.on("request", request => {
      const requestURL = request.url();
      if (!isLocalResource(requestURL, documentURL)) unexpectedRequests.add(requestURL);
    });
    await context.route("**/*", route => isLocalResource(route.request().url(), documentURL)
      ? route.continue() : route.abort());
    const page = await context.newPage();
    page.on("pageerror", error => browserErrors.add(error.message));
    page.on("console", message => {
      if (message.type() === "error") browserErrors.add(message.text());
    });

    let checkError = null;
    let geometry = {};
    let width = null;
    let flowResult = null;
    try {
      await page.goto(documentURL, { waitUntil: "load", timeout: 15000 });
      await page.evaluate(() => document.fonts.ready);
      width = await page.evaluate(() => ({
        viewport: document.documentElement.clientWidth,
        content: document.documentElement.scrollWidth,
      }));
      geometry = Object.fromEntries(await Promise.all(anchors.map(async ([name, selector]) => {
        const node = page.locator(selector);
        if (await node.count() !== 1) throw new Error("Anchor must select one element: " + name + " = " + selector);
        const box = await node.boundingBox({ timeout: 5000 });
        if (!box || !await node.isVisible()) throw new Error("Anchor is hidden: " + name + " = " + selector);
        return [name, box];
      })));
      if (screenshot) {
        await page.screenshot({ path: screenshot, animations: "disabled", caret: "hide" });
      }
      if (flow) flowResult = (await flow({ page, context, assert })) ?? null;
    } catch (error) {
      checkError = error.message;
    }
    const horizontalOverflow = width && Math.max(0, width.content - width.viewport);
    const passed = !checkError && !unexpectedRequests.size && !browserErrors.size &&
      (allowOverflow || horizontalOverflow === 0);
    return {
      passed, viewport, dpr, horizontalOverflow, geometry, unexpectedRequests: [...unexpectedRequests],
      browserErrors: [...browserErrors], checkError, flowResult,
    };
  } finally {
    try {
      if (browser) await browser.close();
    } finally {
      await fs.rm(folder, { recursive: true, force: true });
    }
  }
}

function parseAnchor(argument) {
  const delimiter = argument.indexOf("=");
  const name = argument.slice(0, delimiter).trim();
  const selector = argument.slice(delimiter + 1).trim();
  if (delimiter === -1 || !name || !selector) throw new Error("Expected --anchor NAME=SELECTOR.");
  return [name, selector];
}

const usage = [
  "Usage: node verify_browser.cjs PAGE.html --viewport WIDTHxHEIGHT [options]",
  "  --dpr NUMBER         Device pixel ratio (default 1)",
  "  --screenshot PATH   Save the initial viewport before the interaction flow",
  "  --anchor NAME=CSS   Measure one visible element (repeatable)",
  "  --flow PATH         Run an agent-authored CommonJS interaction test",
  "  --allow-overflow    Report document overflow without failing",
  "  --browser-executable PATH   Use a locally installed Chromium or Chrome",
].join("\n");

async function main() {
  const args = parseArgs({
    allowPositionals: true,
    options: {
      viewport: { type: "string" }, dpr: { type: "string", default: "1" },
      screenshot: { type: "string" }, anchor: { type: "string", multiple: true, default: [] },
      flow: { type: "string" }, "allow-overflow": { type: "boolean", default: false },
      "browser-executable": { type: "string" }, help: { type: "boolean", short: "h" },
    },
  });
  if (args.values.help) { console.log(usage); return; }
  const [file] = args.positionals;
  const viewport = args.values.viewport?.match(/^([1-9]\d{0,3})x([1-9]\d{0,3})$/i);
  const dpr = Number(args.values.dpr);
  if (args.positionals.length !== 1 || !viewport || !Number.isFinite(dpr) || dpr <= 0 || dpr > 5) {
    throw new Error(usage);
  }
  const flow = args.values.flow ? require(path.resolve(args.values.flow)) : undefined;
  if (flow !== undefined && typeof flow !== "function") throw new Error("A flow file must export a function.");
  const anchors = args.values.anchor.map(parseAnchor);
  if (new Set(anchors.map(([name]) => name)).size !== anchors.length) throw new Error("Anchor names must be unique.");
  const result = await verifyBrowser({
    file, viewport: { width: Number(viewport[1]), height: Number(viewport[2]) }, dpr,
    executablePath: args.values["browser-executable"] || process.env.CHROME_EXECUTABLE,
    screenshot: args.values.screenshot, anchors, flow, allowOverflow: args.values["allow-overflow"],
  });
  console.log(JSON.stringify(result, null, 2));
  if (!result.passed) process.exitCode = 1;
}

module.exports = { verifyBrowser };

if (require.main === module) {
  main().catch(error => { console.error(error.message); process.exitCode = 2; });
}
