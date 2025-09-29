from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    engine = db.engine
    dialect = engine.dialect.name
    print("Dialect:", dialect)

    existing = set()
    try:
        if dialect == 'sqlite':
            res = db.session.execute(text("PRAGMA table_info(settings)"))
            existing = {row[1] for row in res.fetchall()}
        else:
            res = db.session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='settings'"))
            existing = {row[0] for row in res.fetchall()}
    except Exception as e:
        print("Error checking existing columns:", e)
        raise

    print("Existing settings columns:", len(existing))

    targets = [
        ("china_town_phone1", "VARCHAR(50)"),
        ("china_town_phone2", "VARCHAR(50)"),
        ("place_india_phone1", "VARCHAR(50)"),
        ("place_india_phone2", "VARCHAR(50)")
    ]

    added = 0
    for name, coltype in targets:
        if name in existing:
            print("Exists:", name)
            continue
        try:
            db.session.execute(text(f"ALTER TABLE settings ADD COLUMN {name} {coltype}"))
            print("Added:", name)
            added += 1
        except Exception as e:
            print("Failed to add", name, "error:", e)
    db.session.commit()
    print("Done. Added", added, "column(s).")
