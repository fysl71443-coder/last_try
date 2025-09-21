#!/usr/bin/env python3
"""
Utility: Delete the legacy 'Meals' (or 'MEALS') menu category and its items from the simplified menu models.
- Works with the blueprint app factory in app/__init__.py
- Targets app.models.MenuCategory and app.models.MenuItem

Run:
  python scripts/delete_meals_category.py
"""
import sys
from sqlalchemy import or_, func

from app import create_app
from extensions import db


def main():
    app = create_app()
    with app.app_context():
        # Lazy import to ensure db is bound
        from app.models import MenuCategory, MenuItem

        # Find categories named 'Meals' (any case, strip spaces)
        targets = (
            db.session.query(MenuCategory)
            .filter(func.lower(func.trim(MenuCategory.name)).in_(['meals']))
            .all()
        )
        if not targets:
            print("No 'Meals' category found. Nothing to delete.")
            return 0

        deleted_items = 0
        deleted_cats = 0
        for cat in targets:
            # Delete items in this category
            items = db.session.query(MenuItem).filter_by(category_id=cat.id).all()
            for it in items:
                db.session.delete(it)
                deleted_items += 1
            # Delete category itself
            db.session.delete(cat)
            deleted_cats += 1
        db.session.commit()
        print(f"Deleted {deleted_items} menu items and {deleted_cats} 'Meals' category record(s).")
        return 0


if __name__ == '__main__':
    raise SystemExit(main())

