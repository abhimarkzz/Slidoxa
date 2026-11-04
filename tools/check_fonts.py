"""Validate the Slidoxa font set under assets/fonts/.

Exit 0 on success, 1 on any missing or unopenable file, OFL.txt absent,
or font metadata name mismatch. Does not rely on filenames alone;
each TTF is opened via fontTools and the name-table `name ID 16 /
Typographic Family Name` (fallback: name ID 1 `Family Name`) is
compared against the declared family.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from fontTools.ttLib import TTFont, TTLibError
except ImportError:
    print("fontTools is required: pip install fontTools", file=sys.stderr)
    sys.exit(1)

FONTS_ROOT = Path(__file__).resolve().parent.parent / "assets" / "fonts"

# family dir name -> (expected family-name substring, list of TTF files that must exist)
EXPECTED: dict[str, tuple[str, list[str]]] = {
    "PlusJakartaSans": ("Plus Jakarta Sans", [
        "PlusJakartaSans-VariableFont_wght.ttf",
        "PlusJakartaSans-Italic-VariableFont_wght.ttf",
    ]),
    "Inter": ("Inter", [
        "Inter-VariableFont_opsz,wght.ttf",
        "Inter-Italic-VariableFont_opsz,wght.ttf",
    ]),
    "JetBrainsMono": ("JetBrains Mono", [
        "JetBrainsMono-VariableFont_wght.ttf",
        "JetBrainsMono-Italic-VariableFont_wght.ttf",
    ]),
    "NotoSansSC": ("Noto Sans SC", ["NotoSansSC-Regular.ttf"]),
    "NotoSansJP": ("Noto Sans JP", ["NotoSansJP-Regular.ttf"]),
    "NotoSansKR": ("Noto Sans KR", ["NotoSansKR-Regular.ttf"]),
    "NotoSansDevanagari": ("Noto Sans Devanagari", ["NotoSansDevanagari-Regular.ttf"]),
    "NotoSansTelugu": ("Noto Sans Telugu", ["NotoSansTelugu-Regular.ttf"]),
    "NotoSansArabic": ("Noto Sans Arabic", ["NotoSansArabic-Regular.ttf"]),
}


def _family_from_name_table(font: TTFont) -> str | None:
    name = font["name"]
    # Prefer Typographic Family (ID 16); fall back to Family Name (ID 1).
    for name_id in (16, 1):
        for record in name.names:
            if record.nameID != name_id:
                continue
            try:
                value = record.toUnicode()
            except UnicodeDecodeError:
                continue
            if value:
                return value
    return None


def main() -> int:
    errors: list[str] = []

    if not FONTS_ROOT.is_dir():
        print(f"FAIL: fonts root missing: {FONTS_ROOT}", file=sys.stderr)
        return 1

    for family_dir, (expected_family, files) in EXPECTED.items():
        base = FONTS_ROOT / family_dir

        ofl = base / "OFL.txt"
        if not ofl.is_file():
            errors.append(f"{family_dir}: missing OFL.txt")

        for filename in files:
            path = base / filename
            if not path.is_file():
                errors.append(f"{family_dir}: missing {filename}")
                continue
            try:
                font = TTFont(path, lazy=False)
            except TTLibError as exc:
                errors.append(f"{family_dir}/{filename}: unreadable ({exc})")
                continue
            family_name = _family_from_name_table(font)
            if not family_name:
                errors.append(f"{family_dir}/{filename}: no family name in metadata")
            elif expected_family.lower() not in family_name.lower():
                errors.append(
                    f"{family_dir}/{filename}: family metadata says "
                    f"{family_name!r}, expected to contain {expected_family!r}"
                )

    if errors:
        print("FAIL:", file=sys.stderr)
        for line in errors:
            print(f"  - {line}", file=sys.stderr)
        return 1

    print(f"OK: {sum(len(v[1]) for v in EXPECTED.values())} fonts validated across "
          f"{len(EXPECTED)} families; all OFL.txt files present.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
