# -*- coding: utf-8 -*-
"""
أنواع المصروفات الموجّهة (Type-driven expenses).
المستخدم يختار النوع → النظام يحدد الحساب، الضريبة، الذمم الدائنة (منصة/حكومة).
يشمل تكلفة البضائع المباعة (COGS)، تكاليف العمالة، المصاريف التشغيلية، التسويقية، المنصات، الحكومية، وأخرى.
"""

# كل فئة: id, label_ar, label_en, default_vat (bool), sub_types
# كل sub_type: id, label_ar, label_en, account_code, liability_code (اختياري), default_vat
# إيجار: لا تشمل ضريبة. الخدمات من مورد بفاتورة ضريبية: تشمل ضريبة عند توفرها.

EXPENSE_CATEGORIES = [
    # ─── 1. تكلفة البضائع المباعة (COGS – مباشرة) ───
    {
        "id": "cogs",
        "label_ar": "تكلفة البضائع المباعة (COGS)",
        "label_en": "Cost of goods sold (COGS)",
        "icon": "fa-box",
        "default_vat": False,
        "sub_types": [
            {"id": "food_meat_veg_dairy", "label_ar": "مشتريات المواد الغذائية (لحوم، خضروات، ألبان)", "label_en": "Food (meat, vegetables, dairy)", "account_code": "5110", "liability_code": None, "default_vat": False},
            {"id": "beverages", "label_ar": "مشتريات المشروبات", "label_en": "Beverages", "account_code": "5120", "liability_code": None, "default_vat": False},
            {"id": "spoilage_waste", "label_ar": "تكلفة الهدر والتالف", "label_en": "Spoilage & waste", "account_code": "5160", "liability_code": None, "default_vat": False, "is_internal_adjustment": True, "source": "inventory_adjustment"},
            {"id": "packaging", "label_ar": "مواد تغليف", "label_en": "Packaging", "account_code": "5130", "liability_code": None, "default_vat": False},
            {"id": "cleaning_supplies", "label_ar": "مواد التنظيف", "label_en": "Cleaning supplies", "account_code": "5140", "liability_code": None, "default_vat": False},
        ],
    },
    # ─── 2. تكاليف العمالة (رواتب وأجور) ───
    {
        "id": "labour",
        "label_ar": "تكاليف العمالة (رواتب وأجور)",
        "label_en": "Labour (salaries & wages)",
        "icon": "fa-users",
        "default_vat": False,
        "sub_types": [
            {"id": "salaries_chefs", "label_ar": "رواتب الشيفات والطهاة", "label_en": "Salaries – chefs & cooks", "account_code": "5310", "liability_code": None, "default_vat": False},
            {"id": "wages_waiters", "label_ar": "أجور النوادل وموظفي الخدمة", "label_en": "Wages – waiters & service", "account_code": "5310", "liability_code": None, "default_vat": False},
            {"id": "wages_cleaning_prep", "label_ar": "أجور عمال النظافة والتجهيز", "label_en": "Wages – cleaning & prep", "account_code": "5310", "liability_code": None, "default_vat": False},
            {"id": "health_insurance", "label_ar": "تأمين صحي", "label_en": "Health insurance", "account_code": "5325", "liability_code": None, "default_vat": False},
            {"id": "incentives", "label_ar": "حوافز", "label_en": "Incentives", "account_code": "5330", "liability_code": None, "default_vat": False},
            {"id": "allowances", "label_ar": "بدلات", "label_en": "Allowances", "account_code": "5320", "liability_code": None, "default_vat": False},
        ],
    },
    # ─── 3. المصاريف التشغيلية (إشغال، مرافق، معدات، تغليف، إدارية) ───
    {
        "id": "operating",
        "label_ar": "المصاريف التشغيلية",
        "label_en": "Operating expenses",
        "icon": "fa-building",
        "default_vat": False,
        "sub_types": [
            # أ. الإشغال
            {"id": "rent", "label_ar": "إيجار المبنى", "label_en": "Rent", "account_code": "5270", "liability_code": None, "default_vat": False},
            {"id": "property_tax", "label_ar": "ضرائب العقارات", "label_en": "Property tax", "account_code": "5275", "liability_code": None, "default_vat": False},
            {"id": "property_insurance", "label_ar": "التأمين على الممتلكات", "label_en": "Property insurance", "account_code": "5278", "liability_code": None, "default_vat": False},
            # ب. المرافق
            {"id": "electricity", "label_ar": "كهرباء", "label_en": "Electricity", "account_code": "5210", "liability_code": None, "default_vat": False},
            {"id": "water", "label_ar": "ماء", "label_en": "Water", "account_code": "5220", "liability_code": None, "default_vat": False},
            {"id": "gas", "label_ar": "غاز", "label_en": "Gas", "account_code": "5215", "liability_code": None, "default_vat": False},
            {"id": "internet", "label_ar": "إنترنت", "label_en": "Internet", "account_code": "5230", "liability_code": None, "default_vat": False},
            # ج. المعدات والصيانة
            {"id": "kitchen_equipment_maint", "label_ar": "صيانة أجهزة المطبخ", "label_en": "Kitchen equipment maintenance", "account_code": "5242", "liability_code": None, "default_vat": True},
            {"id": "tableware", "label_ar": "أدوات المائدة", "label_en": "Tableware", "account_code": "5280", "liability_code": None, "default_vat": False},
            {"id": "cleaning_materials", "label_ar": "مواد التنظيف", "label_en": "Cleaning materials", "account_code": "5140", "liability_code": None, "default_vat": False},
            # د. التغليف
            {"id": "packaging_boxes", "label_ar": "علب الوجبات الجاهزة", "label_en": "Takeaway boxes", "account_code": "5130", "liability_code": None, "default_vat": False},
            {"id": "napkins", "label_ar": "مناديل", "label_en": "Napkins", "account_code": "5130", "liability_code": None, "default_vat": False},
            {"id": "bags", "label_ar": "أكياس", "label_en": "Bags", "account_code": "5130", "liability_code": None, "default_vat": False},
            # هـ. إدارية
            {"id": "license_fees", "label_ar": "رسوم التراخيص", "label_en": "License fees", "account_code": "5410", "liability_code": None, "default_vat": False},
            {"id": "pos_subscription", "label_ar": "اشتراكات برامج المحاسبة (POS)", "label_en": "POS / accounting subscriptions", "account_code": "5430", "liability_code": None, "default_vat": False},
            {"id": "delivery_costs", "label_ar": "تكاليف التوصيل", "label_en": "Delivery costs", "account_code": "5260", "liability_code": None, "default_vat": False},
        ],
    },
    # ─── 4. المصروفات التسويقية ───
    {
        "id": "marketing",
        "label_ar": "المصروفات التسويقية",
        "label_en": "Marketing expenses",
        "icon": "fa-bullhorn",
        "default_vat": True,
        "sub_types": [
            {"id": "social_media", "label_ar": "إعلانات التواصل الاجتماعي", "label_en": "Social media advertising", "account_code": "5515", "liability_code": None, "default_vat": True},
            {"id": "print_materials", "label_ar": "مطبوعات", "label_en": "Print materials", "account_code": "5512", "liability_code": None, "default_vat": True},
            {"id": "promotional_offers", "label_ar": "عروض ترويجية", "label_en": "Promotional offers", "account_code": "5530", "liability_code": None, "default_vat": True},
            {"id": "promotional_gifts", "label_ar": "هدايا ترويجية", "label_en": "Promotional gifts", "account_code": "5535", "liability_code": None, "default_vat": True},
            {"id": "advertising", "label_ar": "دعاية وإعلان", "label_en": "Advertising", "account_code": "5510", "liability_code": None, "default_vat": True},
        ],
    },
    # ─── 5. مصروفات تشغيلية إضافية (عام / شائع) ───
    {
        "id": "operating_extra",
        "label_ar": "مصروفات تشغيلية إضافية (عام)",
        "label_en": "Additional operating (general)",
        "icon": "fa-plug",
        "default_vat": False,
        "sub_types": [
            {"id": "water_general", "label_ar": "ماء (بدون تخصيص)", "label_en": "Water (general)", "account_code": "5220", "liability_code": None, "default_vat": False},
            {"id": "electricity_general", "label_ar": "كهرباء (بدون تخصيص)", "label_en": "Electricity (general)", "account_code": "5210", "liability_code": None, "default_vat": False},
            {"id": "gas_general", "label_ar": "غاز (بدون تخصيص)", "label_en": "Gas (general)", "account_code": "5215", "liability_code": None, "default_vat": False},
            {"id": "internet_general", "label_ar": "الإنترنت", "label_en": "Internet", "account_code": "5230", "liability_code": None, "default_vat": False},
            {"id": "building_maintenance", "label_ar": "صيانة المباني", "label_en": "Building maintenance", "account_code": "5245", "liability_code": None, "default_vat": True},
            {"id": "security_services", "label_ar": "خدمات أمن", "label_en": "Security services", "account_code": "5255", "liability_code": None, "default_vat": True},
        ],
    },
    # ─── 6. مصروفات خدمات (Service Expenses) ───
    {
        "id": "services",
        "label_ar": "مصروفات خدمات",
        "label_en": "Service expenses",
        "icon": "fa-wrench",
        "default_vat": True,
        "sub_types": [
            {"id": "equipment_maintenance", "label_ar": "صيانة أجهزة", "label_en": "Equipment maintenance", "account_code": "5242", "liability_code": None, "default_vat": True},
            {"id": "consulting", "label_ar": "استشارات", "label_en": "Consulting", "account_code": "5445", "liability_code": None, "default_vat": True},
            {"id": "employee_training", "label_ar": "تدريب الموظفين", "label_en": "Employee training", "account_code": "5360", "liability_code": None, "default_vat": True},
            {"id": "temporary_contractors", "label_ar": "رواتب مؤقتة / متعاقدين", "label_en": "Temporary / contractors", "account_code": "5315", "liability_code": None, "default_vat": False},
        ],
    },
    # ─── 7. مصروفات منصات إلكترونية (Platform Expenses) ───
    {
        "id": "platform_expenses",
        "label_ar": "مصروفات منصات إلكترونية",
        "label_en": "Platform expenses",
        "icon": "fa-mobile-screen",
        "default_vat": False,
        "sub_types": [
            {"id": "commission_hunger", "label_ar": "عمولة منصة (هنقرستيشن)", "label_en": "Commission (Hungerstation)", "account_code": "5550", "liability_code": "2113", "default_vat": False},
            {"id": "commission_jahez", "label_ar": "عمولة منصة (جاهز)", "label_en": "Commission (Jahez)", "account_code": "5550", "liability_code": "2115", "default_vat": False},
            {"id": "commission_keeta", "label_ar": "عمولة منصة (كيتا)", "label_en": "Commission (Keeta)", "account_code": "5550", "liability_code": "2114", "default_vat": False},
            {"id": "commission_noon", "label_ar": "عمولة منصة (نون)", "label_en": "Commission (Noon)", "account_code": "5550", "liability_code": "2116", "default_vat": False},
            {"id": "platform_delivery", "label_ar": "توصيل", "label_en": "Delivery", "account_code": "5265", "liability_code": None, "default_vat": False},
            {"id": "platform_subscription", "label_ar": "اشتراك منصات", "label_en": "Platform subscription", "account_code": "5435", "liability_code": None, "default_vat": False},
        ],
    },
    # ─── 8. المصروفات الحكومية ───
    {
        "id": "government",
        "label_ar": "المصروفات الحكومية",
        "label_en": "Government expenses",
        "icon": "fa-landmark",
        "default_vat": False,
        "sub_types": [
            {"id": "zakat", "label_ar": "زكاة", "label_en": "Zakat", "account_code": "5410", "liability_code": "2134", "default_vat": False},
            {"id": "municipality", "label_ar": "رسوم بلدية", "label_en": "Municipality fees", "account_code": "5410", "liability_code": None, "default_vat": False},
            {"id": "licenses", "label_ar": "رخص", "label_en": "Licenses", "account_code": "5410", "liability_code": None, "default_vat": False},
            {"id": "gosi", "label_ar": "GOSI", "label_en": "GOSI", "account_code": "5340", "liability_code": "2131", "default_vat": False},
        ],
    },
    # ─── 9. أخرى (Other) ───
    {
        "id": "other",
        "label_ar": "أخرى",
        "label_en": "Other",
        "icon": "fa-ellipsis",
        "default_vat": False,
        "sub_types": [
            {"id": "misc", "label_ar": "متنوع", "label_en": "Miscellaneous", "account_code": "5470", "liability_code": None, "default_vat": False},
        ],
    },
]


def get_sub_type_by_ids(category_id, sub_type_id):
    """تُرجع sub_type dict من category_id + sub_type_id أو None."""
    for cat in EXPENSE_CATEGORIES:
        if cat["id"] != category_id:
            continue
        for st in cat.get("sub_types", []):
            if st["id"] == sub_type_id:
                return {
                    "account_code": st["account_code"],
                    "liability_code": st.get("liability_code"),
                    "default_vat": st.get("default_vat", cat.get("default_vat", False)),
                    "is_internal_adjustment": st.get("is_internal_adjustment", False),
                    "source": st.get("source"),
                }
    return None


def get_category_by_id(category_id):
    """تُرجع الفئة كاملة أو None."""
    for cat in EXPENSE_CATEGORIES:
        if cat["id"] == category_id:
            return cat
    return None
