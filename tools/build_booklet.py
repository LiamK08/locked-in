#!/usr/bin/env python3
"""Build the A3 booklet HTML from crops/manifest.json.

Usage: build_booklet.py <crops_dir> <out_dir>
Writes <out_dir>/booklet.html and copies the crop images into <out_dir>/img/.
"""
import html, json, os, shutil, sys
from datetime import date

CROPS, OUT = sys.argv[1], sys.argv[2]
os.makedirs(os.path.join(OUT, "img"), exist_ok=True)
man = json.load(open(os.path.join(CROPS, "manifest.json")))

DPI = 200
SCALE_Q = 1.4       # question crops are printed 25% larger than the worksheet size
SCALE_S = 1.0
MAX_IMG_W_MM = 238  # content width is 265 mm (297 - 2*16)
MAX_Q_H_MM = 290    # keep at least ~70 mm of working space on a page

TOPIC_BY_CODE = {
    "S1": "Statistics S1 - Data analysis",
    "S2": "Statistics S2 - Relative frequency and probability",
    "S4": "Statistics S4 - Bivariate data analysis",
    "S5": "Statistics S5 - The normal distribution",
    "F1": "Financial F1 - Money matters",
    "F4": "Financial F4 - Investments and loans",
    "F5": "Financial F5 - Annuities",
    "A1": "Algebra A1 - Formulae and equations",
    "A2": "Algebra A2 - Linear relationships",
    "A4": "Algebra A4 - Types of relationships",
    "M6": "Measurement M6 - Non-right-angled trigonometry",
}
TOPIC_BY_OLD = {
    "Data": "Data analysis (now Statistics S1)",
    "FS Health": "Bivariate data (now Statistics S4)",
    "Algebra": "Algebra (now A2 Linear relationships)",
    "Probability": "Probability (now Statistics S2)",
    "Financial Maths": "Financial mathematics",
    "Statistics": "Statistics",
}


def topic_label(m):
    if m["code"] and m["code"] in TOPIC_BY_CODE:
        return TOPIC_BY_CODE[m["code"]]
    return TOPIC_BY_OLD.get(m["topic"], m["topic"])


def exam_label(m):
    if m["year"] >= 2019:
        return f"{m['year']} HSC Mathematics Standard 2"
    if m["year"] >= 2014:
        return f"{m['year']} HSC Mathematics General 2"
    return f"{m['year']} HSC General Mathematics"


ROMAN = ["i", "ii", "iii", "iv", "v", "vi"]


def fmt_label(lab):
    if not lab:
        return None
    lab = lab.replace("part ", "").strip("()")
    return f"({lab})"


def mean_breakdown(m):
    """Return (headline, short label, by-part string or None) for the state mean mark."""
    means = m["means"]
    if len(means) == 1:
        lab = fmt_label(means[0]["label"])
        if lab and len(m["marks_parts"]) > 1:
            return f"{means[0]['pct']}%", f"state mean mark, part {lab}", None
        return f"{means[0]['pct']}%", "state mean mark", None
    labels = []
    for i, x in enumerate(means):
        lab = fmt_label(x["label"])
        if not lab:
            lab = f"({ROMAN[i]})" if len(means) == len(m["marks_parts"]) else f"part {i + 1}"
        labels.append(lab)
    lowest = min(range(len(means)), key=lambda i: means[i]["pct"])
    bypart = " &middot; ".join(f"{lab} {x['pct']}%" for lab, x in zip(labels, means))
    low = labels[lowest] if labels[lowest].startswith("part") else f"part {labels[lowest]}"
    return f"{means[lowest]['pct']}%", f"state mean mark, {low}", bypart


TARGET_Q_PT = 12.0   # printed size of the question body text
TARGET_S_PT = 9.0    # printed size of the solution text


def img_tag(im, scale, cls="qimg", body_pt=7.0):
    nat_w = im["w"] / DPI * 25.4
    # normalise so body text prints at a consistent size whatever the source worksheet used
    if cls == "qimg":
        scale = max(1.25, min(2.0, TARGET_Q_PT / body_pt)) * (scale / SCALE_Q)
    else:
        scale = max(0.9, min(1.4, TARGET_S_PT / body_pt))
    w_mm = nat_w * scale
    h_mm = im["h"] / DPI * 25.4 * scale
    if w_mm > MAX_IMG_W_MM:
        f = MAX_IMG_W_MM / w_mm
        w_mm *= f; h_mm *= f
    return f'<img class="{cls}" src="img/{im["path"]}" style="width:{w_mm:.1f}mm" alt="">', h_mm


def q_block(m, rank, max_h=MAX_Q_H_MM):
    head, detail, bypart = mean_breakdown(m)
    marks = m["marks_total"]
    marks_s = f"{marks} mark{'s' if marks != 1 else ''}" if marks else ""
    if m["mc"]:
        marks_s = "Multiple choice &middot; 1 mark"
    imgs = []
    total_h = 0
    for im in m["q_images"]:
        tag, h = img_tag(im, SCALE_Q, body_pt=m["body_pt"])
        imgs.append(tag); total_h += h
    if total_h > max_h:
        f = max_h / total_h
        imgs = []
        for im in m["q_images"]:
            tag, h = img_tag(im, SCALE_Q * f, body_pt=m["body_pt"])
            imgs.append(tag)
    pct = int(head.rstrip("%"))
    band = "b1" if pct < 20 else "b2" if pct < 35 else "b3"
    return f"""
    <div class="qhead {band}">
      <div class="rank"><span class="hash">#</span>{rank}</div>
      <div class="ref">
        <div class="exam">{html.escape(exam_label(m))} &middot; Question {html.escape(m['qnum'])}</div>
        <div class="topic">{html.escape(topic_label(m))}{' &middot; ' + marks_s if marks_s else ''}</div>
      </div>
      <div class="mean"><div class="pct">{head}</div><div class="lbl">{html.escape(detail)}</div></div>
    </div>
    {('<div class="bypart">State mean mark by part: ' + bypart + '</div>') if bypart else ''}
    <div class="qbody">{''.join(imgs)}</div>
    """


def s_block(m, rank):
    head, detail, bypart = mean_breakdown(m)
    imgs = "".join(img_tag(im, SCALE_S, "simg", body_pt=m["body_pt"])[0] for im in m["s_images"])
    return f"""
    <div class="sol">
      <div class="shead"><span class="srank">#{rank}</span> {html.escape(exam_label(m))} &middot; Q{html.escape(m['qnum'])} &middot; state mean {head}</div>
      {imgs}
    </div>"""


# ---------- page plan ----------
pages = []  # list of dicts: kind, items
i = 0
rank_of = {}
for r, m in enumerate(man, start=1):
    rank_of[m["id"]] = r
# multiple-choice questions share a page in pairs: a lone MC is paired with the next MC in rank order
used = set()
order = list(man)
for m in order:
    if m["id"] in used:
        continue
    used.add(m["id"])
    if m["mc"]:
        partner = next((x for x in order if x["mc"] and x["id"] not in used), None)
        if partner:
            used.add(partner["id"])
            pages.append(dict(kind="mc2", items=[m, partner]))
        else:
            pages.append(dict(kind="mc1", items=[m]))
    else:
        pages.append(dict(kind="ext", items=[m]))

FRONT_PAGES = 4  # cover, about, contents (2 pages)
page_of = {}
for k, p in enumerate(pages):
    for m in p["items"]:
        page_of[m["id"]] = FRONT_PAGES + k + 1
first_sol_page = FRONT_PAGES + len(pages) + 1
sol_page = {}
if os.path.exists(os.path.join(OUT, "solpages.json")):
    sol_page = json.load(open(os.path.join(OUT, "solpages.json")))

# ---------- HTML ----------
n_mc = sum(1 for m in man if m["mc"])
n_std2 = sum(1 for m in man if m["year"] >= 2019)
years = sorted({m["year"] for m in man})
today = date.today().strftime("%-d %B %Y")

css = """
@page { size: 297mm 420mm; margin: 14mm 16mm 18mm 16mm; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: Inter, 'Liberation Sans', 'DejaVu Sans', Arial, sans-serif; color: #111; font-size: 12pt; }
.page { height: 386mm; page-break-after: always; display: flex; flex-direction: column; position: relative; overflow: hidden; padding-bottom: 7mm; }
.page:last-child { page-break-after: auto; }
h1 { font-size: 40pt; margin: 0 0 8mm 0; line-height: 1.1; letter-spacing: -0.01em; }
h2 { font-size: 22pt; margin: 0 0 6mm 0; }
.cover { justify-content: center; padding: 20mm; border: 1.2mm solid #1d3557; }
.cover .kicker { color: #1d3557; font-weight: 600; letter-spacing: .12em; text-transform: uppercase; font-size: 12pt; margin-bottom: 10mm; }
.cover .sub { font-size: 18pt; color: #333; max-width: 200mm; line-height: 1.4; }
.cover .meta { margin-top: 24mm; font-size: 12pt; color: #444; line-height: 1.6; }
.cover .big { font-size: 110pt; font-weight: 800; color: #1d3557; line-height: 1; margin: 10mm 0 4mm 0; }
.about p, .about li { font-size: 12.5pt; line-height: 1.5; max-width: 230mm; }
.about ul { padding-left: 7mm; }
table.toc { border-collapse: collapse; width: 100%; font-size: 11pt; }
table.toc th { text-align: left; background: #1d3557; color: #fff; padding: 2.2mm 2.5mm; font-weight: 600; }
table.toc td { padding: 2.2mm 2.5mm; border-bottom: 0.25mm solid #d8dde6; vertical-align: top; }
table.toc tr:nth-child(even) td { background: #f4f6fa; }
table.toc td.num { text-align: right; font-variant-numeric: tabular-nums; }
table.toc td.pct { font-weight: 700; text-align: right; }
.qhead { display: flex; align-items: stretch; border: 0.5mm solid #1d3557; border-radius: 2mm; overflow: hidden; margin-bottom: 6mm; }
.qhead .rank { background: #1d3557; color: #fff; font-size: 30pt; font-weight: 800; padding: 3mm 6mm; display: flex; align-items: center; min-width: 32mm; justify-content: center; }
.qhead .rank .hash { font-size: 16pt; opacity: .7; margin-right: 1mm; font-weight: 600; }
.qhead .ref { flex: 1; padding: 3mm 5mm; display: flex; flex-direction: column; justify-content: center; }
.qhead .exam { font-size: 15pt; font-weight: 700; }
.qhead .topic { font-size: 11.5pt; color: #333; margin-top: 1.2mm; }
.qhead .mean { padding: 2.5mm 5mm; min-width: 78mm; max-width: 110mm; border-left: 0.4mm solid #1d3557; display: flex; flex-direction: column; justify-content: center; text-align: right; }
.qhead .mean .pct { font-size: 26pt; font-weight: 800; line-height: 1; }
.qhead .mean .lbl { font-size: 9.5pt; color: #333; margin-top: 1.5mm; line-height: 1.25; white-space: nowrap; }
.bypart { font-size: 10.5pt; color: #333; margin: -3mm 0 5mm 1mm; }
.qhead.b1 .mean { background: #fde8e8; } .qhead.b1 .pct { color: #b3261e; }
.qhead.b2 .mean { background: #fff0db; } .qhead.b2 .pct { color: #b45309; }
.qhead.b3 .mean { background: #fff8d6; } .qhead.b3 .pct { color: #8a6d00; }
.qbody img { display: block; margin: 0 0 3mm 2mm; }
.work { flex: 1; border: 0.3mm dashed #b7bfcc; border-radius: 2mm; margin-top: 4mm; position: relative; min-height: 40mm; }
.work .wl { position: absolute; top: 2mm; left: 3mm; font-size: 9pt; color: #8a94a6; letter-spacing: .08em; text-transform: uppercase; }
.half { height: 50%; min-height: 0; overflow: hidden; display: flex; flex-direction: column; padding-bottom: 4mm; }
.half .work { min-height: 22mm; }
.half + .half { border-top: 0.3mm solid #c9d0db; padding-top: 5mm; }
.mcans { margin-top: 3mm; font-size: 11pt; color: #333; }
.mcans span { display: inline-block; border: 0.35mm solid #1d3557; border-radius: 50%; width: 9mm; height: 9mm; line-height: 8.3mm; text-align: center; margin-right: 4mm; font-weight: 700; }
.solpage { display: block; height: auto; }
.solflow { column-count: 2; column-gap: 10mm; column-fill: auto; }
.sol { break-inside: avoid; margin-bottom: 7mm; padding-bottom: 4mm; border-bottom: 0.25mm solid #d8dde6; }
.shead { font-size: 10pt; font-weight: 600; color: #1d3557; margin-bottom: 2mm; }
.shead .srank { background: #1d3557; color: #fff; padding: 0.5mm 2mm; border-radius: 1mm; margin-right: 1.5mm; }
.sol img { display: block; max-width: 100%; }
.sectitle { font-size: 16pt; font-weight: 700; color: #1d3557; border-bottom: 0.5mm solid #1d3557; padding-bottom: 2mm; margin-bottom: 6mm; }
.foot { position: absolute; bottom: 0; left: 0; right: 0; height: 5mm; font-size: 8.5pt; color: #8a94a6; display: flex; justify-content: space-between; }
"""

parts = []
parts.append(f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>HSC Mathematics Standard 2: hardest questions booklet</title><style>{css}</style></head><body>""")

# cover
parts.append(f"""
<section class="page cover">
  <div class="kicker">HSC Mathematics Standard 2 &middot; A3 practice booklet</div>
  <h1>The questions the state found hardest</h1>
  <div class="sub">{len(man)} past HSC questions, ranked from the lowest state mean mark upwards.
  Every page gives you the original question, the state mean mark, and room to work. Worked solutions
  with markers' comments start on page {first_sol_page}.</div>
  <div class="big">{len(man)}</div>
  <div class="meta">
    Exams covered: {years[0]}&ndash;{years[-1]} &middot; {n_std2} questions from the current Mathematics Standard 2 exams (2019 onward),
    {len(man) - n_std2} from the earlier General Mathematics papers on the same content.<br>
    Lowest state mean mark in the set: {man[0]['rank_pct']}% &middot; highest: {man[-1]['rank_pct']}%<br>
    Compiled {today} from the SmarterMaths revision worksheets in the shared Year 12 Drive, which quote NESA's state mean mark for each question.
  </div>
</section>""")

# about
parts.append(f"""
<section class="page about">
  <h2>How this booklet was built, and how to use it</h2>
  <p><b>Where the percentages come from.</b> After every HSC, NESA records the mean mark the state achieved on each question.
  The SmarterMaths revision worksheets saved in the shared Year 12 Drive print that figure beside each past-paper question as
  <i>&ldquo;Mean mark xx%&rdquo;</i> (the state's average mark as a percentage of the marks available). For a multiple-choice question
  that is simply the percentage of the state that chose the correct answer. For a multi-part question SmarterMaths sometimes reports the
  figure only for the hardest part, and sometimes for each part; the booklet shows whatever was reported and ranks each question by its
  lowest reported figure.</p>
  <p><b>What is in the set.</b> Every Mathematics Standard 2 / General Mathematics HSC question in those worksheets that carries a reported
  state mean mark, with duplicates removed: {len(man)} questions from the {years[0]}&ndash;{years[-1]} exams. SmarterMaths only annotates
  questions the state found hard (roughly 50% or below), so the set is already the hard end of the exam. The worksheets available in the
  Drive cover statistics (data analysis, bivariate data, the normal distribution), probability, financial mathematics (investments, loans,
  annuities) and some algebra. They do not cover networks, measurement or trigonometry, so no questions from those topics appear here.
  Questions from before 2019 come from the General Mathematics / Mathematics General 2 papers; they are included only where SmarterMaths
  maps them onto the current Standard 2 syllabus.</p>
  <p><b>How to use it.</b></p>
  <ul>
    <li>Work in rank order if you want the hardest material first, or use the contents page to pick a topic.</li>
    <li>Print on A3 (portrait). Each extended-response question has its own page with working space; multiple-choice questions share a page.</li>
    <li>Do the question under exam conditions before you look at the solution. Allow about 1.5 minutes per mark.</li>
    <li>The colour of the percentage tile flags how badly the state went: red is below 20%, orange is 20&ndash;34%, yellow is 35% and above.</li>
    <li>Worked solutions (with SmarterMaths' markers' comments) are collected at the back from page {first_sol_page}, in the same rank order.</li>
  </ul>
  <p><b>Honest caveats.</b> The ranking is by the lowest reported mean mark, so a 1-mark part at 13% sits above a whole 5-mark question
  at 28%. Two large SmarterMaths worksheets in the Drive (&ldquo;Displaying Data&rdquo; and &ldquo;Summary Statistics&rdquo;) could not be
  opened for this build, so a handful of hard data-display questions may be missing. Question images are reproduced from the worksheets
  (copyright NESA for the exam questions and SmarterMaths for the solutions) for personal study only.</p>
</section>""")

# contents (two pages of 25 rows)
def short_exam(m):
    if m["year"] >= 2019:
        return f"{m['year']} HSC Maths Standard 2"
    if m["year"] >= 2014:
        return f"{m['year']} HSC Maths General 2"
    return f"{m['year']} HSC General Maths"

rows = []
for r, m in enumerate(man, start=1):
    head, detail, bypart = mean_breakdown(m)
    det = bypart if bypart else (detail.replace("state mean mark", "").strip(", ") or "")
    rows.append(f"<tr><td class='num'>{r}</td><td>{html.escape(short_exam(m))}</td><td>Q{html.escape(m['qnum'])}{' MC' if m['mc'] else ''}</td>"
                f"<td>{html.escape(topic_label(m))}</td><td class='num'>{m['marks_total'] or ''}</td><td class='pct'>{head}</td>"
                f"<td>{det}</td><td class='num'>{page_of[m['id']]}</td><td class='num'>{sol_page.get(m['id'], '')}</td></tr>")
thead = "<thead><tr><th>Rank</th><th>Exam</th><th>Question</th><th>Syllabus topic</th><th>Marks</th><th>State mean</th><th>By part</th><th>Page</th><th>Solution</th></tr></thead>"
half = (len(rows) + 1) // 2
for part_no, chunk in enumerate((rows[:half], rows[half:]), start=1):
    parts.append(f"""
<section class="page">
  <h2>Contents, ranked by state mean mark (lowest first){' (continued)' if part_no == 2 else ''}</h2>
  <table class="toc">{thead}<tbody>{''.join(chunk)}</tbody></table>
  <div class="foot"><span>Contents {part_no} of 2</span><span>Page {2 + part_no}</span></div>
</section>""")

# question pages
for k, p in enumerate(pages):
    pno = FRONT_PAGES + k + 1
    if p["kind"] == "ext":
        m = p["items"][0]; r = rank_of[m["id"]]
        parts.append(f"""<section class="page">{q_block(m, r)}<div class="work"><div class="wl">Working</div></div>
        <div class="foot"><span>#{r} &middot; {html.escape(exam_label(m))} Q{html.escape(m['qnum'])} &middot; solution on page {sol_page.get(m['id'], str(first_sol_page) + '+')}</span><span>Page {pno}</span></div></section>""")
    else:
        halves = []
        for m in p["items"]:
            r = rank_of[m["id"]]
            halves.append(f"""<div class="half">{q_block(m, r, max_h=108)}<div class="mcans">Answer: <span>A</span><span>B</span><span>C</span><span>D</span></div>
            <div class="work"><div class="wl">Working</div></div></div>""")
        refs = " &middot; ".join(f"#{rank_of[m['id']]} {html.escape(exam_label(m))} Q{html.escape(m['qnum'])}" for m in p["items"])
        parts.append(f"""<section class="page">{''.join(halves)}<div class="foot"><span>{refs}</span><span>Page {pno}</span></div></section>""")

# solutions: flow in two columns; let the browser paginate
sols = "".join(s_block(m, rank_of[m["id"]]) for m in man)
parts.append(f"""
<section class="solpage">
  <div class="sectitle">Worked solutions and markers' comments (rank order)</div>
  <div class="solflow">{sols}</div>
</section>""")
parts.append("</body></html>")

# copy images
for m in man:
    for im in m["q_images"] + m["s_images"]:
        shutil.copy(os.path.join(CROPS, im["path"]), os.path.join(OUT, "img", im["path"]))

open(os.path.join(OUT, "booklet.html"), "w").write("\n".join(parts))
json.dump(dict(pages=len(pages), first_sol_page=first_sol_page, page_of=page_of), open(os.path.join(OUT, "plan.json"), "w"), indent=1)
print(f"question pages: {len(pages)}; solutions start on page {first_sol_page}")
