#!/usr/bin/env python3
"""Pull the published Job Site Feed sheet and turn it into jobs.tsv.

Security rules (nothing gets past these, no matter what is typed in the sheet):
  * Only whitelisted columns are read; any other column is ignored.
  * Every field must match a strict pattern; HTML/script characters are rejected.
  * Rows that look like they contain an email, phone number or SSN are dropped.
  * Only rows with Show = TRUE are published.
  * Size and row caps; on any failure the last good jobs.tsv is kept (exit 1).

Usage (GitHub Actions passes FEED_URL):  python3 sync_feed.py
"""
import csv, io, os, re, sys, datetime, urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "jobs.tsv"
FEED_URL = os.environ.get("FEED_URL", "")
MAX_BYTES = 2_000_000
MAX_ROWS = 3000

STATES = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD",
          "MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC",
          "SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"}
TYPES = {"Temp-to-Hire", "Direct Hire"}
SHIFTS = {"", "1st shift", "2nd shift", "3rd shift", "Nights", "Weekends", "Rotating"}

# sheet header -> (tsv column, validator)
TEXT = re.compile(r"^[A-Za-z0-9 &/()'.,#+\-]{2,80}$")
PLACE = re.compile(r"^[A-Za-z .'\-]{2,40}$")
COLUMNS = {
    "Job ID":   ("id",       lambda v: v.upper() if re.fullmatch(r"[A-Za-z0-9]{2,8}", v) else None),
    "Title":    ("title",    lambda v: v if TEXT.fullmatch(v) else None),
    "City":     ("city",     lambda v: v if PLACE.fullmatch(v) else None),
    "State":    ("state",    lambda v: v.upper() if v.upper() in STATES else None),
    "ZIP":      ("zip",      lambda v: v.zfill(5) if re.fullmatch(r"\d{4,5}", v) else ("" if v == "" else None)),
    "Pay":      ("pay",      lambda v: pay(v)),
    "Type":     ("type",     lambda v: v if v in TYPES else None),
    "Shift":    ("shift",    lambda v: v if v in SHIFTS else None),
    "Openings": ("openings", lambda v: str(int(float(v))) if re.fullmatch(r"\d{1,3}(\.0+)?", v) and 0 < int(float(v)) < 1000 else "1"),
    "Office":   ("branch",   lambda v: v if PLACE.fullmatch(v) else None),
    "Posted":   ("posted",   lambda v: date(v)),
}
REQUIRED = ["Job ID", "Title", "City", "State", "Type", "Office"]
SENSITIVE = re.compile(r"@|\b\d{3}[-.\s)]+\d{3}[-.\s]+\d{4}\b|\b\d{3}-\d{2}-\d{4}\b|https?://|www\.", re.I)
TSV_COLS = ["id", "title", "city", "state", "zip", "pay", "type", "shift", "openings", "branch", "posted"]

def pay(v):
    if v == "": return ""
    m = re.fullmatch(r"\$?\s*(\d{1,3}(?:\.\d{1,2})?)\s*(?:/\s*hr|/\s*hour|per hour)?", v, re.I)
    return f"${float(m.group(1)):.2f}/hr" if m and 7 <= float(m.group(1)) < 200 else None

def date(v):
    today = datetime.date.today()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            d = datetime.datetime.strptime(v, fmt).date()
            return d.isoformat() if datetime.date(2020, 1, 1) <= d <= today else today.isoformat()
        except ValueError:
            pass
    return today.isoformat()

def fail(msg):
    print(f"FEED REJECTED: {msg}. Keeping the last good jobs.tsv.")
    sys.exit(1)

def main():
    if not FEED_URL.startswith("https://docs.google.com/spreadsheets/"):
        fail("FEED_URL is missing or not a Google Sheets address")
    req = urllib.request.Request(FEED_URL, headers={"User-Agent": "ambassador-jobs-sync"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES: fail("feed is too large")
    text = raw.decode("utf-8-sig", errors="replace")
    if text.lstrip().lower().startswith("<"): fail("got a web page, not CSV (is the sheet still published?)")

    reader = csv.DictReader(io.StringIO(text))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    missing = [h for h in REQUIRED + ["Show"] if h not in headers]
    if missing: fail(f"missing columns {missing}")

    jobs, seen, dropped = [], set(), []
    for n, row in enumerate(reader, start=2):
        if n > MAX_ROWS + 1: fail("too many rows")
        row = {k.strip(): (v or "").strip() for k, v in row.items() if k}
        if row.get("Show", "").upper() not in ("TRUE", "YES", "Y", "1", "X"): continue
        if any(SENSITIVE.search(row.get(h, "")) for h in COLUMNS):
            dropped.append(f"row {n}: looks like contact info"); continue
        out, bad = {}, None
        for h, (col, check) in COLUMNS.items():
            val = check(row.get(h, ""))
            if val is None:
                if h in REQUIRED: bad = h; break
                val = ""
            out[col] = val
        if bad: dropped.append(f"row {n}: bad {bad}"); continue
        if out["id"] in seen: dropped.append(f"row {n}: duplicate Job ID"); continue
        seen.add(out["id"])
        jobs.append(out)

    if not jobs: fail("no publishable rows (all hidden or invalid)")
    for d in dropped[:50]: print("skipped", d)
    jobs.sort(key=lambda j: (j["state"], j["city"], j["title"]))
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(TSV_COLS)
        for j in jobs: w.writerow([j[c] for c in TSV_COLS])
    print(f"Feed OK: {len(jobs)} jobs published, {len(dropped)} rows skipped")

if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as ex:  # network or parse error: never break the live site
        fail(f"{type(ex).__name__}: {ex}")
