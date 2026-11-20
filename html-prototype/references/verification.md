# 原型验收

## 用最终的打开方式完成检查

1. 将最终 HTML 单独复制到空目录，用桌面浏览器通过本地文件打开。关闭网络或拦截远程请求，查看控制台、资源和正常交互。另检查有没有访问其他本地文件。
2. 以需求指定的端和视口分别检查。既有页面对照相同的状态、尺寸、缩放和滚动位置。检查溢出、遮挡、固定区域、弹层、导航和键盘焦点。
3. 走主路径和会使结果不同的分支。记录起点、操作、预期、实际和结论，修复后重复相关用例。
4. 随需求文档交付时，从接收方入口打开附件或预览。若预览只支持静态展示，确认下载的是验收版本，并写明交互打开方式。

## 示例验收用例

示例使用虚构图书借阅站点，管理员设置各分馆的借阅须知。读者仅在目标分馆看到已发布的须知。

| 前置与操作 | 可观察的验证 |
|---|---|
| 分馆 A 无须知。填写文本、勾选启用并保存 | 分馆 A 的读者视图出现已提交内容。重开设置可回显 |
| 编辑文本后取消，打开读者视图 | 分馆 A 仍显示上次提交的文本 |
| 切换到分馆 B | 分馆 B 没有分馆 A 的须知 |
| 在分馆 A 停用后打开读者视图 | 分馆 A 的须知隐藏 |
| 将单个 HTML 放到空目录，在窄视口离线重走主路径 | 样式正常，页面无横向溢出，保存和读取仍可操作 |

## 理解检查结果

随 Skill 提供的 Python 脚本检查 HTML 中常见的资源属性、内联 CSS 里的 URL 和顶层页面跳转配置。它能找出许多遗漏的本地文件、外链字体和 CDN 依赖。通过静态检查后，继续用浏览器验证 JavaScript 产生的请求、视觉和行为。通过原型验收只说明相应模拟场景的结果，正式接口以实际联调记录为准。

## 用随包脚本复跑

脚本是可选工具。有浏览器控制能力时，可以直接对最终文件执行同样的测量和交互。没有浏览器时先做静态检查，明确留下尚未验证的项目。

### 浏览器截图、几何和关键路径

在项目中安装 Playwright，再按目标视口运行。可以用已安装的 Chrome 或 Chromium，传入 `--browser-executable`。脚本走系统临时目录和本地文件协议，浏览器上下文关闭网络，收集额外请求和控制台错误，记录首屏横向溢出，并可执行交互断言。

```sh
npm install --no-save playwright
npx playwright install chromium
node path/to/html-prototype/scripts/verify_browser.cjs prototype.html --viewport 1440x900 --dpr 1 --screenshot prototype.png --anchor "table=.rules-table"
```

`--anchor NAME=CSS` 可以重复，要求每个选择器命中一个可见元素，输出以 CSS 像素记录位置与尺寸。基线和迭代稿用同一组锚点检查位置。规模较大时只选本次需要保留的代表区域。刻意允许页面横向滚动时用 `--allow-overflow`，并在验收中说明。

给本次原型写一个精简的 CommonJS 流程脚本，随命令传 `--flow flow.cjs`。只使用当前任务中自己编写或已审核的流程测试。入口传入 Playwright 的 `page`、`context` 和 Node `assert`。截图在流程运行前拍摄，可在流程内另拍关键状态。

```js
module.exports = async ({ page, assert }) => {
  await page.getByRole("button", { name: "编辑" }).click();
  await page.getByLabel("预约说明").fill("演示内容");
  await page.getByRole("button", { name: "保存" }).click();
  await page.getByText("演示内容", { exact: true }).waitFor();
  await page.getByRole("button", { name: "编辑" }).click();
  assert.equal(await page.getByLabel("预约说明").inputValue(), "演示内容");
  return ["保存成功", "重开回显"];
};
```

截图命令本身会检查载入状态。附加流程断言或人工操作用于验证实际交互。

### 像素差与局部修改

```sh
python3 -m pip install Pillow
python3 path/to/html-prototype/scripts/compare_images.py reference.png baseline.png
python3 path/to/html-prototype/scripts/compare_images.py baseline.png iteration.png --change-region 620,40,118,36 --tolerance 3 --check --diff difference.png
```

两图须等尺寸。可预先声明一个或多个计划改动矩形，参数使用截图像素 `X,Y,WIDTH,HEIGHT`。在 DPR 1.5 下，用 CSS 坐标乘以 1.5，再向外取整。为新控件的描边或阴影预留合理范围，核对旁边原有控件仍在原位。容差是单个 RGB 通道等级，`--check` 在区域外有像素超出容差时返回失败。源图和基线可以只统计差异，用肉眼核对素材、色彩和字形。报告分别写几何偏移和像素差，注明裁切、替换和浏览器差异。

上述 `node` 和 `npm` 命令也适用于 Windows PowerShell。Windows 的 Python 命令可使用 `py -3`。
