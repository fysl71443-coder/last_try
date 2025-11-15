#!/usr/bin/env python3
"""
Create test data for the restaurant system
"""

from app import create_app, db
from sqlalchemy import inspect, text
from models import Settings, Employee, EmployeeSalaryDefault, RawMaterial, Meal, User
from datetime import datetime

app = create_app()

def create_test_data():
    """Create comprehensive test data"""
    with app.app_context():
        try:
            print('DB URI:', app.config.get('SQLALCHEMY_DATABASE_URI'))
        except Exception:
            pass

        # Ensure employees table has backward-compatible columns
        try:
            insp = inspect(db.engine)
            cols = [c['name'] for c in insp.get_columns('employees')]
            with db.engine.begin() as conn:
                if 'active' not in cols:
                    conn.execute(text('ALTER TABLE employees ADD COLUMN active INTEGER DEFAULT 1'))
                if 'work_hours' not in cols:
                    conn.execute(text('ALTER TABLE employees ADD COLUMN work_hours INTEGER DEFAULT 0'))
        except Exception:
            pass
        try:
            # Create settings if missing
            if not Settings.query.first():
                settings = Settings(
                    company_name='مطعم الصين وقصر الهند',
                    tax_number='123456789',
                    address='الرياض، المملكة العربية السعودية',
                    phone='0112345678',
                    email='info@restaurant.com',
                    vat_rate=15.0,
                    currency='SAR',
                    china_town_label='China Town',
                    place_india_label='Palace India',
                    china_town_void_password='1991',
                    place_india_void_password='1991',
                    china_town_vat_rate=15.0,
                    place_india_vat_rate=15.0,
                    china_town_discount_rate=0.0,
                    place_india_discount_rate=0.0,
                    receipt_paper_width='80',
                    receipt_font_size=12,
                    receipt_logo_height=40,
                    receipt_extra_bottom_mm=15,
                    receipt_show_tax_number=True,
                    receipt_footer_text='شكراً لزيارتكم - Thank you for visiting'
                )
                db.session.add(settings)
                print('✅ Settings created')
            
            # Create employees if missing
            try:
                emp_count = Employee.query.count()
            except Exception:
                emp_count = 0
            if emp_count == 0:
                sample_employees = [
                    {
                        'employee_code': 'EMP001',
                        'full_name': 'أحمد محمد علي',
                        'national_id': '1234567890',
                        'department': 'المطبخ',
                        'position': 'طباخ رئيسي',
                        'phone': '0501234567',
                        'email': 'ahmed@restaurant.com',
                        'hire_date': datetime.now().date(),
                        'status': 'active'
                    },
                    {
                        'employee_code': 'EMP002', 
                        'full_name': 'فاطمة أحمد',
                        'national_id': '0987654321',
                        'department': 'الخدمة',
                        'position': 'نادلة',
                        'phone': '0509876543',
                        'email': 'fatima@restaurant.com',
                        'hire_date': datetime.now().date(),
                        'status': 'active'
                    },
                    {
                        'employee_code': 'EMP003',
                        'full_name': 'محمد سالم',
                        'national_id': '1122334455',
                        'department': 'الإدارة',
                        'position': 'مشرف',
                        'phone': '0501122334',
                        'email': 'mohammed@restaurant.com',
                        'hire_date': datetime.now().date(),
                        'status': 'active'
                    },
                    {
                        'employee_code': 'EMP004',
                        'full_name': 'سارة خالد',
                        'national_id': '5566778899',
                        'department': 'المحاسبة',
                        'position': 'محاسبة',
                        'phone': '0505566778',
                        'email': 'sara@restaurant.com',
                        'hire_date': datetime.now().date(),
                        'status': 'active'
                    }
                ]
                
                for emp_data in sample_employees:
                    emp = Employee(**emp_data)
                    db.session.add(emp)
                    db.session.flush()  # Get the ID
                    
                    # Add default salary
                    salary_default = EmployeeSalaryDefault(
                        employee_id=emp.id,
                        base_salary=5000.0,
                        allowances=500.0,
                        deductions=100.0
                    )
                    db.session.add(salary_default)
                
                print('✅ Sample employees created')
            
            # Add some raw materials if missing
            if RawMaterial.query.count() < 5:
                raw_materials = [
                    {
                        'name': 'Rice',
                        'name_ar': 'أرز',
                        'unit': 'kg',
                        'cost_per_unit': 5.0,
                        'stock_quantity': 100.0,
                        'active': True
                    },
                    {
                        'name': 'Chicken',
                        'name_ar': 'دجاج',
                        'unit': 'kg',
                        'cost_per_unit': 15.0,
                        'stock_quantity': 50.0,
                        'active': True
                    },
                    {
                        'name': 'Vegetables',
                        'name_ar': 'خضروات',
                        'unit': 'kg',
                        'cost_per_unit': 8.0,
                        'stock_quantity': 30.0,
                        'active': True
                    }
                ]
                
                for material_data in raw_materials:
                    if not RawMaterial.query.filter_by(name=material_data['name']).first():
                        material = RawMaterial(**material_data)
                        db.session.add(material)
                
                print('✅ Raw materials added')
            
            # Add some meals if missing
            try:
                if Meal.query.count() < 5:
                    uid = None
                    u = User.query.first()
                    if u:
                        uid = u.id
                    meals = [
                        {
                            'name': 'Chicken Curry',
                            'name_ar': 'كاري الدجاج',
                            'description': 'Delicious chicken curry',
                            'selling_price': 25.0,
                            'active': True,
                            'user_id': uid or 1
                        },
                        {
                            'name': 'Fried Rice',
                            'name_ar': 'أرز مقلي',
                            'description': 'Chinese fried rice',
                            'selling_price': 20.0,
                            'active': True,
                            'user_id': uid or 1
                        },
                        {
                            'name': 'Vegetable Soup',
                            'name_ar': 'شوربة خضار',
                            'description': 'Fresh vegetable soup',
                            'selling_price': 15.0,
                            'active': True,
                            'user_id': uid or 1
                        }
                    ]
                    for meal_data in meals:
                        if not Meal.query.filter_by(name=meal_data['name']).first():
                            try:
                                meal = Meal(**meal_data)
                                db.session.add(meal)
                            except Exception:
                                pass
                    print('✅ Sample meals added')
            except Exception:
                pass
            
            # Commit all changes
            db.session.commit()
            print('✅ All test data created successfully')
            
            # Print summary
            print(f'\n📊 Data Summary:')
            print(f'   Settings: {Settings.query.count()}')
            print(f'   Employees: {Employee.query.count()}')
            print(f'   Raw Materials: {RawMaterial.query.count()}')
            print(f'   Meals: {Meal.query.count()}')
            
        except Exception as e:
            db.session.rollback()
            print(f'❌ Error creating test data: {e}')
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    create_test_data()
