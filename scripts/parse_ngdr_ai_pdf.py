"""Parse the NGDR AI Query Results PDF (Balaghat Mn borehole query) into a CSV.

PDF structure (verified via pdfplumber diagnostics):
- 195 landscape pages; 51 records; a record starts on a page whose ID column
  (x<60) holds a 1-2 digit number and CONTINUES onto following pages.
- Per page, the data zone is 205 < top < 560 (above: page/col headers with
  vertical text ending at top~199; below: footer at top~574).
- Column left edges (from the raw cell rectangles, matching pdfplumber coords):
  ID 30-60 | NUID 60-94 | ProjectTitle 94-104 | Commodity 104-207 |
  StateName 207-217 | District 217-351.6 | Toposheet 351.6-796.7 | Stage 796.7+
- Narrow columns (ProjectTitle, StateName, Stage) render ONE CHARACTER per
  line with 8.625pt leading; word boundaries show as a skipped slot (gap
  >= ~1.6x the char pitch). Wide columns wrap mid-token -> join lines with ''.
"""
import csv
import os
import re

import pdfplumber

PDF = r"C:\Users\Debu018\Downloads\NGDR_i_want_to_find_the_borehole_da_2026-09-28 (8).pdf"
OUT = os.path.join("data", "external", "geology", "ngdr",
                   "ngdr_ai_query_balaghat_boreholes.csv")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

COLS = ["id", "nuid", "project_title", "commodity", "state_name",
        "district_name", "toposheet_number", "exploration_stage"]
BOUNDS = [30, 60, 94, 104, 207, 217, 351.6, 796.7, 10_000]
VERTICAL_COLS = {"project_title", "state_name", "exploration_stage"}
ID_RE = re.compile(r"^\d{1,2}$")
CHAR_PITCH = 8.625


def col_index(x):
    for i in range(len(COLS)):
        if BOUNDS[i] - 2 <= x < BOUNDS[i + 1] - 2:
            return i
    return None


def join_vertical(words):
    """One char per line; a skipped leading slot = word boundary."""
    ws = sorted(words, key=lambda w: w["top"])
    out = []
    prev_top = None
    for w in ws:
        if prev_top is not None and (w["top"] - prev_top) > CHAR_PITCH * 1.6:
            out.append(" ")
        out.append(w["text"])
        prev_top = w["top"]
    return "".join(out)


def join_wide(words):
    """Multi-char words per line, wrapped mid-token -> concatenate lines."""
    lines = {}
    for w in words:
        lines.setdefault(round(w["top"] / 3), []).append(w)
    parts = []
    for key in sorted(lines):
        grp = sorted(lines[key], key=lambda w: w["x0"])
        parts.append("".join(t["text"] for t in grp))
    return "".join(parts)


def fix_nuid(raw):
    """NUID renders as interleaved vertical halves, e.g. '7286-1971CRO-0'.
    Pattern: <digits2>-<year><prefix><digits2>-  ->  CRO-07286-1971
    Robust approach: strip spaces, find letter prefix and merge the two
    numeric groups around it: A-B + C-  =>  PREFIX + C + A + - + B
    """
    t = raw.replace(" ", "")
    m = re.match(r"^(\d{2,5})-(\d{4})(([A-Z]+)-?(\d{0,2}))?$", t)
    if m:
        num, year, prefix, tail = m.group(1), m.group(2), m.group(4) or "", m.group(5) or ""
        # tail is the leading digit(s) of num (vertical wrap), prefix letters
        return f"{prefix}-{tail}{num}-{year}" if tail else f"{prefix}-{num}-{year}"
    return t


def fix_stage(raw):
    """'4 G' / 'G 3' variants -> 'G4' / 'G3'."""
    m = re.search(r"(\d)\s*G|G\s*(\d)", raw)
    if m:
        return f"G{m.group(1) or m.group(2)}"
    return raw.replace(" ", "")


def main():
    records = []
    cur = None
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages:
            zone = [w for w in page.extract_words() if 205 < w["top"] < 560]
            zone.sort(key=lambda w: (round(w["top"], 1), w["x0"]))
            for w in zone:
                ci = col_index(w["x0"])
                if ci is None:
                    continue
                if ci == 0 and ID_RE.match(w["text"]):
                    cur = {c: [] for c in COLS}
                    records.append(cur)
                if cur is None:
                    continue
                cur[COLS[ci]].append(w)

    rows = []
    for r in records:
        row = []
        for c in COLS:
            if not r[c]:
                row.append("")
            elif c in VERTICAL_COLS:
                row.append(" ".join(join_vertical(r[c]).split()))
            else:
                row.append(" ".join(join_wide(r[c]).split()))
        rows.append(row)

        # NUID/stage normalization: NUID is one token 'CRO-07286-1971';
    # stage is G2/G3/G4
    for r in rows:
        r[1] = r[1].replace(" ", "")
        r[7] = fix_stage(r[7])

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(COLS)
        w.writerows(rows)
    print(f"Parsed {len(rows)} records -> {OUT}")
    for r in rows[:8]:
        print(f"  {r[0]:>2} | {r[1][:18]:<18} | {r[3][:9]:<9} | "
              f"{r[5][:38]:<38} | {r[7][:6]}")
    print("  ...")
    for r in rows[-3:]:
        print(f"  {r[0]:>2} | {r[1][:18]:<18} | {r[3][:9]:<9} | "
              f"{r[5][:38]:<38} | {r[7][:6]}")


if __name__ == "__main__":
    main()
