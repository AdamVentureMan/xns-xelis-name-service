## Post Office / Commercial Address Audit (Ohio SWVF)

This folder contains a **single-file** pipeline:

- Download/cache **USPS Facilities** for a state (default: **OH**) with **lat/long**.
- Scan one or more Ohio SWVF voter files (`SWVF_*.txt` or `SWVF_*.csv`) in **chunks**.
- Flag records that match:
  - **Facility street address** (exact normalized address + city, or address + ZIP5 fallback)
  - **PO BOX–style addresses** (won’t usually match facility street address; flagged separately)
  - **Commercial mail keywords** (PMB/UPS Store/Mail Center/USPS/Post Office, etc.)
- Produce output usable for both:
  - **Auditing** (OVC overlap reports)
  - **Mapping** (facility coords + optional geocoding)

### Requirements

Install dependencies (recommended in a virtualenv):

```bash
python -m pip install -r post_office_audit/requirements.txt
```

### Run

Run the single master script (no args). It looks for voter files under `./data` and writes outputs under `./output`:

```bash
python post_office_audit/master_pipeline_standalone.py
```

### Notes

- The master script downloads Ohio Votes Count IDs (default enabled) and writes overlap CSVs.
- Geocoding is **enabled by default** for mapping keyword-only and OVC voter addresses. Results are cached under `output/geocode_cache.csv`.

You can override paths via environment variables:

- `POST_OFFICE_DATA_DIR`: folder containing `SWVF_*.txt`/`SWVF_*.csv` and where USPS cache will be stored
- `POST_OFFICE_OUTPUT_DIR`: folder where results will be written
- `POST_OFFICE_STATE`: 2-letter state code (default `OH`)

Example:

```bash
POST_OFFICE_DATA_DIR="/path/to/data" POST_OFFICE_OUTPUT_DIR="/path/to/output" python post_office_audit/master_pipeline_standalone.py
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

