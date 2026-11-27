#!/usr/bin/env python3
"""Generate the SEO files for the portfolio from content/site.json.

The site is a single page (index.html) that renders everything in the
browser. On its own, that means /about, /work, /bittersugar ... reply with a
404 status and the home page's title, so search engines will not index
them. This script writes a real page for each route (about.html,
work.html, bittersugar.html ...) with its own title, description, canonical
link, social-share tags and structured data, plus content/seo.json (used
by the page while you click around) and sitemap.xml.

Run it from the project folder after changing content/site.json or
index.html:

    python3 tools/build_seo.py

Python 3 standard library only.
"""
import datetime
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import content  # noqa: E402  (merges site.json with the uploaded stories/singles)

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://rojanshrestha.com"

data = content.load()
artist = data["artist"]
name = artist["name"]
pieces = data.get("pieces", [])
tearsheet = data.get("tearsheet", [])
singles = data.get("singles", [])
categories = {c["id"]: c for c in data.get("workCategories", [])}
overrides = data.get("seo", {})  # optional hand-written overrides per route

HOME_IMAGE = data["home"]["photo"]
HOME_ALT = data["home"].get("alt", "")


def esc(s):
    return html.escape(s, quote=True)


def flat(images):
    out = []
    for x in images:
        out.extend(x if isinstance(x, list) else [x])
    return out


def jpeg_size(path):
    """(width, height) of a JPEG, read from its header (no image library needed)."""
    import struct
    with open(path, "rb") as f:
        data = f.read()
    i = 2
    while i < len(data) - 9:
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        length = struct.unpack(">H", data[i + 2:i + 4])[0]
        i += 2 + length
    return None


def first_sentence(text):
    m = re.match(r"(.+?[.!?])(\s|$)", text.strip())
    return m.group(1) if m else text.strip()


RESERVED = {"work", "about", "contact", "piece", "content", "images", "models", "tools"}


def snippet(text, limit=155):
    """First sentence of a description, trimmed to fit a search result."""
    one = first_sentence(" ".join(text.split()))
    if len(one) <= limit:
        return one
    return one[: limit - 1].rsplit(" ", 1)[0].rstrip(",;:") + "\u2026"


def piece_path(i):
    """A project's address is its slug (e.g. /bittersugar)."""
    slug = pieces[i].get("slug")
    assert slug and re.fullmatch(r"[a-z0-9-]+", slug) and slug not in RESERVED, \
        f"piece {i} needs a unique lowercase 'slug' in site.json (got {slug!r})"
    return "/" + slug


def category_pieces(cat_id):
    return [i for i, p in enumerate(pieces) if p.get("category", "projects") == cat_id]


# ---------------------------------------------------------------- route table
HOME_TITLE = f"{name} | Photographer and Photojournalist, Kathmandu"
routes = {}

routes["/"] = dict(
    title=HOME_TITLE,
    description=(
        f"Portfolio of {name}, photographer and photojournalist in Kathmandu, "
        "Nepal: projects including “If you could do it all again” and "
        "“Bitter Sugar.”"
    ),
    image=HOME_IMAGE, image_alt=HOME_ALT, view="home",
)
routes["/work"] = dict(
    title=f"Work | {name}",
    description=(f"Photographic projects by {name}, photographer and "
                 "photojournalist based in Kathmandu, Nepal."),
    image=HOME_IMAGE, image_alt=HOME_ALT, view="work",
)
if category_pieces("projects"):
    titles = [pieces[i]["title"] for i in category_pieces("projects")]
    routes["/work/projects"] = dict(
        title=f"Projects | {name}",
        description=f"Photographic projects by {name}: "
                    + " and ".join(f"“{t}”" for t in titles) + ".",
        image=flat(pieces[category_pieces("projects")[0]]["images"])[0],
        view="category", category="projects",
    )
if category_pieces("editorial"):
    routes["/work/editorial"] = dict(
        title=f"Editorial | {name}",
        description=f"Editorial photography by {name}, photojournalist based in Kathmandu, Nepal.",
        image=flat(pieces[category_pieces("editorial")[0]]["images"])[0],
        view="category", category="editorial",
    )
if tearsheet:
    routes["/work/tearsheet"] = dict(
        title=f"Tearsheet | {name}",
        description=f"Photographs by {name} as published in international media.",
        image=tearsheet[0]["image"], view="tearsheet",
    )
# the Singles page always exists (the Work page links to it); while it has no
# photos it asks search engines not to list it and stays out of the sitemap
routes["/work/singles"] = dict(
    title=f"Singles | {name}",
    description=f"Single photographs by {name}, photographer and photojournalist based in Kathmandu, Nepal.",
    image=singles[0]["image"] if singles else HOME_IMAGE, view="singles",
    noindex=not singles,
)
routes["/about"] = dict(
    title=f"About {name} | Photojournalist, Kathmandu",
    description=first_sentence(data["about"]["bio"]),
    image=HOME_IMAGE, image_alt=HOME_ALT, view="about",
)
routes["/contact"] = dict(
    title=f"Contact | {name}",
    description=(f"Contact {name}, photographer and photojournalist in "
                 "Kathmandu, Nepal, for assignments and prints."),
    image=HOME_IMAGE, image_alt=HOME_ALT, view="contact",
)
for i, p in enumerate(pieces):
    imgs = flat(p.get("images", []))
    default_desc = (f"{p['title']}, a photographic project by {name}, "
                    "photographer and photojournalist based in Kathmandu, Nepal.")
    routes[piece_path(i)] = dict(
        title=f"{p['title']} | {name}",
        description=p.get("metaDescription") or snippet(p.get("description", "")) or default_desc,
        image=imgs[0] if imgs else HOME_IMAGE,
        view="piece", piece=i,
    )

for path, extra in overrides.items():
    if path in routes:
        routes[path].update(extra)

for r in routes.values():
    r["image_url"] = SITE + r["image"]


# ------------------------------------------------------------- structured data
PERSON_ID = SITE + "/#person"


def person_node():
    return {
        "@type": "Person",
        "@id": PERSON_ID,
        "name": name,
        "alternateName": artist.get("nameDevanagari", ""),
        "url": SITE + "/",
        "image": SITE + HOME_IMAGE,
        "jobTitle": artist.get("role", "Photographer"),
        "description": data["about"]["bio"],
        "email": "mailto:" + artist["email"],
        "address": {"@type": "PostalAddress", "addressLocality": "Kathmandu", "addressCountry": "NP"},
        "sameAs": [u for u in artist.get("social", {}).values() if u],
    }


RIGHTS = artist.get("rights", {})
LICENSE_URL = SITE + RIGHTS.get("licensePage", "/contact")


def photo_node(src, description, title=""):
    """A photo with its creator, credit, copyright and licence page, so
    Google Images can show the photographer and a Licensable badge."""
    node = {"@type": "ImageObject", "contentUrl": SITE + src,
            "creator": {"@id": PERSON_ID},
            "creditText": RIGHTS.get("credit", name),
            "copyrightNotice": RIGHTS.get("copyright", f"© {name}"),
            "license": LICENSE_URL,
            "acquireLicensePage": LICENSE_URL}
    if title:
        node["name"] = title
    if description:
        node["description"] = description
    return node


def ld_for(path, r):
    graph = [
        person_node(),
        {"@type": "WebSite", "@id": SITE + "/#website", "name": name,
         "alternateName": [x for x in (artist.get("nameDevanagari"), "rojanshrestha.com") if x],
         "url": SITE + "/",
         "publisher": {"@id": PERSON_ID}},
    ]
    if path != "/":
        crumbs = [("Home", SITE + "/")]
        if path.startswith("/work/"):
            crumbs.append(("Work", SITE + "/work"))
        if r["view"] == "piece":
            crumbs.append(("Work", SITE + "/work"))
            crumbs.append(("Projects", SITE + "/work/projects"))
        crumbs.append((r["title"].split(" | ")[0], SITE + path))
        graph.append({
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": n + 1, "name": t, "item": u}
                for n, (t, u) in enumerate(crumbs)
            ],
        })
    if path == "/":
        graph.append(photo_node(HOME_IMAGE, HOME_ALT))
    if r["view"] == "about":
        graph.append({"@type": "AboutPage", "url": SITE + path, "name": r["title"],
                      "mainEntity": {"@id": PERSON_ID}})
    if r["view"] == "contact":
        graph.append({"@type": "ContactPage", "url": SITE + path, "name": r["title"],
                      "mainEntity": {"@id": PERSON_ID}})
    if r["view"] == "singles":
        graph.append({
            "@type": "ImageGallery", "name": "Singles", "url": SITE + path,
            "description": r["description"], "author": {"@id": PERSON_ID},
            "image": [photo_node(it["image"], it.get("alt", ""), it.get("title") or f"Photograph {n + 1}")
                      for n, it in enumerate(singles)],
        })
    if r["view"] == "piece":
        p = pieces[r["piece"]]
        graph.append({
            "@type": "ImageGallery",
            "name": p["title"],
            "url": SITE + path,
            "description": p.get("description") or r["description"],
            "author": {"@id": PERSON_ID},
            "image": [
                photo_node(src, (p.get("alt") or {}).get(src, ""), f"{p['title']} — photograph {n + 1}")
                for n, src in enumerate(flat(p.get("images", [])))
            ],
        })
    return {"@context": "https://schema.org", "@graph": graph}


# --------------------------------------------------------------- page rewriting
template = (ROOT / "index.html").read_text(encoding="utf-8")


def set_meta(doc, selector_re, value):
    """Replace content="..." of the first <meta> matching selector_re."""
    pat = re.compile(r'(<meta\s+' + selector_re + r'\s+content=")[^"]*(")')
    assert pat.search(doc), selector_re
    return pat.sub(lambda m: m.group(1) + esc(value) + m.group(2), doc, count=1)


def fill(doc, element_id, inner_html):
    """Put inner_html inside the element with this id. Finds the element's
    real closing tag (counting nested tags), so it is safe to run repeatedly."""
    m = re.search(r'<(\w+)\b[^>]*\bid="' + re.escape(element_id) + r'"[^>]*>', doc)
    assert m, element_id
    tag, start, depth = m.group(1), m.end(), 1
    for t in re.finditer(r"<(/?)" + tag + r"\b[^>]*>", doc[start:]):
        depth += -1 if t.group(1) else 1
        if depth == 0:
            return doc[:start] + inner_html + doc[start + t.start():]
    raise AssertionError("unclosed element " + element_id)


def render(path, r):
    doc = template
    url = SITE + ("/" if path == "/" else path)
    doc = re.sub(r"<title>.*?</title>", lambda m: "<title>" + esc(r["title"]) + "</title>", doc, count=1, flags=re.S)
    doc = set_meta(doc, r'name="description"', r["description"])
    doc = re.sub(r'(<link rel="canonical" href=")[^"]*(")', lambda m: m.group(1) + url + m.group(2), doc, count=1)
    doc = set_meta(doc, r'property="og:title"', r["title"])
    doc = set_meta(doc, r'property="og:description"', r["description"])
    doc = set_meta(doc, r'property="og:url"', url)
    doc = set_meta(doc, r'property="og:image"', r["image_url"])
    doc = set_meta(doc, r'property="og:image:alt"', r.get("image_alt") or r["title"])
    doc = set_meta(doc, r'name="twitter:title"', r["title"])
    doc = set_meta(doc, r'name="twitter:description"', r["description"])
    doc = set_meta(doc, r'name="twitter:image"', r["image_url"])
    ld = json.dumps(ld_for(path, r), ensure_ascii=False, indent=2).replace("</", "<\\/")
    doc = re.sub(r'(<script type="application/ld\+json">\s*).*?(\s*</script>)',
                 lambda m: m.group(1) + ld + m.group(2), doc, count=1, flags=re.S)

    # readable text in the HTML itself, for crawlers that do not run scripts
    # The home page is the page about the artist (name, bio, contact); every
    # other page carries only its own text, so Google ranks the home page for
    # the name instead of whichever page has the most copies of the bio.
    view = r["view"]
    is_home = view == "home"
    with_bio = is_home or view == "about"
    with_contact = is_home or view == "contact"
    doc = fill(doc, "brandLink", f'<span class="brand-name">{esc(artist.get("nameDevanagari", name))}</span>'
                                 f'<span class="sr-only"> {esc(name)}</span>')
    doc = fill(doc, "homeHeading", esc(f"{name} \u2014 Photographer and photojournalist in Kathmandu, Nepal") if is_home else "")
    doc = fill(doc, "workHeading", esc(f"{name} \u2014 Work") if view == "work" else "")
    doc = fill(doc, "aboutHeading", esc(f"About {name}") if with_bio else "")
    # About: the bio's first sentence is the large statement, the rest sits below
    bio = data["about"]["bio"]
    m = re.match(r"^(.+?\.)\s+(.*)$", bio, re.S)
    statement, rest = (m.group(1), m.group(2)) if m else (bio, "")
    doc = fill(doc, "aboutStatement", esc(statement) if with_bio else "")
    doc = fill(doc, "aboutBio", esc(rest) if with_bio else "")
    doc = fill(doc, "aboutFacts", "<br>".join(esc(f) for f in data["about"].get("facts", [])) if with_bio else "")
    doc = fill(doc, "aboutWorked", "<br>".join(esc(f) for f in data["about"].get("workedWith", [])) if with_bio else "")
    workshops = "".join(
        f'<div class="ws"><span class="ws-title">{esc(w["title"])}</span>'
        f'<span class="ws-where">{esc(" — ".join(x for x in (w.get("place"), w.get("year")) if x))}</span></div>'
        for w in data["about"].get("workshops", []))
    doc = fill(doc, "aboutWorkshops", workshops if with_bio else "")
    pubs = sorted({t["publication"] for t in data.get("tearsheet", []) if t.get("publication")}, key=str.lower)
    doc = fill(doc, "aboutPubs", esc(", ".join(pubs)) if with_bio else "")
    note = next((f for f in data["about"].get("facts", []) if re.search(r"assignment|print", f, re.I)), "")
    doc = fill(doc, "contactNote", esc(note) if with_contact else "")
    doc = fill(doc, "contactRights", esc(RIGHTS.get("note", "")) if with_contact else "")
    if r.get("noindex"):
        doc = doc.replace('<link rel="canonical"', '<meta name="robots" content="noindex">\n<link rel="canonical"', 1)
    doc = fill(doc, "contactName", esc(name) if with_contact else "")
    doc = fill(doc, "contactRole", esc(artist.get("role", "")) if with_contact else "")
    tel = re.sub(r"[^\d+]", "", artist["phone"])
    email_href, email_text = ("mailto:" + esc(artist["email"]), esc(artist["email"])) if with_contact else ("#", "")
    phone_href, phone_text = ("tel:" + tel, esc(artist["phone"])) if with_contact else ("#", "")
    doc = re.sub(r'(<a id="contactEmail" href=")[^"]*(">).*?(</a>)',
                 lambda m: m.group(1) + email_href + m.group(2) + email_text + m.group(3), doc, count=1, flags=re.S)
    doc = re.sub(r'(<a id="contactPhone" href=")[^"]*(">).*?(</a>)',
                 lambda m: m.group(1) + phone_href + m.group(2) + phone_text + m.group(3), doc, count=1, flags=re.S)
    items = []
    for cid, c in categories.items():
        items.append(f'<li><a href="/work/{cid}"><span class="name">{esc(c["label"])}</span></a></li>')
    doc = fill(doc, "workIndex", "".join(items))
    if r["view"] == "piece":
        p = pieces[r["piece"]]
        doc = fill(doc, "pieceTitle", esc(p["title"]))
        body = ""
        if p.get("description"):
            paras = "".join(f"<p>{esc(t)}</p>" for t in re.split(r"\n\s*\n", p["description"]) if t.strip())
            body += f'<div class="piece-description">{paras}</div>'
        imgs = flat(p.get("images", []))
        alts, caps = p.get("alt") or {}, p.get("captions") or {}
        for n, src in enumerate(imgs):
            alt = alts.get(src) or f'{p["title"]} — photograph {n + 1} of {len(imgs)}'
            body += f'<img src="{esc(src)}" alt="{esc(alt)}" loading="lazy">'
            if caps.get(src):
                body += f'<p class="photo-caption">{esc(caps[src])}</p>'
        doc = fill(doc, "pieceFrame", body)
    if r["view"] == "category":
        links = ""
        for i in category_pieces(r["category"]):
            links += f'<a class="prow" href="{piece_path(i)}"><span class="pt">{esc(pieces[i]["title"])}</span></a>'
        doc = fill(doc, "catStories", links)
        doc = fill(doc, "catLabel", esc(categories[r["category"]]["label"]))

    # show the right section straight away (no blank flash while content loads)
    doc = re.sub(r'(<section class="view) active"', r'\1"', doc)
    if r["view"] in ("home", "work", "about", "contact"):
        doc = re.sub(r'(<section class="view)(" data-view="' + r["view"] + '")',
                     lambda m: m.group(1) + " active" + m.group(2), doc, count=1)
    return doc


def out_file(path):
    if path == "/":
        return ROOT / "index.html"
    return ROOT / (path.strip("/") + ".html")


# the template is index.html itself, so build the home page last and from a
# clean copy of its own head/body (render() is idempotent)
written = []
# pages written on an earlier run for stories/sections that no longer exist are removed
manifest_file = ROOT / "content/generated-pages.json"
previous_pages = set(json.loads(manifest_file.read_text())) if manifest_file.exists() else set()
current_pages = {str(out_file(p).relative_to(ROOT)) for p in routes if p != "/"}
for stale in sorted(previous_pages - current_pages):
    stale_file = ROOT / stale
    if stale_file.exists():
        stale_file.unlink()
        print("removed old page:", stale)
manifest_file.write_text(json.dumps(sorted(current_pages), indent=2) + "\n", encoding="utf-8")

for path, r in routes.items():
    f = out_file(path)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(render(path, r), encoding="utf-8")
    written.append(str(f.relative_to(ROOT)))
    if path == "/":
        template = f.read_text(encoding="utf-8")  # later pages build on the refreshed home

# old /piece/N addresses: small pages that forward to the project's own address
for i, original in enumerate(data["_site_pieces"]):
    new = "/" + original["slug"]
    stub = ROOT / "piece" / f"{i}.html"
    stub.parent.mkdir(exist_ok=True)
    stub.write_text(
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">\n'
        f'<title>{esc(routes[new]["title"])}</title>\n'
        f'<link rel="canonical" href="{SITE}{new}">\n'
        f'<meta http-equiv="refresh" content="0; url={new}">\n'
        f'<script>location.replace("{new}");</script>\n'
        '</head><body>\n'
        f'<p><a href="{new}">{esc(original["title"])}</a></p>\n'
        '</body></html>\n', encoding="utf-8")
    written.append(str(stub.relative_to(ROOT)))

(ROOT / "404.html").write_text((ROOT / "index.html").read_text(encoding="utf-8"), encoding="utf-8")

# ------------------------------------------------------------------ seo.json
seo_json = {
    p: {"title": r["title"], "description": r["description"], "image": r["image_url"]}
    for p, r in routes.items()
}
# photo sizes, so the page can reserve each photo's space before it loads
sizes = {}
for src in ([HOME_IMAGE] + [s for p in pieces for s in flat(p.get("images", []))]
            + [it["image"] for it in singles]):
    f = ROOT / src.lstrip("/")
    if f.exists() and src not in sizes:
        wh = jpeg_size(f)
        if wh:
            sizes[src] = list(wh)
seo_json["_sizes"] = sizes
(ROOT / "content/seo.json").write_text(json.dumps(seo_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ----------------------------------------------------------------- sitemap.xml
today = datetime.date.today().isoformat()
import hashlib
lastmod_file = ROOT / "content/lastmod.json"
lastmod = json.loads(lastmod_file.read_text()) if lastmod_file.exists() else {}
for path in routes:
    digest = hashlib.sha1((ROOT / ("index.html" if path == "/" else path.strip("/") + ".html")).read_bytes()).hexdigest()
    if lastmod.get(path, {}).get("hash") != digest:
        lastmod[path] = {"hash": digest, "date": today}
lastmod = {p: v for p, v in lastmod.items() if p in routes}
lastmod_file.write_text(json.dumps(lastmod, indent=2, sort_keys=True) + "\n", encoding="utf-8")
lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
         'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
priority = {"/": "1.0", "/work": "0.9", "/work/projects": "0.8"}
for path, r in routes.items():
    if r.get("noindex"):
        continue
    loc = SITE + ("/" if path == "/" else path)
    lines += ["  <url>", f"    <loc>{loc}</loc>", f"    <lastmod>{lastmod[path]['date']}</lastmod>",
              f"    <priority>{priority.get(path, '0.7' if r["view"] == "piece" else '0.6')}</priority>"]
    if r["view"] == "piece":
        for src in flat(pieces[r["piece"]].get("images", [])):
            lines.append(f"    <image:image><image:loc>{SITE}{esc(src)}</image:loc></image:image>")
    elif r["view"] in ("singles", "tearsheet"):
        for it in (singles if r["view"] == "singles" else tearsheet):
            lines.append(f"    <image:image><image:loc>{SITE}{esc(it['image'])}</image:loc></image:image>")
    elif path == "/":
        lines.append(f"    <image:image><image:loc>{SITE}{esc(HOME_IMAGE)}</image:loc></image:image>")
    lines.append("  </url>")
lines.append("</urlset>")
(ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")

print("wrote:", ", ".join(written + ["404.html", "content/seo.json", "sitemap.xml"]))
