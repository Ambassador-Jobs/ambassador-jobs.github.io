# Ambassador Personnel Jobs

Public job board for Ambassador Personnel at **https://ambassador-jobs.github.io/**

Every job, branch office, state and city has its own static HTML page so Google (and Google for Jobs) can crawl it without running JavaScript.

| Page | Example |
|---|---|
| All jobs, grouped by branch, with search | `/` (also `/?q=forklift&state=GA`) |
| Branch office | `/branches/pooler/` |
| State | `/locations/ga/` |
| City | `/locations/ga/savannah/` |
| Job (JobPosting structured data) | `/jobs/<id>-<title-city-st>.html` |
| Sitemap / XML job feed | `/sitemap.xml`, `/feed.xml` |

## How it works
- `jobs.tsv` holds the public job data, one job per line (opens in Excel): title, city/state/ZIP, pay, type, shift, branch, openings, first-posted date.
- `site_gen.py` turns `jobs.tsv` into the full site.
- `.github/workflows/pages.yml` runs `site_gen.py` and publishes to GitHub Pages on every push to `main`.

## Updating jobs
1. In the Ambassador_Order_Board sheet, open the **Orders** tab → File → Download → CSV.
2. Run `python3 build.py Orders.csv` in this folder (it keeps each job's first-posted date).
3. Upload the new `jobs.tsv` here (Add file → Upload files → Commit). The site rebuilds itself in about a minute.

Filled jobs drop off automatically, and their pages return "This job has been filled".

Only orders with open headcount are published, and only public-safe fields: customer names, street addresses, recruiters, req numbers and notes never leave the sheet.

To change where **Apply now** goes, edit `APPLY_URL` at the top of `site_gen.py`.
