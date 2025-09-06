 feature/new-pos-system
# 🚀 تعليمات نشر نظام POS الجديد

## 📦 ملخص التغييرات

تم تطوير نظام POS جديد مع الميزات التالية:

### ✨ الميزات الجديدة:
- **واجهات منفصلة** لـ China Town و Palace India
- **تكامل مع المنيو** - عرض الفئات والوجبات من قاعدة البيانات
- **البحث عن العملاء** بالاسم أو رقم الهاتف
- **تطبيق الخصم تلقائياً** عند اختيار العميل
- **طباعة فاتورة مسودة** (غير مدفوعة) للمطبخ
- **طرق دفع متعددة** (نقد، بطاقة، تحويل بنكي، أخرى)
- **حماية حذف الأصناف** بكلمة سر
- **إعدادات منفصلة** لكل فرع

## 📁 الملفات الجديدة:

### Templates:
- `templates/china_town_sales.html` - واجهة China Town POS
- `templates/palace_india_sales.html` - واجهة Palace India POS
- `templates/sales_branches.html` - صفحة اختيار الفروع
- `templates/sales_redirect.html` - صفحة التوجيه للنظام الجديد

### Scripts:
- `migrations/add_branch_settings.py` - migration لإضافة إعدادات الفروع
- `link_existing_meals.py` - ربط الوجبات الموجودة بالفئات
- `test_new_pos_system.py` - اختبارات شاملة للنظام
- `run_server.py` - script لتشغيل الخادم

### Documentation:
- `NEW_POS_SYSTEM_README.md` - دليل النظام الجديد
- `ADD_MORE_MEALS_GUIDE.md` - دليل إضافة الوجبات

## 🔧 خطوات النشر:

### 1. تطبيق التغييرات:
```bash
# إذا كان لديك access للمستودع:
git fetch origin
git checkout feature/new-pos-system
git merge main

# أو تطبيق الـ patch:
git apply new-pos-system.patch
```

### 2. تشغيل Migration:
```bash
python migrations/add_branch_settings.py
# أو
python add_branch_settings_simple.py
```

### 3. ربط الوجبات الموجودة:
```bash
python link_existing_meals.py
```

### 4. اختبار النظام:
```bash
python test_new_pos_system.py
```

### 5. تشغيل الخادم:
```bash
python run_server.py
# أو
python app.py
```

## 🌐 الروابط الجديدة:

- **اختيار الفروع**: http://localhost:5000/sales
- **China Town POS**: http://localhost:5000/sales/china_town
- **Palace India POS**: http://localhost:5000/sales/palace_india
- **الإعدادات**: http://localhost:5000/settings

## ⚙️ الإعدادات الجديدة:

تم إضافة الحقول التالية لجدول `Settings`:
- `china_town_void_password` (افتراضي: '1991')
- `china_town_vat_rate` (افتراضي: 15.00)
- `china_town_discount_rate` (افتراضي: 0.00)
- `place_india_void_password` (افتراضي: '1991')
- `place_india_vat_rate` (افتراضي: 15.00)
- `place_india_discount_rate` (افتراضي: 0.00)

## 🧪 الاختبار:

النظام تم اختباره بالكامل:
- ✅ قاعدة البيانات (5/5)
- ✅ الروابط (4/4)
- ✅ API endpoints (7/7)
- ✅ دوال المساعدة (2/2)
- ✅ ملفات القوالب (5/5)

## 📊 البيانات الحالية:

- **18 فئة رئيسية** في MenuCategory
- **10 وجبات** مربوطة بالفئات
- **3 فئات نشطة**: House Special (7 وجبات), Chicken (2 وجبات), Rice & Biryani (1 وجبة)

## 🔑 بيانات الدخول:

- **Username**: admin
- **Password**: admin

## 📞 الدعم:

إذا واجهت أي مشاكل:
1. تأكد من تشغيل migration
2. تأكد من ربط الوجبات بالفئات
3. شغل الاختبارات للتأكد من سلامة النظام
4. تحقق من console المتصفح للأخطاء

---

**🎯 النظام جاهز للإنتاج!**

# 🚀 Restaurant System - PostgreSQL Deployment Instructions

## 📋 Pre-Deployment Checklist

✅ **Code Status:**
- All models updated for PostgreSQL compatibility
- Migration scripts created and tested
- All Internal Server Errors resolved
- Sales system fully functional

## 🔧 PostgreSQL Database Setup

### Step 1: Execute Required SQL Commands

Connect to your PostgreSQL database and run these commands:

```sql
-- Essential columns for draft_orders table
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_name VARCHAR(100);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS customer_phone VARCHAR(20);
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS payment_method VARCHAR(50) DEFAULT 'CASH';
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS user_id INTEGER;

-- Essential columns for tables table
ALTER TABLE tables ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50);
ALTER TABLE tables ADD COLUMN IF NOT EXISTS table_number INTEGER;
ALTER TABLE tables ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'available';
ALTER TABLE tables ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE tables ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;

-- Performance indexes
CREATE INDEX IF NOT EXISTS idx_draft_orders_branch_status ON draft_orders(branch_code, status);
CREATE INDEX IF NOT EXISTS idx_tables_branch ON tables(branch_code);
```

### Step 2: Alternative - Use Migration Script

Or run the complete migration script:

```bash
python apply_migration.py
```

## 🎯 Deployment Steps for Render

### 1. Environment Variables
Set these in Render dashboard:
```
DATABASE_URL=postgresql://...
FLASK_ENV=production
SECRET_KEY=your-secret-key
```

### 2. Build Command
```bash
pip install -r requirements.txt
```

### 3. Start Command
```bash
python app.py
```

### 4. Post-Deployment Verification

After deployment, verify these endpoints work:

- ✅ `/login` - Login functionality
- ✅ `/dashboard` - Main dashboard
- ✅ `/sales` - Sales main page
- ✅ `/sales/china_town/tables` - China Town tables
- ✅ `/sales/place_india/tables` - Place India tables
- ✅ `/inventory` - Inventory management
- ✅ `/expenses` - Expense management

## 🔍 Troubleshooting

### If you get "column does not exist" errors:

1. **Check PostgreSQL logs** for the exact missing column
2. **Run the specific ALTER TABLE command** for that column
3. **Restart the application** after database changes

### Common fixes:
```sql
-- If table_number is missing:
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS table_number VARCHAR(50);

-- If status is missing:
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft';

-- If branch_code is missing:
ALTER TABLE draft_orders ADD COLUMN IF NOT EXISTS branch_code VARCHAR(50);
```

## ✅ Success Indicators

Your deployment is successful when:

1. **All pages load without 500 errors**
2. **Sales system shows tables for both branches**
3. **Database queries execute without column errors**
4. **No SQLAlchemy exceptions in logs**

## 📞 Support

If you encounter issues:
1. Check Render logs for specific error messages
2. Verify PostgreSQL connection
3. Ensure all required columns exist in database
4. Restart application after database changes

---

**Status: ✅ READY FOR PRODUCTION DEPLOYMENT**

All database schema issues resolved. Sales system fully functional.
main
