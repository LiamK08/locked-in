#!/usr/bin/env python3
"""Export the ranked question list (crops/manifest.json) to CSV."""
import csv, json, re, sys
ROMAN = ["i", "ii", "iii", "iv", "v", "vi"]
man = json.load(open(sys.argv[1]))
with open(sys.argv[2], "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["rank", "year", "exam", "question", "multiple_choice", "syllabus_code", "topic", "marks",
                "lowest_state_mean_mark_pct", "state_mean_marks_by_part", "smartermaths_header", "source_worksheet"])
    for r, m in enumerate(man, start=1):
        exam = ("Mathematics Standard 2" if m["year"] >= 2019 else "Mathematics General 2" if m["year"] >= 2014 else "General Mathematics")
        labels = []
        for i, x in enumerate(m["means"]):
            lab = x["label"]
            if not lab:
                lab = ROMAN[i] if len(m["means"]) == len(m["marks_parts"]) else f"part {i + 1}"
            labels.append(lab.replace("part ", "") if lab.startswith("part (") else lab)
        if len(m["means"]) == 1 and len(m["marks_parts"]) <= 1:
            parts = f"{m['means'][0]['pct']}%"
        else:
            parts = "; ".join(f"({lab}) {x['pct']}%" if not lab.startswith("part") else f"{lab} {x['pct']}%" for lab, x in zip(labels, m["means"]))
        w.writerow([r, m["year"], exam, m["qnum"], "yes" if m["mc"] else "no", m["code"] or "", m["topic"], m["marks_total"] or "",
                    m["rank_pct"], parts, m["header"], re.sub(r"^[A-Za-z0-9_-]{33}__", "", m["source_file"])])
print("wrote", sys.argv[2])
