"""Shared content loader.

content/site.json holds the hand-written content (about, contact, the first two
projects ...). The upload system keeps two more files up to date by itself:

    content/stories.json   stories added through the stories/ folder
    content/singles.json   photos added through the singles/ folder

load() merges them into one dictionary, newest uploads first. The website
(index.html) merges them the same way, so both always agree.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def read_json(relative, default):
    path = ROOT / relative
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load():
    data = read_json("content/site.json", {})
    stories = read_json("content/stories.json", [])
    extra_singles = read_json("content/singles.json", [])
    data["_site_pieces"] = list(data.get("pieces", []))  # the original, hand-written ones
    data["pieces"] = list(stories) + data["_site_pieces"]
    data["singles"] = list(extra_singles) + list(data.get("singles", []))
    return data
