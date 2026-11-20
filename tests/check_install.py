"""Run the exact project install commands from the README in an isolated folder."""

import argparse
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


REPO = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("shell", choices=("sh", "powershell"))
    parser.add_argument("--pwsh", default="pwsh")
    args = parser.parse_args()
    readme = (REPO / "README.md").read_text(encoding="utf-8")
    section = readme.split("### 手动安装", 1)[1].split("## 试一次", 1)[0]
    script = re.search(r"```" + args.shell + r"\n(.*?)\n```", section, re.S).group(1)

    with tempfile.TemporaryDirectory(prefix="html prototype ") as directory:
        root = Path(directory)
        source = root / "html-prototype"
        shutil.copytree(REPO / "html-prototype", source, ignore=shutil.ignore_patterns("__pycache__"))
        command = ["sh", "-c", script]
        if args.shell == "powershell":
            command = [args.pwsh, "-NoProfile", "-NonInteractive", "-Command", script]
        subprocess.run(command, cwd=root, check=True)
        destination = root / ".agents/skills/html-prototype"
        expected = {file.relative_to(source): file.read_bytes() for file in source.rglob("*") if file.is_file()}
        actual = {
            file.relative_to(destination): file.read_bytes()
            for file in destination.rglob("*") if file.is_file()
        }
        if actual != expected or not (destination / "SKILL.md").is_file():
            raise SystemExit("The installed directory did not match the source skill.")
        print(f"{args.shell}: installed {len(actual)} files at the documented path.")


if __name__ == "__main__":
    main()
