# HSC Mathematics Standard 2: the questions the state found hardest

An A3 practice booklet of past HSC Mathematics Standard 2 (and earlier General
Mathematics) questions, ranked from the lowest state mean mark upwards, with
working space on every page and the worked solutions at the back.

* **Booklet (print this):** [`booklet/HSC_Maths_Standard_2_Hardest_Questions_A3.pdf`](booklet/HSC_Maths_Standard_2_Hardest_Questions_A3.pdf)
* **Ranked list as a spreadsheet:** [`data/hardest_questions.csv`](data/hardest_questions.csv)

## Where the percentages come from

NESA records the mean mark the state achieved on every HSC question. The
SmarterMaths revision worksheets saved in the shared Year 12 Google Drive
(folders `MATHS ADVANCED / ADV - Smarter Maths` and the Year 11/12 statistics,
probability and financial worksheets) print that figure beside each past-paper
question as *"Mean mark xx%"*: the state's average mark as a percentage of the
marks available. For a multiple-choice question that is the percentage of the
state that chose the right answer.

Every Standard 2 / General Mathematics HSC question in those worksheets that
carries a reported mean mark was extracted, duplicates were removed, and the
questions were ranked by their lowest reported figure. SmarterMaths only
annotates questions the state found hard (roughly 50% and below), so the whole
set is the hard end of the exams.

## What is (and is not) covered

* 50 questions from the 2009 to 2020 exams; 8 are from the current Mathematics
  Standard 2 papers (2019 onward), the rest from the General Mathematics /
  Mathematics General 2 papers on content that SmarterMaths maps to the current
  syllabus.
* Topics: statistics (data analysis, bivariate data, the normal distribution),
  probability, financial mathematics (investments, loans, annuities) and some
  algebra. The worksheets in the Drive do not cover networks, measurement or
  trigonometry, so those topics are absent.
* Two large worksheets in the Drive ("Displaying Data" and "Summary
  Statistics") could not be downloaded in this build, so a few hard
  data-display questions may be missing.
* NESA's own site was not reachable from the build environment, so the
  questions and solutions are reproduced from the worksheets rather than from
  the original exam PDFs. Exam questions are copyright NESA and the solutions
  copyright SmarterMaths; this booklet is for personal study.

## Printing

The PDF is 52 pages at A3 portrait. Print at 100% on A3 (or "fit to page" on
A4 for a smaller copy). Pages 5 to 45 are the questions: one extended-response
question per page, two multiple-choice questions per page. Pages 46 to 52 are
the worked solutions in rank order; the footer of each question page says which
page its solution is on, and the two contents pages list everything.

## Rebuilding

The pipeline lives in `tools/` and needs Python 3 with `pymupdf` and `numpy`,
plus Node with Playwright and Chromium for the PDF step.

```
python3 tools/extract_catalog.py <folder of SmarterMaths PDFs> catalog.json
python3 tools/make_crops.py catalog.json <folder of SmarterMaths PDFs> crops
python3 tools/build_booklet.py crops booklet && node tools/print.js booklet/booklet.html booklet/booklet.pdf
python3 tools/find_solpages.py booklet/booklet.pdf crops/manifest.json booklet/plan.json booklet/solpages.json
python3 tools/build_booklet.py crops booklet && node tools/print.js booklet/booklet.html booklet/booklet.pdf
python3 tools/export_csv.py crops/manifest.json data/hardest_questions.csv
```

`extract_catalog.py` finds every question header and "Mean mark" annotation in
the worksheets, `make_crops.py` renders each question and its worked solution
as a trimmed image, `build_booklet.py` lays out the A3 pages as HTML and
`print.js` prints them with Chromium. The second build pass fills in the
solution page numbers. The SmarterMaths PDFs themselves are not in this
repository.
