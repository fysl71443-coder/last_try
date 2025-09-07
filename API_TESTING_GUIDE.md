# 🔍 دليل فحص API للأقسام والمنتجات

## 📊 **الوضع الحالي:**

### ✅ **البيانات المحلية جاهزة:**
- **21 قسم نشط** في قاعدة البيانات
- **22 منتج** موزع على 9 أقسام
- **API Routes** تعمل بشكل مثالي

### 📋 **الأقسام المتوفرة:**
1. **Appetizers** (3 منتجات) ✅
2. **Beef & Lamb** (3 منتجات) ✅
3. **Charcoal Grill / Kebabs** (3 منتجات) ✅
4. **Chicken** (3 منتجات) ✅
5. **Chinese Sizzling** (3 منتجات) ✅
6. **House Special** (7 منتجات) ✅
7. **Juices** (4 منتجات) ✅
8. **Rice & Biryani** (3 منتجات) ✅
9. **Soft Drink** (3 منتجات) ✅
10. **12 قسم إضافي** جاهز لإضافة منتجات

## 🌐 **فحص API على Render:**

### 1️⃣ **استخدام السكريبت المتقدم:**

```bash
# تثبيت المكتبة المطلوبة
pip install requests

# تشغيل السكريبت
python check_render_data.py
```

### 2️⃣ **فحص يدوي باستخدام curl:**

```bash
# فحص الأقسام
curl -X GET "https://restaurant-system-fnbm.onrender.com/api/categories"

# فحص المنتجات للقسم الأول
curl -X GET "https://restaurant-system-fnbm.onrender.com/api/items?category_id=1"

# فحص المنتجات لقسم الدجاج
curl -X GET "https://restaurant-system-fnbm.onrender.com/api/items?category_id=4"
```

### 3️⃣ **فحص عبر المتصفح:**

```
# الأقسام
https://restaurant-system-fnbm.onrender.com/api/categories

# المنتجات
https://restaurant-system-fnbm.onrender.com/api/items?category_id=1
```

## 🔧 **السكريبت المتقدم:**

### **check_render_data.py** - فحص شامل:

```python
import requests
import json
from datetime import datetime

BASE_URL = "https://restaurant-system-fnbm.onrender.com"

def get_categories():
    """جلب الأقسام من API"""
    try:
        url = f"{BASE_URL}/api/categories"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            print("❌ مطلوب تسجيل الدخول للوصول للـ API")
            return []
        else:
            print(f"❌ فشل في جلب الأقسام - Status: {response.status_code}")
            return []
    except Exception as e:
        print(f"❌ خطأ في الشبكة: {e}")
        return []

def get_items(category_id):
    """جلب المنتجات لقسم معين"""
    try:
        url = f"{BASE_URL}/api/items?category_id={category_id}"
        response = requests.get(url, timeout=15)
        
        if response.status_code == 200:
            return response.json()
        else:
            return []
    except Exception:
        return []

def main():
    print("🚀 فحص API على Render...")
    
    categories = get_categories()
    if not categories:
        print("❌ لم يتم العثور على أقسام")
        return
    
    print(f"✅ تم جلب {len(categories)} قسم")
    
    total_items = 0
    for cat in categories:
        items = get_items(cat['id'])
        total_items += len(items)
        print(f"📂 {cat['name']}: {len(items)} منتج")
        
        for item in items[:2]:  # أول منتجين
            print(f"   • {item['name']} - {item['price']} SAR")
    
    print(f"\n📊 الملخص:")
    print(f"   الأقسام: {len(categories)}")
    print(f"   المنتجات: {total_items}")

if __name__ == "__main__":
    main()
```

## 🎯 **النتائج المتوقعة:**

### ✅ **إذا كان API يعمل:**
```
🚀 فحص API على Render...
✅ تم جلب 21 قسم
📂 Appetizers: 3 منتج
   • Spring Rolls - 15.0 SAR
   • Chicken Samosa - 12.0 SAR
📂 Beef & Lamb: 3 منتج
   • Beef Curry - 45.0 SAR
   • Lamb Biryani - 50.0 SAR
...
📊 الملخص:
   الأقسام: 21
   المنتجات: 22
```

### ❌ **إذا كان هناك مشكلة:**
```
❌ مطلوب تسجيل الدخول للوصول للـ API
```
أو
```
❌ فشل في جلب الأقسام - Status: 500
```

## 🔧 **حل المشاكل المحتملة:**

### 1️⃣ **مشكلة تسجيل الدخول (401):**
- API يتطلب تسجيل دخول
- **الحل:** إضافة authentication للسكريبت أو جعل API عام

### 2️⃣ **خطأ خادم (500):**
- مشكلة في قاعدة البيانات على Render
- **الحل:** فحص logs على Render

### 3️⃣ **لا توجد بيانات:**
- الجداول فارغة على Render
- **الحل:** تشغيل migration scripts على Render

## 🚀 **الخطوات التالية:**

### 1. **فحص API محلياً:**
```bash
python test_local_api.py
```

### 2. **فحص API على Render:**
```bash
python check_render_data.py
```

### 3. **إذا فشل API على Render:**
- فحص Render logs
- تشغيل migration scripts
- إضافة البيانات التجريبية

### 4. **اختبار واجهة POS:**
```
https://restaurant-system-fnbm.onrender.com/sales/china_town
```

## 📝 **ملاحظات مهمة:**

1. **API محمي بـ login_required** - قد يحتاج authentication
2. **البيانات المحلية جاهزة** - 21 قسم و 22 منتج
3. **النظام جاهز للاستخدام** محلياً
4. **Render قد يحتاج migration** لنقل البيانات

## ✅ **التأكد من النجاح:**

عندما يعمل API بشكل صحيح، ستحصل على:
- **JSON response** مع قائمة الأقسام
- **JSON response** مع قائمة المنتجات لكل قسم
- **واجهة POS** تعرض الأقسام والمنتجات ديناميكياً

🎯 **الهدف:** التأكد من أن الأقسام والمنتجات تظهر في واجهة POS على Render كما تعمل محلياً!
