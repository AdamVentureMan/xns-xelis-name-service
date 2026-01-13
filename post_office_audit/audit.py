from __future__ import annotations

import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
from tqdm.auto import tqdm


ARCGIS_USPS_FACILITIES_URL = (
    "https://services5.arcgis.com/TBEibzxOE0dzXUyc/arcgis/rest/services/"
    "USPS_Facilities/FeatureServer/0/query"
)


CITY_ALIASES: Dict[str, str] = {
    "ST MARYS": "SAINT MARYS",
    "ST. MARYS": "SAINT MARYS",
    "BOARDMAN": "YOUNGSTOWN",
    "POLAND": "YOUNGSTOWN",
    "WINTERSVILLE": "STEUBENVILLE",
}

PUNCT_RE = re.compile(r"[.,#]")
MULTISPACE_RE = re.compile(r"\s+")

# PO BOX style: often won't match USPS facility street address; flag separately.
PO_BOX_RE = re.compile(
    r"\b(P\.?\s*O\.?\s*BOX|PO\s*BOX|P\s*O\s*BOX|POST\s+OFFICE\s+BOX)\b",
    re.IGNORECASE,
)

# Commercial keywords: can catch mail centers/PMB/etc. Kept separate from PO BOX.
COMMERCIAL_RE = re.compile(
    r"\b(PMB|UPS\s*STORE|MAIL\s*(CENTER|CTR)|USPS|POST\s*OFFICE)\b",
    re.IGNORECASE,
)

UNIT_RE = re.compile(r"\b(APT|UNIT|STE|SUITE|#)\b", re.IGNORECASE)


@dataclass(frozen=True)
class Config:
    state: str
    data_dir: Path
    output_dir: Path
    voter_glob: str = "SWVF_*"
    usps_cache_name: str = "usps_facilities.csv"
    chunksize: int = 100_000
    encoding: str = "ISO-8859-1"


def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name, "").strip()
    return Path(val) if val else default


def load_config() -> Config:
    state = os.environ.get("POST_OFFICE_STATE", "OH").strip().upper() or "OH"
    data_dir = _env_path("POST_OFFICE_DATA_DIR", Path("data"))
    output_dir = _env_path("POST_OFFICE_OUTPUT_DIR", Path("output"))
    return Config(state=state, data_dir=data_dir, output_dir=output_dir)


def normalize_text_series(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str).str.upper().str.replace("-", " ", regex=False)
    s = s.str.replace(PUNCT_RE, "", regex=True)
    s = s.str.replace(MULTISPACE_RE, " ", regex=True).str.strip()
    return s


def extract_zip5_series(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str)
    return s.str.extract(r"(\d{5})", expand=False).fillna("")


def detect_delimiter(path: Path, *, encoding: str) -> str:
    """
    Ohio SWVF commonly arrives as .txt but is still delimited (often pipe).
    We use a lightweight heuristic over the first non-empty line.
    """
    candidates = ["|", "\t", ","]
    try:
        with path.open("rb") as f:
            sample = f.read(64 * 1024)
        text = sample.decode(encoding, errors="ignore")
    except Exception:
        return ","

    first_nonempty = ""
    for line in text.splitlines():
        if line.strip():
            first_nonempty = line
            break
    if not first_nonempty:
        return ","

    counts = {c: first_nonempty.count(c) for c in candidates}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def request_json_with_backoff(
    session: requests.Session,
    url: str,
    params: Dict[str, str],
    *,
    timeout: int = 45,
    max_attempts: int = 5,
) -> Dict:
    delay = 2.0
    last_exc: Optional[BaseException] = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = session.get(url, params=params, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001 - deliberate: network/JSON errors treated uniformly
            last_exc = exc
            if attempt == max_attempts:
                break
            time.sleep(delay)
            delay *= 2

    raise RuntimeError(f"Request failed after {max_attempts} attempts: {last_exc}") from last_exc


def download_usps_facilities(state: str, cache_csv: Path, *, force: bool = False) -> pd.DataFrame:
    if cache_csv.exists() and not force:
        df = pd.read_csv(cache_csv, low_memory=False)
        return df

    cache_csv.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()

    all_features: List[Dict] = []
    offset = 0
    record_count = 1000

    while True:
        params = {
            "where": f"STATE='{state}'",
            "outFields": "*",
            "returnGeometry": "true",
            "outSR": "4326",
            "f": "json",
            "resultRecordCount": str(record_count),
            "resultOffset": str(offset),
            "orderByFields": "OBJECTID",
        }

        data = request_json_with_backoff(session, ARCGIS_USPS_FACILITIES_URL, params)
        if "error" in data:
            msg = data["error"].get("message", "Unknown ArcGIS error")
            raise RuntimeError(f"ArcGIS API error: {msg}")

        features = data.get("features", []) or []
        if not features:
            break

        all_features.extend(features)

        # ArcGIS commonly stops when fewer than record_count is returned.
        if len(features) < record_count:
            break

        offset += record_count

    # Extract relevant fields
    rows: List[Dict[str, object]] = []
    for f in all_features:
        attrs = f.get("attributes", {}) or {}
        geom = f.get("geometry", {}) or {}

        zip_val = attrs.get("ZIP_CODE")
        name_val = attrs.get("LOCALE_NAME") or attrs.get("AREA_NAME") or attrs.get("NAME")

        rows.append(
            {
                "po_name": name_val or "",
                "po_address": attrs.get("ADDRESS") or "",
                "po_city": attrs.get("CITY") or "",
                "po_zip5": (str(zip_val)[:5] if zip_val else ""),
                "po_lat": geom.get("y"),
                "po_long": geom.get("x"),
            }
        )

    df = pd.DataFrame(rows)
    df.to_csv(cache_csv, index=False)
    return df


def build_reference(df_usps: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    df = df_usps.copy()
    df["addr_norm"] = normalize_text_series(df["po_address"])
    df["city_norm"] = normalize_text_series(df["po_city"])
    df["zip5"] = extract_zip5_series(df["po_zip5"])
    df["city_norm"] = df["city_norm"].replace(CITY_ALIASES)

    keep_cols = [
        "addr_norm",
        "city_norm",
        "zip5",
        "po_name",
        "po_address",
        "po_city",
        "po_zip5",
        "po_lat",
        "po_long",
    ]
    df = df[keep_cols]

    # Deterministic dedupe in case the API returns duplicates.
    df_city = df.sort_values(["addr_norm", "city_norm", "po_name"]).drop_duplicates(
        subset=["addr_norm", "city_norm"], keep="first"
    )
    df_zip = df.sort_values(["addr_norm", "zip5", "po_name"]).drop_duplicates(
        subset=["addr_norm", "zip5"], keep="first"
    )

    return df_city, df_zip


def detect_flags(addr_series: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
    addr = addr_series.fillna("").astype(str)
    flag_po_box_style = addr.str.contains(PO_BOX_RE, na=False)
    flag_commercial_keyword = addr.str.contains(COMMERCIAL_RE, na=False)
    has_unit = addr.str.contains(UNIT_RE, na=False)
    return flag_po_box_style, flag_commercial_keyword, has_unit


def infer_usecols(header_cols: Iterable[str]) -> Tuple[List[str], bool]:
    """
    Returns (usecols, has_addr2).
    If required columns are missing, returns ([], False) indicating "read all cols".
    """
    cols = set(header_cols)
    required = {
        "RESIDENTIAL_ADDRESS1",
        "RESIDENTIAL_CITY",
        "RESIDENTIAL_ZIP",
        "SOS_VOTERID",
        "FIRST_NAME",
        "LAST_NAME",
    }
    if not required.issubset(cols):
        return [], False
    usecols = sorted(required)
    has_addr2 = "RESIDENTIAL_ADDRESS2" in cols
    if has_addr2:
        usecols.append("RESIDENTIAL_ADDRESS2")
    return usecols, has_addr2


def scan_voter_file(
    path: Path,
    *,
    df_city: pd.DataFrame,
    df_zip: pd.DataFrame,
    cfg: Config,
    output_csv: Path,
    write_header: bool,
) -> Tuple[int, int]:
    sep = detect_delimiter(path, encoding=cfg.encoding)
    header = pd.read_csv(path, nrows=0, encoding=cfg.encoding, sep=sep)
    usecols, has_addr2 = infer_usecols(header.columns)

    reader = pd.read_csv(
        path,
        chunksize=cfg.chunksize,
        low_memory=False,
        encoding=cfg.encoding,
        sep=sep,
        usecols=(usecols or None),
    )

    total_flagged = 0
    total_high_priority = 0

    for chunk in tqdm(reader, desc=f"Scanning {path.name}"):
        chunk = chunk.rename(
            columns={
                "RESIDENTIAL_ADDRESS1": "addr1",
                "RESIDENTIAL_ADDRESS2": "addr2",
                "RESIDENTIAL_CITY": "city",
                "RESIDENTIAL_ZIP": "zip",
                "SOS_VOTERID": "voter_id",
                "FIRST_NAME": "first_name",
                "LAST_NAME": "last_name",
            }
        )

        if "addr1" not in chunk.columns:
            # Unexpected schema; nothing we can do safely without guessing.
            continue

        addr = chunk["addr1"].fillna("").astype(str)
        if has_addr2 and "addr2" in chunk.columns:
            addr2 = chunk["addr2"].fillna("").astype(str)
            addr = (addr + " " + addr2).str.replace(MULTISPACE_RE, " ", regex=True).str.strip()

        city = chunk.get("city", pd.Series([""] * len(chunk))).fillna("").astype(str)
        zip_series = chunk.get("zip", pd.Series([""] * len(chunk)))

        addr_norm = normalize_text_series(addr)
        city_norm = normalize_text_series(city).replace(CITY_ALIASES)
        zip5 = extract_zip5_series(zip_series)

        base = pd.DataFrame(
            {
                "source_file": path.name,
                "voter_id": chunk.get("voter_id", ""),
                "first_name": chunk.get("first_name", ""),
                "last_name": chunk.get("last_name", ""),
                "addr": addr,
                "city": city,
                "zip": zip5,
                "addr_norm": addr_norm,
                "city_norm": city_norm,
                "zip5": zip5,
            }
        )

        # Facility match (address+city)
        m_city = base.merge(
            df_city,
            on=["addr_norm", "city_norm"],
            how="left",
            suffixes=("", "_po"),
        )
        city_hit = m_city["po_name"].notna() & (m_city["po_name"].astype(str) != "")

        # Facility match fallback (address+zip5)
        m_zip = base.merge(
            df_zip,
            on=["addr_norm", "zip5"],
            how="left",
            suffixes=("", "_zip"),
        )
        zip_hit = m_zip["po_name"].notna() & (m_zip["po_name"].astype(str) != "")

        # Choose best facility match: city first, else zip.
        po_name = m_city["po_name"].where(city_hit, m_zip["po_name"])
        po_address = m_city["po_address"].where(city_hit, m_zip["po_address"])
        po_city = m_city["po_city"].where(city_hit, m_zip["po_city"])
        po_zip5 = m_city["po_zip5"].where(city_hit, m_zip["po_zip5"])
        po_lat = m_city["po_lat"].where(city_hit, m_zip["po_lat"])
        po_long = m_city["po_long"].where(city_hit, m_zip["po_long"])

        flag_facility_street_match = city_hit | zip_hit

        flag_po_box_style, flag_commercial_keyword, has_unit = detect_flags(addr)

        # Only keep "commercial keyword" separate; PO BOX is its own category.
        flag_any = flag_facility_street_match | flag_po_box_style | flag_commercial_keyword

        # Build a compact, auditable reason string.
        match_reason = pd.Series([""] * len(base))
        match_reason = match_reason.where(~city_hit, "facility_street_city")
        match_reason = match_reason.where(~(~city_hit & zip_hit), "facility_street_zip")

        # If no facility match, mark other flags as primary reason.
        match_reason = match_reason.mask(match_reason.eq("") & flag_po_box_style, "po_box_style")
        match_reason = match_reason.mask(
            match_reason.eq("") & ~flag_po_box_style & flag_commercial_keyword,
            "commercial_keyword",
        )

        # If multiple flags apply, append them for clarity.
        # (e.g. "facility_street_city;po_box_style")
        extra_po_box = flag_po_box_style & ~match_reason.str.contains("po_box_style", regex=False)
        extra_comm = flag_commercial_keyword & ~match_reason.str.contains("commercial_keyword", regex=False)
        extra_fac = flag_facility_street_match & ~match_reason.str.contains("facility_street", regex=False)

        match_reason = match_reason.where(~(match_reason.ne("") & extra_fac), match_reason + ";facility_street")
        match_reason = match_reason.where(~(match_reason.ne("") & extra_po_box), match_reason + ";po_box_style")
        match_reason = match_reason.where(~(match_reason.ne("") & extra_comm), match_reason + ";commercial_keyword")

        out = pd.DataFrame(
            {
                "source_file": base["source_file"],
                "voter_id": base["voter_id"],
                "first_name": base["first_name"],
                "last_name": base["last_name"],
                "addr": base["addr"],
                "city": base["city"],
                "zip5": base["zip5"],
                "flag_facility_street_match": flag_facility_street_match,
                "flag_po_box_style": flag_po_box_style,
                "flag_commercial_keyword": flag_commercial_keyword,
                "match_reason": match_reason,
                "po_name": po_name,
                "po_address": po_address,
                "po_city": po_city,
                "po_zip5": po_zip5,
                "po_lat": po_lat,
                "po_long": po_long,
                "has_unit": has_unit,
            }
        )

        out = out[flag_any].copy()
        if out.empty:
            continue

        total_flagged += len(out)
        total_high_priority += int((~out["has_unit"]).sum())

        output_csv.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output_csv, index=False, mode="a", header=write_header)
        write_header = False

    return total_flagged, total_high_priority


def main() -> int:
    cfg = load_config()
    cfg.data_dir.mkdir(parents=True, exist_ok=True)
    cfg.output_dir.mkdir(parents=True, exist_ok=True)

    voter_files = [
        p
        for p in sorted(cfg.data_dir.glob(cfg.voter_glob))
        if p.is_file() and p.suffix.lower() in {".csv", ".txt"}
    ]
    if not voter_files:
        print(f"No voter files found under: {cfg.data_dir.resolve()}", file=sys.stderr)
        print(f"Expected pattern: {cfg.voter_glob} (filtered to .csv/.txt)", file=sys.stderr)
        return 2

    usps_cache_csv = cfg.data_dir / cfg.usps_cache_name
    print(f"Loading USPS facilities for {cfg.state} (cache: {usps_cache_csv})...")
    df_usps = download_usps_facilities(cfg.state, usps_cache_csv)
    df_city, df_zip = build_reference(df_usps)

    output_csv = cfg.output_dir / "flagged_voter_addresses.csv"
    if output_csv.exists():
        output_csv.unlink()

    total_flagged = 0
    total_high_priority = 0
    write_header = True

    print(f"Scanning {len(voter_files)} voter files in {cfg.data_dir}...")
    for vf in voter_files:
        flagged, high_priority = scan_voter_file(
            vf,
            df_city=df_city,
            df_zip=df_zip,
            cfg=cfg,
            output_csv=output_csv,
            write_header=write_header,
        )
        write_header = False if output_csv.exists() else True
        total_flagged += flagged
        total_high_priority += high_priority

    print("\nAudit complete")
    print(f"- Output: {output_csv}")
    print(f"- Total flags: {total_flagged}")
    print(f"- High priority (no unit): {total_high_priority}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

