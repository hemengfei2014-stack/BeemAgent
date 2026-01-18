# Doc System Synthetic Data

This directory contains synthetic data for the Doc System, generated based on the schema definitions.

## Directory Structure

- `data/`: Contains the generated data files (TSV format).
  - `ods_docs_min.txt`: Document metadata.
  - `dwd_user_doc_access_min.txt`: User document access permissions.
- `scripts/`: Contains Python scripts for data generation and processing.
  - `generate_doc_data.py`: Script to generate synthetic doc data.
  - `convert_data_to_json.py`: Script to convert TSV data to JSON for web visualization.
  - `validate_doc_data.py`: Script to validate data schema and logic.
- `web/`: Contains a simple web interface to visualize the doc data.

## Usage

### 1. Generate Data

Run the generation script to create new data in `data/`:

```bash
python3 scripts/generate_doc_data.py
```

### 2. Validate Data

Run the validation script to ensure data integrity:

```bash
python3 scripts/validate_doc_data.py
```

The validation script checks:
- Schema completeness (required fields).
- Foreign key constraints (Org, User references).
- Business rules (Tenant isolation, Owner access, Valid content types).

### 3. Web Visualization

To view the data in a web interface:

1.  Convert the data to JSON:
    ```bash
    python3 scripts/convert_data_to_json.py
    ```
2.  Start the web server (port 8083):
    ```bash
    cd web
    python3 -m http.server 8083
    ```
3.  Access `http://localhost:8083` in your browser.
