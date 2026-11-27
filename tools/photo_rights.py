#!/usr/bin/env python3
"""Write the photographer's name, credit line and copyright into every photo.

Google Images reads these fields from the file itself and can show
"Creator", "Credit" and "Copyright" under a photo, plus a "Licensable"
badge linking to the licence page. Because they live inside the file,
they stay with the photo when someone else re-posts it.

The fields are written twice, in the two formats in use:
  * XMP   (dc:creator, photoshop:Credit, dc:rights, xmpRights:WebStatement,
           plus:Licensor/LicensorURL, dc:description)
  * IPTC  (By-line, Credit, Copyright Notice), the older format some tools read

The photo itself is not re-saved: only these two metadata blocks are
replaced, so image quality is untouched. Running it again changes nothing
unless the details changed.

Covers the story photos, singles and the home photo, never the tearsheets
(those are the publications' pages). Settings come from "rights" in
content/site.json. Run by hand with:

    python3 tools/photo_rights.py

Python 3 standard library only.
"""
import re
import struct
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
import content  # noqa: E402

SITE = "https://rojanshrestha.com"
XMP_HEADER = b"http://ns.adobe.com/xap/1.0/\x00"
PS_HEADER = b"Photoshop 3.0\x00"


def xmp_packet(creator, credit, copyright_text, license_url, description="", dates=None):
    a = lambda s: escape(s, {'"': "&quot;"})
    dates = dates or {}
    date_attrs = "".join(f'\n    {k}="{a(v)}"' for k, v in sorted(dates.items()))
    desc = (f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{escape(description)}'
            f"</rdf:li></rdf:Alt></dc:description>") if description else ""
    xml = f"""<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>
<x:xmpmeta xmlns:x="adobe:ns:meta/">
 <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">
  <rdf:Description rdf:about=""
    xmlns:dc="http://purl.org/dc/elements/1.1/"
    xmlns:photoshop="http://ns.adobe.com/photoshop/1.0/"
    xmlns:xmpRights="http://ns.adobe.com/xap/1.0/rights/"
    xmlns:plus="http://ns.useplus.org/ldf/xmp/1.0/"
    xmlns:xmp="http://ns.adobe.com/xap/1.0/"{date_attrs}
    photoshop:Credit="{a(credit)}"
    xmpRights:Marked="True"
    xmpRights:WebStatement="{a(license_url)}">
   <dc:creator><rdf:Seq><rdf:li>{escape(creator)}</rdf:li></rdf:Seq></dc:creator>
   <dc:rights><rdf:Alt><rdf:li xml:lang="x-default">{escape(copyright_text)}</rdf:li></rdf:Alt></dc:rights>
   {desc}
   <plus:Licensor><rdf:Seq><rdf:li rdf:parseType="Resource"><plus:LicensorURL>{escape(license_url)}</plus:LicensorURL></rdf:li></rdf:Seq></plus:Licensor>
  </rdf:Description>
 </rdf:RDF>
</x:xmpmeta>
<?xpacket end="w"?>"""
    return xml.encode("utf-8")


OURS = {(1, 90), (2, 0), (2, 80), (2, 110), (2, 116)}


def old_iim(ps_payload):
    """IPTC-IIM records already in a Photoshop block, as [(record, number, value)]."""
    out, data = [], ps_payload[len(PS_HEADER):]
    i = data.find(b"8BIM\x04\x04")
    if i < 0:
        return out
    name_len = data[i + 6]
    j = i + 6 + 1 + name_len + ((1 + name_len) % 2)
    size = struct.unpack(">I", data[j:j + 4])[0]
    iim, k = data[j + 4:j + 4 + size], 0
    while k + 5 <= len(iim) and iim[k] == 0x1C:
        rec, num, ln = iim[k + 1], iim[k + 2], struct.unpack(">H", iim[k + 3:k + 5])[0]
        out.append((rec, num, iim[k + 5:k + 5 + ln]))
        k += 5 + ln
    return out


def iptc_block(creator, credit, copyright_text, keep=()):
    """Photoshop image resource 0x0404 holding IPTC-IIM records, as UTF-8.
    `keep` carries over the photo's other records, such as the date taken."""
    def dataset(record, number, value):
        return b"\x1c" + bytes([record, number]) + struct.pack(">H", len(value)) + value
    kept = b"".join(dataset(r, n, v) for r, n, v in keep if (r, n) not in OURS)
    iim = (dataset(1, 90, b"\x1b%G")                      # coded character set: UTF-8
           + dataset(2, 0, b"\x00\x04")                    # record version
           + dataset(2, 80, creator.encode("utf-8"))       # By-line (creator)
           + dataset(2, 110, credit.encode("utf-8"))       # Credit
           + dataset(2, 116, copyright_text.encode("utf-8"))  # Copyright Notice
           + kept)
    resource = b"8BIM" + struct.pack(">H", 0x0404) + b"\x00\x00" + struct.pack(">I", len(iim)) + iim
    if len(resource) % 2:
        resource += b"\x00"
    return PS_HEADER + resource


def segment(marker, payload):
    assert len(payload) + 2 <= 0xFFFF, "metadata block too large"
    return b"\xff" + bytes([marker]) + struct.pack(">H", len(payload) + 2) + payload


DATE_FIELDS = ("photoshop:DateCreated", "xmp:CreateDate")


def with_rights(jpeg, s, description=""):
    """Return the JPEG bytes with our XMP (APP1) and IPTC (APP13) blocks,
    replacing any earlier ones. The capture dates already in the photo are
    kept; other old XMP (camera serial numbers, lens) is dropped. Image data
    is copied unchanged."""
    if jpeg[:2] != b"\xff\xd8":
        raise ValueError("not a JPEG")
    pos, kept_head, insert_at = 2, [], None
    dates, keep_iim = {}, []
    while pos < len(jpeg):
        if jpeg[pos] != 0xFF:
            raise ValueError("unexpected JPEG structure")
        marker = jpeg[pos + 1]
        if marker == 0xD9 or marker == 0xDA:      # end of image / start of scan: rest is image data
            break
        length = struct.unpack(">H", jpeg[pos + 2:pos + 4])[0]
        seg = jpeg[pos:pos + 2 + length]
        payload = seg[4:]
        old_xmp = marker == 0xE1 and payload.startswith(XMP_HEADER)
        old_iptc = marker == 0xED and payload.startswith(PS_HEADER)
        if old_xmp:
            text = payload[len(XMP_HEADER):].decode("utf-8", "replace")
            for field in DATE_FIELDS:
                m = re.search(field + r'="([^"]+)"', text) or re.search("<" + field + r">([^<]+)<", text)
                if m:
                    dates[field] = m.group(1)
        if old_iptc:
            keep_iim = old_iim(payload)
        if not (old_xmp or old_iptc):
            kept_head.append(seg)
        if marker in (0xE0, 0xE1) and not old_xmp:   # keep JFIF / Exif first
            insert_at = len(kept_head)
        pos += 2 + length
    xmp = xmp_packet(s["creator"], s["credit"], s["copyright_text"], s["license_url"], description, dates)
    iptc = iptc_block(s["creator"], s["credit"], s["copyright_text"], keep_iim)
    ours = [segment(0xE1, XMP_HEADER + xmp), segment(0xED, iptc)]
    at = insert_at if insert_at is not None else 0
    head = kept_head[:at] + ours + kept_head[at:]
    return b"\xff\xd8" + b"".join(head) + jpeg[pos:]


def settings():
    data = content.load()
    artist = data["artist"]
    r = artist.get("rights", {})
    name = artist["name"]
    alts = {}
    for p in data.get("pieces", []):
        alts.update(p.get("alt", {}))
    for s in data.get("singles", []):
        if s.get("alt"):
            alts[s["image"]] = s["alt"]
    if data.get("home", {}).get("alt"):
        alts[data["home"]["photo"]] = data["home"]["alt"]
    return dict(creator=name, credit=r.get("credit", name),
                copyright_text=r.get("copyright", f"© {name}. All rights reserved."),
                license_url=SITE + r.get("licensePage", "/contact")), alts


def photos():
    """Every photo except the tearsheets."""
    images = ROOT / "images"
    for f in sorted(images.rglob("*")):
        if f.suffix.lower() in (".jpg", ".jpeg") and "tearsheet" not in f.relative_to(images).parts:
            yield f


def apply_all(quiet=False):
    s, alts = settings()
    changed = 0
    for f in photos():
        web_path = "/" + str(f.relative_to(ROOT)).replace("\\", "/")
        before = f.read_bytes()
        after = with_rights(before, s, alts.get(web_path, ""))
        if after != before:
            f.write_bytes(after)
            changed += 1
    if not quiet:
        print(f"photo rights: {changed} photo(s) updated")
    return changed


if __name__ == "__main__":
    apply_all()
