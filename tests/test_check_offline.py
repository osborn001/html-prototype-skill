import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


CHECKER = Path(__file__).resolve().parents[1] / "html-prototype/scripts/check_offline.py"
spec = importlib.util.spec_from_file_location("check_offline", CHECKER)
check_offline = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_offline)


class OfflineCheckTests(unittest.TestCase):
    def test_inline_resources_and_normal_links(self):
        html = """<style>
          /* url(fake-dependency) */
          .card { background: url('data:image/gif;base64,AAAA') }
        </style>
        <img srcset="data:image/gif;base64,AAAA 1x, data:image/gif;base64,BBBB 2x">
        <svg><use href="#symbol"></use></svg>
        <a href="https://example.org/docs">Docs</a>
        <script>const string = '<img src="code-not-markup.png">';</script>"""
        self.assertEqual(check_offline.check_html(html), [])

    def test_detects_common_separate_resources(self):
        html = """<style>@import "theme.css"; .card {background:url(pic.png)}</style>
        <script src="//example.org/app.js"></script>
        <link rel="preload" href="fonts/a.woff2">
        <img srcset="data:image/gif;base64,AAAA 1x, images/high.png 2x">
        <img srcset="images/regular.png, images/next.png 2x">
        <meta http-equiv="refresh" content="0; url=page.html">
        <svg><use xlink:href="icons.svg#item"></use></svg>
        <div style="background: url('/assets/bg.png')"></div>"""
        actual = {value for _, _, _, value in check_offline.check_html(html)}
        self.assertEqual(actual, {
            "theme.css", "pic.png", "//example.org/app.js", "fonts/a.woff2",
            "images/high.png", "images/regular.png", "images/next.png",
            "page.html", "icons.svg#item", "/assets/bg.png",
        })

    def test_cli_reports_exit_codes(self):
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / "示例 空格.html"
            for expected, html in [(0, "<h1>Demo</h1>"), (1, '<img src="missing.png">')]:
                file.write_text(html, encoding="utf-8")
                run = subprocess.run(
                    [sys.executable, str(CHECKER), str(file)], capture_output=True, text=True,
                )
                self.assertEqual(run.returncode, expected, run.stderr)
            run = subprocess.run(
                [sys.executable, str(CHECKER), str(file.with_name("missing.html"))],
                capture_output=True, text=True,
            )
            self.assertEqual(run.returncode, 2)


if __name__ == "__main__":
    unittest.main()
