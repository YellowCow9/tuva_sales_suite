#!/bin/bash
# Run the Tuva Grant Radar app using the project virtualenv.
# Usage: bash run.sh
set -e
cd "$(dirname "$0")"
tuva_env/bin/python -m streamlit run app.py "$@"
