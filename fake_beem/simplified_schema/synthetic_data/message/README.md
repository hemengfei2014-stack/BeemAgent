# Message System Synthetic Data

This directory contains synthetic data for the Message System (IM), generated based on the schema definitions.

## Directory Structure

- `data/`: Contains the generated data files (TSV format).
  - `ods_im_message_min.txt`: Message details.
  - `ods_im_session_participant_min.txt`: Session participants.
- `scripts/`: Contains Python scripts for data generation and processing.
  - `generate_message_data.py`: Script to generate synthetic message data.
  - `convert_data_to_json.py`: Script to convert TSV data to JSON for web visualization.
  - `validate_message_data.py`: Script to validate data schema and logic.
- `web/`: Contains a simple web interface to visualize the message data.

## Usage

### 1. Generate Data

Run the generation script to create new data in `data/`:

```bash
python3 scripts/generate_message_data.py
```

### 2. Validate Data

Run the validation script to ensure data integrity:

```bash
python3 scripts/validate_message_data.py
```

### 3. Web Visualization

To view the data in a web interface:

1.  Convert the data to JSON:
    ```bash
    python3 scripts/convert_data_to_json.py
    ```
2.  Start the web server (port 8082):
    ```bash
    cd web
    python3 -m http.server 8082
    ```
3.  Access `http://localhost:8082` in your browser.
