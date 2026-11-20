"""Compare two equal-size browser screenshots and isolate intentional changes."""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw


def rectangle(value):
    try:
        x, y, width, height = (int(part) for part in value.split(","))
    except ValueError:
        raise argparse.ArgumentTypeError("expected X,Y,WIDTH,HEIGHT") from None
    if min(x, y) < 0 or min(width, height) < 1:
        raise argparse.ArgumentTypeError("the rectangle must have a non-negative origin and positive size")
    return x, y, x + width, y + height


def load_rgb(file):
    with Image.open(file) as image:
        overlay = image.convert("RGBA")
    return Image.alpha_composite(Image.new("RGBA", overlay.size, "white"), overlay).convert("RGB")


def measure(reference, candidate, tolerance, regions):
    if reference.size != candidate.size:
        raise ValueError("images have different dimensions: {} and {}".format(reference.size, candidate.size))
    width, height = reference.size
    if any(x1 > width or y1 > height for _, _, x1, y1 in regions):
        raise ValueError("a change region extends outside the screenshot")
    red, green, blue = ImageChops.difference(reference, candidate).split()
    peak = ImageChops.lighter(ImageChops.lighter(red, green), blue)
    outside = peak.copy()
    for region in regions:
        outside.paste(0, region)
    above = outside.point(lambda value: 255 if value > tolerance else 0)
    outside_histogram = outside.histogram()
    results = {
        "imageWidth": width,
        "imageHeight": height,
        "tolerance": tolerance,
        "changedPixels": width * height - peak.histogram()[0],
        "outsideChangedPixels": width * height - outside_histogram[0],
        "outsideAboveTolerance": above.histogram()[255],
        "outsideMaxChannelDifference": outside.getextrema()[1],
        "unexpectedBounds": above.getbbox(),
    }
    return results, above


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--tolerance", type=int, default=0, choices=range(256), metavar="0..255",
                        help="maximum RGB channel delta to ignore (default 0)")
    parser.add_argument("--change-region", type=rectangle, action="append", default=[],
                        metavar="X,Y,WIDTH,HEIGHT", help="expected change area, in image pixels (repeatable)")
    parser.add_argument("--check", action="store_true", help="exit 1 when outside differences exceed tolerance")
    parser.add_argument("--diff", type=Path, help="save candidate image with unexpected pixels highlighted")
    args = parser.parse_args()
    try:
        reference, candidate = load_rgb(args.reference), load_rgb(args.candidate)
        results, overlay = measure(reference, candidate, args.tolerance, args.change_region)
        if args.diff:
            highlighted = Image.blend(candidate, Image.new("RGB", candidate.size, "#f53539"), 0.65)
            marked = Image.composite(highlighted, candidate, overlay)
            draw = ImageDraw.Draw(marked)
            for x0, y0, x1, y1 in args.change_region:
                draw.rectangle((x0, y0, x1 - 1, y1 - 1), outline="#316fe9", width=2)
            marked.save(args.diff)
    except (OSError, ValueError) as error:
        parser.exit(2, str(error) + "\n")
    print(json.dumps(results, indent=2))
    return int(args.check and results["outsideAboveTolerance"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
