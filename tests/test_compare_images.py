from pathlib import Path
import json
import subprocess
import sys
import tempfile
import unittest

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / "html-prototype/scripts/compare_images.py"


class ScreenshotComparisonTests(unittest.TestCase):
    def test_region_mask_and_tolerance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            left, right, marked = (root / name for name in ("原图.png", "新稿.png", "对照.png"))
            blank = Image.new("RGB", (8, 5), (220, 220, 220))
            blank.save(left)
            candidate = blank.copy()
            candidate.putpixel((2, 2), (0, 0, 0))
            candidate.putpixel((5, 3), (219, 220, 220))
            candidate.putpixel((7, 4), (219, 216, 220))
            candidate.save(right)

            command = [sys.executable, str(SCRIPT), str(left), str(right), "--change-region", "1,1,3,3"]
            run = subprocess.run(command + ["--tolerance", "3", "--check", "--diff", str(marked)],
                                 capture_output=True, text=True)
            result = json.loads(run.stdout)
            self.assertEqual(run.returncode, 1)
            self.assertEqual(result["changedPixels"], 3)
            self.assertEqual(result["outsideChangedPixels"], 2)
            self.assertEqual(result["outsideMaxChannelDifference"], 4)
            self.assertEqual(result["outsideAboveTolerance"], 1)
            self.assertEqual(result["unexpectedBounds"], [7, 4, 8, 5])
            self.assertTrue(marked.is_file())

            tolerated = subprocess.run(command + ["--check", "--tolerance", "4"], capture_output=True, text=True)
            self.assertEqual(tolerated.returncode, 0)
            self.assertEqual(json.loads(tolerated.stdout)["outsideAboveTolerance"], 0)

    def test_dimensions_and_out_of_bounds_regions_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            left = Path(directory) / "a.png"
            right = Path(directory) / "b.png"
            Image.new("RGB", (2, 2)).save(left)
            Image.new("RGB", (3, 2)).save(right)
            command = [sys.executable, str(SCRIPT), str(left), str(right)]
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn("different dimensions", run.stderr)
            Image.new("RGB", (2, 2)).save(right)
            run = subprocess.run(command + ["--change-region", "1,1,3,3"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn("outside the screenshot", run.stderr)


if __name__ == "__main__":
    unittest.main()
