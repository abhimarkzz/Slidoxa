"""Download the Slidoxa font set into assets/fonts/.

Sources: official Google Fonts + google/fonts GitHub raw blobs. Only
files that ship under the SIL Open Font License are pulled; the
matching OFL.txt is downloaded alongside each family.

Running the script is idempotent: existing files are skipped unless
``--force`` is passed.
"""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path

RAW = "https://raw.githubusercontent.com/google/fonts/main"

# family -> list of (dest_relative, source_url)
MANIFEST: dict[str, list[tuple[str, str]]] = {
    "PlusJakartaSans": [
        ("PlusJakartaSans/PlusJakartaSans-VariableFont_wght.ttf",
         f"{RAW}/ofl/plusjakartasans/PlusJakartaSans[wght].ttf"),
        ("PlusJakartaSans/PlusJakartaSans-Italic-VariableFont_wght.ttf",
         f"{RAW}/ofl/plusjakartasans/PlusJakartaSans-Italic[wght].ttf"),
        ("PlusJakartaSans/OFL.txt",
         f"{RAW}/ofl/plusjakartasans/OFL.txt"),
    ],
    "Inter": [
        ("Inter/Inter-VariableFont_opsz,wght.ttf",
         f"{RAW}/ofl/inter/Inter[opsz,wght].ttf"),
        ("Inter/Inter-Italic-VariableFont_opsz,wght.ttf",
         f"{RAW}/ofl/inter/Inter-Italic[opsz,wght].ttf"),
        ("Inter/OFL.txt",
         f"{RAW}/ofl/inter/OFL.txt"),
    ],
    "JetBrainsMono": [
        ("JetBrainsMono/JetBrainsMono-VariableFont_wght.ttf",
         f"{RAW}/ofl/jetbrainsmono/JetBrainsMono[wght].ttf"),
        ("JetBrainsMono/JetBrainsMono-Italic-VariableFont_wght.ttf",
         f"{RAW}/ofl/jetbrainsmono/JetBrainsMono-Italic[wght].ttf"),
        ("JetBrainsMono/OFL.txt",
         f"{RAW}/ofl/jetbrainsmono/OFL.txt"),
    ],
    # Noto Sans CJK (SC/JP/KR): the CJK Google Fonts repo ships weight-
    # specific Regular TTFs under ofl/notosanssc etc. For a Slidoxa
    # baseline we pull Regular only; additional weights can be added in
    # a later font-expansion pass.
    "NotoSansSC": [
        ("NotoSansSC/NotoSansSC-Regular.ttf",
         f"{RAW}/ofl/notosanssc/NotoSansSC%5Bwght%5D.ttf"),
        ("NotoSansSC/OFL.txt",
         f"{RAW}/ofl/notosanssc/OFL.txt"),
    ],
    "NotoSansJP": [
        ("NotoSansJP/NotoSansJP-Regular.ttf",
         f"{RAW}/ofl/notosansjp/NotoSansJP%5Bwght%5D.ttf"),
        ("NotoSansJP/OFL.txt",
         f"{RAW}/ofl/notosansjp/OFL.txt"),
    ],
    "NotoSansKR": [
        ("NotoSansKR/NotoSansKR-Regular.ttf",
         f"{RAW}/ofl/notosanskr/NotoSansKR%5Bwght%5D.ttf"),
        ("NotoSansKR/OFL.txt",
         f"{RAW}/ofl/notosanskr/OFL.txt"),
    ],
    "NotoSansDevanagari": [
        ("NotoSansDevanagari/NotoSansDevanagari-Regular.ttf",
         f"{RAW}/ofl/notosansdevanagari/NotoSansDevanagari%5Bwdth%2Cwght%5D.ttf"),
        ("NotoSansDevanagari/OFL.txt",
         f"{RAW}/ofl/notosansdevanagari/OFL.txt"),
    ],
    "NotoSansTelugu": [
        ("NotoSansTelugu/NotoSansTelugu-Regular.ttf",
         f"{RAW}/ofl/notosanstelugu/NotoSansTelugu%5Bwdth%2Cwght%5D.ttf"),
        ("NotoSansTelugu/OFL.txt",
         f"{RAW}/ofl/notosanstelugu/OFL.txt"),
    ],
    "NotoSansArabic": [
        ("NotoSansArabic/NotoSansArabic-Regular.ttf",
         f"{RAW}/ofl/notosansarabic/NotoSansArabic%5Bwdth%2Cwght%5D.ttf"),
        ("NotoSansArabic/OFL.txt",
         f"{RAW}/ofl/notosansarabic/OFL.txt"),
    ],
}


def fetch(url: str, dest: Path, force: bool) -> bool:
    if dest.exists() and not force:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "slidoxa-font-fetcher/1.0"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # noqa: S310
        dest.write_bytes(resp.read())
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent / "assets" / "fonts")
    args = parser.parse_args()

    total = fetched = 0
    for family, entries in MANIFEST.items():
        for rel, url in entries:
            total += 1
            dest = args.root / rel
            try:
                if fetch(url, dest, args.force):
                    fetched += 1
                    print(f"[fetched] {rel}")
                else:
                    print(f"[present] {rel}")
            except Exception as exc:
                print(f"[FAILED]  {rel}: {exc}", file=sys.stderr)
                return 1
    print(f"done: {fetched} fetched, {total - fetched} already present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
