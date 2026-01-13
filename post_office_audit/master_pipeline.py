from __future__ import annotations

"""
MASTER PIPELINE (no CLI args)

Run the entire workflow end-to-end with sensible defaults:
1) Scan SWVF files in ./data (or POST_OFFICE_DATA_DIR) and write output/flagged_voter_addresses.csv
2) Download/cache Ohio Votes Count voter IDs under ./output (or POST_OFFICE_OUTPUT_DIR)
3) Generate output/flagged_addresses_map.html (annotated with Ohio Votes Count status)

Usage:
    python post_office_audit/master_pipeline.py
"""

import os
import sys
from pathlib import Path


def _print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _ensure_defaults() -> None:
    """
    Set defaults only if env vars are not already provided.
    """
    os.environ.setdefault("POST_OFFICE_DATA_DIR", "data")
    os.environ.setdefault("POST_OFFICE_OUTPUT_DIR", "output")
    os.environ.setdefault("POST_OFFICE_STATE", "OH")

    # Ohio Votes Count defaults (enabled)
    os.environ.setdefault("OVC_ENABLE", "1")
    os.environ.setdefault(
        "OVC_URL",
        "https://ohiovotescount.com/us-post-office-registrations-voter-registration-issues-january-2026/",
    )
    os.environ.setdefault("OVC_FORCE", "0")


def main() -> int:
    _ensure_defaults()

    data_dir = Path(os.environ["POST_OFFICE_DATA_DIR"])
    out_dir = Path(os.environ["POST_OFFICE_OUTPUT_DIR"])
    state = os.environ["POST_OFFICE_STATE"]

    _print_header("POST OFFICE AUDIT - MASTER PIPELINE")
    print(f"Data dir:   {data_dir.resolve()}")
    print(f"Output dir: {out_dir.resolve()}")
    print(f"State:      {state}")
    print(f"OVC enable: {os.environ.get('OVC_ENABLE')}")

    # Import locally so this file stays standalone when copied.
    try:
        from post_office_audit import audit as audit_mod  # type: ignore
        from post_office_audit import map_flagged as map_mod  # type: ignore
    except Exception:
        # Fallback for running as a script without package context (common on Windows).
        here = Path(__file__).resolve().parent
        sys.path.insert(0, str(here.parent))
        from post_office_audit import audit as audit_mod  # type: ignore
        from post_office_audit import map_flagged as map_mod  # type: ignore

    _print_header("STEP 1: Scan SWVF files")
    rc = audit_mod.main()
    if rc != 0:
        print("ERROR: scan failed; not generating map.")
        return rc

    flagged_csv = out_dir / "flagged_voter_addresses.csv"
    if not flagged_csv.exists():
        print(f"ERROR: expected output missing: {flagged_csv}")
        return 2

    _print_header("STEP 2: Download/cache Ohio Votes Count IDs (optional)")
    if os.environ.get("OVC_ENABLE", "1").strip().lower() in {"1", "true", "t", "yes", "y"}:
        try:
            ids = map_mod.download_ovc_voter_ids(output_dir=out_dir, url=os.environ["OVC_URL"], force=os.environ.get("OVC_FORCE", "0") == "1")
            print(f"Ohio Votes Count IDs cached: {len(ids)}")
        except Exception as e:
            print(f"WARNING: OVC step failed; continuing without it: {e}")
            os.environ["OVC_ENABLE"] = "0"
    else:
        print("OVC disabled; skipping.")

    _print_header("STEP 3: Generate interactive HTML map")
    try:
        out_path = map_mod.create_map()
        print(f"Map written: {out_path}")
    except Exception as e:
        print(f"WARNING: map generation failed: {e}")
        print(f"You can still use the CSV: {flagged_csv}")
        return 0

    _print_header("DONE")
    print("Outputs:")
    print(f"- {flagged_csv}")
    print(f"- {out_dir / 'flagged_addresses_map.html'}")
    if os.environ.get("OVC_ENABLE") == "1":
        print(f"- {out_dir / 'ovc_voter_ids.csv'}")
        print(f"- {out_dir / 'ovc_source.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

