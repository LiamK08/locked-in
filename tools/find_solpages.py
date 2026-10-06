#!/usr/bin/env python3
"""Second pass helper: find the page on which each solution block landed."""
import json, sys, re, pymupdf
pdf, manifest, plan, out = sys.argv[1:5]
man = json.load(open(manifest)); plan = json.load(open(plan))
doc = pymupdf.open(pdf)
first = plan["first_sol_page"]
res = {}
for pno in range(first - 1, doc.page_count):
    text = doc[pno].get_text()
    for r, m in enumerate(man, start=1):
        key = f"#{r} "
        # shead text: "#r <exam label> · Q<qnum> · state mean"
        if re.search(rf"#{r}\s+\d{{4}} HSC .*?Q{re.escape(m['qnum'])}\b", text):
            res.setdefault(m["id"], pno + 1)
json.dump(res, open(out, "w"), indent=1)
print(f"solutions located for {len(res)}/{len(man)} questions; pages {min(res.values()) if res else '-'}..{max(res.values()) if res else '-'}")
