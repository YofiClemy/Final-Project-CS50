# PlantWeb

Track your houseplants and never miss a watering.

## How to run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export SECRET_KEY="change-me"
sqlite3 database.db < schema.sql
flask --app app run  # or: gunicorn -c gunicorn_config.py app:app
