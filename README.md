# Tuva Tool

## Overview
Tuva Tool is a Python-based utility for ingesting, processing, and analyzing NIH grant and lead data. It provides two main functionalities:

1. **Lead Generation for New Prospects:**
   - Filters professors who have recently been awarded an R1 grant.
   - Matches their research interests with Tuva's current target areas.
   - Generates a curated list of potential leads for outreach.

2. **Grant Matching for Existing Clients:**
   - Uses recently funded projects or publication abstracts from current Tuva clients.
   - Identifies suitable grant opportunities for these clients.
   - Calculates a 'similarity score' between new grants and those previously won by the client, aiding targeted recommendations.

These functionalities streamline the workflow for extracting, embedding, matching, and formatting research opportunities and principal investigator profiles, supporting sales and research teams in identifying relevant leads and grant matches.

## Features
- **Lead Filtering:** Identifies professors with recent R1 grants and matches their interests to Tuva's targets.
- **Client Grant Matching:** Finds suitable grants for existing clients based on their recent projects or publication abstracts, with similarity scoring.
- **Data Ingestion:** Imports NIH leads and open opportunities from CSV and text files.
- **Profile Management:** Organizes PI profiles and abstracts for targeted analysis.
- **Grant Matching:** Automated matching of grants to PI profiles using embeddings and custom logic.
- **Formatting & Output:** Converts results to structured JSON, ready for downstream applications.
- **Embedding & Analysis:** Supports embedding grant data for similarity search and lead identification.

## Directory Structure
- `data/` — Raw and processed data files, including CSVs and PI profile abstracts.
- `output/` — Generated JSON schemas and formatted results.
- `scripts/` — Python scripts for ingestion, embedding, matching, formatting, and utility operations.
- `tuva_env/` — Python virtual environment and dependencies.

## Key Scripts
- `ingest_nih.py` — Main entry for ingesting NIH data.
- `scripts/embed_grants.py` — Embeds grant data for similarity analysis.
- `scripts/fetch_pi_history.py` — Retrieves PI history.
- `scripts/find_open_grants.py` — Identifies open grant opportunities.
- `scripts/format_json.py` — Formats results into JSON.
- `scripts/match_grants.py` — Matches grants to PI profiles.

## Setup
1. **Clone the repository:**
   ```bash
   git clone <repo-url>
   cd tuva_tool
   ```
2. **Create and activate the Python environment:**
   ```bash
   python3 -m venv tuva_env
   source tuva_env/bin/activate
   ```
3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage
Run scripts as needed, for example:
```bash
python scripts/format_json.py
```

### Lead Generation
To generate a list of leads (professors with recent R1 grants matching Tuva's targets), use the relevant ingestion and filtering scripts.

### Grant Matching for Clients
To generate suitable grant recommendations for existing clients, use their recent project abstracts or publication data as input. The tool will output grants with similarity scores to those previously won.

## Data Sources
- NIH leads and opportunities (CSV, TXT)
- PI profile abstracts (TXT)

## Output
- Curated lead lists for new prospects.
- Grant recommendations with similarity scores for existing clients.
- JSON schemas and formatted results for integration with sales tools or analytics platforms.

## License
[MIT License](LICENSE)

## Contact
For questions or support, contact the repository maintainer.
