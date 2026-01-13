from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote_plus

import pandas as pd
import folium
from folium import plugins


def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name, "").strip()
    return Path(val) if val else default


def load_paths() -> Tuple[Path, Path]:
    data_dir = _env_path("POST_OFFICE_DATA_DIR", Path("data"))
    output_dir = _env_path("POST_OFFICE_OUTPUT_DIR", Path("output"))
    return data_dir, output_dir


def _to_bool_series(s: pd.Series) -> pd.Series:
    """
    Robustly interpret bool-ish columns that may be True/False or 0/1 or 'True'/'False'.
    """
    if s.dtype == bool:
        return s.fillna(False)
    # Common CSV cases: "True"/"False", "0"/"1", empty
    return (
        s.fillna(False)
        .astype(str)
        .str.strip()
        .str.lower()
        .isin({"true", "1", "t", "yes", "y"})
    )


def _safe_float(x) -> Optional[float]:
    try:
        if pd.isna(x):
            return None
        return float(x)
    except Exception:
        return None


def _gmaps_search_url(query: str) -> str:
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"


def create_map() -> Path:
    data_dir, output_dir = load_paths()
    output_dir.mkdir(parents=True, exist_ok=True)

    flagged_path = output_dir / "flagged_voter_addresses.csv"
    if not flagged_path.exists():
        raise FileNotFoundError(f"Missing flagged file: {flagged_path}")

    df = pd.read_csv(flagged_path, low_memory=False)
    if df.empty:
        raise RuntimeError("flagged_voter_addresses.csv is empty (no flags).")

    # Normalize expected columns
    for col in ["addr", "city", "zip5", "match_reason"]:
        if col not in df.columns:
            df[col] = ""

    df["flag_facility_street_match"] = _to_bool_series(df.get("flag_facility_street_match", pd.Series(False, index=df.index)))
    df["flag_po_box_style"] = _to_bool_series(df.get("flag_po_box_style", pd.Series(False, index=df.index)))
    df["flag_commercial_keyword"] = _to_bool_series(df.get("flag_commercial_keyword", pd.Series(False, index=df.index)))
    df["has_unit"] = _to_bool_series(df.get("has_unit", pd.Series(False, index=df.index)))

    df["po_lat"] = df.get("po_lat", pd.Series([None] * len(df)))
    df["po_long"] = df.get("po_long", pd.Series([None] * len(df)))

    # Center map on available facility coords; otherwise default Ohio center.
    coords = df.loc[df["flag_facility_street_match"], ["po_lat", "po_long"]].copy()
    coords["po_lat"] = coords["po_lat"].apply(_safe_float)
    coords["po_long"] = coords["po_long"].apply(_safe_float)
    coords = coords.dropna()

    if not coords.empty:
        center = [coords["po_lat"].mean(), coords["po_long"].mean()]
        zoom = 7
    else:
        center = [40.4173, -82.9071]
        zoom = 7

    m = folium.Map(location=center, zoom_start=zoom, tiles="OpenStreetMap")

    # Layer groups (we only plot records with facility coordinates).
    fg_review = folium.FeatureGroup(name="Facility match (needs review: no unit)", show=True)
    fg_legit = folium.FeatureGroup(name="Facility match (likely legit: has unit)", show=True)

    # Cluster facility markers (keeps map responsive for large result sets).
    cluster_review = plugins.MarkerCluster(name="Cluster: needs review")
    cluster_legit = plugins.MarkerCluster(name="Cluster: likely legit")
    cluster_review.add_to(fg_review)
    cluster_legit.add_to(fg_legit)

    # Stats
    added_facility = 0
    skipped_no_coords = 0
    count_po_box_only = 0
    count_keyword_only = 0

    for _, row in df.iterrows():
        addr = str(row.get("addr", "")).strip()
        city = str(row.get("city", "")).strip()
        zip5 = str(row.get("zip5", "")).strip()
        state = os.environ.get("POST_OFFICE_STATE", "OH").strip().upper() or "OH"

        voter_query = ", ".join([p for p in [addr, city, state, zip5] if p])
        voter_gmaps = _gmaps_search_url(voter_query or f"{city}, {state}")

        has_unit = bool(row.get("has_unit", False))
        is_facility = bool(row.get("flag_facility_street_match", False))
        is_po_box = bool(row.get("flag_po_box_style", False))
        is_keyword = bool(row.get("flag_commercial_keyword", False))

        voter_id = row.get("voter_id", "N/A")
        name = f"{row.get('first_name', '')} {row.get('last_name', '')}".strip()
        reason = str(row.get("match_reason", "")).strip()

        # Build popup with Google Maps links.
        popup_html = f"""
        <div style="width: 340px; font-family: Arial, sans-serif;">
          <h4 style="margin: 0 0 10px 0;">Flagged voter address</h4>
          <table style="width: 100%; font-size: 12px;">
            <tr><td><b>Voter ID:</b></td><td>{voter_id}</td></tr>
            <tr><td><b>Name:</b></td><td>{name or "N/A"}</td></tr>
            <tr><td><b>Address:</b></td><td>{addr}</td></tr>
            <tr><td><b>City/ZIP:</b></td><td>{city} {zip5}</td></tr>
            <tr><td><b>Has unit/apt:</b></td><td>{"Yes" if has_unit else "No"}</td></tr>
            <tr><td><b>Reason:</b></td><td>{reason or "N/A"}</td></tr>
            <tr><td><b>Flags:</b></td><td>
              {"Facility" if is_facility else ""}{"; " if is_facility and (is_po_box or is_keyword) else ""}
              {"PO BOX" if is_po_box else ""}{"; " if is_po_box and is_keyword else ""}
              {"Keyword" if is_keyword else ""}
            </td></tr>
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
            po_query = ", ".join([p for p in [po_name or po_addr, po_city, state, po_zip] if p])
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
            icon = "home" if has_unit else "exclamation-sign"
            tooltip = f"{name or voter_id} — {city} ({'has unit' if has_unit else 'no unit'})"

            marker = folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=420),
                icon=folium.Icon(color=color, icon=icon),
                tooltip=tooltip,
            )
            marker.add_to(cluster_legit if has_unit else cluster_review)
            added_facility += 1
        else:
            # PO BOX / keyword-only records typically do not have coordinates without geocoding.
            if is_po_box:
                count_po_box_only += 1
            elif is_keyword:
                count_keyword_only += 1

    fg_review.add_to(m)
    fg_legit.add_to(m)

    # Legend
    legend_html = """
    <div style="position: fixed; bottom: 50px; left: 50px; z-index: 1000;
                background: white; padding: 12px; border-radius: 6px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.3); font-family: Arial;">
      <h4 style="margin: 0 0 8px 0;">Legend</h4>
      <div style="font-size: 12px; line-height: 1.4;">
        <div><span style="color: red;">&#9679;</span> Facility match — needs review (no unit)</div>
        <div><span style="color: orange;">&#9679;</span> Facility match — likely legit (has unit)</div>
        <div style="margin-top: 6px; color: #666;">
          PO BOX / keyword-only flags are reported in the console (not mapped) unless you add geocoding.
        </div>
      </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(legend_html))

    folium.LayerControl(collapsed=False).add_to(m)
    plugins.Fullscreen().add_to(m)

    out_path = output_dir / "flagged_addresses_map.html"
    m.save(str(out_path))

    print("Map created")
    print(f"- Output: {out_path}")
    print(f"- Facility markers added: {added_facility}")
    if skipped_no_coords:
        print(f"- Facility matches missing coords (skipped): {skipped_no_coords}")
    if count_po_box_only or count_keyword_only:
        print(f"- PO BOX-only flags (not mapped): {count_po_box_only}")
        print(f"- Keyword-only flags (not mapped): {count_keyword_only}")
    return out_path


if __name__ == "__main__":
    create_map()

