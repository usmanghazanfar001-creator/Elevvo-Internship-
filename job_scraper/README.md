# Job Listings Scraper & Market Analysis

A small, polite scraping pipeline: **scrape -> clean -> CSV -> analyse**, built with
`requests`, `BeautifulSoup` and `pandas` (charts with `matplotlib`).

```
job_scraper/
├── scraper.py         robots.txt check, retrying HTTP client, selector-driven page scraper
├── board_scraper.py   Bonus: second source (Arbeitnow public job-board API)
├── cleaner.py         pandas cleaning + CSV save/load
├── analysis.py        top skills / titles / per-location / per-company + bar chart
├── main.py            command-line entry point
├── data/              output (CSV + PNG) is written here
├── tests/             tiny sample HTML pages used for offline testing
├── requirements.txt
└── README.md
```

## How to run

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 1. Put your real contact e-mail in USER_AGENT (top of scraper.py).

# 2. The Elevvo practice page
python main.py --url "https://THE-ELEVVO-PRACTICE-PAGE" --max-pages 1
#    (or: set ELEVVO_URL=https://...  and just run  python main.py)

# 3. Bonus: real public job board (Arbeitnow API)
python main.py --source board --max-pages 3 --delay 2
```

Useful flags: `--delay` (seconds between pages), `--top` (rows in top-N tables),
`--out-dir`, `-v` (debug logging).

Exit codes: `0` ok, `2` missing URL, `3` blocked by robots.txt, `4` download failed,
`5` no listings extracted (selectors probably need updating).

Offline smoke test with the bundled sample pages:

```bash
python -m http.server 8765 --directory tests &
python main.py --url http://localhost:8765/sample_jobs.html --max-pages 2 --delay 0.2
```

## What each step does

1. **robots.txt** - `check_robots()` downloads `/robots.txt`, parses it with
   `urllib.robotparser`, prints the verdict and refuses to continue if the path is
   disallowed. Missing robots.txt (404) = allowed; 401/403/5xx/network error = treated
   as *not allowed* (fail closed). It is re-checked before every extra page.
2. **Scrape** - for each listing card: title, company, location, skills, posted date.
   A missing element gives `None` / `[]`, never an exception.
3. **Clean** (`cleaner.py`) - collapse whitespace; title-case only values that are ALL
   CAPS or all lowercase (so "IBM" survives); skills split on `, ; | /`, lower-cased,
   aliased (`js` -> `javascript`) and de-duplicated; dates parsed with
   `errors="coerce"` (bad dates become `NaT`); rows without a title dropped; missing
   company/location -> `Unknown`; case-insensitive de-duplication.
4. **Save** - `data/jobs_clean.csv` (skills joined with `;`).
5. **Analyse** - top-10 skills, common titles, jobs per location and per company,
   chart saved to `data/jobs_top_skills.png`.
6. **Errors** - 10 s timeouts, bad status codes, missing fields, invalid selectors and
   malformed JSON are all caught and logged.
7. **Retries (bonus 1)** - `fetch_with_retry()` retries timeouts, connection errors and
   429/5xx with exponential backoff (1 s, 2 s, 4 s + jitter, honouring `Retry-After`).
   Other 4xx errors fail immediately because retrying will not help.
8. **Second source (bonus 2)** - `board_scraper.py` reads Arbeitnow's public JSON job
   API. Skills are extracted from the HTML description with BeautifulSoup and a keyword
   list (`SKILL_KEYWORDS`).

## Ethical scraping notes

- **Read robots.txt and the terms of service first.** The code checks robots.txt for
  you; the terms are for *you* to read, and they can change.
- **Identify yourself.** The User-Agent names the project and a contact address - edit it.
- **Be gentle.** Delay between page requests, few pages, retries with backoff (never a
  tight retry loop). Do not run it in a loop or in parallel.
- **Prefer official APIs** over HTML scraping when one exists (that is why bonus 2 uses
  one).
- **Do not collect personal data**, do not log in or bypass blocks/CAPTCHAs, and do not
  republish scraped data wholesale. Credit the source (Arbeitnow asks for attribution
  as a good practice; the program prints a reminder).
- This is a learning project. Practice sites are meant to be scraped; real sites are
  not obliged to be.

*Why not Remotive?* Its public API is popular, but its robots.txt disallows `/api/*` and
its terms limit use (attribution, a few calls per day, no re-submission to other job
boards), so it was skipped in favour of a source whose robots.txt allows the path.

## If the page layout changes (adjusting selectors)

All selectors live in one dict, `DEFAULT_SELECTORS` in `scraper.py`. No parsing code
needs to change.

1. Open the page, right-click one job -> **Inspect**. Find the element that wraps one
   whole listing (the *card*) - e.g. `<div class="card-content">`.
2. Fill in `card` with its CSS selector (`div.card-content`, `article.job`, `li.result`).
3. For each field, find the element **inside** a card and write a selector *relative to
   the card*: `title` -> `h2.title`, `company` -> `h3.company`, and so on.
4. Prefer stable hooks (semantic classes, `data-*` attributes, `itemprop`) over fragile
   ones (`div > div:nth-child(3)`, auto-generated class names like `css-1x8f2`).
5. Add several comma-separated fallbacks: `"h2.title, .job-title, h2"`.
6. Dates: if the page uses `<time datetime="...">` the machine-readable attribute is
   used automatically; otherwise the visible text is parsed (pandas handles most formats).
7. If the "no listing cards matched" warning appears or the exit code is `5`, the card
   selector is wrong - test in the browser console with
   `document.querySelectorAll("div.card-content").length`.
8. If content only appears after JavaScript runs (view-source is nearly empty),
   `requests` cannot see it. Look in DevTools -> Network -> Fetch/XHR for a JSON endpoint
   and request that instead (as `board_scraper.py` does).

Quick way to experiment without re-running everything:

```python
from scraper import parse_listings, DEFAULT_SELECTORS
html = open("saved_page.html", encoding="utf-8").read()
sel = {**DEFAULT_SELECTORS, "card": "div.card-content", "title": "h2.title"}
print(parse_listings(html, sel)[:3])
```

## Sample output (from the bundled `tests/` sample pages)

```
[robots.txt] none found (HTTP 404) -> allowed
INFO scraper: Page 1: 6 listings
INFO scraper: Page 2: 1 listings
WARNING cleaner: 3 rows have a missing/unparseable posted date
WARNING cleaner: Dropping 1 rows with no title
INFO cleaner: Cleaned 7 raw rows -> 5 rows

Listings analysed: 5
Posted between 2026-10-01 and 2026-10-05

=== Top 10 skills ===
           skill  listings  share_%
          python         4     80.0
             sql         4     80.0
           excel         2     40.0
      javascript         1     20.0
          pandas         1     20.0
          django         1     20.0
      postgresql         1     20.0
machine learning         1     20.0
         tableau         1     20.0

=== Most common job titles ===
           title  jobs
    Data Analyst     2
Python Developer     1
Backend Engineer     1
     ML Engineer     1

=== Jobs per location ===
location  jobs
 Karachi     2
  Lahore     1
  Remote     1
 Unknown     1
```

Messy input rows (extra spaces, `ACME CORP` vs `Acme Corp`, a duplicate listing, a card
with no title, a missing company, an unparseable date) were all handled without crashing.
