const assert = require("node:assert/strict");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { test } = require("node:test");
const { chromium } = require("playwright");

const sample = path.join(__dirname, "../examples/workshop-booking.html");
const viewports = [
  { width: 1440, height: 900 },
  { width: 390, height: 844 },
];

for (const viewport of viewports) {
  test(`booking notices work offline at ${viewport.width} × ${viewport.height}`, async () => {
    const directory = await fs.mkdtemp(path.join(os.tmpdir(), "html-prototype-"));
    const file = path.join(directory, "workshop-booking.html");
    let browser;
    try {
      await fs.copyFile(sample, file);
      const fileURL = pathToFileURL(file).href;
      browser = await chromium.launch({
        executablePath: process.env.CHROME_EXECUTABLE || undefined,
      });
      const context = await browser.newContext({ viewport, offline: true });
      const page = await context.newPage();
      const requests = [];
      const errors = [];
      page.on("request", (request) => {
        const url = request.url();
        if (url !== fileURL && !url.startsWith("data:") && !url.startsWith("blob:")) {
          requests.push(url);
        }
      });
      page.on("pageerror", (error) => errors.push(error.message));
      page.on("console", (message) => {
        if (message.type() === "error") errors.push(message.text());
      });
      await page.goto(fileURL);

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
      assert.deepEqual(requests, []);
      assert.deepEqual(errors, []);
    } finally {
      if (browser) await browser.close();
      await fs.rm(directory, { recursive: true, force: true });
    }
  });
}
