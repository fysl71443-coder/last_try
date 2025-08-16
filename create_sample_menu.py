from app import app, db
from models import MenuSection, MenuSectionItem, Meal

BRANCHES = ['place_india', 'china_town']

SECTIONS_BY_BRANCH = {
    'place_india': [
        {'name': 'Appetizers', 'order': 1, 'image_url': '/static/img/item-placeholder.svg'},
        {'name': 'Chicken', 'order': 2, 'image_url': '/static/img/item-placeholder.svg'},
        {'name': 'Rice & Biryani', 'order': 3, 'image_url': '/static/img/item-placeholder.svg'},
    ],
    'china_town': [
        {'name': 'Soups', 'order': 1, 'image_url': '/static/img/item-placeholder.svg'},
        {'name': 'Noodles & Chopsuey', 'order': 2, 'image_url': '/static/img/item-placeholder.svg'},
        {'name': 'House Special', 'order': 3, 'image_url': '/static/img/item-placeholder.svg'},
    ],
}

# Sample price overrides per index to demonstrate effect
PRICE_OVERRIDES = [None, 12.00, 18.50, None, 24.00]


def ensure_sample_meals(min_count=10):
    """Ensure there are at least min_count active meals to bind in menu items.
    Uses an existing user as owner; if none exists, skips creating meals.
    """
    created = 0
    meals = Meal.query.filter_by(active=True).all()
    if len(meals) >= min_count:
        return meals, created
    # Find any existing user to attribute meals to
    try:
        from models import User
        u = User.query.first()
        user_id = u.id if u else None
    except Exception:
        user_id = None
    if not user_id:
        # No user available; do not create meals
        return meals, created
    # Create additional simple meals
    base_idx = len(meals) + 1
    for i in range(base_idx, min_count + 1):
        m = Meal(name=f'Sample Meal {i}', name_ar=f'وجبة {i}', description='Sample',
                 category='General', total_cost=5.0, profit_margin_percent=30,
                 selling_price=10.0 + i, active=True, user_id=user_id)
        db.session.add(m)
        created += 1
    if created:
        db.session.commit()
    return Meal.query.filter_by(active=True).all(), created


def run():
    with app.app_context():
        meals, created_meals = ensure_sample_meals()
        print(f"Existing active meals: {len(meals)} (created {created_meals} new)")

        total_sections_added = 0
        total_items_added = 0

        for branch in BRANCHES:
            sections_conf = SECTIONS_BY_BRANCH.get(branch, [])
            for sc in sections_conf:
                # Idempotent section insert
                sec = (MenuSection.query
                       .filter_by(name=sc['name'], branch=branch)
                       .first())
                if not sec:
                    sec = MenuSection(name=sc['name'], branch=branch,
                                      display_order=sc['order'], image_url=sc['image_url'])
                    db.session.add(sec)
                    db.session.flush()
                    total_sections_added += 1

                # Attach first 5 meals as sample items (idempotent per meal)
                for idx, meal in enumerate(meals[:5], start=0):
                    exists = (MenuSectionItem.query
                              .filter_by(section_id=sec.id, meal_id=meal.id)
                              .first())
                    if exists:
                        continue
                    price_override = PRICE_OVERRIDES[idx] if idx < len(PRICE_OVERRIDES) else None
                    item = MenuSectionItem(section_id=sec.id, meal_id=meal.id,
                                            display_order=idx,
                                            price_override=price_override,
                                            image_url='/static/img/item-placeholder.svg')
                    db.session.add(item)
                    total_items_added += 1

        db.session.commit()
        print(f"Seed done. Added sections: {total_sections_added}, items: {total_items_added}")


if __name__ == '__main__':
    run()

