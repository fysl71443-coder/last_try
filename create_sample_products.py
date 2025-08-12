from app import app, db
from models import Product
from decimal import Decimal

def create_sample_products():
    with app.app_context():
        # Check if products already exist
        existing_products = Product.query.count()
        if existing_products > 0:
            print(f'Products already exist ({existing_products} products found)')
            return
        
        # Sample products data
        products_data = [
            # Rice and Grains
            {'name': 'Basmati Rice 5kg', 'name_ar': 'أرز بسمتي 5 كيلو', 'price': 25.50, 'category': 'Rice & Grains'},
            {'name': 'Jasmine Rice 2kg', 'name_ar': 'أرز ياسمين 2 كيلو', 'price': 18.75, 'category': 'Rice & Grains'},
            {'name': 'Brown Rice 1kg', 'name_ar': 'أرز بني 1 كيلو', 'price': 12.00, 'category': 'Rice & Grains'},
            {'name': 'White Rice 10kg', 'name_ar': 'أرز أبيض 10 كيلو', 'price': 45.00, 'category': 'Rice & Grains'},
            {'name': 'Bulgur Wheat 500g', 'name_ar': 'برغل 500 جرام', 'price': 8.50, 'category': 'Rice & Grains'},
            
            # Spices and Seasonings
            {'name': 'Mixed Spices 100g', 'name_ar': 'توابل مشكلة 100 جرام', 'price': 15.00, 'category': 'Spices'},
            {'name': 'Turmeric Powder 50g', 'name_ar': 'كركم مطحون 50 جرام', 'price': 6.75, 'category': 'Spices'},
            {'name': 'Cumin Seeds 100g', 'name_ar': 'كمون حب 100 جرام', 'price': 9.25, 'category': 'Spices'},
            {'name': 'Black Pepper 50g', 'name_ar': 'فلفل أسود 50 جرام', 'price': 12.50, 'category': 'Spices'},
            {'name': 'Cardamom 25g', 'name_ar': 'هيل 25 جرام', 'price': 22.00, 'category': 'Spices'},
            
            # Legumes and Pulses
            {'name': 'Red Lentils 1kg', 'name_ar': 'عدس أحمر 1 كيلو', 'price': 14.00, 'category': 'Legumes'},
            {'name': 'Chickpeas 1kg', 'name_ar': 'حمص 1 كيلو', 'price': 16.50, 'category': 'Legumes'},
            {'name': 'Black Beans 500g', 'name_ar': 'فول أسود 500 جرام', 'price': 11.75, 'category': 'Legumes'},
            {'name': 'Green Lentils 1kg', 'name_ar': 'عدس أخضر 1 كيلو', 'price': 15.25, 'category': 'Legumes'},
            {'name': 'Fava Beans 1kg', 'name_ar': 'فول مدمس 1 كيلو', 'price': 13.50, 'category': 'Legumes'},
            
            # Oils and Cooking Essentials
            {'name': 'Olive Oil 500ml', 'name_ar': 'زيت زيتون 500 مل', 'price': 28.00, 'category': 'Oils'},
            {'name': 'Sunflower Oil 1L', 'name_ar': 'زيت دوار الشمس 1 لتر', 'price': 19.50, 'category': 'Oils'},
            {'name': 'Coconut Oil 250ml', 'name_ar': 'زيت جوز الهند 250 مل', 'price': 24.75, 'category': 'Oils'},
            {'name': 'Sesame Oil 200ml', 'name_ar': 'زيت سمسم 200 مل', 'price': 16.25, 'category': 'Oils'},
            
            # Tea and Beverages
            {'name': 'Black Tea 250g', 'name_ar': 'شاي أحمر 250 جرام', 'price': 21.00, 'category': 'Beverages'},
            {'name': 'Green Tea 100g', 'name_ar': 'شاي أخضر 100 جرام', 'price': 18.50, 'category': 'Beverages'},
            {'name': 'Cardamom Tea 200g', 'name_ar': 'شاي بالهيل 200 جرام', 'price': 26.75, 'category': 'Beverages'},
            {'name': 'Mint Tea 150g', 'name_ar': 'شاي بالنعناع 150 جرام', 'price': 15.75, 'category': 'Beverages'},
            
            # Sugar and Sweeteners
            {'name': 'White Sugar 2kg', 'name_ar': 'سكر أبيض 2 كيلو', 'price': 8.50, 'category': 'Sugar'},
            {'name': 'Brown Sugar 1kg', 'name_ar': 'سكر بني 1 كيلو', 'price': 12.25, 'category': 'Sugar'},
            {'name': 'Honey 500g', 'name_ar': 'عسل طبيعي 500 جرام', 'price': 35.00, 'category': 'Sugar'},
            
            # Flour and Baking
            {'name': 'All Purpose Flour 2kg', 'name_ar': 'دقيق أبيض 2 كيلو', 'price': 11.50, 'category': 'Flour'},
            {'name': 'Whole Wheat Flour 1kg', 'name_ar': 'دقيق قمح كامل 1 كيلو', 'price': 9.75, 'category': 'Flour'},
            {'name': 'Corn Flour 500g', 'name_ar': 'دقيق ذرة 500 جرام', 'price': 7.25, 'category': 'Flour'},
            
            # Canned and Preserved
            {'name': 'Tomato Paste 400g', 'name_ar': 'معجون طماطم 400 جرام', 'price': 5.50, 'category': 'Canned'},
            {'name': 'Coconut Milk 400ml', 'name_ar': 'حليب جوز الهند 400 مل', 'price': 8.75, 'category': 'Canned'},
        ]
        
        # Create products
        created_products = []
        for product_data in products_data:
            product = Product(
                name=product_data['name'],
                name_ar=product_data['name_ar'],
                price_before_tax=Decimal(str(product_data['price'])),
                category=product_data['category'],
                active=True
            )
            db.session.add(product)
            created_products.append(product)
        
        db.session.commit()
        
        print(f'Created {len(created_products)} sample products successfully!')
        
        # Print summary by category
        categories = {}
        for product in created_products:
            if product.category not in categories:
                categories[product.category] = 0
            categories[product.category] += 1
        
        print('\nProducts by category:')
        for category, count in categories.items():
            print(f'- {category}: {count} products')
        
        print('\nSample products:')
        for i, product in enumerate(created_products[:5]):
            print(f'- {product.display_name} - ${product.price_before_tax}')
        print('...')

if __name__ == '__main__':
    create_sample_products()
