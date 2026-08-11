"""Perceptual-hash dedup: never pay a VLM call for a screen we've already judged."""
import imagehash
from PIL import Image

# Hamming distance at or below this counts as "same screen".
NEAR_DUPLICATE_THRESHOLD = 4


def screenshot_hash(path: str) -> str:
    return str(imagehash.phash(Image.open(path)))


def is_near_duplicate(phash: str, seen: list[str]) -> bool:
    h = imagehash.hex_to_hash(phash)
    return any(h - imagehash.hex_to_hash(s) <= NEAR_DUPLICATE_THRESHOLD for s in seen)
