"""Validate root LICENSE file for GitHub/HACS detection.

GitHub's licensee fuzzy-matches LICENSE against the MIT template. Extra lines
such as an SPDX-License-Identifier header can drop similarity below the match
threshold and yield spdx_id NOASSERTION, which fails HACS validation.
Keep LICENSE as the canonical MIT text (title + copyright + body only).
"""

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
    if not text.startswith("MIT License"):
        errors.append("LICENSE must start with 'MIT License' title")
    if "Copyright" not in text:
        errors.append("LICENSE must contain a copyright line")
    if "Permission is hereby granted, free of charge" not in text:
        errors.append("LICENSE must contain the MIT permission grant")
    if "SPDX-License-Identifier" in text:
        errors.append(
            "LICENSE must not contain SPDX-License-Identifier "
            "(breaks GitHub/licensee MIT detection → HACS NOASSERTION)"
        )

    if errors:
        for err in errors:
            print(err, file=sys.stderr)
        return 1

    print("OK LICENSE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
