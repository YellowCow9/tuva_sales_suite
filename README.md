# Tuva Sales Suite
The Tuva Sales Suite is a Python-based utility for ingesting, processing, and analyzing governmental grant data. It provides two main functionalities:

1. **Lead Generation for Prospective Customers:**
   - Aggregates professors who have been awarded an R1 grant within the last 90 days.
   - Matches their research interests with Tuva's current target area — computational science.
   - Generates a curated list of potential leads for outreach.

2. **Grant Matching for Existing Clients:**
   - Uses recently funded NIH/NSF projects or publication abstracts for specified researchers.
   - Identifies suitable grant opportunities for these researchers.
   - Calculates a ML-based 'similarity score' between open grants and those previously won by the client, aiding targeted recommendations.

## Project Structure & Key Components
- **data/**: Raw and processed data files (NIH grants, PI profiles, client/project abstracts).
- **output/**: Results and reports (JSON, CSV) for integration or review.
- **scripts/**: Modular Python scripts for data ingestion, filtering, embedding, matching, and formatting, organized by the two core functionalities.
   - Recently Funded Professors: Ingests and formats new R1 grant awardees.
   - Grant Matching for Clients: Embeds, matches, and ranks grants for existing clients.
- **tuva_env/**: Python virtual environment and dependencies.

## Running the App

Always launch the app using the project virtualenv wrapper to avoid environment conflicts:

```bash
bash run.sh
```

This is equivalent to `tuva_env/bin/python -m streamlit run app.py` and ensures the correct pinned dependencies in `tuva_env/` are used instead of any system-level Anaconda install.

**Do not** use a bare `streamlit run app.py` — this resolves to the system Anaconda `streamlit` binary, which uses incompatible package versions and will crash on import.

### First-time setup

If you haven't installed dependencies into the virtualenv yet, run once from the `tuva_tool/` directory:

```bash
tuva_env/bin/pip install -r requirements.txt
```

Then start the app with `bash run.sh`.

## Contact
For questions or support, please contact aryanthakur0319@gmail.com!
