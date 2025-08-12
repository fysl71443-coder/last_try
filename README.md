# Flask Accounting App - Login Screen

This repo contains a starter Flask app implementing a bilingual (Arabic/English) login screen using PostgreSQL.

## Quick start (local)
1. Copy `.env.example` to `.env` and update values.
2. Create a Python venv and install dependencies: `python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt`
3. Create the Postgres DB and set `DATABASE_URL`.
4. Initialize DB and migrations:
   - `flask db init`
   - `flask db migrate -m "init"`
   - `flask db upgrade`
5. Run app: `flask run --host=0.0.0.0 --port=8000`

## Notes
- Use Render's PostgreSQL add-on and set `DATABASE_URL` in Render environment variables.
- For production, change `SECRET_KEY` and enable HTTPS.
# RESTAURANT-SYSTEM
