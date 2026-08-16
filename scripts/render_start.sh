#!/bin/sh
# Render's dockerCommand doesn't reliably shell-parse an inline "a && b && c"
# string (quoting gets lost), so the multi-step start sequence lives here
# instead -- see render.yaml.
set -e
alembic upgrade head
python scripts/seed_demo.py
exec uvicorn wildfirewatch.api.main:app --host 0.0.0.0 --port 8000
