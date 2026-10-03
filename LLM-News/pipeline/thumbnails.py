"""Make the small WebP card thumbnails for images that don't have one yet (articles written before
thumbnails existed). Safe to run again: existing thumbnails are skipped.

    python pipeline/thumbnails.py              # every edition
    python pipeline/thumbnails.py 2026-10-02   # one edition
"""
import json
import sys
from pathlib import Path

from media import make_thumbnail

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "apps" / "static"


def main():
    dates = sys.argv[1:] or sorted(p.name for p in (STATIC / "images").iterdir() if p.is_dir())
    made = 0
    for date in dates:
        for image in sorted((STATIC / "images" / date).glob("group_*.*")):
            if ".thumb." in image.name or image.with_name(f"{image.stem}.thumb.webp").exists():
                continue
            thumb = make_thumbnail(image)
            if not thumb:
                continue
            made += 1
            article_file = STATIC / "articles" / date / f"{image.stem}.json"
            if article_file.exists():  # record it so the website uses it
                article = json.loads(article_file.read_text(encoding="utf-8"))
                article["image_thumb"] = thumb
                article_file.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"{date}/{thumb}: {image.stat().st_size // 1024} KB -> {(image.with_name(thumb)).stat().st_size // 1024} KB")
    print(f"Made {made} thumbnail(s).")


if __name__ == "__main__":
    main()
