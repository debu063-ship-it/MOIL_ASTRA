"""Normalize the NGDR CSV: repair NUID tokens and clean district/state text.

NUID repair: the pdf words in the NUID column arrive sorted by (top, x0).
Because 'CRO-0' sits one line ABOVE '7286-1', which sits above '971', the
naive join yields e.g. '7286-1971CRO-0' (lines reordered by wrap). The true
reading order by top is prefix -> body -> year, so we rebuild with a regex:
  ^([A-Z]+-\d)(\d{4}-\d{4})$  -> 'CRO-0' + '7286-1971'  (correct order)
  ^(\d{4}-\d{4})([A-Z]+-\d)$  -> needs swap to prefix + tail
  ^(\d{4})-(\d{4})([A-Z]+-\d)$ variants likewise.
Simplest robust repair: capture letters, the two numeric groups and the year,
then emit PREFIX-REST-NUM-YEAR with REST = the short leading fragment.
"""
import re

import pandas as pd

CSV = "data/external/geology/ngdr/ngdr_ai_query_balaghat_boreholes.csv"
OUT = CSV  # in-place


def repair_nuid(t):
    t = re.sub(r"\s+", "", str(t))
    # already good: CRO-18470-1972
    if re.match(r"^[A-Z]+-\d{4,6}-\d{4}$", t):
        return t
    # forms:  7286-1971CRO-0 | 0528-1973CRO-1 | 4494-1979CRO-0 | 0150-1975
    m = re.match(r"^([A-Z]+)-(\d{1,2})(\d{3,5})-(\d{4})$", t)
    if m:
        return f"{m.group(1)}-{m.group(2)}{m.group(3)}-{m.group(4)}"
    m = re.match(r"^(\d{3,5})-(\d{4})([A-Z]+)-(\d{1,2})$", t)
    if m:
        # prefix-fragment moved AFTER year: rebuild as PREFIX-frag+num-YEAR
        return f"{m.group(3)}-{m.group(4)}{m.group(1)}-{m.group(2)}"
    m = re.match(r"^(\d{4})-(\d{4})([A-Z]+)-(\d{1,2})$", t)
    if m:
        return f"{m.group(3)}-{m.group(4)}{m.group(1)}-{m.group(2)}"
    # bare 0150-1975: prefix unknown -> keep
    return t


def main():
    df = pd.read_csv(CSV)
    df["nuid"] = df["nuid"].map(repair_nuid)
    # stage already normalized by parser; tidy the stragglers
    df["exploration_stage"] = df["exploration_stage"].str.replace(r"[^\w]", "", regex=True)
    df.to_csv(OUT, index=False)
    bad = df[~df["nuid"].str.match(r"^[A-Z]*-?\d{4,6}-\d{4}$", na=False)]
    print(f"{len(df)} rows; {len(bad)} NUIDs still non-standard:")
    if len(bad):
        print(bad[["id", "nuid"]].to_string())
    print(df[["id", "nuid", "exploration_stage"]].head(12).to_string())


if __name__ == "__main__":
    main()
