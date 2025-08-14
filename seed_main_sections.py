from app import app, db
from models import MenuSection

SECTIONS = [
    'مقبلات - Appetizers',
    'الشوربات - Soups',
    'السلطات - Salads',
    'مخصوص للبيت - House Special',
    'روبيان - Prawns',
    'مأكولات بحرية - Seafoods',
    'طبق ساخن - Chinese Sizzling',
    'شو فاو - Shaw Faw',
    'الدجاج - Chicken',
    'لحوم بقر وخروف - Beef & Lamb',
    'أرز & برياني - Rice & Biryani',
    'ماكارونا - Noodles & Chopsuey',
    'مشوية - Charcoal Grill / Kebabs',
    'دجاج هندي - Indian Delicacy (Chicken)',
    'سمك هندي - Indian Delicacy (Fish)',
    'خضروات هندية - Indian Delicacy (Vegetables)',
    'العصائر - Juices',
    'المشروبات & حلويات - Soft Drink',
]


def run(seed_branch=None):
    # seed_branch=None => تظهر في جميع الفروع (POS يقرأ branch==None أو يطابق الفرع)
    with app.app_context():
        added = 0
        for idx, name in enumerate(SECTIONS):
            q = MenuSection.query.filter(MenuSection.name==name)
            if seed_branch is None:
                q = q.filter(MenuSection.branch==None)  # noqa: E711
            else:
                q = q.filter(MenuSection.branch==seed_branch)
            ex = q.first()
            if not ex:
                db.session.add(MenuSection(
                    name=name,
                    branch=seed_branch,
                    display_order=idx,
                    image_url=None,
                ))
                added += 1
        db.session.commit()
        total = MenuSection.query.count()
        print(f"Seed complete. Added={added}, Total sections now={total}")


if __name__ == '__main__':
    # أدخل None لتكون عامة لكل الفروع
    run(seed_branch=None)

