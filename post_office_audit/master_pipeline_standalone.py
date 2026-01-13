from __future__ import annotations

"""
POST OFFICE AUDIT — STANDALONE MASTER PIPELINE (single file)

This script is intentionally self-contained: it does NOT import from other local modules.
Run it with no CLI args:

    python master_pipeline_standalone.py

Defaults (override via environment variables if desired):
  - POST_OFFICE_DATA_DIR   (default: ./data)   contains SWVF_*.txt / SWVF_*.csv and USPS cache CSV
  - POST_OFFICE_OUTPUT_DIR (default: ./output) output CSV + HTML map + OVC cache
  - POST_OFFICE_STATE      (default: OH)

Ohio Votes Count (optional; enabled by default):
  - OVC_ENABLE (default: 1)
  - OVC_URL    (default: Jan 2026 page)
  - OVC_FORCE  (default: 0) force re-download

Outputs:
  - output/flagged_voter_addresses.csv
  - output/flagged_addresses_map.html
  - output/ovc_voter_ids.csv (if OVC enabled and parse succeeds)
  - output/ovc_source.html   (if OVC enabled and download succeeds)
"""

import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import quote_plus

import pandas as pd
import requests
import folium
from folium import plugins
from tqdm.auto import tqdm


# -----------------------------
# Constants / patterns
# -----------------------------

ARCGIS_USPS_FACILITIES_URL = (
    "https://services5.arcgis.com/TBEibzxOE0dzXUyc/arcgis/rest/services/"
    "USPS_Facilities/FeatureServer/0/query"
)

DEFAULT_OVC_URL = "https://ohiovotescount.com/us-post-office-registrations-voter-registration-issues-january-2026/"

CITY_ALIASES: Dict[str, str] = {
    "ST MARYS": "SAINT MARYS",
    "ST. MARYS": "SAINT MARYS",
    "BOARDMAN": "YOUNGSTOWN",
    "POLAND": "YOUNGSTOWN",
    "WINTERSVILLE": "STEUBENVILLE",
}

PUNCT_RE = re.compile(r"[.,#]")
MULTISPACE_RE = re.compile(r"\s+")

PO_BOX_RE = re.compile(
    r"\b(?:P\.?\s*O\.?\s*BOX|PO\s*BOX|P\s*O\s*BOX|POST\s+OFFICE\s+BOX)\b",
    re.IGNORECASE,
)

COMMERCIAL_RE = re.compile(
    r"\b(?:PMB|UPS\s*STORE|MAIL\s*(?:CENTER|CTR)|USPS|POST\s*OFFICE)\b",
    re.IGNORECASE,
)

# Non-capturing groups prevent pandas warnings in str.contains().
UNIT_RE = re.compile(r"(?:\b(?:APT|UNIT|STE|SUITE)\b|#)", re.IGNORECASE)


# -----------------------------
# Small helpers
# -----------------------------

def _bool_env(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "t", "yes", "y"}


def _print_header(title: str) -> None:
    print("\n" + "=" * 76)
    print(title)
    print("=" * 76)


def normalize_text_series(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str).str.upper().str.replace("-", " ", regex=False)
    s = s.str.replace(PUNCT_RE, "", regex=True)
    s = s.str.replace(MULTISPACE_RE, " ", regex=True).str.strip()
    return s


def extract_zip5_series(s: pd.Series) -> pd.Series:
    s = s.fillna("").astype(str)
    return s.str.extract(r"(\d{5})", expand=False).fillna("")


def _safe_float(x) -> Optional[float]:
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def _gmaps_search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def detect_delimiter(path: Path, *, encoding: str) -> str:
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


# -----------------------------
# USPS facilities download/cache
# -----------------------------

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
        except Exception as exc:
            last_exc = exc
            if attempt == max_attempts:
                break
            time.sleep(delay)
            delay *= 2

    raise RuntimeError(f"Request failed after {max_attempts} attempts: {last_exc}") from last_exc


def download_usps_facilities(state: str, cache_csv: Path, *, force: bool = False) -> pd.DataFrame:
    if cache_csv.exists() and not force:
        return pd.read_csv(cache_csv, low_memory=False)

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
        if len(features) < record_count:
            break
        offset += record_count

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
    df["city_norm"] = normalize_text_series(df["po_city"]).replace(CITY_ALIASES)
    df["zip5"] = extract_zip5_series(df["po_zip5"])

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

    df_city = df.sort_values(["addr_norm", "city_norm", "po_name"]).drop_duplicates(
        subset=["addr_norm", "city_norm"], keep="first"
    )
    df_zip = df.sort_values(["addr_norm", "zip5", "po_name"]).drop_duplicates(
        subset=["addr_norm", "zip5"], keep="first"
    )
    return df_city, df_zip


# -----------------------------
# SWVF scan
# -----------------------------

def detect_flags(addr_series: pd.Series) -> Tuple[pd.Series, pd.Series, pd.Series]:
    addr = addr_series.fillna("").astype(str)
    flag_po_box_style = addr.str.contains(PO_BOX_RE, na=False)
    flag_commercial_keyword = addr.str.contains(COMMERCIAL_RE, na=False)
    has_unit = addr.str.contains(UNIT_RE, na=False)
    return flag_po_box_style, flag_commercial_keyword, has_unit


def infer_usecols(header_cols: Iterable[str]) -> Tuple[List[str], bool]:
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
    addr2_candidates = ["RESIDENTIAL_ADDRESS2", "RESIDENTIAL_SECONDARY_ADDR", "RESIDENTIAL_SECONDARY_ADDRESS"]
    has_addr2 = any(c in cols for c in addr2_candidates)
    for c in addr2_candidates:
        if c in cols:
            usecols.append(c)
    return usecols, has_addr2


def scan_voter_file(
    path: Path,
    *,
    df_city: pd.DataFrame,
    df_zip: pd.DataFrame,
    output_csv: Path,
    chunksize: int,
    encoding: str,
    write_header: bool,
) -> Tuple[int, int, bool]:
    sep = detect_delimiter(path, encoding=encoding)
    header = pd.read_csv(path, nrows=0, encoding=encoding, sep=sep)
    usecols, has_addr2 = infer_usecols(header.columns)

    reader = pd.read_csv(
        path,
        chunksize=chunksize,
        low_memory=False,
        encoding=encoding,
        sep=sep,
        usecols=(usecols or None),
    )

    total_flagged = 0
    total_high_priority = 0
    header_written = not write_header

    for chunk in tqdm(reader, desc=f"Scanning {path.name}"):
        chunk = chunk.reset_index(drop=True).rename(
            columns={
                "RESIDENTIAL_ADDRESS1": "addr1",
                "RESIDENTIAL_ADDRESS2": "addr2",
                "RESIDENTIAL_SECONDARY_ADDR": "addr2",
                "RESIDENTIAL_SECONDARY_ADDRESS": "addr2",
                "RESIDENTIAL_CITY": "city",
                "RESIDENTIAL_ZIP": "zip",
                "SOS_VOTERID": "voter_id",
                "FIRST_NAME": "first_name",
                "LAST_NAME": "last_name",
            }
        )

        if "addr1" not in chunk.columns:
            continue

        addr = chunk["addr1"].fillna("").astype(str)
        if has_addr2 and "addr2" in chunk.columns:
            addr2 = chunk["addr2"].fillna("").astype(str)
            addr = (addr + " " + addr2).str.replace(MULTISPACE_RE, " ", regex=True).str.strip()

        city = chunk.get("city", pd.Series([""] * len(chunk), index=chunk.index)).fillna("").astype(str)
        zip_series = chunk.get("zip", pd.Series([""] * len(chunk), index=chunk.index))

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
                "zip5": zip5,
                "addr_norm": addr_norm,
                "city_norm": city_norm,
                "zip5_key": zip5,
            }
        )

        m_city = base.merge(df_city, on=["addr_norm", "city_norm"], how="left")
        city_hit = m_city["po_name"].notna() & (m_city["po_name"].astype(str) != "")

        m_zip = base.rename(columns={"zip5_key": "zip5"}).merge(df_zip, on=["addr_norm", "zip5"], how="left")
        zip_hit = m_zip["po_name"].notna() & (m_zip["po_name"].astype(str) != "")

        po_name = m_city["po_name"].where(city_hit, m_zip["po_name"])
        po_address = m_city["po_address"].where(city_hit, m_zip["po_address"])
        po_city = m_city["po_city"].where(city_hit, m_zip["po_city"])
        po_zip5 = m_city["po_zip5"].where(city_hit, m_zip["po_zip5"])
        po_lat = m_city["po_lat"].where(city_hit, m_zip["po_lat"])
        po_long = m_city["po_long"].where(city_hit, m_zip["po_long"])

        flag_facility_street_match = city_hit | zip_hit
        flag_po_box_style, flag_commercial_keyword, has_unit = detect_flags(addr)
        flag_any = flag_facility_street_match | flag_po_box_style | flag_commercial_keyword

        match_reason = pd.Series([""] * len(base), index=base.index)
        match_reason = match_reason.where(~city_hit, "facility_street_city")
        match_reason = match_reason.where(~(~city_hit & zip_hit), "facility_street_zip")
        match_reason = match_reason.mask(match_reason.eq("") & flag_po_box_style, "po_box_style")
        match_reason = match_reason.mask(
            match_reason.eq("") & ~flag_po_box_style & flag_commercial_keyword, "commercial_keyword"
        )

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
                "has_unit": has_unit.fillna(False).astype(bool),
            }
        )

        out = out[flag_any].copy()
        if out.empty:
            continue

        total_flagged += len(out)
        total_high_priority += int((~out["has_unit"]).sum())

        output_csv.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(output_csv, index=False, mode="a", header=not header_written)
        header_written = True

    return total_flagged, total_high_priority, header_written


# -----------------------------
# Ohio Votes Count scrape/cache
# -----------------------------

def download_ovc_voter_ids(
    *,
    output_dir: Path,
    url: str,
    force: bool = False,
) -> Set[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    html_cache = output_dir / "ovc_source.html"
    ids_cache = output_dir / "ovc_voter_ids.csv"

    if ids_cache.exists() and not force:
        try:
            cached = pd.read_csv(ids_cache, dtype=str)
            if "voter_id" in cached.columns:
                return set(cached["voter_id"].fillna("").astype(str).str.strip())
        except Exception:
            pass

    if not html_cache.exists() or force:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
        resp.raise_for_status()
        html_cache.write_text(resp.text, encoding="utf-8", errors="ignore")

    html = html_cache.read_text(encoding="utf-8", errors="ignore")
    tables = pd.read_html(html)  # requires lxml

    all_ids: Set[str] = set()
    for t in tables:
        if t.empty:
            continue
        t.columns = [str(c).strip() for c in t.columns]
        lower_cols = {c.lower(): c for c in t.columns}
        candidates = ["sos voter id", "sos_voterid", "voter id", "voter_id", "sos voterid"]

        col = None
        for cand in candidates:
            if cand in lower_cols:
                col = lower_cols[cand]
                break
        if col is None:
            for c in t.columns:
                cl = c.lower()
                if "voter" in cl and "id" in cl:
                    col = c
                    break
        if col is None:
            continue

        ids = t[col].astype(str).str.strip()
        ids = ids[ids.ne("") & ids.ne("nan")]
        all_ids.update(ids.tolist())

    pd.DataFrame({"voter_id": sorted(all_ids)}).to_csv(ids_cache, index=False)
    return all_ids


# -----------------------------
# Map generation
# -----------------------------

def _to_bool_series(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s.fillna(False)
    return (
        s.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "t", "yes", "y"})
    )


def create_map(flagged_csv: Path, output_html: Path, *, ovc_ids: Optional[Set[str]] = None) -> None:
    df = pd.read_csv(flagged_csv, low_memory=False)
    if df.empty:
        raise RuntimeError("flagged_voter_addresses.csv is empty (no flags).")

    for col in ["addr", "city", "zip5", "match_reason"]:
        if col not in df.columns:
            df[col] = ""

    df["flag_facility_street_match"] = _to_bool_series(
        df.get("flag_facility_street_match", pd.Series(False, index=df.index))
    )
    df["flag_po_box_style"] = _to_bool_series(df.get("flag_po_box_style", pd.Series(False, index=df.index)))
    df["flag_commercial_keyword"] = _to_bool_series(
        df.get("flag_commercial_keyword", pd.Series(False, index=df.index))
    )
    df["has_unit"] = _to_bool_series(df.get("has_unit", pd.Series(False, index=df.index)))

    df["po_lat"] = df.get("po_lat", pd.Series([None] * len(df)))
    df["po_long"] = df.get("po_long", pd.Series([None] * len(df)))

    df["voter_id"] = df.get("voter_id", pd.Series([""] * len(df))).fillna("").astype(str).str.strip()
    df["ovc_reported"] = df["voter_id"].isin(ovc_ids) if ovc_ids else False

    coords = df.loc[df["flag_facility_street_match"], ["po_lat", "po_long"]].copy()
    coords["po_lat"] = coords["po_lat"].apply(_safe_float)
    coords["po_long"] = coords["po_long"].apply(_safe_float)
    coords = coords.dropna()
    center = [coords["po_lat"].mean(), coords["po_long"].mean()] if not coords.empty else [40.4173, -82.9071]

    m = folium.Map(location=center, zoom_start=7, tiles="OpenStreetMap")
    fg_review = folium.FeatureGroup(name="Facility match (needs review: no unit)", show=True)
    fg_legit = folium.FeatureGroup(name="Facility match (likely legit: has unit)", show=True)

    added_facility = 0
    skipped_no_coords = 0
    count_po_box_only = 0
    count_keyword_only = 0
    count_ovc_reported = int(df["ovc_reported"].sum())

    state = os.environ.get("POST_OFFICE_STATE", "OH").strip().upper() or "OH"

    for _, row in df.iterrows():
        addr = str(row.get("addr", "")).strip()
        city = str(row.get("city", "")).strip()
        zip5 = str(row.get("zip5", "")).strip()
        voter_query = ", ".join([p for p in [addr, city, state, zip5] if p])
        voter_gmaps = _gmaps_search_url(voter_query or f"{city}, {state}")

        has_unit = bool(row.get("has_unit", False))
        is_facility = bool(row.get("flag_facility_street_match", False))
        is_po_box = bool(row.get("flag_po_box_style", False))
        is_keyword = bool(row.get("flag_commercial_keyword", False))
        on_ovc = bool(row.get("ovc_reported", False))

        voter_id = row.get("voter_id", "N/A")
        name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
        reason = str(row.get("match_reason", "")).strip()

        popup_html = f"""
        <div style="width: 360px; font-family: Arial, sans-serif;">
          <h4 style="margin: 0 0 10px 0;">Flagged voter address</h4>
          <table style="width: 100%; font-size: 12px;">
            <tr><td><b>Voter ID:</b></td><td>{voter_id}</td></tr>
            <tr><td><b>Name:</b></td><td>{name or "N/A"}</td></tr>
            <tr><td><b>Address:</b></td><td>{addr}</td></tr>
            <tr><td><b>City/ZIP:</b></td><td>{city} {zip5}</td></tr>
            <tr><td><b>Has unit/apt:</b></td><td>{"Yes" if has_unit else "No"}</td></tr>
            <tr><td><b>Reason:</b></td><td>{reason or "N/A"}</td></tr>
            <tr><td><b>On Ohio Votes Count:</b></td><td>{"Yes" if on_ovc else "No"}</td></tr>
          </table>
          <hr style="margin: 10px 0;">
          <p style="margin: 6px 0;">
            <a href="{voter_gmaps}" target="_blank">Search voter address in Google Maps</a>
          </p>
        </div>
        """

        if is_facility:
            lat = _safe_float(row.get("po_lat"))
            lon = _safe_float(row.get("po_long"))
            if lat is None or lon is None:
                skipped_no_coords += 1
                continue

            po_name = str(row.get("po_name", "")).strip()
            po_addr = str(row.get("po_address", "")).strip()
            po_city = str(row.get("po_city", "")).strip()
            po_zip = str(row.get("po_zip5", "")).strip()
            po_gmaps = _gmaps_search_url(f"{lat},{lon}")

            popup_html = popup_html.replace(
                "</div>",
                f"""
                <p style="margin: 6px 0;">
                  <a href="{po_gmaps}" target="_blank">Open facility coordinates in Google Maps</a>
                </p>
                <p style="margin: 6px 0; font-size: 11px; color: #666;">
                  <b>Facility:</b> {po_name or "N/A"} — {po_addr}, {po_city} {po_zip}
                </p>
                </div>
                """,
            )

            color = "orange" if has_unit else "red"
            icon = "star" if on_ovc else ("home" if has_unit else "exclamation-sign")
            tooltip = f"{name or voter_id} — {city} ({'has unit' if has_unit else 'no unit'})"

            folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=460),
                icon=folium.Icon(color=color, icon=icon),
                tooltip=tooltip,
            ).add_to(fg_legit if has_unit else fg_review)
            added_facility += 1
        else:
            if is_po_box:
                count_po_box_only += 1
            elif is_keyword:
                count_keyword_only += 1

    fg_review.add_to(m)
    fg_legit.add_to(m)

    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                background: white; padding: 12px; border-radius: 6px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3); font-family: Arial;">
      <h4 style="margin: 0 0 8px 0;">Legend</h4>
      <div style="font-size: 12px; line-height: 1.4;">
        <div><span style="color: red;">&#9679;</span> Facility match — needs review (no unit)</div>
        <div><span style="color: orange;">&#9679;</span> Facility match — likely legit (has unit)</div>
        <div style="margin-top: 6px; color: #666;">
          Star icon: also reported on Ohio Votes Count (if enabled).
        </div>
        <div style="margin-top: 6px; color: #666;">
          PO BOX / keyword-only flags are not mapped without geocoding.
        </div>
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)
    plugins.Fullscreen().add_to(m)

    output_html.parent.mkdir(parents=True, exist_ok=True)
    m.save(str(output_html))

    print("Map created")
    print(f"- Output: {output_html}")
    print(f"- Facility markers added: {added_facility}")
    if skipped_no_coords:
        print(f"- Facility matches missing coords (skipped): {skipped_no_coords}")
    if count_po_box_only or count_keyword_only:
        print(f"- PO BOX-only flags (not mapped): {count_po_box_only}")
        print(f"- Keyword-only flags (not mapped): {count_keyword_only}")
    if ovc_ids is not None:
        print(f"- Flagged records also on Ohio Votes Count: {count_ovc_reported}")


# -----------------------------
# Main
# -----------------------------

def main() -> int:
    os.environ.setdefault("POST_OFFICE_DATA_DIR", "data")
    os.environ.setdefault("POST_OFFICE_OUTPUT_DIR", "output")
    os.environ.setdefault("POST_OFFICE_STATE", "OH")
    os.environ.setdefault("OVC_ENABLE", "1")
    os.environ.setdefault("OVC_URL", DEFAULT_OVC_URL)
    os.environ.setdefault("OVC_FORCE", "0")

    data_dir = Path(os.environ["POST_OFFICE_DATA_DIR"])
    output_dir = Path(os.environ["POST_OFFICE_OUTPUT_DIR"])
    state = os.environ["POST_OFFICE_STATE"].strip().upper() or "OH"
    encoding = "ISO-8859-1"
    chunksize = 100_000

    _print_header("POST OFFICE AUDIT — STANDALONE MASTER PIPELINE")
    print(f"Data dir:   {data_dir.resolve()}")
    print(f"Output dir: {output_dir.resolve()}")
    print(f"State:      {state}")

    data_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    voter_files = [
        p
        for p in sorted(data_dir.glob("SWVF_*"))
        if p.is_file() and p.suffix.lower() in {".csv", ".txt"}
    ]
    if not voter_files:
        print(f"ERROR: no voter files found in {data_dir} matching SWVF_*.txt/.csv", file=sys.stderr)
        return 2

    _print_header("STEP 1: Load/cache USPS facilities")
    usps_cache_csv = data_dir / "usps_facilities.csv"
    df_usps = download_usps_facilities(state, usps_cache_csv, force=False)
    df_city, df_zip = build_reference(df_usps)
    print(f"USPS facilities loaded: {len(df_usps)} (cache: {usps_cache_csv})")

    _print_header("STEP 2: Scan SWVF files")
    flagged_csv = output_dir / "flagged_voter_addresses.csv"
    if flagged_csv.exists():
        flagged_csv.unlink()

    total_flagged = 0
    total_high_priority = 0
    header_needed = True

    print(f"Scanning {len(voter_files)} voter files in {data_dir}...")
    for vf in voter_files:
        flagged, high_priority, header_written = scan_voter_file(
            vf,
            df_city=df_city,
            df_zip=df_zip,
            output_csv=flagged_csv,
            chunksize=chunksize,
            encoding=encoding,
            write_header=header_needed,
        )
        total_flagged += flagged
        total_high_priority += high_priority
        header_needed = not header_written

    print("\nAudit complete")
    print(f"- Output: {flagged_csv}")
    print(f"- Total flags: {total_flagged}")
    print(f"- High priority (no unit): {total_high_priority}")

    if not flagged_csv.exists():
        print("ERROR: flagged output file was not created.", file=sys.stderr)
        return 2

    _print_header("STEP 3: Ohio Votes Count (optional)")
    ovc_ids: Optional[Set[str]] = None
    if _bool_env("OVC_ENABLE", True):
        try:
            ovc_ids = download_ovc_voter_ids(
                output_dir=output_dir,
                url=os.environ.get("OVC_URL", DEFAULT_OVC_URL),
                force=_bool_env("OVC_FORCE", False),
            )
            print(f"Ohio Votes Count IDs loaded: {len(ovc_ids)}")
        except Exception as e:
            print(f"WARNING: OVC download/parse failed; continuing without comparison: {e}")
            ovc_ids = None
    else:
        print("OVC disabled; skipping.")

    _print_header("STEP 4: Generate interactive map")
    map_html = output_dir / "flagged_addresses_map.html"
    try:
        create_map(flagged_csv, map_html, ovc_ids=ovc_ids)
    except Exception as e:
        print(f"WARNING: map generation failed: {e}")
        return 0

    _print_header("DONE")
    print("Outputs:")
    print(f"- {flagged_csv}")
    print(f"- {map_html}")
    if ovc_ids is not None:
        print(f"- {output_dir / 'ovc_voter_ids.csv'}")
        print(f"- {output_dir / 'ovc_source.html'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

