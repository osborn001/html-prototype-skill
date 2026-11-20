const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { test } = require("node:test");
const { verifyBrowser } = require("../html-prototype/scripts/verify_browser.cjs");

const sample = path.join(__dirname, "../examples/workshop-booking.html");
const viewports = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
];

async function checkBooking({ page, assert }) {
  const button = (name) => page.getByRole("button", { name, exact: true });
  const roomSettings = button("设置提示（陶艺室）");
  const dialog = page.getByRole("dialog");
  const field = dialog.getByLabel("提示内容");
  const enabled = dialog.getByRole("checkbox", { name: "启用预约提示" });
  const notice = page.locator("#visitor-notice");
  const noticeText = "请在陶艺室门口领取围裙。";

  async function visitRoom(name) {
    await button("访客视图").click();
    await button(name).click();
  }

  async function checkWidth() {
    assert.equal(await page.evaluate(
      () => document.documentElement.scrollWidth <= document.documentElement.clientWidth,
    ), true);
  }

  await checkWidth();
  await visitRoom("陶艺室");
  assert.equal(await notice.isVisible(), false);
  await button("管理视图").click();
  await roomSettings.click();
  await checkWidth();
  await enabled.check();
  await field.fill("   ");
  await button("保存").click();
  assert.equal(await dialog.getByRole("alert").isVisible(), true);

  await field.fill(noticeText);
  await button("保存").click();
  await visitRoom("陶艺室");
  assert.match(await notice.innerText(), /请在陶艺室门口领取围裙。/);
  await checkWidth();
  await visitRoom("木工室");
  assert.doesNotMatch(await notice.innerText(), /陶艺室门口/);

  await button("管理视图").click();
  await roomSettings.click();
  assert.equal(await field.inputValue(), noticeText);
  assert.equal(await enabled.isChecked(), true);
  await field.fill("没有提交的草稿");
  await button("取消").click();
  await page.waitForFunction(() => document.activeElement?.getAttribute("data-edit") === "clay");
  await visitRoom("陶艺室");
  assert.match(await notice.innerText(), /请在陶艺室门口领取围裙。/);

  await button("管理视图").click();
  await roomSettings.click();
  await field.fill("关闭对话框时丢弃的草稿");
  await page.keyboard.press("Escape");
  await roomSettings.click();
  assert.equal(await field.inputValue(), noticeText);
  await enabled.uncheck();
  await button("保存").click();
  await visitRoom("陶艺室");
  assert.equal(await notice.isVisible(), false);
}

for (const viewport of viewports) {
  test(`booking notices work offline at ${viewport.width} × ${viewport.height}`, async () => {
    const result = await verifyBrowser({
      file: sample,
      viewport,
      executablePath: process.env.CHROME_EXECUTABLE,
      anchors: [["heading", "#admin-heading"]],
      flow: checkBooking,
    });
    assert.equal(result.passed, true, JSON.stringify(result));
    assert.ok(result.geometry.heading.width > 0);
  });
}

test("runtime requests, JavaScript errors, and overflowing pages fail offline verification", async () => {
  const folder = await fs.mkdtemp(path.join(os.tmpdir(), "offline-fixture-"));
  try {
    const file = path.join(folder, "test prototype.html");
    await fs.writeFile(file, [
      "<!doctype html><div style='width:800px'>Offline test</div>",
      "<script>const image = new Image(); image.src = 'https://example.org/asset.png';",
      "document.body.append(image); throw new Error('synthetic error');</script>",
    ].join(""));
    const result = await verifyBrowser({
      file, viewport: { width: 400, height: 600 }, executablePath: process.env.CHROME_EXECUTABLE,
      flow: async ({ page }) => {
        await page.waitForFunction(() => document.querySelector("img").complete);
        return ["waited for the image"];
      },
    });
    assert.equal(result.passed, false);
    assert.ok(result.horizontalOverflow > 0);
    assert.deepEqual(result.unexpectedRequests, ["https://example.org/asset.png"]);
    assert.ok(result.browserErrors.includes("synthetic error"));
    assert.deepEqual(result.flowResult, ["waited for the image"]);
  } finally {
    await fs.rm(folder, { recursive: true, force: true });
  }
});
