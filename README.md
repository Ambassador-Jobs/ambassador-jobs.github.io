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
- **Job Site Feed** (a separate Google Sheet, published read-only as CSV) is where jobs are managed: untick **Show** to hide a job, edit a title, add or remove rows.
- Every hour (or on demand with **Actions -> Build and publish job site -> Run workflow**), `sync_feed.py` pulls the feed, validates it, and writes `jobs.tsv`.
- `site_gen.py` turns `jobs.tsv` into the full site, and GitHub Pages publishes it.
- If the feed isn't set up yet (`FEED_URL` repository variable empty), the committed `jobs.tsv` is used.

## Security
- The Order Board is never published or connected. Only the separate feed sheet is published, and it holds only public job-ad fields.
- No passwords, tokens or API keys exist anywhere in this setup.
- `sync_feed.py` only reads whitelisted columns, checks every field against a strict pattern, rejects HTML/script characters, and drops any row that looks like it contains an email, phone number, SSN or link.
- If the feed is broken, empty or rejected, nothing is deployed: the live site stays exactly as it was.
- Pages have a Content-Security-Policy (no inline or outside scripts), and the hidden Google job data is escaped so it can't inject code.
- The workflow has no default permissions, uses only GitHub's own actions pinned to exact commit SHAs, and doesn't keep repository credentials.
- Repository settings: only GitHub-created actions allowed, SHA pinning required, default workflow token read-only.
- Turn on two-factor authentication for the account that owns this repo.

To change where **Apply now** goes, edit `APPLY_URL` at the top of `site_gen.py`.
