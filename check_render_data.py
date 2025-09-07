#!/usr/bin/env python3
"""
✅ تحقق من الأقسام والمنتجات عبر API على Render
"""

import requests
import json
from datetime import datetime

BASE_URL = "https://restaurant-system-fnbm.onrender.com"

def test_connection():
    """اختبار الاتصال بالخادم"""
    try:
        print("🔗 اختبار الاتصال بالخادم...")
        response = requests.get(f"{BASE_URL}/", timeout=10)
        print(f"✅ الخادم متاح - Status: {response.status_code}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ فشل الاتصال بالخادم: {e}")
        return False

def get_categories():
    """جلب الأقسام من API"""
    try:
        print("📋 جلب الأقسام...")
        url = f"{BASE_URL}/api/categories"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            categories = response.json()
            print(f"✅ تم جلب {len(categories)} قسم بنجاح")
            return categories
        elif response.status_code == 401:
            print("❌ مطلوب تسجيل الدخول للوصول للـ API")
            return []
        else:
            print(f"❌ فشل في جلب الأقسام - Status: {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"❌ خطأ في الشبكة أثناء جلب الأقسام: {e}")
        return []

def get_items(category_id):
    """جلب المنتجات لقسم معين"""
    try:
        url = f"{BASE_URL}/api/items?category_id={category_id}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            items = response.json()
            return items
        elif response.status_code == 401:
            print("❌ مطلوب تسجيل الدخول للوصول للمنتجات")
            return []
        else:
            print(f"❌ فشل في جلب المنتجات للقسم {category_id} - Status: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"❌ خطأ في الشبكة أثناء جلب المنتجات: {e}")
        return []

def test_local_api():
    """اختبار API المحلي كبديل"""
    try:
        print("\n🏠 اختبار API المحلي...")
        local_url = "http://localhost:5000/api/categories"
        response = requests.get(local_url, timeout=5)
        
        if response.status_code == 200:
            categories = response.json()
            print(f"✅ API المحلي يعمل - {len(categories)} قسم")
            return categories
        else:
            print(f"❌ API المحلي لا يعمل - Status: {response.status_code}")
            return []
    except requests.exceptions.RequestException:
        print("❌ الخادم المحلي غير متاح")
        return []

def generate_report(categories_data):
    """إنشاء تقرير مفصل"""
    report = []
    report.append("=" * 60)
    report.append("📊 تقرير الأقسام والمنتجات")
    report.append("=" * 60)
    report.append(f"📅 التاريخ: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"🌐 الخادم: {BASE_URL}")
    report.append("")
    
    total_items = 0
    categories_with_items = 0
    
    for cat in categories_data:
        items = get_items(cat['id'])
        item_count = len(items)
        total_items += item_count
        
        if item_count > 0:
            categories_with_items += 1
        
        report.append(f"📂 {cat['name']} (ID: {cat['id']})")
        report.append(f"   📊 عدد المنتجات: {item_count}")
        
        if items:
            for item in items[:3]:  # أول 3 منتجات فقط
                report.append(f"      • {item['name']} - {item['price']} SAR")
            if len(items) > 3:
                report.append(f"      ... و {len(items) - 3} منتج آخر")
        else:
            report.append("      ⚠️ لا توجد منتجات في هذا القسم")
        report.append("")
    
    report.append("=" * 60)
    report.append("📈 الملخص:")
    report.append(f"   📋 إجمالي الأقسام: {len(categories_data)}")
    report.append(f"   🍽️ إجمالي المنتجات: {total_items}")
    report.append(f"   ✅ أقسام تحتوي على منتجات: {categories_with_items}")
    report.append(f"   ⚠️ أقسام فارغة: {len(categories_data) - categories_with_items}")
    
    if categories_with_items > 0:
        report.append("   🎯 الحالة: النظام جاهز للاستخدام!")
    else:
        report.append("   ❌ الحالة: يحتاج إضافة منتجات للأقسام")
    
    report.append("=" * 60)
    
    return "\n".join(report)

def save_report(report_content):
    """حفظ التقرير في ملف"""
    try:
        filename = f"render_api_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print(f"💾 تم حفظ التقرير في: {filename}")
    except Exception as e:
        print(f"❌ فشل في حفظ التقرير: {e}")

def main():
    """الدالة الرئيسية"""
    print("🚀 بدء فحص API على Render...")
    print("=" * 60)
    
    # اختبار الاتصال
    if not test_connection():
        print("\n🏠 جاري المحاولة مع الخادم المحلي...")
        categories = test_local_api()
        if not categories:
            print("❌ لا يمكن الوصول لأي خادم")
            return
    else:
        # جلب الأقسام من Render
        categories = get_categories()
    
    if not categories:
        print("❌ لم يتم العثور على أقسام")
        return
    
    print(f"\n📊 تم جلب {len(categories)} قسم:")
    print("-" * 40)
    
    # عرض الأقسام والمنتجات
    for i, cat in enumerate(categories, 1):
        print(f"{i:2d}. 📂 {cat['name']} (ID: {cat['id']})")
        
        items = get_items(cat['id'])
        print(f"     📊 عدد المنتجات: {len(items)}")
        
        if items:
            # عرض أول 3 منتجات
            for item in items[:3]:
                print(f"        • {item['name']} - {item['price']} SAR")
            if len(items) > 3:
                print(f"        ... و {len(items) - 3} منتج آخر")
        else:
            print("        ⚠️ لا توجد منتجات")
        print()
    
    # إنشاء وحفظ التقرير
    report = generate_report(categories)
    print(report)
    save_report(report)
    
    print("✅ انتهى الفحص بنجاح!")

if __name__ == "__main__":
    main()
