#!/usr/bin/env python3
"""Parse SmarterMaths worksheet PDFs (2-up landscape prints) into a question catalog.

For every worksheet we locate each question header ("N. Topic, TAG CODE YEAR SRC QNUM [MC]")
both in the Questions section and in the Worked Solutions section, record the page/column
regions each spans, extract the text, and pull out every "Mean mark xx%" annotation that
SmarterMaths prints in the worked solution (state mean mark as a percentage of the marks
available).
"""
import json, os, re, sys
import pymupdf

SRC_DIR = sys.argv[1]
OUT = sys.argv[2]

HEADER_RE = re.compile(
    r"^\s*(\d{1,3})\.\s+(.+?),\s+(STD2|STD1|2ADV|2UG|2UA|2U|3U|EXT1|EXT2|MET1|MET2|SPEC|MA|ME|FUR)\s+(.*?)\s*$"
)
MEAN_RE = re.compile(r"[Mm]ean mark[^%\d]{0,45}?(\d{1,3})%")
MARKS_RE = re.compile(r"\((\d+)\s+marks?\)")

SKIP_FILES = ("Sydney_Grammar",)


def page_lines(page):
    """Return list of dicts: text, bbox, col for each text line on the page."""
    W = page.rect.width
    out = []
    d = page.get_text("dict")
    for b in d["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b["lines"]:
            text = "".join(s["text"] for s in l["spans"]).strip()
            if not text:
                continue
            x0, y0, x1, y1 = l["bbox"]
            col = 0 if (x0 + x1) / 2 < W / 2 else 1
            out.append(dict(text=text, x0=x0, y0=y0, x1=x1, y1=y1, col=col,
                            size=max(s["size"] for s in l["spans"]),
                            bold=any("Bold" in s["font"] or "bold" in s["font"].lower() for s in l["spans"])))
    return out


def parse_header(m):
    n, topic, tag, rest = int(m.group(1)), m.group(2).strip(), m.group(3), m.group(4).strip()
    rest = rest.replace("–", "-")
    code = None; year = None; source = None; qnum = None; mc = False
    toks = rest.split()
    if toks and toks[-1] == "MC":
        mc = True; toks = toks[:-1]
    # patterns: [CODE] YEAR SRC QNUM | [CODE] SM-Bank N | [CODE] EQ-Bank N
    if toks and re.fullmatch(r"[A-Z]\d(\.\d)?", toks[0]):
        code = toks[0]; toks = toks[1:]
    if toks and re.fullmatch(r"(19|20)\d\d", toks[0]):
        year = int(toks[0]); toks = toks[1:]
    if toks:
        source = toks[0]; toks = toks[1:]
    if toks:
        qnum = " ".join(toks)
    if source and re.fullmatch(r"\d+[a-z]?\*?", source) and qnum is None:
        qnum, source = source, "HSC"
    return dict(n=n, topic=topic, tag=tag, code=code, year=year, source=source, qnum=qnum, mc=mc,
                header=m.group(0).strip())


def main():
    catalog = []
    for fn in sorted(os.listdir(SRC_DIR)):
        if not fn.lower().endswith(".pdf") or any(s in fn for s in SKIP_FILES):
            continue
        path = os.path.join(SRC_DIR, fn)
        doc = pymupdf.open(path)
        W, H = doc[0].rect.width, doc[0].rect.height
        # gather all lines in reading order: page, col, y
        all_lines = []
        for pno, page in enumerate(doc):
            for l in page_lines(page):
                l["page"] = pno
                all_lines.append(l)
        furniture = {}
        for l in all_lines:
            t = l["text"]
            if re.match(r"^\d{2}/\d{2}/\d{4}, \d{2}:\d{2}", t) or t == "SmarterMaths Client App" or t.startswith("https://teacher.smartermaths") or re.fullmatch(r"\d+/\d+", t):
                f = furniture.setdefault((l["page"], l["col"]), dict(top=0.0, bottom=H))
                if l["y1"] < H / 2:
                    f["top"] = max(f["top"], l["y1"])
                else:
                    f["bottom"] = min(f["bottom"], l["y0"])
        all_lines = [l for l in all_lines if not (re.match(r"^\d{2}/\d{2}/\d{4}, \d{2}:\d{2}", l["text"]) or l["text"] == "SmarterMaths Client App" or l["text"].startswith("https://teacher.smartermaths") or re.fullmatch(r"\d+/\d+", l["text"]))]
        all_lines.sort(key=lambda l: (l["page"], l["col"], l["y0"], l["x0"]))
        # mark anchors
        anchors = []  # (idx, kind, info)
        for i, l in enumerate(all_lines):
            m = HEADER_RE.match(l["text"])
            if m and l["size"] >= 8:
                anchors.append((i, "q", parse_header(m)))
            elif re.fullmatch(r"Worked Solutions", l["text"]) and l["bold"] and l["size"] > 8:
                anchors.append((i, "ws", None))
            elif l["text"].startswith("Copyright ©"):
                anchors.append((i, "copy", None))
        # split into question section and solution section
        ws_idx = [a for a in anchors if a[1] == "ws"]
        ws_line = ws_idx[0][0] if ws_idx else None
        if ws_line is None:
            # fallback: second occurrence of header n=1
            ones = [a for a in anchors if a[1] == "q" and a[2]["n"] == 1]
            ws_line = ones[1][0] if len(ones) > 1 else len(all_lines)
        q_anchors = [a for a in anchors if a[1] in ("q", "copy") and a[0] < ws_line]
        s_anchors = [a for a in anchors if a[1] in ("q", "copy") and a[0] > ws_line]

        def regions(start_i, end_i):
            """Column regions covered by lines[start_i:end_i] -> list of (page,col,y0,y1)."""
            lines = all_lines[start_i:end_i]
            if not lines:
                return []
            regs = []
            cur = None
            for l in lines:
                key = (l["page"], l["col"])
                if cur is None or cur[0] != key:
                    if cur is not None:
                        regs.append(cur)
                    cur = [key, l["y0"], l["y1"]]
                else:
                    cur[1] = min(cur[1], l["y0"]); cur[2] = max(cur[2], l["y1"])
            regs.append(cur)
            return [dict(page=k[0], col=k[1], y0=y0, y1=y1) for k, y0, y1 in regs]

        def section_items(anchs, sec_end):
            items = {}
            for j, (i, kind, info) in enumerate(anchs):
                if kind != "q":
                    continue
                nxt = anchs[j + 1][0] if j + 1 < len(anchs) else sec_end
                text = "\n".join(l["text"] for l in all_lines[i:nxt])
                st = all_lines[i]
                if nxt < len(all_lines):
                    en = all_lines[nxt]
                    end_anchor = dict(page=en["page"], col=en["col"], y0=en["y0"])
                else:
                    end_anchor = None
                items[info["n"]] = dict(info=info, start=i, end=nxt, text=text,
                                        regions=regions(i, nxt),
                                        start_anchor=dict(page=st["page"], col=st["col"], y0=st["y0"], y1=st["y1"], x0=st["x0"]),
                                        end_anchor=end_anchor)
            return items

        q_items = section_items(q_anchors, ws_line)
        s_items = section_items(s_anchors, len(all_lines))
        for n, q in sorted(q_items.items()):
            s = s_items.get(n)
            means = []
            if s:
                # walk the solution lines in order, remembering the last part label seen
                PART_RE = re.compile(r"^\s*(?:\(([ivx]{1,4})\)|([ivx]{1,4})\.|\(([a-h])\)|([a-h])\.)(?:\s.*)?$")
                last_part = None
                for l in all_lines[s["start"]:s["end"]]:
                    pm = PART_RE.match(l["text"])
                    if pm:
                        last_part = next(g for g in pm.groups() if g)
                    for m in MEAN_RE.finditer(l["text"]):
                        inner = m.group(0)
                        lm2 = re.search(r"part\s*\(?([ivxa-z]+)\)?", inner)
                        label = lm2.group(1) if lm2 else last_part
                        means.append(dict(pct=int(m.group(1)), label=label, raw=inner, y=l["y0"], page=l["page"]))
                for m in []:
                    ctx = s["text"][max(0, m.start() - 40):m.start()]
                    label = None
                    lm = re.search(r"(?:part\s*)?(\([ivx]+\)|\([a-z]\)|\b[a-z]\.|\b[ivx]+\.)\s*$", s["text"][m.start():m.end()].replace("Mean mark", ""))
                    inner = m.group(0)
                    lm2 = re.search(r"(part\s*\(?[ivxa-z]+\)?|\([ivxa-z]+\))", inner)
                    if lm2:
                        label = lm2.group(1)
                    means.append(dict(pct=int(m.group(1)), label=label, raw=inner))
            marks = [int(x) for x in MARKS_RE.findall(q["text"])]
            catalog.append(dict(
                file=fn, page_w=W, page_h=H, furniture={f"{k[0]}_{k[1]}": v for k, v in furniture.items()}, **q["info"],
                marks_parts=marks, marks_total=(sum(marks) if marks else (1 if q["info"]["mc"] else None)),
                means=means,
                q_regions=q["regions"], q_text=q["text"],
                q_start=q["start_anchor"], q_end=q["end_anchor"],
                s_regions=(s["regions"] if s else []), s_text=(s["text"] if s else ""),
                s_start=(s["start_anchor"] if s else None), s_end=(s["end_anchor"] if s else None),
            ))
    json.dump(catalog, open(OUT, "w"), indent=1)
    print(f"wrote {len(catalog)} items to {OUT}")


if __name__ == "__main__":
    main()
