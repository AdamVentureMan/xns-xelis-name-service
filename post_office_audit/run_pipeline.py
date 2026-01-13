from __future__ import annotations

"""
Standalone runner for the post_office_audit pipeline.

Orchestrates:
1) Scan SWVF files and produce flagged output CSV (audit.py)
2) (Optional) Download/cache Ohio Votes Count voter IDs (ovc_scrape.py)
3) Generate interactive HTML map (map_flagged.py)
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional


def run_script(script_path: Path, description: str, *, env: Optional[Dict[str, str]] = None) -> bool:
    print(f"\n{'=' * 70}")
    print(f"STEP: {description}")
    print(f"{'=' * 70}")
    print(f"Running: {sys.executable} {script_path}")

    try:
        subprocess.run([sys.executable, str(script_path)], check=True, env=env)
        print(f"✓ {description} completed")
        return True
    except subprocess.CalledProcessError as e:
        print(f"✗ {description} failed (exit code {e.returncode})")
        return False
    except Exception as e:
        print(f"✗ {description} failed (unexpected): {e}")
        return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the full post office audit pipeline.")
    ap.add_argument("--data-dir", default=os.environ.get("POST_OFFICE_DATA_DIR", "data"))
    ap.add_argument("--output-dir", default=os.environ.get("POST_OFFICE_OUTPUT_DIR", "output"))
    ap.add_argument("--state", default=os.environ.get("POST_OFFICE_STATE", "OH"))
    ap.add_argument(
        "--skip-ovc",
        action="store_true",
        help="Skip downloading/parsing Ohio Votes Count voter IDs",
    )
    ap.add_argument(
        "--ovc-url",
        default=os.environ.get(
            "OVC_URL",
            "https://ohiovotescount.com/us-post-office-registrations-voter-registration-issues-january-2026/",
        ),
        help="Ohio Votes Count page URL",
    )
    ap.add_argument(
        "--force-ovc",
        action="store_true",
        help="Force re-download Ohio Votes Count page (refresh cache)",
    )
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    audit_py = here / "audit.py"
    ovc_py = here / "ovc_scrape.py"
    map_py = here / "map_flagged.py"

    env = os.environ.copy()
    env["POST_OFFICE_DATA_DIR"] = str(Path(args.data_dir))
    env["POST_OFFICE_OUTPUT_DIR"] = str(Path(args.output_dir))
    env["POST_OFFICE_STATE"] = str(args.state).strip().upper() or "OH"

    print("=" * 70)
    print("POST OFFICE AUDIT PIPELINE")
    print("=" * 70)
    print(f"Data dir:   {env['POST_OFFICE_DATA_DIR']}")
    print(f"Output dir: {env['POST_OFFICE_OUTPUT_DIR']}")
    print(f"State:      {env['POST_OFFICE_STATE']}")

    # Step 1: scan voter files (required)
    if not run_script(audit_py, "Scan SWVF files and flag commercial/post-office patterns", env=env):
        print("\nERROR: Audit step failed; not generating maps.")
        return 2

    # Step 2: optional Ohio Votes Count scrape (map step can also do this, but this pre-caches it)
    if args.skip_ovc:
        env["OVC_ENABLE"] = "0"
        print("\nOVC comparison: disabled (skip requested)")
    else:
        env["OVC_ENABLE"] = "1"
        env["OVC_URL"] = args.ovc_url
        if args.force_ovc:
            env["OVC_FORCE"] = "1"
        if ovc_py.exists():
            run_script(ovc_py, "Download/cache Ohio Votes Count voter IDs", env=env)

    # Step 3: map (requires audit output)
    if not run_script(map_py, "Generate interactive HTML map", env=env):
        print("\nWARNING: Map step failed, but the CSV output is still available.")

    out_dir = Path(env["POST_OFFICE_OUTPUT_DIR"])
    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)
    print("Outputs (expected):")
    print(f"- {out_dir / 'flagged_voter_addresses.csv'}")
    print(f"- {out_dir / 'flagged_addresses_map.html'}")
    if not args.skip_ovc:
        print(f"- {out_dir / 'ovc_voter_ids.csv'}")
        print(f"- {out_dir / 'ovc_source.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

