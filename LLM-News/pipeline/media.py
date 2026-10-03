"""Images and audio for quick_news articles: pick and download the feed image, make a small WebP
thumbnail for cards, and read the summary aloud with edge-tts."""
import asyncio
import html
import re
import urllib.request
from pathlib import Path

import edge_tts
from PIL import Image

USER_AGENT = "Mozilla/5.0 (LLM-NewsHub quick_news)"
VOICE = "en-US-AriaNeural"  # same voice as deployment/audio/tts.py
IMAGE_TYPES = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp", "image/gif": "gif"}
MIN_IMAGE_BYTES = 2 * 1024  # anything smaller is a spacer/tracking image
MAX_IMAGE_BYTES = 5 * 1024 * 1024
THUMB_WIDTH = 800  # cards are about 400px wide; 2x for sharp screens
IMG_TAG = re.compile(r"<img[^>]+src=[\"']([^\"']+)", re.IGNORECASE)


def best_image(entry) -> str:
    """Largest image a feed entry offers: media tags first, then an <img> in its HTML."""
    candidates = []
    for media in entry.get("media_content", []) + entry.get("media_thumbnail", []):
        width = str(media.get("width") or "0")
        if media.get("url") and media.get("medium", "image") == "image":
            candidates.append((int(width) if width.isdigit() else 0, media["url"]))
    if candidates:
        url = max(candidates)[1]
    else:
        markup = " ".join([entry.get("summary", "")] + [c.get("value", "") for c in entry.get("content", [])])
        urls = (html.unescape(src) for src in IMG_TAG.findall(markup))
        # Feeds embed analytics pixels (e.g. NPR's npr-rss-pixel.png) and broken src='undefined'
        url = next((u for u in urls if u.startswith(("https://", "http://"))
                    and "pixel" not in u and "tracking" not in u), "")
    # BBC feeds list 240px thumbnails; the same image is served at 976px
    return url.replace("/ace/standard/240/", "/ace/standard/976/")


def download_image(url: str, folder: Path, stem: str) -> str:
    """Save a feed image as <stem>.<its real format>; returns the file name, or "" when skipped.
    Only http(s) URLs, known image types and sizes within the byte limits."""
    if not url.startswith(("https://", "http://")):
        return ""
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=20) as response:
            extension = IMAGE_TYPES.get(response.headers.get_content_type())
            if not extension:
                return ""
            data = response.read(MAX_IMAGE_BYTES + 1)
    except Exception as e:
        print(f"    image skipped ({e})")
        return ""
    if not MIN_IMAGE_BYTES <= len(data) <= MAX_IMAGE_BYTES:
        return ""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{stem}.{extension}").write_bytes(data)
    return f"{stem}.{extension}"


def make_thumbnail(image: Path, width: int = THUMB_WIDTH) -> str:
    """Write <stem>.thumb.webp (at most `width` px wide) next to an image; returns its name or "" """
    target = image.with_name(f"{image.stem}.thumb.webp")
    try:
        with Image.open(image) as picture:
            picture.thumbnail((width, width * 3))
            if picture.mode not in ("RGB", "RGBA"):
                picture = picture.convert("RGBA" if "transparency" in picture.info else "RGB")
            picture.save(target, "WEBP", quality=72, method=6)
        return target.name
    except Exception as e:
        print(f"    thumbnail skipped ({e})")
        target.unlink(missing_ok=True)
        return ""


def make_audio(text: str, path: Path) -> bool:
    """Read text aloud to an mp3 with edge-tts."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        asyncio.run(edge_tts.Communicate(text, VOICE).save(str(path)))
        return True
    except Exception as e:
        path.unlink(missing_ok=True)  # don't leave a partial mp3 the website would try to play
        print(f"    audio skipped ({str(e)[:120]})")
        return False
