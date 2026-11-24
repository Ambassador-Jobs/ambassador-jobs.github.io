#!/usr/bin/env python3
"""Generate the static, crawlable job site from jobs.tsv into _site/.

Every page Google needs is real HTML (no JavaScript required to see a job):
  /                              all jobs grouped by branch + search box
  /branches/<branch>/            one page per branch office
  /locations/<st>/               one page per state
  /locations/<st>/<city>/        one page per city
  /jobs/<id>-<title-city-st>.html one page per job with JobPosting JSON-LD
  /sitemap.xml /robots.txt /feed.xml /404.html

Run by the GitHub Actions workflow on every push; run locally with:
  python3 site_gen.py && python3 -m http.server -d _site
"""
import csv, json, re, shutil, datetime, html
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
OUT = ROOT / "_site"
BASE = "https://ambassador-jobs.github.io"
ORG = "Ambassador Personnel"
ORG_URL = "https://www.teamambassador.com"
APPLY_URL = "https://www.teamambassador.com/Login.aspx?ref=/Application.aspx?id=000054VZ"  # Apply button
STATES = {"AL":"Alabama","AR":"Arkansas","CT":"Connecticut","DE":"Delaware","FL":"Florida","GA":"Georgia",
  "IL":"Illinois","IN":"Indiana","KY":"Kentucky","LA":"Louisiana","MD":"Maryland","MI":"Michigan","MO":"Missouri",
  "MS":"Mississippi","NC":"North Carolina","NH":"New Hampshire","NJ":"New Jersey","NY":"New York","OH":"Ohio",
  "OK":"Oklahoma","PA":"Pennsylvania","SC":"South Carolina","TN":"Tennessee","TX":"Texas","VA":"Virginia",
  "WI":"Wisconsin","WV":"West Virginia","AZ":"Arizona","CA":"California","CO":"Colorado","IA":"Iowa","KS":"Kansas",
  "MA":"Massachusetts","MN":"Minnesota","NE":"Nebraska","NV":"Nevada","OR":"Oregon","UT":"Utah","WA":"Washington"}

e = lambda s: html.escape(str(s or ""), quote=True)

def ld(obj):
    """JSON-LD that can never break out of its <script> tag."""
    s = json.dumps(obj).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    return '<script type="application/ld+json">' + s + "</script>"
slug = lambda s: re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")

def branch_label(b):
    return "Corporate" if b == "Ambassador Corporate" else b

def job_url(j): return f"/jobs/{slug(j['id'])}-{j['slug']}.html"
def branch_url(b): return f"/branches/{slug(branch_label(b))}/"
def state_url(st): return f"/locations/{st.lower()}/"
def city_url(j): return f"/locations/{j['state'].lower()}/{slug(j['city'])}/"

def desc_text(j):
    t = f"{ORG} is hiring a {j['title']} in {j['city']}, {j['state']}."
    if j["pay"]: t += f" Pay is {j['pay']}."
    if j["shift"]: t += f" Shift: {j['shift']}."
    t += f" This is a {j['type'].lower()} position"
    t += f" with openings for {j['openings']} people." if j["openings"] > 1 else "."
    return t

def type_text(j):
    if j["type"] == "Direct Hire":
        return "This is a direct-hire position: you are hired directly by the employer from day one."
    return (f"This is a temp-to-hire position: you start on assignment through {ORG}, "
            "with the opportunity to be hired on permanently by the employer.")

def sections(j):
    """(heading, paragraph) pairs used on the job page and in the JobPosting description."""
    where = f"{j['city']}, {j['state']}"
    n = f" We have {j['openings']} openings for this role." if j["openings"] > 1 else ""
    return [
        ("About the job", f"{ORG} is hiring a {j['title']} in {where}.{n} {type_text(j)}"),
        ("Schedule", f"Shift: {j['shift']}." if j["shift"] else "Your recruiter will go over the shift and schedule when you apply."),
        ("Pay", f"{j['pay']}." if j["pay"] else "Pay is discussed with your recruiter during your interview."),
        ("How to apply", f"Click Apply now and complete the {ORG} application, mentioning Job ID {j['id']}. "
            "A recruiter will follow up with the requirements, schedule and start date."),
        (f"About {ORG}", f"{ORG} is a staffing company that connects people with temp-to-hire and "
            f"direct-hire jobs at employers across {N_STATES} states."),
        ("Equal opportunity", f"{ORG} is an equal opportunity employer. All qualified applicants receive "
            "consideration for employment without regard to race, color, religion, sex, national origin, age, "
            "disability, veteran status or any other protected status."),
    ]

ICON = "/icon.svg"
LOGO = "https://www.teamambassador.com/Images/logo.png"
N_JOBS = 0

def navlinks(on):
    items = (("jobs", "/", "All jobs"), ("offices", "/#branches", "Offices"), ("locations", "/locations/", "Locations"))
    return "".join(f'<a class="tab{" on" if k == on else ""}" href="{u}">{t}</a>' for k, u, t in items) + \
        f'<a class="nbtn" href="{APPLY_URL}" rel="noopener noreferrer">Apply online</a>'

ORG_LD = {"@type":"Organization","name":ORG,"url":ORG_URL,"sameAs":ORG_URL,"logo":BASE+ICON}

def page(title, desc, path, body, head_extra="", crumbs=None, nav="jobs"):
    bc = ""
    if crumbs:
        items = [{"@type":"ListItem","position":i+1,"name":n,"item":BASE+u} for i,(n,u) in enumerate(crumbs)]
        head_extra += ld({"@context":"https://schema.org","@type":"BreadcrumbList","itemListElement":items})
        bc = '<nav class="crumbs">' + " › ".join(
            f'<a href="{e(u)}">{e(n)}</a>' if i < len(crumbs)-1 else e(n) for i,(n,u) in enumerate(crumbs)) + "</nav>"
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)}</title>
<meta name="description" content="{e(desc[:158])}">
<link rel="canonical" href="{BASE}{path}">
<meta property="og:title" content="{e(title)}"><meta property="og:description" content="{e(desc[:158])}">
<meta property="og:url" content="{BASE}{path}"><meta property="og:type" content="website"><meta property="og:site_name" content="{ORG} Jobs">
<meta name="twitter:card" content="summary">
<link rel="icon" href="{ICON}" type="image/svg+xml">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'self'; script-src 'self'; img-src 'self' https://www.teamambassador.com; base-uri 'none'; form-action 'none'">
<meta name="referrer" content="strict-origin-when-cross-origin">
<link rel="stylesheet" href="/style.css">
{head_extra}
</head><body>
<div class="topbar"><span><b>Now hiring</b> · {N_JOBS} open jobs in {N_STATES} states</span><span>Jobs updated {TODAY}</span></div>
<header class="masthead"><a href="/" class="brand"><img src="{LOGO}" alt="{ORG}" width="210" height="56"></a>
<p class="tagline">Delivering <span>STAFFING &amp; HR</span> Results</p></header>
<nav class="navbar" aria-label="Main"><div class="navrow">{navlinks(nav)}</div></nav>
<main>{bc}{body}</main>
<footer>{ORG} is an equal opportunity employer. Jobs updated {TODAY}.</footer>
</body></html>"""

def card(j, show_branch=False):
    extra = f" · {e(branch_label(j['branch']))} office" if show_branch else ""
    meta = f"{e(j['city'])}, {e(j['state'])}" + (f" · {e(j['shift'])}" if j["shift"] else "") + extra
    search = e(f"{j['title']} {j['city']} {j['state']} {STATES.get(j['state'],'')} {j['zip']} {branch_label(j['branch'])}".lower())
    chips = "".join(f'<span class="chip{c}">{e(v)}</span>' for v, c in
        ((j["pay"], " ok"), (j["type"], " full" if j["type"] == "Direct Hire" else ""), (j["shift"], "")) if v)
    return (f'<a class="card" href="{job_url(j)}" data-s="{search}" data-st="{e(j["state"])}" data-ty="{e(j["type"])}">'
            f'<h3>{e(j["title"])}</h3><div class="sub">{meta}</div><div class="chips">{chips}</div>'
            f'<span class="btns"><span class="btn primary">View job</span></span></a>')

def itemlist(jobs):
    return ld({"@context":"https://schema.org","@type":"ItemList",
        "itemListElement":[{"@type":"ListItem","position":i+1,"url":BASE+job_url(j)} for i,j in enumerate(jobs)]})

def write(path, text):
    p = OUT / path.lstrip("/")
    if path.endswith("/"): p = p / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")

def jobposting(j, valid):
    data = {"@context":"https://schema.org/","@type":"JobPosting",
      "title": j["title"],
      "description": "".join(f"<h2>{e(h)}</h2><p>{e(t)}</p>" for h, t in sections(j)),
      "identifier": {"@type":"PropertyValue","name":ORG,"value":j["id"]},
      "datePosted": j.get("posted") or TODAY, "validThrough": valid + "T23:59:59-05:00",
      "employmentType": "FULL_TIME" if j["type"] == "Direct Hire" else ["TEMPORARY","FULL_TIME"],
      "hiringOrganization": {"@type":"Organization","name":ORG,"sameAs":ORG_URL,"logo":BASE+ICON},
      "jobLocation": {"@type":"Place","address":{"@type":"PostalAddress","addressLocality":j["city"],
          "addressRegion":j["state"],"addressCountry":"US", **({"postalCode":j["zip"]} if j["zip"] else {})}},
      "totalJobOpenings": j["openings"], "directApply": False, "url": BASE + job_url(j)}
    if j.get("payValue"):
        data["baseSalary"] = {"@type":"MonetaryAmount","currency":"USD",
            "value":{"@type":"QuantitativeValue","value":j["payValue"],"unitText":"HOUR"}}
    return ld(data)

FILTER_JS = '<script src="/search.js" defer></script>'

def filters(jobs):
    sts = sorted({j["state"] for j in jobs})
    opts = "".join(f'<option value="{s}">{e(STATES.get(s,s))}</option>' for s in sts)
    return (f'<form class="filters" role="search" action="/">'
            f'<input id="q" name="q" type="search" placeholder="Search job title, city, ZIP or office" aria-label="Search jobs">'
            f'<select id="st" name="state" aria-label="State"><option value="">All states</option>{opts}</select>'
            f'<select id="ty" name="type" aria-label="Job type"><option value="">All types</option>'
            f'<option>Temp-to-Hire</option><option>Direct Hire</option></select></form>'
            f'<p class="count" id="n">{len(jobs)} open jobs</p>')

def main():
    global TODAY, N_STATES, N_JOBS
    with (ROOT / "jobs.tsv").open(encoding="utf-8") as f:
        jobs = list(csv.DictReader(f, delimiter="\t"))
    TODAY = datetime.date.today().isoformat()
    valid = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    apply = APPLY_URL
    for j in jobs:
        j["openings"] = int(j.get("openings") or 1)
        j.setdefault("slug", slug(f"{j['title']}-{j['city']}-{j['state']}"))
        m = re.search(r"\d+(\.\d+)?", j.get("pay") or "")
        j.setdefault("payValue", float(m.group()) if m else None)
    if OUT.exists(): shutil.rmtree(OUT)
    OUT.mkdir()
    shutil.copy(ROOT / "style.css", OUT / "style.css")
    shutil.copy(ROOT / "search.js", OUT / "search.js")
    shutil.copy(ROOT / "icon.svg", OUT / "icon.svg")
    for f in ROOT.glob("google*.html"):  # Google Search Console verification file(s)
        shutil.copy(f, OUT / f.name)
    (OUT / ".nojekyll").write_text("")

    by_branch = defaultdict(list)
    for j in jobs: by_branch[j["branch"]].append(j)
    branches = sorted(by_branch, key=lambda b: (b == "Ambassador Corporate", branch_label(b)))
    by_state = defaultdict(list); by_city = defaultdict(list)
    for j in jobs:
        by_state[j["state"]].append(j); by_city[(j["state"], j["city"])].append(j)
    N_STATES = len(by_state); N_JOBS = len(jobs)
    lastmod = {}  # url -> newest first-posted date of the jobs on that page
    def seen(u, js):
        lastmod[u] = max((x.get("posted") or TODAY) for x in js)
    key = lambda j: (j["state"], j["city"], j["title"])
    urls = ["/", "/locations/"]; seen("/", jobs); seen("/locations/", jobs)

    # Home: all jobs grouped by branch
    chips = "".join(f'<a class="chip" href="{branch_url(b)}">{e(branch_label(b))} <b>{len(by_branch[b])}</b></a>' for b in branches)
    groups = "".join(
        f'<section class="group" id="{slug(branch_label(b))}"><h2><a href="{branch_url(b)}">{e(branch_label(b))} office</a> '
        f'<span class="n">{len(by_branch[b])}</span></h2><div class="grid">'
        + "".join(card(j) for j in sorted(by_branch[b], key=key)) + "</div></section>" for b in branches)
    home_ld = ld({"@context":"https://schema.org","@type":"WebSite",
        "name":f"{ORG} Jobs","url":BASE+"/","publisher":ORG_LD}) + ld({"@context":"https://schema.org", **ORG_LD})
    home_states = "".join(f'<li><a href="{state_url(st)}">Jobs in {e(STATES.get(st, st))}</a> <span class="n">{len(by_state[st])}</span></li>'
        for st in sorted(by_state, key=lambda s: STATES.get(s, s)))
    write("/", page(f"Jobs at {ORG} | {len(jobs)} Openings Hiring Now",
        f"{len(jobs)} open jobs with {ORG} — warehouse, production, maintenance, drivers, office and more. Browse by office or location and apply online.",
        "/", f'<h1 class="section">Find your next job</h1><p class="sub">{len(jobs)} temp-to-hire and direct-hire openings across {len(branches)} offices.</p>'
        + filters(jobs) + f'<h2 class="section">Browse by office</h2><div class="chips" id="branches">{chips}</div>'
        + f'<h2 class="section">Browse by state</h2><ul class="states">{home_states}</ul>' + groups + FILTER_JS, home_ld))

    # Branch pages
    for b in branches:
        js = sorted(by_branch[b], key=key); lbl = branch_label(b); u = branch_url(b); urls.append(u); seen(u, js)
        cities = sorted({f"{j['city']}, {j['state']}" for j in js})
        write(u, page(f"{lbl} Office Jobs | {ORG}",
            f"{len(js)} open jobs from the {ORG} {lbl} office in {', '.join(cities[:6])}. Apply online today.",
            u, f'<h1>{e(lbl)} office jobs</h1><p class="sub">{len(js)} openings · {e(", ".join(cities))}</p>'
            + filters(js) + '<section class="group"><div class="grid">' + "".join(card(j) for j in js) + "</div></section>" + FILTER_JS,
            itemlist(js), [("Jobs","/"),(f"{lbl} office", u)], "offices"))

    # Location pages
    st_links = ""
    for st in sorted(by_state):
        js = sorted(by_state[st], key=key); name = STATES.get(st, st); u = state_url(st); urls.append(u); seen(u, js)
        cities = sorted({j["city"] for j in js})
        st_links += f'<li><a href="{u}">{e(name)}</a> <span class="n">{len(js)}</span></li>'
        city_chips = "".join(f'<a class="chip" href="/locations/{st.lower()}/{slug(c)}/">{e(c)} <b>{len(by_city[(st,c)])}</b></a>' for c in cities)
        write(u, page(f"Jobs in {name} | {ORG}",
            f"{len(js)} open jobs in {name}: {', '.join(cities[:8])}. Apply online with {ORG}.",
            u, f'<h1>Jobs in {e(name)}</h1><p class="sub">{len(js)} openings in {len(cities)} cities</p><div class="chips">{city_chips}</div>'
            + filters(js) + '<section class="group"><div class="grid">' + "".join(card(j, True) for j in js) + "</div></section>" + FILTER_JS,
            itemlist(js), [("Jobs","/"),("Locations","/locations/"),(name,u)], "locations"))
        for c in cities:
            cj = sorted(by_city[(st,c)], key=key); cu = city_url(cj[0]); urls.append(cu); seen(cu, cj)
            titles = sorted({j["title"] for j in cj})
            write(cu, page(f"Jobs in {c}, {st} | {ORG}",
                f"{len(cj)} open jobs in {c}, {st}: {', '.join(titles[:6])}. Apply online with {ORG}.",
                cu, f'<h1>Jobs in {e(c)}, {e(st)}</h1><p class="sub">{len(cj)} openings</p>'
                + '<section class="group"><div class="grid">' + "".join(card(j, True) for j in cj) + "</div></section>",
                itemlist(cj), [("Jobs","/"),("Locations","/locations/"),(name,u),(c,cu)], "locations"))
    write("/locations/", page(f"Jobs by Location | {ORG}", f"Browse {ORG} jobs by state and city.",
        "/locations/", f'<h1>Jobs by location</h1><ul class="states">{st_links}</ul>', "", [("Jobs","/"),("Locations","/locations/")], "locations"))

    # Job pages
    for j in jobs:
        u = job_url(j); urls.append(u); seen(u, [j])
        where = f"{j['city']}, {j['state']}"
        facts = "".join(f"<div><b>{k}</b>{e(v)}</div>" for k, v in (("Pay", j["pay"]), ("Type", j["type"]),
            ("Shift", j["shift"]), ("Location", f"{where} {j['zip']}".strip()), ("Office", branch_label(j["branch"]))) if v)
        more = [x for x in by_city[(j["state"], j["city"])] if x is not j][:6]
        more_html = ('<h2 class="section">More jobs in ' + e(where) + '</h2><div class="grid">' + "".join(card(x) for x in more) + "</div>") if more else ""
        write(u, page(f"{j['title']} – {where} | {ORG}", desc_text(j), u,
            f'<article class="job"><h1>{e(j["title"])}</h1><div class="meta">{e(where)}'
            + (' <span class="chip full">Direct Hire</span>' if j["type"] == "Direct Hire" else "")
            + f'</div><div class="facts">{facts}</div>'
            f'<p><a class="btn primary" href="{e(apply)}" rel="noopener noreferrer">Apply now</a></p>'
            + "".join(f"<h2>{e(h)}</h2><p>{e(t)}</p>" for h, t in sections(j))
            + f'<p><a class="btn primary" href="{e(apply)}" rel="noopener noreferrer">Apply now</a></p>'
            f'<p class="meta">Job ID {e(j["id"])} · Mention this ID when you apply.</p></article>' + more_html,
            jobposting(j, valid),
            [("Jobs","/"),(STATES.get(j["state"], j["state"]), state_url(j["state"])),(j["city"], city_url(j)),(j["title"], u)]))

    write("/404.html", page(f"Page not found | {ORG}", "This job may have been filled.", "/404.html",
        '<article class="job"><h1>This job has been filled</h1><p>Good news — there are more openings. <a href="/">See all jobs</a>.</p></article>',
        '<meta name="robots" content="noindex">'))
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    (OUT / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"<url><loc>{BASE}{u}</loc><lastmod>{lastmod[u]}</lastmod></url>\n" for u in urls) + "</urlset>\n")
    feed = "".join(f"""<job><referencenumber>{e(j['id'])}</referencenumber><title>{e(j['title'])}</title><company>{ORG}</company>
<city>{e(j['city'])}</city><state>{e(j['state'])}</state><postalcode>{e(j['zip'])}</postalcode><country>US</country>
<url>{BASE}{job_url(j)}</url><date>{j.get('posted') or TODAY}</date><jobtype>{e(j['type'])}</jobtype><salary>{e(j['pay'])}</salary>
<description>{e(desc_text(j))}</description></job>
""" for j in jobs)
    (OUT / "feed.xml").write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<source><publisher>{ORG}</publisher>'
        f"<publisherurl>{BASE}/</publisherurl><lastBuildDate>{TODAY}</lastBuildDate>\n{feed}</source>\n")
    print(f"{len(jobs)} jobs, {len(branches)} branches, {len(by_state)} states, {len(by_city)} cities -> {len(urls)} pages in _site/")

if __name__ == "__main__":
    main()
