#!/usr/bin/env python3
"""Generate the SEO files for the portfolio from content/site.json.

The site is a single page (index.html) that renders everything in the
browser. On its own, that means /about, /work, /piece/0 ... reply with a
404 status and the home page's title, so search engines will not index
them. This script writes a real page for each route (about.html,
work.html, piece/0.html ...) with its own title, description, canonical
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
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://rojanshrestha.com"

data = json.loads((ROOT / "content/site.json").read_text(encoding="utf-8"))
artist = data["artist"]
name = artist["name"]
pieces = data.get("pieces", [])
tearsheet = data.get("tearsheet", [])
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


def first_sentence(text):
    m = re.match(r"(.+?[.!?])(\s|$)", text.strip())
    return m.group(1) if m else text.strip()


def piece_path(i):
    return f"/piece/{i}"


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
        description=p.get("metaDescription", default_desc),
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


def ld_for(path, r):
    graph = [
        person_node(),
        {"@type": "WebSite", "@id": SITE + "/#website", "name": name, "url": SITE + "/",
         "publisher": {"@id": PERSON_ID}},
    ]
    if path != "/":
        crumbs = [("Home", SITE + "/")]
        if path.startswith("/work/"):
            crumbs.append(("Work", SITE + "/work"))
        if path.startswith("/piece/"):
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
    if r["view"] == "about":
        graph.append({"@type": "AboutPage", "url": SITE + path, "name": r["title"],
                      "mainEntity": {"@id": PERSON_ID}})
    if r["view"] == "contact":
        graph.append({"@type": "ContactPage", "url": SITE + path, "name": r["title"],
                      "mainEntity": {"@id": PERSON_ID}})
    if r["view"] == "piece":
        p = pieces[r["piece"]]
        graph.append({
            "@type": "ImageGallery",
            "name": p["title"],
            "url": SITE + path,
            "description": p.get("description") or r["description"],
            "author": {"@id": PERSON_ID},
            "image": [
                {"@type": "ImageObject", "contentUrl": SITE + src,
                 "name": f"{p['title']} — photograph {n + 1}",
                 "creator": {"@id": PERSON_ID}}
                for n, src in enumerate(flat(p.get("images", []))[:20])
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
    """Put inner_html inside the element with this id (idempotent)."""
    pat = re.compile(r'(id="' + element_id + r'"[^>]*>)(.*?)(</(?:h1|p|a|ul|div)>)', re.S)
    assert pat.search(doc), element_id
    return pat.sub(lambda m: m.group(1) + inner_html + m.group(3), doc, count=1)


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
    doc = fill(doc, "homeHeading", esc(f"{name} — {artist.get('role', 'Photographer')}"))
    doc = fill(doc, "workHeading", esc(f"{name} — Work"))
    doc = fill(doc, "aboutHeading", esc(f"About {name}"))
    doc = fill(doc, "aboutBio", esc(data["about"]["bio"]))
    doc = fill(doc, "aboutFacts", "<br>".join(esc(f) for f in data["about"].get("facts", [])))
    doc = fill(doc, "contactName", esc(name))
    doc = fill(doc, "contactRole", esc(artist.get("role", "")))
    doc = re.sub(r'(<a id="contactEmail" href=")[^"]*(">).*?(</a>)',
                 lambda m: m.group(1) + "mailto:" + esc(artist["email"]) + m.group(2) + esc(artist["email"]) + m.group(3), doc, count=1, flags=re.S)
    tel = re.sub(r"[^\d+]", "", artist["phone"])
    doc = re.sub(r'(<a id="contactPhone" href=")[^"]*(">).*?(</a>)',
                 lambda m: m.group(1) + "tel:" + tel + m.group(2) + esc(artist["phone"]) + m.group(3), doc, count=1, flags=re.S)
    items = []
    for cid in ("projects", "editorial", "tearsheet"):
        if cid in categories:
            items.append(f'<li><a href="/work/{cid}"><span class="name">{esc(categories[cid]["label"])}</span></a></li>')
    doc = fill(doc, "workIndex", "".join(items))
    if r["view"] == "piece":
        p = pieces[r["piece"]]
        doc = fill(doc, "pieceTitle", esc(p["title"]))
        body = ""
        if p.get("description"):
            body += f'<p class="piece-description">{esc(p["description"])}</p>'
        imgs = flat(p.get("images", []))
        for n, src in enumerate(imgs):
            body += f'<img src="{esc(src)}" alt="{esc(p["title"])} — photograph {n + 1} of {len(imgs)}" loading="lazy">'
        doc = fill(doc, "pieceFrame", body)
    if r["view"] == "category":
        links = ""
        for i in category_pieces(r["category"]):
            links += f'<a class="story" href="/piece/{i}"><span class="title">{esc(pieces[i]["title"])}</span></a>'
        doc = fill(doc, "catStories", links)
        doc = fill(doc, "catLabel", esc(categories[r["category"]]["label"]))

    # show the right section straight away (no blank flash while content loads)
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
for path, r in routes.items():
    f = out_file(path)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(render(path, r), encoding="utf-8")
    written.append(str(f.relative_to(ROOT)))
    if path == "/":
        template = f.read_text(encoding="utf-8")  # later pages build on the refreshed home

(ROOT / "404.html").write_text((ROOT / "index.html").read_text(encoding="utf-8"), encoding="utf-8")

# ------------------------------------------------------------------ seo.json
seo_json = {
    p: {"title": r["title"], "description": r["description"], "image": r["image_url"]}
    for p, r in routes.items()
}
(ROOT / "content/seo.json").write_text(json.dumps(seo_json, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# ----------------------------------------------------------------- sitemap.xml
today = datetime.date.today().isoformat()
lines = ['<?xml version="1.0" encoding="UTF-8"?>',
         '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
         'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
priority = {"/": "1.0", "/work": "0.9", "/work/projects": "0.8"}
for path, r in routes.items():
    loc = SITE + ("/" if path == "/" else path)
    lines += ["  <url>", f"    <loc>{loc}</loc>", f"    <lastmod>{today}</lastmod>",
              f"    <priority>{priority.get(path, '0.7' if path.startswith('/piece') else '0.6')}</priority>"]
    if r["view"] == "piece":
        for src in flat(pieces[r["piece"]].get("images", [])):
            lines.append(f"    <image:image><image:loc>{SITE}{esc(src)}</image:loc></image:image>")
    elif path == "/":
        lines.append(f"    <image:image><image:loc>{SITE}{esc(HOME_IMAGE)}</image:loc></image:image>")
    lines.append("  </url>")
lines.append("</urlset>")
(ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")

print("wrote:", ", ".join(written + ["404.html", "content/seo.json", "sitemap.xml"]))
