# NTB Seychelles Procurement Intelligence

A Python toolkit that scrapes, structures, and visualises all public procurement data published by the **[National Tender Board of Seychelles](https://www.ntb.sc)** — across four data sources, combined into a single interactive dashboard with CSV / Excel / JSON export.

---

## What it does

| Module | Source URL | What it extracts |
|---|---|---|
| `ntb_seychelles_scraper.py` | `/tenders/awarded-tenders` | Contract winner, SR value, org, category — per awarded period |
| `ntb_minutes_scraper.py` | `/tenders/minutes-of-tenders` | All competing bids per tender opening (bidder name + price) |
| `ntb_eoi_scraper.py` | `/tenders/expression-of-interest` | EOI / limited bidding notices, deadlines, descriptions |
| `ntb_advertised_scraper.py` | `/tenders` | Full advertised tenders — eligibility, contractor class, dossier fee, pre-bid meeting |
| `ntb_dashboard.py` | — | Combines all four datasets into one interactive Plotly Dash dashboard |
| `main.py` | — | Single entry point to run any/all scrapers and launch the dashboard |

---

## Dashboard sections

- **Headline KPIs** — total SR awarded, tenders opened, EOI count, advertised count
- **Procurement funnel** — Advertised → EOI → Minutes → Awarded with volume at each stage
- **Awarded spend** — SR value by category (bar + treemap) and by org (horizontal bar)
- **Bidding market** — competition level (bids per tender distribution) + most frequent low bidders
- **Pipeline tracker** — upcoming advertised tenders sorted by deadline
- **Organisation deep dive** — per-org breakdown across all four data stages
- **Full-text search** — query across all datasets simultaneously
- **Data export** — download any dataset or the combined master as CSV, Excel (.xlsx with summary sheets), or JSON

---

## Project structure

```
ntb-seychelles/
├── main.py                      # Single entry point — run scrapers + dashboard
├── ntb_dashboard.py             # Plotly Dash dashboard (combines all 4 datasets)
├── requirements.txt
├── .gitignore
├── README.md
└── scrapers/
    ├── ntb_seychelles_scraper.py    # Awarded tenders
    ├── ntb_minutes_scraper.py       # Minutes of tenders
    ├── ntb_eoi_scraper.py           # Expressions of interest
    └── ntb_advertised_scraper.py    # Advertised tenders
```

---

## Quickstart

### 1. Clone and install

```bash
git clone https://github.com/your-username/ntb-seychelles.git
cd ntb-seychelles

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Run everything (scrape all + launch dashboard)

```bash
python main.py --all
```

This will:
1. Scrape all four NTB data sources (takes ~60–90 minutes for full runs)
2. Save CSVs, PDFs, and HTML caches to `./data/`
3. Launch the dashboard at **http://localhost:8050**

### 3. Quick test run (3 pages per scraper)

```bash
python main.py --all --max-pages 3
```

### 4. Launch dashboard from existing data (no scraping)

```bash
python main.py --dashboard-only
```

---

## Running scrapers individually

Each scraper can also be run standalone from the `scrapers/` directory:

```bash
# Awarded tenders
python scrapers/ntb_seychelles_scraper.py
python scrapers/ntb_seychelles_scraper.py --sr-only --out data/ntb_tenders.csv

# Minutes of tenders (all competing bids)
python scrapers/ntb_minutes_scraper.py
python scrapers/ntb_minutes_scraper.py --max-pages 5   # test run

# Expressions of interest
python scrapers/ntb_eoi_scraper.py
python scrapers/ntb_eoi_scraper.py --skip-fetch        # use cached HTML

# Advertised tenders
python scrapers/ntb_advertised_scraper.py
python scrapers/ntb_advertised_scraper.py --no-pdfs    # HTML only, much faster
```

---

## CLI reference

### `main.py`

| Flag | Description |
|---|---|
| `--all` | Run all four scrapers |
| `--awarded` | Run awarded tenders scraper only |
| `--minutes` | Run minutes scraper only |
| `--eoi` | Run EOI scraper only |
| `--advertised` | Run advertised scraper only |
| `--dashboard-only` | Skip scraping, launch dashboard from existing CSVs |
| `--no-dashboard` | Scrape only, do not launch dashboard |
| `--combine-only` | Merge CSVs into `ntb_master.csv` without launching dashboard |
| `--max-pages N` | Limit listing pages per scraper (default: unlimited) |
| `--skip-download` | Skip PDF downloads; parse only cached files (awarded + minutes) |
| `--skip-fetch` | Skip detail-page fetches; use cached HTML (EOI + advertised) |
| `--no-pdfs` | Skip PDF processing in advertised scraper (faster) |
| `--sr-only` | Keep only SR-denominated rows in output |
| `--out-dir PATH` | Output directory for all CSVs/PDFs (default: `./data`) |
| `--port N` | Dashboard port (default: 8050) |

### `ntb_dashboard.py`

```bash
python ntb_dashboard.py \
  --awarded   data/ntb_tenders.csv \
  --minutes   data/ntb_minutes.csv \
  --eoi       data/ntb_eoi.csv \
  --advertised data/ntb_advertised.csv \
  --port 8050
```

| Flag | Description |
|---|---|
| `--awarded PATH` | Path to awarded tenders CSV |
| `--minutes PATH` | Path to minutes CSV |
| `--eoi PATH` | Path to EOI CSV |
| `--advertised PATH` | Path to advertised tenders CSV |
| `--port N` | Dashboard port (default: 8050) |
| `--combine-only` | Write `ntb_master.csv` and exit without launching dashboard |

---

## Output files

After a full run, `./data/` contains:

| File | Description |
|---|---|
| `ntb_tenders.csv` | Awarded contracts (one row per contract) |
| `ntb_minutes.csv` | All bids from tender openings (one row per bidder per tender) |
| `ntb_eoi.csv` | Expressions of interest and limited bidding notices |
| `ntb_advertised.csv` | Advertised tenders with full eligibility/deadline details |
| `ntb_master.csv` | All four datasets combined with a `source` column |
| `ntb_tenders.xlsx` | Awarded data with summary sheets (by org, category, period) |
| `ntb_minutes.xlsx` | Minutes data with top bidders, category breakdown |
| `ntb_eoi.xlsx` | EOI data with type, org, deadline timeline sheets |
| `ntb_advertised.xlsx` | Advertised data with contractor class, fee breakdown |

---

## Output columns

### Awarded tenders (`ntb_tenders.csv`)

| Column | Description |
|---|---|
| `period` | Reporting period label (e.g. "May–Aug 2025") |
| `org` | Procuring entity |
| `description` | Project description |
| `winner` | Successful bidder |
| `sr_value` | Contract value in SR (null for foreign currency) |
| `currency` | Currency code (SR / USD / EUR / GBP…) |
| `foreign_amount` | Value in foreign currency where applicable |
| `amount_raw` | Raw amount string from PDF |
| `category` | Inferred project category |

### Minutes of tenders (`ntb_minutes.csv`)

| Column | Description |
|---|---|
| `title` | Tender title |
| `org` | Procuring entity |
| `tender_description` | Full tender description from PDF |
| `opening_date` | Date and time of tender opening |
| `n_bids_declared` | Number of bids declared at opening |
| `bid_number` | Bid position (T1 = lowest/first read out) |
| `bidder_name` | Company name |
| `currency` | Bid currency |
| `bid_amount` | Bid value |
| `category` | Inferred category |
| `created_date` | Date published on NTB website |
| `pdf_url` | Source PDF URL |
| `detail_url` | NTB detail page URL |

### Expressions of interest (`ntb_eoi.csv`)

| Column | Description |
|---|---|
| `title` | EOI title |
| `org` | Procuring entity |
| `eoi_type` | EOI / Limited Bidding / Prequalification / Other |
| `category` | Inferred category |
| `tags` | Site-assigned tags (e.g. "Good and Services", "Vehicles") |
| `created_date` | Date published |
| `submission_deadline` | ISO date |
| `submission_time` | Time of deadline |
| `description` | Full body text |
| `pdf_url` | Attached document URL (if any) |
| `pdf_text` | Extracted PDF text (if `--download-pdfs` used) |
| `detail_url` | NTB detail page URL |

### Advertised tenders (`ntb_advertised.csv`)

| Column | Description |
|---|---|
| `title` | Tender title |
| `org` | Procuring entity |
| `category` | Inferred category |
| `tags` | Site-assigned tags |
| `source_of_finance` | Funding source |
| `project_title` | Formal project title |
| `eligibility` | Raw eligibility text |
| `contractor_class` | Required contractor class(es) |
| `performance_period` | Contract duration |
| `place_of_performance` | Project location |
| `dossier_fee` | Tender document fee (e.g. "SR 350" / "Free") |
| `pre_bid_meeting` | Mandatory pre-bid meeting date |
| `contact_email` | Contact email(s) |
| `created_date` | Date published |
| `submission_deadline` | ISO date |
| `submission_time` | Time of deadline |
| `pdf_url` | Attached document URL |
| `pdf_accessible` | Whether PDF was successfully downloaded |
| `description` | Full body text |
| `detail_url` | NTB detail page URL |

---

## Data availability notes

- **Awarded tenders:** PDFs exist for May–Aug 2025, Jan–Apr 2025, Nov–Dec 2024, and Jan–Apr 2021. PDFs for 2022–2024 periods return HTTP 404 — they appear to have been removed from the NTB server.
- **Minutes of tenders:** ~158 listing pages as of April 2026, PDFs largely accessible.
- **Expressions of interest:** ~28 listing pages, data lives in HTML (PDFs mostly 404).
- **Advertised tenders:** ~153 listing pages, PDFs mostly accessible and contain richer structured data than the HTML pages.

---

## Responsible scraping

All scrapers include:
- A configurable delay between requests (default 1.2–1.5 seconds)
- HTML and PDF caching to avoid redundant network calls on re-runs
- `--max-pages` to limit scope during development
- A descriptive `User-Agent` header identifying the scraper

Please respect the NTB's servers and do not reduce delays below 1 second.

---

## Extending the project

### Adding a new data source

1. Create `scrapers/ntb_new_source_scraper.py` following the same pattern (argparse CLI, `--out`, `--max-pages`, category classifier, CSV + Excel output).
2. Add a `run_new_source()` function in `main.py`.
3. Load it in `ntb_dashboard.py` inside `combine()` and `compute_stats()`.

### Changing the category classifier

All scrapers share the same `CATEGORY_RULES` list — a list of `(category_name, regex_pattern)` tuples evaluated in order. Edit the rules in any scraper file. Consider extracting them to a shared `scrapers/categories.py` module if you want a single source of truth.

### Connecting a database

Replace the CSV outputs with SQLAlchemy inserts by swapping `df.to_csv()` for `df.to_sql()`. The `ntb_master.csv` schema maps cleanly to a single wide table; alternatively normalise into separate tables per source.

---

## License

MIT — see `LICENSE` for details.

---

## Acknowledgements

Data sourced from the [National Tender Board of Seychelles](https://www.ntb.sc), a public government institution. This project is an independent tool for transparency and analysis and is not affiliated with the NTB.
