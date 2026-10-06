#!/usr/bin/env python3
"""Render question / worked-solution crops for the Standard-2 pool from catalog.json.

Each SmarterMaths PDF page is a 2-up landscape print (two app pages side by side).  A question
spans from its header line to the next header; we cut that span into column regions, work out the
horizontal extent of each region from the real content (text lines, drawings, images), render at
200 dpi, strip the grey "Worked Solutions" banner, drop trailing dotted answer lines / rules, and
trim white margins.
"""
import json, os, sys
import numpy as np
import pymupdf

CAT, SRC_DIR, OUT_DIR = sys.argv[1], sys.argv[2], sys.argv[3]
DPI = 200
os.makedirs(OUT_DIR, exist_ok=True)
cat = json.load(open(CAT))

_docs, _boxes = {}, {}


def get_doc(fn):
    if fn not in _docs:
        _docs[fn] = pymupdf.open(os.path.join(SRC_DIR, fn))
    return _docs[fn]


def content_boxes(fn, pno):
    """All content bboxes on a page (text lines, drawings, images), excluding page furniture."""
    key = (fn, pno)
    if key in _boxes:
        return _boxes[key]
    page = get_doc(fn)[pno]
    W, H = page.rect.width, page.rect.height
    boxes = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            t = "".join(s["text"] for s in l["spans"]).strip()
            if not t:
                continue
            if t == "SmarterMaths Client App" or t.startswith("https://teacher.smartermaths") or \
               (len(t) < 8 and "/" in t and t.replace("/", "").isdigit()) or \
               (len(t) > 15 and t[2] == "/" and t[5] == "/" and ":" in t):
                continue
            boxes.append(tuple(l["bbox"]))
    for dr in page.get_drawings():
        r = dr["rect"]
        if r.width > 0.45 * W or r.height > 0.6 * H or r.is_empty:
            continue  # page borders / banners
        boxes.append((r.x0, r.y0, r.x1, r.y1))
    for info in page.get_image_info():
        x0, y0, x1, y1 = info["bbox"]
        if (x1 - x0) > 0.45 * W or (y1 - y0) > 0.6 * H:
            continue
        boxes.append((x0, y0, x1, y1))
    _boxes[key] = boxes
    return boxes


def col_of(box, W):
    return 0 if (box[0] + box[2]) / 2 < W / 2 else 1


def col_box(fn, pno, col, item, y0, y1):
    """Horizontal extent for column `col` between y0..y1, derived from content on that page."""
    page = get_doc(fn)[pno]
    W, H = page.rect.width, page.rect.height
    boxes = content_boxes(fn, pno)
    mine = [b for b in boxes if col_of(b, W) == col and b[3] > y0 and b[1] < y1]
    other = [b for b in boxes if col_of(b, W) != col and b[3] > y0 and b[1] < y1]
    if col == 0:
        x0 = 4
        x1 = (max(b[2] for b in mine) + 6) if mine else W / 2 - 2
        if other:
            x1 = min(x1, min(b[0] for b in other) - 2)
        x1 = max(x1, W / 2 - 40)
    else:
        x1 = W - 4
        x0 = (min(b[0] for b in mine) - 6) if mine else W / 2 + 2
        if other:
            x0 = max(x0, max(b[2] for b in other) + 2)
        x0 = min(x0, W / 2 + 40)
    return x0, x1


def vertical_limits(item, pno, col, H):
    f = item["furniture"].get(f"{pno}_{col}", {"top": 10.0, "bottom": H - 10.0})
    return max(f["top"] + 2, 8), min(f["bottom"] - 2, H - 8)


def regions(item, start, end):
    """List of (page, col, x0, y0, x1, y1) from start anchor to end anchor."""
    fn = item["file"]; doc = get_doc(fn)
    out = []
    p, c = start["page"], start["col"]
    while True:
        H = doc[p].rect.height
        top, bottom = vertical_limits(item, p, c, H)
        y0 = start["y1"] + 1 if (p, c) == (start["page"], start["col"]) else top
        y0 = max(y0, top)
        last = end is not None and (p, c) == (end["page"], end["col"])
        y1 = min(end["y0"] - 4, bottom) if last else bottom
        if y1 - y0 > 4:
            x0, x1 = col_box(fn, p, c, item, y0, y1)
            out.append((p, c, x0, y0, x1, y1))
        if last or end is None and p == doc.page_count - 1 and c == 1:
            break
        c += 1
        if c > 1:
            c = 0; p += 1
        if p >= doc.page_count:
            break
    return out


def strip_banner(arr):
    """Cut off a vertical grey banner sitting in the right part of the crop."""
    g = (arr.max(axis=2) - arr.min(axis=2) < 12) & (arr.mean(axis=2) > 90) & (arr.mean(axis=2) < 200)
    colfrac = g.mean(axis=0)
    grey = colfrac > 0.6
    W = arr.shape[1]
    # find the leftmost start of a contiguous grey run located in the right 25% of the crop
    cut = None
    j = W - 1
    while j >= 0:
        if grey[j]:
            k = j
            while k >= 0 and grey[k]:
                k -= 1
            if (j - k) >= 6 and j >= 0.75 * W:
                cut = k + 1
            j = k
        else:
            j -= 1
    if cut is not None:
        arr = arr[:, :max(cut - 3, 0)]
    return arr


def ink_bands(dark):
    rows = dark.any(axis=1)
    bands = []
    i = 0; n = len(rows)
    while i < n:
        if rows[i]:
            j = i
            while j < n and rows[j]:
                j += 1
            bands.append((i, j))
            i = j
        else:
            i += 1
    return bands


def drop_trailing_rules(arr):
    """Remove trailing bands that are thin (dotted answer lines, horizontal rules)."""
    dark = (arr < 235).any(axis=2)
    bands = ink_bands(dark)
    while bands and (bands[-1][1] - bands[-1][0]) <= 9:
        bands.pop()
    if not bands:
        return None
    return arr[:bands[-1][1] + 1]


def render(item, regs, prefix):
    fn = item["file"]; doc = get_doc(fn)
    files = []
    for k, (p, c, x0, y0, x1, y1) in enumerate(regs):
        pix = doc[p].get_pixmap(clip=pymupdf.Rect(x0, y0, x1, y1), dpi=DPI, colorspace=pymupdf.csRGB)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]
        arr = strip_banner(arr)
        if arr.shape[1] < 40:
            continue
        arr = drop_trailing_rules(arr)
        if arr is None:
            continue
        dark = (arr < 235).any(axis=2)
        rows = np.where(dark.any(axis=1))[0]; cols = np.where(dark.any(axis=0))[0]
        if len(rows) == 0:
            continue
        pad = 8
        r0, r1 = max(rows[0] - pad, 0), min(rows[-1] + pad, arr.shape[0] - 1)
        c0, c1 = max(cols[0] - pad, 0), min(cols[-1] + pad, arr.shape[1] - 1)
        crop = np.ascontiguousarray(arr[r0:r1 + 1, c0:c1 + 1])
        if crop.shape[0] < 60 or crop.shape[1] < 150:
            continue
        out = pymupdf.Pixmap(pymupdf.csRGB, crop.shape[1], crop.shape[0], crop.tobytes(), 0)
        path = f"{prefix}_{k}.png"
        out.save(os.path.join(OUT_DIR, path))
        files.append(dict(path=path, w=crop.shape[1], h=crop.shape[0], page=p, col=c))
    return files


def norm_q(q):
    return (q or "").replace("*", "")


_bodypt = {}
def body_pt(fn):
    """Median body-text font size (PDF points) of a worksheet, used to normalise print size."""
    if fn not in _bodypt:
        sizes = []
        for page in get_doc(fn):
            for b in page.get_text("dict")["blocks"]:
                if b.get("type") != 0:
                    continue
                for l in b["lines"]:
                    for sp in l["spans"]:
                        if 5 <= sp["size"] <= 11 and len(sp["text"].strip()) > 20:
                            sizes.append(sp["size"])
        sizes.sort()
        _bodypt[fn] = sizes[len(sizes) // 2] if sizes else 7.0
    return _bodypt[fn]


pool = [c for c in cat if c["means"] and c["tag"] in ("STD2", "2UG", "STD1") and c["source"] == "HSC" and c["year"]]
groups = {}
for c in pool:
    groups.setdefault((c["year"], norm_q(c["qnum"])), []).append(c)


def pref(c):
    return (0 if c["tag"] == "STD2" else 1, 0 if "Interpretation" in c["file"] else 1, len(c["q_regions"]))


manifest = []
for key, items in groups.items():
    items.sort(key=pref)
    best = items[0]
    year, qn = key
    kid = f"{year}_Q{qn}"
    qregs = regions(best, best["q_start"], best["q_end"])
    sregs = regions(best, best["s_start"], best["s_end"]) if best["s_start"] else []
    qfiles = render(best, qregs, f"{kid}_q")
    sfiles = render(best, sregs, f"{kid}_s")
    allmeans = {}
    for it in items:
        for m in it["means"]:
            allmeans[(m["label"], m["pct"])] = m
    # keep the order of the chosen source's annotations first
    means = list(best["means"])
    for m in allmeans.values():
        if (m["label"], m["pct"]) not in {(x["label"], x["pct"]) for x in means}:
            means.append(m)
    manifest.append(dict(
        id=kid, year=year, qnum=qn, mc=best["mc"], tag=best["tag"], code=best["code"], topic=best["topic"],
        header=best["header"], marks_total=best["marks_total"], marks_parts=best["marks_parts"],
        means=means, rank_pct=min(m["pct"] for m in means),
        source_file=best["file"], source_n=best["n"], body_pt=body_pt(best["file"]),
        alt_sources=[dict(file=i["file"], n=i["n"], tag=i["tag"]) for i in items[1:]],
        q_images=qfiles, s_images=sfiles, q_text=best["q_text"], s_text=best["s_text"],
    ))
manifest.sort(key=lambda m: (m["rank_pct"], -m["year"]))
json.dump(manifest, open(os.path.join(OUT_DIR, "manifest.json"), "w"), indent=1)
for m in manifest:
    print(f"{m['rank_pct']:>3}%  {m['id']:<12} {m['tag']} {m['code'] or '-':<4} {'MC' if m['mc'] else '  '} mk={m['marks_total']}  q={len(m['q_images'])} s={len(m['s_images'])}  {m['topic']}")
print(len(manifest), "unique questions")
