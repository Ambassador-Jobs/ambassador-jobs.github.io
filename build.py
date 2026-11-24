#!/usr/bin/env python3
"""Ambassador Jobs feed builder.

Reads the Orders tab of the Ambassador Order Board (exported as CSV, or the
orders.json pulled by Claude) and writes the public job data, jobs.tsv.
site_gen.py turns jobs.tsv into the website (GitHub Actions runs it).

Only public-safe fields are published: title, city/state/zip, pay, type,
shift and branch. Customer names, street addresses, recruiters, req numbers
and internal notes never leave the sheet.

Usage:
  python3 build.py Orders.csv        # File > Download > CSV of the Orders tab
  python3 build.py orders.json
"""
import csv, json, re, sys, datetime
from pathlib import Path

OUT = Path(__file__).parent

def load(path):
    p = Path(path)
    if p.suffix == ".json":
        return json.loads(p.read_text())
    with p.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def num(v):
    try: return int(float(v or 0))
    except ValueError: return 0

JUNK = re.compile(r"^(admin|test|tbd|general)$|PSYS|project$|\d{4,}", re.I)

OVERRIDES = {  # odd internal titles -> public titles
    "batesville-ph-bread-(lids/oven/pan-o-mat)": "Production Helper - Bread",
    "sanitor-overnight-bakery (temp)": "Sanitor - Overnight",
    "hsaa plant 2- 1st shift custodian": "Custodian - 1st Shift",
}
TYPOS = {"Logists": "Logistics", "Maintanenace": "Maintenance", "Representataive": "Representative",
         "Acquistion": "Acquisition", "Acqusition": "Acquisition", "Opertor": "Operator", "Assebmly": "Assembly",
         "Inegrated": "Integrated", "Electical": "Electrical", "Oil Mil ": "Oil Mill ", "Hvac": "HVAC"}
STOP = {"of", "the", "and", "inc", "llc", "co", "corp", "corporation", "company", "group", "sales", "services"}

def clean_title(pos, city, customer=""):
    if (pos or "").strip().lower() in OVERRIDES:
        return OVERRIDES[pos.strip().lower()]
    t = re.sub(r"^\s*DIRECT\s*HIRE\s*:?\s*", "", pos or "", flags=re.I)
    t = re.sub(r"^\s*\d{1,3}\s*-\s*", "", t).strip()
    t = re.sub(r"\s*-\s*(1ST|2ND|3RD)$", lambda m: " - " + m.group(1).lower() + " shift", t, flags=re.I)
    if city:
        c = city.split(",")[0].strip()
        t = re.sub(r"\s*-\s*" + re.escape(c) + r"\s*$", "", t, flags=re.I)
    t = re.sub(r"\s*-\s*(AUGUSTA|CHARLESTON|POOLER|SAVANNAH)\s*$", "", t, flags=re.I)
    t = re.sub(r"\s*-?\s*(Harvest\s+20\d\d|20\d\d\s+Season)", " (Seasonal)", t)
    t = re.sub(r"_DIFF\b|-REPLACEMENT\b|\s*\(Temp\)", "", t)
    # strip a "City-" or "Customer - " prefix so client names never go public
    cwords = {w for w in re.findall(r"[a-z']+", re.sub(r"^\d+\s*-\s*", "", customer.lower())) if len(w) > 2 and w not in STOP}
    m = re.match(r"^([^-]+?)\s*-\s*(.+)$", t)
    if m:
        head = m.group(1).strip().lower()
        if (city and head == city.split(",")[0].strip().lower()) or (set(re.findall(r"[a-z']+", head)) & cwords):
            t = m.group(2)
    if t.isupper() and " " in t:
        t = re.sub(r"\b(Ii|Iii|Iv)\b", lambda m: m.group().upper(), t.title())
    if t.lower().startswith("prospective distributor"):
        t = "Route Sales Representative"
    for a, b in TYPOS.items():
        t = t.replace(a, b)
    return re.sub(r"\s{2,}", " ", t).strip(" -")

def shift_of(*texts):
    s = " ".join(texts).lower()
    for k, v in (("1st", "1st shift"), ("2nd", "2nd shift"), ("3rd", "3rd shift"),
                 ("night", "Nights"), ("weekend", "Weekends"), ("rotating", "Rotating")):
        if k in s: return v
    return ""

def location(row):
    addr = row.get("Worksite Address", "") or ""
    site = row.get("Work Site", "") or ""
    m = re.search(r"([A-Za-z .'\-]+),?\s+([A-Z]{2})\s+(\d{5})", addr)
    if m:
        city = m.group(1).split(",")[-1].strip()
        city = {"St.Louis": "St. Louis", "Euince": "Eunice", "Pinkard": "Pinckard", "LUBBOCK": "Lubbock"}.get(city, city)
        return city, m.group(2), m.group(3)
    m = re.search(r"([A-Za-z .'\-]+),?\s+([A-Z]{2})\b", site)
    if m:
        return m.group(1).strip(), m.group(2), ""
    return "", "", ""

def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")

def build(rows):
    jobs, seen = [], set()
    for r in rows:
        if num(r.get("Open")) <= 0: continue
        city, state, zipc = location(r)
        title = clean_title(r.get("Position", ""), r.get("Work Site", ""), r.get("Customer", ""))
        if not title or not city or JUNK.search(title): continue
        code = (r.get("Code") or "").strip()
        if not code or code in seen: continue
        seen.add(code)
        pay = (r.get("Pay") or "").strip()
        m = re.search(r"\d+(\.\d+)?", pay.replace(",", ""))
        typ = (r.get("Type") or "Regular").strip()
        jobs.append({
            "id": code,
            "title": title,
            "city": city, "state": state, "zip": zipc,
            "pay": f"${float(m.group()):.2f}/hr" if m and float(m.group()) < 200 else "",
            "type": "Direct Hire" if typ == "Direct Hire" or "direct hire" in (r.get("Position") or "").lower() else "Temp-to-Hire",
            "shift": shift_of(r.get("Position", ""), r.get("Description", "")),
            "openings": num(r.get("Open")),
            "branch": (r.get("Branch") or "").strip(),
        })
    jobs.sort(key=lambda j: (j["state"], j["city"], j["title"]))
    return jobs

COLS = ["id", "title", "city", "state", "zip", "pay", "type", "shift", "openings", "branch", "posted"]

def write(jobs):
    """jobs.tsv: one job per line, tab-separated (opens in Excel)."""
    today = datetime.date.today().isoformat()
    old = {}
    f = OUT / "jobs.tsv"
    if f.exists():
        old = {r["id"]: r.get("posted") for r in csv.DictReader(f.open(encoding="utf-8"), delimiter="\t")}
    for j in jobs:
        j["posted"] = old.get(j["id"]) or today
    with f.open("w", newline="", encoding="utf-8") as out:
        w = csv.writer(out, delimiter="\t", lineterminator="\n")
        w.writerow(COLS)
        for j in jobs:
            w.writerow([str(j[c]).replace("\t", " ") for c in COLS])

if __name__ == "__main__":
    if len(sys.argv) != 2: sys.exit(__doc__)
    jobs = build(load(sys.argv[1]))
    write(jobs)
    print(f"Built {len(jobs)} jobs -> jobs.tsv (upload it; GitHub builds the pages)")
