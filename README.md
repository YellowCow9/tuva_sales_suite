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

## Contact
For questions or support, please contact aryanthakur0319@gmail.com!
