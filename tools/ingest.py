#!/usr/bin/env python3
"""Turn uploaded folders into website content.

You never edit JSON. You drop things into two places on GitHub:

  stories/<projects or editorial>/<any folder name>/
        story.txt      title + text (optional; the folder name is the title otherwise)
        01.jpg 02.jpg  your photos, shown in file-name order
                       name two photos 03a.jpg and 03b.jpg to show them side by side
        captions.txt   optional: one line per photo, e.g.  03: Sarlahi, 2023. A farmer ...
                       (shown under the photo and used as its description for Google)

  singles/
        any photos     optional  <same name>.txt  with "Title:" / "Alt:" lines

  tearsheet/
        screenshots    optional  <same name>.txt  with "Publication:", "Date:",
                       "Link:" and "Alt:" lines

This script (run automatically by GitHub, or by hand: python3 tools/ingest.py):
  * shrinks each photo (longest side 1600px, JPEG) and gives it a clear file name,
    e.g. images/bittersugar/rojan_shrestha_bittersugar_07.jpg
  * removes the big original from the repo so it does not fill up
  * records the story / single in content/stories.json or content/singles.json
  * writes the photographer's name, credit and copyright into every photo
    (tools/photo_rights.py), so Google Images can show them

Uploading more photos into an existing story folder adds them to that story.
Editing story.txt updates the story's title and text. Deleting a story folder
removes the story from the website.

Needs Pillow (pip install pillow). Everything else is the standard library.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import content  # noqa: E402

STORIES_DIR = ROOT / "stories"
SINGLES_DIR = ROOT / "singles"
TEARSHEET_DIR = ROOT / "tearsheet"
IMAGES_DIR = ROOT / "images"
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIDE = 1600
QUALITY = 80
RESERVED = {"work", "about", "contact", "piece", "content", "images", "models",
            "tools", "stories", "singles"}


def say(msg):
    print(msg, flush=True)


def natural_key(text):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", text)]


def hidden(path):
    return path.name.startswith((".", "_"))


def is_photo(path):
    return path.is_file() and not hidden(path) and path.suffix.lower() in IMAGE_EXT


def squash(text):
    """lowercase letters and digits only (matches the site's address style)"""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def shrink(src, dst, quality=QUALITY):
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
        im.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)  # never enlarges
        im.save(dst, "JPEG", quality=quality, optimize=True, progressive=True)


def read_text(path):
    return path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").replace("\r", "\n")


def parse_story_txt(path):
    """Title: ...  /  Slug: ... (optional)  /  Description: then the text."""
    meta, desc = {}, []
    in_desc = False
    for line in read_text(path).split("\n"):
        if in_desc:
            desc.append(line.rstrip())
            continue
        m = re.match(r"^\s*(title|slug)\s*:\s*(.*)$", line, re.I)
        if m:
            meta[m.group(1).lower()] = m.group(2).strip()
            continue
        m = re.match(r"^\s*description\s*:\s*(.*)$", line, re.I)
        if m:
            in_desc = True
            if m.group(1).strip():
                desc.append(m.group(1).rstrip())
            continue
        if line.strip():            # text with no "Description:" label: treat as the description
            in_desc = True
            desc.append(line.rstrip())
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(desc)).strip()
    return meta, text


def parse_captions(path):
    """captions.txt: one line per photo, '03: caption' (or '03a', '03.jpg')."""
    caps = {}
    for line in read_text(path).split("\n"):
        m = re.match(r"^\s*([0-9]+[ab]?)(?:\.[a-z]+)?\s*[:\-–—]\s*(.+?)\s*$", line, re.I)
        if m:
            caps[m.group(1).lower()] = m.group(2)
    return caps


def parse_sidecar(path):
    meta = {}
    for line in read_text(path).split("\n"):
        m = re.match(r"^\s*(title|headline|alt|caption|publication|date|link|url)\s*:\s*(.*)$", line, re.I)
        if m and m.group(2).strip():
            key = m.group(1).lower()
            key = {"link": "url", "caption": "alt", "headline": "title"}.get(key, key)
            meta[key] = m.group(2).strip()
    return meta


def file_slug(text, limit=80):
    """'Nepal’s early vote count' -> 'nepals_early_vote_count' (ASCII, underscores, <= limit)"""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = text.replace("'", "")
    out = ""
    for word in re.sub(r"[^a-z0-9]+", " ", text).split():
        if len(out) + len(word) + 1 > limit:
            break
        out = f"{out}_{word}" if out else word
    return out


def flat(images):
    out = []
    for x in images:
        out.extend(x if isinstance(x, list) else [x])
    return out


def photo_units(folder):
    """Photos in the folder as display units: one photo, or a side-by-side pair."""
    files = sorted((f for f in folder.iterdir() if is_photo(f)), key=lambda f: natural_key(f.stem))
    for f in folder.iterdir():
        if f.is_file() and not hidden(f) and f.suffix.lower() in {".heic", ".heif", ".tif", ".tiff", ".gif"}:
            say(f"  ! skipped {f.name}: please save it as a JPG first")
    pairs, units, used = {}, [], set()
    for f in files:
        m = re.fullmatch(r"(\d+)([ab])", f.stem, re.I)
        if m:
            pairs.setdefault(int(m.group(1)), {})[m.group(2).lower()] = f
    for f in files:
        if f in used:
            continue
        m = re.fullmatch(r"(\d+)([ab])", f.stem, re.I)
        if m and {"a", "b"} <= set(pairs[int(m.group(1))]):
            both = pairs[int(m.group(1))]
            units.append([both["a"], both["b"]])
            used.update(both.values())
        else:
            units.append([f])
            used.add(f)
    return units


def next_number(images):
    nums = [int(m.group(1)) for src in flat(images) if (m := re.search(r"_(\d+)\.jpg$", src))]
    return max(nums, default=0)


def run_stories(data, stories):
    site_slugs = {p.get("slug") for p in data["_site_pieces"]}
    categories = {c["id"] for c in data.get("workCategories", [])} - {"singles", "tearsheet"}
    by_folder = {s["folder"]: s for s in stories}
    processed, new_keys, seen, changed = {}, [], set(), False

    if STORIES_DIR.exists():
        for cat_dir in sorted(p for p in STORIES_DIR.iterdir() if p.is_dir() and not hidden(p)):
            cat = cat_dir.name.lower()
            if cat not in categories:
                say(f"! stories/{cat_dir.name}: not a section (use one of: {', '.join(sorted(categories))})")
                continue
            for folder in sorted(p for p in cat_dir.iterdir() if p.is_dir() and not hidden(p)):
                key = f"{cat}/{folder.name}"
                seen.add(key)
                rec = by_folder.get(key)
                txt = folder / "story.txt"
                meta, desc = ({}, None)
                if txt.exists():
                    meta, desc = parse_story_txt(txt)
                title = meta.get("title") or (rec["title"] if rec and not txt.exists() else None) \
                    or re.sub(r"[_]+", " ", folder.name).strip()
                units = photo_units(folder)

                if rec is None:
                    if not units:
                        say(f"- {key}: no photos yet, nothing to publish")
                        continue
                    taken = site_slugs | {r["slug"] for r in processed.values()} | {s["slug"] for s in stories} | RESERVED
                    slug = squash(meta.get("slug") or title) or squash(folder.name) or "story"
                    base, n = slug, 2
                    while slug in taken:
                        slug, n = f"{base}{n}", n + 1
                    rec = {"folder": key, "slug": slug, "category": cat, "title": title,
                           "description": desc or "", "images": []}
                    changed = True
                    say(f"+ new story: {title}  ({cat}, address /{slug})")
                else:
                    for field, value in (("title", title), ("description", desc if desc is not None else rec.get("description", ""))):
                        if rec.get(field) != value:
                            rec[field] = value
                            changed = True
                    rec["category"] = cat

                number = next_number(rec["images"])
                for unit in units:
                    placed = []
                    for src in unit:
                        number += 1
                        name = f"rojan_shrestha_{rec['slug']}_{number:02d}.jpg"
                        try:
                            shrink(src, IMAGES_DIR / rec["slug"] / name)
                        except Exception as err:  # corrupt or unsupported file: leave it, say so
                            say(f"  ! could not read {src.name}: {err}")
                            number -= 1
                            continue
                        src.unlink()
                        placed.append(f"/images/{rec['slug']}/{name}")
                        rec.setdefault("stems", {})[placed[-1]] = src.stem.lower()
                    if placed:
                        rec["images"].append(placed[0] if len(placed) == 1 else placed)
                        changed = True
                # captions.txt: shown under the photos and used as their descriptions
                cap_file = folder / "captions.txt"
                caps = parse_captions(cap_file) if cap_file.exists() else {}
                captions = {path: caps[stem] for path, stem in rec.get("stems", {}).items() if stem in caps}
                if captions != rec.get("captions", {}):
                    rec["captions"] = captions
                    rec["alt"] = dict(captions)
                    changed = True
                    say(f"  {rec['title']}: {len(captions)} caption(s)")
                if units:
                    say(f"  {rec['title']}: {len(flat(rec['images']))} photographs in total")
                if rec["images"]:
                    processed[key] = rec
                    if key not in by_folder:
                        new_keys.append(key)

    for s in stories:
        if s["folder"] not in seen:
            say(f"- removed story {s['title']} (its folder was deleted)")
            changed = True
    # newest uploads first, then the stories already published in their existing order
    merged = [processed[k] for k in new_keys] + \
             [processed.get(s["folder"], s) for s in stories if s["folder"] in seen]
    return merged, changed


def run_gallery(inbox, folder, prefix, items, label, quality=QUALITY):
    """Photos dropped in `inbox` (singles/ or tearsheet/): shrink them into
    images/<folder>/, read an optional same-name .txt, newest first."""
    changed = False
    if not inbox.exists():
        return items, changed
    taken = {Path(it["image"]).name for it in items}
    fresh = []
    for src in sorted((f for f in inbox.iterdir() if is_photo(f)), key=lambda f: natural_key(f.stem)):
        side = next((f for f in inbox.iterdir()
                     if f.is_file() and f.suffix.lower() == ".txt" and f.stem.lower() == src.stem.lower()), None)
        meta = parse_sidecar(side) if side else {}
        # name the file after the headline/title when one is given (helps Google)
        stem = file_slug(meta.get("title") or src.stem) or "photo"
        name, n = f"{prefix}{stem}.jpg", 2
        while name in taken:
            name, n = f"{prefix}{stem}_{n}.jpg", n + 1
        try:
            shrink(src, IMAGES_DIR / folder / name, quality)
        except Exception as err:
            say(f"  ! could not read {src.name}: {err}")
            continue
        taken.add(name)
        entry = {"image": f"/images/{folder}/{name}"}
        entry.update(meta)
        if side:
            side.unlink()
        src.unlink()
        fresh.append(entry)
        changed = True
        say(f"+ new {label}: {src.name}")
    return fresh + items, changed


def main():
    data = content.load()
    stories = content.read_json("content/stories.json", [])
    singles = content.read_json("content/singles.json", [])
    tearsheet = content.read_json("content/tearsheet.json", [])

    stories, ch1 = run_stories(data, stories)
    singles, ch2 = run_gallery(SINGLES_DIR, "singles", "rojan_shrestha_", singles, "single")
    tearsheet, ch3 = run_gallery(TEARSHEET_DIR, "tearsheet", "rojan_shrestha_", tearsheet,
                                 "tearsheet", quality=88)  # screenshots: keep the text crisp

    for rel, value, changed in (("content/stories.json", stories, ch1),
                                ("content/singles.json", singles, ch2),
                                ("content/tearsheet.json", tearsheet, ch3)):
        path = ROOT / rel
        if changed or not path.exists():
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    import photo_rights  # noqa: E402
    photo_rights.apply_all()
    say("done" if (ch1 or ch2 or ch3) else "nothing new to publish")


if __name__ == "__main__":
    main()
