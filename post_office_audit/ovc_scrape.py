from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List, Optional, Set, Tuple

import pandas as pd
import requests


DEFAULT_OVC_URL = "https://ohiovotescount.com/us-post-office-registrations-voter-registration-issues-january-2026/"


def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name, "").strip()
    return Path(val) if val else default


def load_output_dir() -> Path:
    return _env_path("POST_OFFICE_OUTPUT_DIR", Path("output"))


def download_html(url: str, html_cache: Path, *, force: bool = False) -> str:
    if html_cache.exists() and not force:
        return html_cache.read_text(encoding="utf-8", errors="ignore")

    resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
    resp.raise_for_status()
    html_cache.parent.mkdir(parents=True, exist_ok=True)
    html_cache.write_text(resp.text, encoding="utf-8", errors="ignore")
    return resp.text


def parse_tables(html: str) -> List[pd.DataFrame]:
    """
    Parse all HTML tables into DataFrames. Requires 'lxml'.
    """
    try:
        return pd.read_html(html)
    except ValueError:
        # No tables found
        return []


def _find_voter_id_column(columns: List[str]) -> Optional[str]:
    cols = [str(c).strip() for c in columns]
    lower_map = {c.lower(): c for c in cols}

    candidates = [
        "sos voter id",
        "sos voterid",
        "sos_voterid",
        "voter id",
        "voter_id",
        "voterid",
    ]
    for cand in candidates:
        if cand in lower_map:
            return lower_map[cand]

    for c in cols:
        cl = c.lower()
        if "voter" in cl and "id" in cl:
            return c
    return None


def extract_voter_ids(tables: List[pd.DataFrame]) -> Tuple[Set[str], pd.DataFrame]:
    """
    Returns (unique_ids, combined_rows).
    combined_rows includes an added 'source_table_index' column to aid debugging.
    """
    frames: List[pd.DataFrame] = []
    ids: Set[str] = set()

    for i, t in enumerate(tables):
        if t is None or t.empty:
            continue

        # Normalize columns to strings
        t = t.copy()
        t.columns = [str(c).strip() for c in t.columns]
        t["source_table_index"] = i

        vid_col = _find_voter_id_column(list(t.columns))
        if vid_col:
            vid = t[vid_col].astype(str).str.strip()
            vid = vid[vid.ne("") & vid.ne("nan")]
            ids.update(vid.tolist())

        frames.append(t)

    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return ids, combined


def main() -> int:
    ap = argparse.ArgumentParser(description="Download and parse Ohio Votes Count voter ID tables.")
    ap.add_argument("--url", default=os.environ.get("OVC_URL", DEFAULT_OVC_URL), help="Ohio Votes Count page URL")
    ap.add_argument(
        "--force",
        action="store_true",
        default=os.environ.get("OVC_FORCE", "0").strip().lower() in {"1", "true", "t", "yes", "y"},
        help="Force re-download (ignore cached HTML)",
    )
    ap.add_argument(
        "--output-dir",
        default=str(load_output_dir()),
        help="Output directory (default: POST_OFFICE_OUTPUT_DIR or ./output)",
    )
    args = ap.parse_args()

    output_dir = Path(args.output_dir)
    html_cache = output_dir / "ovc_source.html"
    ids_csv = output_dir / "ovc_voter_ids.csv"
    tables_csv = output_dir / "ovc_tables_combined.csv"

    print(f"Downloading: {args.url}")
    html = download_html(args.url, html_cache, force=args.force)

    tables = parse_tables(html)
    print(f"Found {len(tables)} HTML tables")

    voter_ids, combined = extract_voter_ids(tables)
    print(f"Extracted {len(voter_ids)} unique voter IDs")

    output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"voter_id": sorted(voter_ids)}).to_csv(ids_csv, index=False)
    print(f"Wrote voter IDs: {ids_csv}")

    if not combined.empty:
        combined.to_csv(tables_csv, index=False)
        print(f"Wrote combined tables: {tables_csv}")
    else:
        print("No table rows to write (tables were empty or missing).")

    print(f"Cached HTML: {html_cache}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

