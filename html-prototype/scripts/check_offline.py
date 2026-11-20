"""Find common HTML and CSS resource references that need another file or service."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
import sys


RESOURCE_ATTRIBUTES = {
    "audio": ("src",),
    "base": ("href",),
    "embed": ("src",),
    "feimage": ("href", "xlink:href"),
    "frame": ("src",),
    "iframe": ("src",),
    "image": ("href", "xlink:href"),
    "img": ("src",),
    "input": ("src",),
    "object": ("data",),
    "script": ("src", "href", "xlink:href"),
    "source": ("src",),
    "track": ("src",),
    "use": ("href", "xlink:href"),
    "video": ("src", "poster"),
}
LOADING_RELATIONS = {
    "apple-touch-icon", "dns-prefetch", "icon", "manifest", "modulepreload",
    "preconnect", "prefetch", "preload", "prerender", "stylesheet",
}
CSS_URL = re.compile(r'''\burl\(\s*(?:"([^"]*)"|'([^']*)'|([^)]*))\s*\)''', re.I)
CSS_IMPORT = re.compile(r'''@import\s*["']([^"']+)["']''', re.I)
CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
REFRESH_URL = re.compile(r'''\burl\s*=\s*["']?(.*?)["']?\s*$''', re.I)


def srcset_urls(value):
    remaining = value.lstrip(", \t\n\r\f")
    while remaining:
        token = re.match(r"[^\t\n\r\f ]+", remaining).group()
        yield token.rstrip(",")
        remaining = remaining[len(token):]
        if not token.endswith(","):
            # Skip density or width descriptors before the next candidate.
            remaining = remaining.partition(",")[2]
        remaining = remaining.lstrip(", \t\n\r\f")


class ResourceCheck(HTMLParser):
    def __init__(self):
        super().__init__()
        self.findings = []
        self.in_style = False

    def check_url(self, location, value):
        value = (value or "").strip()
        if value and not value.lower().startswith(("#", "data:")):
            line, column = self.getpos()
            self.findings.append((line, column + 1, location, value))

    def check_css(self, text, location):
        css = CSS_COMMENT.sub("", text)
        for match in CSS_URL.finditer(css):
            value = next(group for group in match.groups() if group is not None)
            self.check_url(location, value)
        for match in CSS_IMPORT.finditer(css):
            self.check_url(location, match.group(1))

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        for attribute in RESOURCE_ATTRIBUTES.get(tag, ()):
            self.check_url(f"{tag}[{attribute}]", attributes.get(attribute))

        relations = (attributes.get("rel") or "").lower().split()
        if tag == "link" and LOADING_RELATIONS.intersection(relations):
            self.check_url("link[href]", attributes.get("href"))
            for value in srcset_urls(attributes.get("imagesrcset") or ""):
                self.check_url("link[imagesrcset]", value)

        for value in srcset_urls(attributes.get("srcset") or ""):
            self.check_url(f"{tag}[srcset]", value)

        if (attributes.get("http-equiv") or "").lower() == "refresh":
            match = REFRESH_URL.search(attributes.get("content") or "")
            if match:
                self.check_url("meta[refresh]", match.group(1))

        for name, value in attrs:
            if value and (name == "style" or "url(" in value.lower() and name in {
                "clip-path", "fill", "filter", "marker-end", "marker-mid",
                "marker-start", "mask", "stroke",
            }):
                self.check_css(value, f"{tag}[{name}]")

        if tag == "style":
            self.in_style = True

    def handle_endtag(self, tag):
        if tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_style:
            self.check_css(data, "style")


def check_html(text):
    parser = ResourceCheck()
    parser.feed(text)
    parser.close()
    return parser.findings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path, help="path to a UTF-8 HTML prototype")
    args = parser.parse_args()
    try:
        findings = check_html(args.html.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError) as error:
        parser.exit(2, f"Cannot read HTML: {error}\n")

    if findings:
        for line, column, location, value in findings:
            # Keep long embedded values and whitespace from flooding the report.
            preview = repr(value[:160])
            print(f"{args.html}:{line}:{column}: {location} uses {preview}")
        return 1

    print(f"{args.html}: no non-embedded references found by the static check.")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")
    sys.exit(main())
