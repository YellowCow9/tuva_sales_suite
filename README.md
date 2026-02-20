# Tuva Sales Suite
The Tuva Sales Suite is a Python-based utility for ingesting, processing, and analyzing NIH grant and lead data. It provides two main functionalities:

1. **Lead Generation for New Prospects:**
   - Filters professors who have recently (within the last 90 days) been awarded an R1 grant.
   - Matches their research interests with Tuva's current target areas (computational science).
   - Generates a curated list of potential leads for outreach.

2. **Grant Matching for Existing Clients:**
   - Uses recently funded projects or publication abstracts from current Tuva clients.
   - Identifies suitable grant opportunities for these clients.
   - Calculates a ML-based 'similarity score' between new grants and those previously won by the client, aiding targeted recommendations.


## Features
- **Lead Filtering:** Identifies professors with recent R1 grants and matches their interests to Tuva's targets.
- **Client Grant Matching:** Finds suitable grants for existing clients based on their recent projects or publication abstracts, with similarity scoring.
- **Data Ingestion:** Imports NIH leads and open opportunities from CSV and text files.
- **Profile Management:** Organizes PI profiles and abstracts for targeted analysis.
- **Grant Matching:** Automated matching of grants to PI profiles using embeddings and custom logic.
- **Formatting & Output:** Converts results to structured JSON, ready for downstream applications.
- **Embedding & Analysis:** Supports embedding grant data for similarity search and lead identification.

## Technical Architecture
### 1. Lead Generation for New Prospects
- **Data Ingestion:** Automated scripts pull and parse NIH grant data (CSV, TXT) and PI profiles. Data sources can be extended to other APIs or institutional feeds as needed.
- **Filtering & Matching:** Logic filters for professors recently awarded R1 grants, then matches their research interests (using keyword and embedding-based approaches) to Tuva’s current target areas.
- **Output:** Results are formatted as JSON/CSV for integration with sales tools or analytics platforms.

### 2. Grant Matching for Existing Clients
- **Client Data Ingestion:** Ingests recently funded project abstracts or publication data for each client (optionally via APIs or manual upload).
- **Embedding & Similarity Scoring:** Uses ML models to embed both client and grant abstracts. Computes cosine-similarity scores to identify the best grant matches for each client.
- **Grant Opportunity Discovery:** Integrates with NIH and other grant APIs to fetch open opportunities.
- **Output:** Produces a ranked list of suitable grants with similarity scores, exportable as JSON/xlsx.

## Project Structure & Key Components

- **data/**: Raw and processed data files (NIH grants, PI profiles, client/project abstracts).
- **output/**: Results and reports (JSON, CSV) for integration or review.
- **scripts/**: Modular Python scripts for data ingestion, filtering, embedding, matching, and formatting, organized by the two core functionalities.
   - Recently Funded Professors: Ingests and formats new R1 grant awardees.
   - Grant Matching for Clients: Embeds, matches, and ranks grants for existing clients.
- **tuva_env/**: Python virtual environment and dependencies.


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
python main.py
```

## Contact
For questions or support, please contact aryanthakur0319@gmail.com!
