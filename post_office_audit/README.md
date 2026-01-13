## Post Office / Commercial Address Audit (Ohio SWVF)

This folder contains a **standalone** pipeline to:

- Download/cache **USPS Facilities** for a state (default: **OH**) with **lat/long**.
- Scan one or more Ohio SWVF voter files (`SWVF_*.txt` or `SWVF_*.csv`) in **chunks**.
- Flag records that match:
  - **Facility street address** (exact normalized address + city, or address + ZIP5 fallback)
  - **PO BOX–style addresses** (won’t usually match facility street address; flagged separately)
  - **Commercial mail keywords** (PMB/UPS Store/Mail Center/USPS/Post Office, etc.)
- Produce output usable for both:
  - **Auditing** (clear `match_reason`, booleans for each flag)
  - **Mapping** (facility `po_lat`/`po_long` when a facility match exists)

### Requirements

Install dependencies (recommended in a virtualenv):

```bash
python -m pip install -r post_office_audit/requirements.txt
```

### Run

By default, the script looks for voter files under `./data` and writes outputs under `./output`:

```bash
python post_office_audit/audit.py
```

### Create an interactive map (HTML)

This uses the facility coordinates already written into `output/flagged_voter_addresses.csv`.

```bash
python post_office_audit/map_flagged.py
```

It writes: `output/flagged_addresses_map.html`

Note: **PO BOX / keyword-only** flags typically have no coordinates without geocoding, so they are **not mapped** (but are counted in the console output and still have Google Maps search links in the CSV).

### Ohio Votes Count comparison (download + map annotation)

By default, the map script will also download the Ohio Votes Count page and extract voter IDs from its HTML tables, then annotate each flagged record with `On Ohio Votes Count: Yes/No` in the popup (and use a **star** icon when `Yes`).

Controls:

- `OVC_ENABLE=0`: disable download/compare
- `OVC_FORCE=1`: force re-download (refresh cache)
- `OVC_URL=...`: override the page URL

### Standalone Ohio Votes Count scraper

If you just want to download/parse the site and save the extracted voter IDs (without generating a map):

```bash
python post_office_audit/ovc_scrape.py
```

Outputs:

- `output/ovc_voter_ids.csv`
- `output/ovc_tables_combined.csv` (all tables concatenated, when present)
- `output/ovc_source.html` (cached page HTML)

You can override paths via environment variables:

- `POST_OFFICE_DATA_DIR`: folder containing `SWVF_*.txt`/`SWVF_*.csv` and where USPS cache will be stored
- `POST_OFFICE_OUTPUT_DIR`: folder where results will be written
- `POST_OFFICE_STATE`: 2-letter state code (default `OH`)

Example:

```bash
POST_OFFICE_DATA_DIR="/path/to/data" POST_OFFICE_OUTPUT_DIR="/path/to/output" python post_office_audit/audit.py
```

### Outputs

The script writes:

- `flagged_voter_addresses.csv`: all flagged records (streamed as chunks are processed)

Key columns include:

- `flag_facility_street_match` (bool): matched a USPS facility street address
- `flag_po_box_style` (bool): PO BOX style detected (may not have facility coords)
- `flag_commercial_keyword` (bool): commercial mail keyword detected
- `match_reason` (string): `facility_street_city`, `facility_street_zip`, `po_box_style`, `commercial_keyword`, or combinations
- `po_name`, `po_address`, `po_city`, `po_zip5`, `po_lat`, `po_long`: facility info (present when facility match exists)

