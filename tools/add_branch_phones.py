from app import create_app
from extensions import db
from sqlalchemy import text

app = create_app()

with app.app_context():
    engine = db.engine
    dialect = engine.dialect.name
    print(f"Dialect: {dialect}")

    # Determine existing columns
    existing = set()
    try:
        if dialect == 'sqlite':
            res = engine.execute(text("PRAGMA table_info(settings)"))
            existing = {row[1] for row in res}
        else:
            res = engine.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='settings'"))
            existing = {row[0] for row in res}
    except Exception as e:
        print(f"❌ Error checking existing columns: {e}")
        raise

    print("Existing settings columns count:", len(existing))

    targets = [
        ("china_town_phone1", "VARCHAR(50)"),
        ("china_town_phone2", "VARCHAR(50)"),
        ("place_india_phone1", "VARCHAR(50)"),
        ("place_india_phone2", "VARCHAR(50)"),
    ]

    added = 0
    for name, coltype in targets:
        if name in existing:
            print(f"✅ Exists: {name}")
            continue
        try:
            engine.execute(text(f"ALTER TABLE settings ADD COLUMN {name} {coltype}"))
            print(f"✅ Added: {name}")
            added += 1
        except Exception as e:
            print(f"⚠️ Failed to add {name}: {e}")
    print(f"Done. Added {added} column(s).")
