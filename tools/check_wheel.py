"""Fail if the built wheel is missing the typing marker or any bundled data file."""

import sys
import zipfile
from pathlib import Path

REQUIRED = ("py.typed", "data/words.txt", "data/ngrams.txt", "data/lookalikes.txt", "data/scripts.txt")


def main() -> int:
    wheels = sorted(Path("dist").glob("*.whl"))
    if not wheels:
        print("no wheel in dist/")
        return 1
    names = zipfile.ZipFile(wheels[-1]).namelist()
    missing = [wanted for wanted in REQUIRED if not any(name.endswith("text_deobfuscate/" + wanted) for name in names)]
    if missing:
        print(f"{wheels[-1].name} is missing: {', '.join(missing)}")
        return 1
    print(f"{wheels[-1].name} has all of: {', '.join(REQUIRED)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
