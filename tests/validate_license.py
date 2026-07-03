"""Validate root LICENSE file for HACS/GitHub detection."""

from __future__ import annotations

import pathlib
import sys

LICENSE = pathlib.Path(__file__).resolve().parents[1] / "LICENSE"


def main() -> int:
    if not LICENSE.is_file():
        print("Missing LICENSE file", file=sys.stderr)
        return 1

    text = LICENSE.read_text(encoding="utf-8")
    errors: list[str] = []
    if "MIT License" not in text:
        errors.append("LICENSE must contain 'MIT License' title")
    if "SPDX-License-Identifier: MIT" not in text:
        errors.append("LICENSE must contain 'SPDX-License-Identifier: MIT'")
    if "Copyright" not in text:
        errors.append("LICENSE must contain a copyright line")

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    print("OK LICENSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
