"""
NTB Seychelles Procurement Intelligence — Main Entry Point
===========================================================
Runs any combination of the four scrapers, then optionally
launches the combined dashboard.

Usage examples
--------------
  # Run everything end-to-end (scrape all + launch dashboard)
  python main.py --all

  # Scrape only, no dashboard
  python main.py --all --no-dashboard

  # Run individual scrapers
  python main.py --awarded
  python main.py --minutes
  python main.py --eoi
  python main.py --advertised

  # Launch dashboard using existing CSV files (no scraping)
  python main.py --dashboard-only

  # Limit pages (useful for quick tests before a full run)
  python main.py --all --max-pages 3

  # Custom output directory
  python main.py --all --out-dir ./my_data
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str], label: str) -> bool:
    """Run a subprocess command, stream output, return True on success."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, text=True)
    if result.returncode != 0:
        print(f"\n  ERROR: {label} exited with code {result.returncode}")
        return False
    return True


def python() -> str:
    """Return the current Python executable path."""
    return sys.executable


# ---------------------------------------------------------------------------
# Individual runners
# ---------------------------------------------------------------------------

def run_awarded(out_dir: Path, max_pages: int, skip_download: bool, sr_only: bool) -> bool:
    cmd = [
        python(), "scrapers/ntb_seychelles_scraper.py",
        "--out", str(out_dir / "ntb_tenders.csv"),
        "--pdf-dir", str(out_dir / "pdfs_awarded"),
    ]
    if max_pages:
        cmd += ["--max-pages", str(max_pages)]
    if skip_download:
        cmd.append("--skip-download")
    if sr_only:
        cmd.append("--sr-only")
    return run(cmd, "Scraping: Awarded Tenders")


def run_minutes(out_dir: Path, max_pages: int, skip_download: bool, sr_only: bool) -> bool:
    cmd = [
        python(), "scrapers/ntb_minutes_scraper.py",
        "--out", str(out_dir / "ntb_minutes.csv"),
        "--pdf-dir", str(out_dir / "pdfs_minutes"),
    ]
    if max_pages:
        cmd += ["--max-pages", str(max_pages)]
    if skip_download:
        cmd.append("--skip-download")
    if sr_only:
        cmd.append("--sr-only")
    return run(cmd, "Scraping: Minutes of Tenders")


def run_eoi(out_dir: Path, max_pages: int, skip_fetch: bool) -> bool:
    cmd = [
        python(), "scrapers/ntb_eoi_scraper.py",
        "--out", str(out_dir / "ntb_eoi.csv"),
        "--cache-dir", str(out_dir / "cache_eoi"),
    ]
    if max_pages:
        cmd += ["--max-pages", str(max_pages)]
    if skip_fetch:
        cmd.append("--skip-fetch")
    return run(cmd, "Scraping: Expressions of Interest")


def run_advertised(out_dir: Path, max_pages: int, skip_fetch: bool, no_pdfs: bool) -> bool:
    cmd = [
        python(), "scrapers/ntb_advertised_scraper.py",
        "--out", str(out_dir / "ntb_advertised.csv"),
        "--cache-dir", str(out_dir / "cache_advertised"),
        "--pdf-dir", str(out_dir / "pdfs_advertised"),
    ]
    if max_pages:
        cmd += ["--max-pages", str(max_pages)]
    if skip_fetch:
        cmd.append("--skip-fetch")
    if no_pdfs:
        cmd.append("--no-pdfs")
    return run(cmd, "Scraping: Advertised Tenders")


def run_dashboard(out_dir: Path, port: int, combine_only: bool) -> bool:
    cmd = [
        python(), "ntb_dashboard.py",
        "--awarded",    str(out_dir / "ntb_tenders.csv"),
        "--minutes",    str(out_dir / "ntb_minutes.csv"),
        "--eoi",        str(out_dir / "ntb_eoi.csv"),
        "--advertised", str(out_dir / "ntb_advertised.csv"),
        "--port",       str(port),
    ]
    if combine_only:
        cmd.append("--combine-only")
    return run(cmd, "Launching Dashboard" if not combine_only else "Combining data into ntb_master.csv")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(
        description="NTB Seychelles Procurement Intelligence — main runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    # Which scrapers to run
    grp = p.add_argument_group("Scrapers to run")
    grp.add_argument("--all",        action="store_true", help="Run all four scrapers")
    grp.add_argument("--awarded",    action="store_true", help="Run awarded tenders scraper")
    grp.add_argument("--minutes",    action="store_true", help="Run minutes of tenders scraper")
    grp.add_argument("--eoi",        action="store_true", help="Run expressions of interest scraper")
    grp.add_argument("--advertised", action="store_true", help="Run advertised tenders scraper")

    # Dashboard
    grp2 = p.add_argument_group("Dashboard")
    grp2.add_argument("--dashboard-only", action="store_true",
                      help="Skip scraping, just launch dashboard from existing CSVs")
    grp2.add_argument("--no-dashboard",   action="store_true",
                      help="Scrape only, do not launch dashboard")
    grp2.add_argument("--combine-only",   action="store_true",
                      help="Combine CSVs into ntb_master.csv without launching dashboard")
    grp2.add_argument("--port", type=int, default=8050, help="Dashboard port (default: 8050)")

    # Scraper options
    grp3 = p.add_argument_group("Scraper options")
    grp3.add_argument("--max-pages",     type=int, default=0,
                      help="Limit listing pages per scraper (0 = unlimited)")
    grp3.add_argument("--skip-download", action="store_true",
                      help="Skip PDF downloads; parse only cached files")
    grp3.add_argument("--skip-fetch",    action="store_true",
                      help="Skip detail page fetches; use cached HTML")
    grp3.add_argument("--no-pdfs",       action="store_true",
                      help="Skip PDF processing in advertised scraper")
    grp3.add_argument("--sr-only",       action="store_true",
                      help="Keep only SR-denominated rows in awarded/minutes output")

    # Output
    grp4 = p.add_argument_group("Output")
    grp4.add_argument("--out-dir", default="./data",
                      help="Directory for all output CSVs and PDFs (default: ./data)")

    args = p.parse_args()

    # If nothing specified, print help
    if not any([args.all, args.awarded, args.minutes, args.eoi,
                args.advertised, args.dashboard_only]):
        p.print_help()
        sys.exit(0)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    start = time.time()
    results = {}

    # ── Run scrapers ──────────────────────────────────────────────────────────
    if not args.dashboard_only:
        if args.all or args.awarded:
            results["awarded"] = run_awarded(
                out_dir, args.max_pages, args.skip_download, args.sr_only
            )

        if args.all or args.minutes:
            results["minutes"] = run_minutes(
                out_dir, args.max_pages, args.skip_download, args.sr_only
            )

        if args.all or args.eoi:
            results["eoi"] = run_eoi(
                out_dir, args.max_pages, args.skip_fetch
            )

        if args.all or args.advertised:
            results["advertised"] = run_advertised(
                out_dir, args.max_pages, args.skip_fetch, args.no_pdfs
            )

    # ── Summary ───────────────────────────────────────────────────────────────
    elapsed = time.time() - start
    if results:
        print(f"\n{'='*60}")
        print("  Scraping summary")
        print(f"{'='*60}")
        for name, ok in results.items():
            status = "OK" if ok else "FAILED"
            print(f"  {name:<15} {status}")
        print(f"  Total time:     {elapsed:.0f}s")
        print(f"  Output dir:     {out_dir.resolve()}")

    # ── Dashboard ─────────────────────────────────────────────────────────────
    if not args.no_dashboard:
        if args.combine_only:
            run_dashboard(out_dir, args.port, combine_only=True)
        else:
            run_dashboard(out_dir, args.port, combine_only=False)


if __name__ == "__main__":
    main()
