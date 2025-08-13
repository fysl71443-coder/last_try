from app import app, db
from models import RawMaterial, Meal, MealIngredient, User
from decimal import Decimal

def create_sample_meals_system():
    with app.app_context():
        # Get admin user
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            print('Admin user not found. Please create admin user first.')
            return
        
        # Check if raw materials already exist
        existing_materials = RawMaterial.query.count()
        if existing_materials == 0:
            print('Creating raw materials...')
            create_raw_materials()
        else:
            print(f'Raw materials already exist ({existing_materials} materials found)')
        
        # Check if meals already exist
        existing_meals = Meal.query.count()
        if existing_meals == 0:
            print('Creating sample meals...')
            create_meals(admin_user)
        else:
            print(f'Meals already exist ({existing_meals} meals found)')

def create_raw_materials():
    """Create raw materials for cooking"""
    raw_materials_data = [
        # Rice and Grains
        {'name': 'Basmati Rice', 'name_ar': 'أرز بسمتي', 'unit': 'kg', 'cost': 2.50, 'category': 'Rice & Grains'},
        {'name': 'Jasmine Rice', 'name_ar': 'أرز ياسمين', 'unit': 'kg', 'cost': 3.00, 'category': 'Rice & Grains'},
        
        # Meat and Protein
        {'name': 'Chicken Breast', 'name_ar': 'صدر دجاج', 'unit': 'kg', 'cost': 8.50, 'category': 'Meat'},
        {'name': 'Chicken Thighs', 'name_ar': 'أفخاذ دجاج', 'unit': 'kg', 'cost': 6.75, 'category': 'Meat'},
        {'name': 'Lamb Meat', 'name_ar': 'لحم خروف', 'unit': 'kg', 'cost': 15.00, 'category': 'Meat'},
        {'name': 'Beef', 'name_ar': 'لحم بقر', 'unit': 'kg', 'cost': 12.00, 'category': 'Meat'},
        
        # Vegetables
        {'name': 'Onions', 'name_ar': 'بصل', 'unit': 'kg', 'cost': 1.20, 'category': 'Vegetables'},
        {'name': 'Tomatoes', 'name_ar': 'طماطم', 'unit': 'kg', 'cost': 2.00, 'category': 'Vegetables'},
        {'name': 'Carrots', 'name_ar': 'جزر', 'unit': 'kg', 'cost': 1.50, 'category': 'Vegetables'},
        {'name': 'Potatoes', 'name_ar': 'بطاطس', 'unit': 'kg', 'cost': 1.00, 'category': 'Vegetables'},
        {'name': 'Bell Peppers', 'name_ar': 'فلفل حلو', 'unit': 'kg', 'cost': 3.50, 'category': 'Vegetables'},
        
        # Spices and Seasonings
        {'name': 'Biryani Masala', 'name_ar': 'بهارات برياني', 'unit': 'gram', 'cost': 0.05, 'category': 'Spices'},
        {'name': 'Turmeric', 'name_ar': 'كركم', 'unit': 'gram', 'cost': 0.03, 'category': 'Spices'},
        {'name': 'Cumin Powder', 'name_ar': 'كمون مطحون', 'unit': 'gram', 'cost': 0.04, 'category': 'Spices'},
        {'name': 'Coriander Powder', 'name_ar': 'كزبرة مطحونة', 'unit': 'gram', 'cost': 0.035, 'category': 'Spices'},
        {'name': 'Garam Masala', 'name_ar': 'جارام ماسالا', 'unit': 'gram', 'cost': 0.06, 'category': 'Spices'},
        {'name': 'Red Chili Powder', 'name_ar': 'فلفل أحمر مطحون', 'unit': 'gram', 'cost': 0.045, 'category': 'Spices'},
        {'name': 'Salt', 'name_ar': 'ملح', 'unit': 'gram', 'cost': 0.001, 'category': 'Spices'},
        
        # Oils and Fats
        {'name': 'Vegetable Oil', 'name_ar': 'زيت نباتي', 'unit': 'liter', 'cost': 4.50, 'category': 'Oils'},
        {'name': 'Ghee', 'name_ar': 'سمن', 'unit': 'kg', 'cost': 12.00, 'category': 'Oils'},
        {'name': 'Olive Oil', 'name_ar': 'زيت زيتون', 'unit': 'liter', 'cost': 8.00, 'category': 'Oils'},
        
        # Dairy
        {'name': 'Yogurt', 'name_ar': 'لبن زبادي', 'unit': 'kg', 'cost': 3.50, 'category': 'Dairy'},
        {'name': 'Milk', 'name_ar': 'حليب', 'unit': 'liter', 'cost': 1.80, 'category': 'Dairy'},
        
        # Others
        {'name': 'Saffron', 'name_ar': 'زعفران', 'unit': 'gram', 'cost': 2.50, 'category': 'Premium Spices'},
        {'name': 'Almonds', 'name_ar': 'لوز', 'unit': 'gram', 'cost': 0.08, 'category': 'Nuts'},
        {'name': 'Raisins', 'name_ar': 'زبيب', 'unit': 'gram', 'cost': 0.06, 'category': 'Dried Fruits'},
    ]
    
    for material_data in raw_materials_data:
        material = RawMaterial(
            name=material_data['name'],
            name_ar=material_data['name_ar'],
            unit=material_data['unit'],
            cost_per_unit=Decimal(str(material_data['cost'])),
            category=material_data['category'],
            active=True
        )
        db.session.add(material)
    
    db.session.commit()
    print(f'Created {len(raw_materials_data)} raw materials')

def create_meals(admin_user):
    """Create sample meals with ingredients"""
    
    # Get raw materials
    materials = {m.name: m for m in RawMaterial.query.all()}
    
    # Sample meals data
    meals_data = [
        {
            'name': 'Chicken Biryani',
            'name_ar': 'برياني دجاج',
            'description': 'Traditional aromatic rice dish with chicken',
            'category': 'Main Course',
            'profit_margin': 35,
            'ingredients': [
                {'material': 'Basmati Rice', 'quantity': 0.3},  # 300g
                {'material': 'Chicken Thighs', 'quantity': 0.4},  # 400g
                {'material': 'Onions', 'quantity': 0.15},  # 150g
                {'material': 'Yogurt', 'quantity': 0.1},  # 100g
                {'material': 'Biryani Masala', 'quantity': 15},  # 15g
                {'material': 'Turmeric', 'quantity': 5},  # 5g
                {'material': 'Ghee', 'quantity': 0.05},  # 50g
                {'material': 'Saffron', 'quantity': 0.2},  # 0.2g
                {'material': 'Almonds', 'quantity': 20},  # 20g
                {'material': 'Raisins', 'quantity': 15},  # 15g
                {'material': 'Salt', 'quantity': 8},  # 8g
            ]
        },
        {
            'name': 'Lamb Biryani',
            'name_ar': 'برياني لحم',
            'description': 'Premium biryani with tender lamb',
            'category': 'Main Course',
            'profit_margin': 40,
            'ingredients': [
                {'material': 'Basmati Rice', 'quantity': 0.3},
                {'material': 'Lamb Meat', 'quantity': 0.35},
                {'material': 'Onions', 'quantity': 0.2},
                {'material': 'Yogurt', 'quantity': 0.12},
                {'material': 'Biryani Masala', 'quantity': 18},
                {'material': 'Garam Masala', 'quantity': 8},
                {'material': 'Ghee', 'quantity': 0.06},
                {'material': 'Saffron', 'quantity': 0.3},
                {'material': 'Almonds', 'quantity': 25},
                {'material': 'Salt', 'quantity': 10},
            ]
        },
        {
            'name': 'Vegetable Curry',
            'name_ar': 'كاري خضار',
            'description': 'Mixed vegetable curry with aromatic spices',
            'category': 'Vegetarian',
            'profit_margin': 45,
            'ingredients': [
                {'material': 'Potatoes', 'quantity': 0.2},
                {'material': 'Carrots', 'quantity': 0.15},
                {'material': 'Bell Peppers', 'quantity': 0.1},
                {'material': 'Onions', 'quantity': 0.1},
                {'material': 'Tomatoes', 'quantity': 0.15},
                {'material': 'Turmeric', 'quantity': 5},
                {'material': 'Cumin Powder', 'quantity': 8},
                {'material': 'Coriander Powder', 'quantity': 6},
                {'material': 'Vegetable Oil', 'quantity': 0.03},
                {'material': 'Salt', 'quantity': 6},
            ]
        },
        {
            'name': 'Chicken Curry',
            'name_ar': 'كاري دجاج',
            'description': 'Spicy chicken curry with traditional spices',
            'category': 'Main Course',
            'profit_margin': 38,
            'ingredients': [
                {'material': 'Chicken Breast', 'quantity': 0.35},
                {'material': 'Onions', 'quantity': 0.12},
                {'material': 'Tomatoes', 'quantity': 0.1},
                {'material': 'Yogurt', 'quantity': 0.08},
                {'material': 'Garam Masala', 'quantity': 10},
                {'material': 'Turmeric', 'quantity': 6},
                {'material': 'Red Chili Powder', 'quantity': 8},
                {'material': 'Vegetable Oil', 'quantity': 0.04},
                {'material': 'Salt', 'quantity': 7},
            ]
        },
        {
            'name': 'Plain Rice',
            'name_ar': 'أرز أبيض',
            'description': 'Simple steamed basmati rice',
            'category': 'Side Dish',
            'profit_margin': 50,
            'ingredients': [
                {'material': 'Basmati Rice', 'quantity': 0.25},
                {'material': 'Salt', 'quantity': 3},
                {'material': 'Ghee', 'quantity': 0.01},
            ]
        }
    ]
    
    created_meals = []
    for meal_data in meals_data:
        # Create meal
        meal = Meal(
            name=meal_data['name'],
            name_ar=meal_data['name_ar'],
            description=meal_data['description'],
            category=meal_data['category'],
            profit_margin_percent=Decimal(str(meal_data['profit_margin'])),
            user_id=admin_user.id
        )
        db.session.add(meal)
        db.session.flush()  # Get meal ID
        
        # Add ingredients
        total_cost = 0
        for ingredient_data in meal_data['ingredients']:
            material_name = ingredient_data['material']
            if material_name in materials:
                material = materials[material_name]
                ingredient = MealIngredient(
                    meal_id=meal.id,
                    raw_material_id=material.id,
                    quantity=Decimal(str(ingredient_data['quantity'])),
                    total_cost=Decimal(str(ingredient_data['quantity'])) * material.cost_per_unit
                )
                db.session.add(ingredient)
                total_cost += float(ingredient.total_cost)
        
        # Update meal costs
        meal.total_cost = Decimal(str(total_cost))
        meal.calculate_selling_price()
        created_meals.append(meal)
    
    db.session.commit()
    
    print(f'Created {len(created_meals)} sample meals:')
    for meal in created_meals:
        print(f'- {meal.display_name}: Cost ${meal.total_cost:.2f} → Price ${meal.selling_price:.2f}')

if __name__ == '__main__':
    create_sample_meals_system()
