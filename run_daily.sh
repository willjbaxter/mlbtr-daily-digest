#!/bin/zsh
# Wrapper to run the daily MLBTR summary with environment variables loaded.

cd "$(dirname "$0")"          # switch to project directory
source .env                      # load GEMINI_API_KEY (or others)
exec .venv/bin/python3 mlbtr_daily_summary.py --out ./out 