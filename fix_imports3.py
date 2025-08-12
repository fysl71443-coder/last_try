import re

# Read the app.py file
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove models. prefix from all model references
replacements = {
    r'models\.User\.': 'User.',
    r'models\.SalesInvoice\.': 'SalesInvoice.',
    r'models\.SalesInvoiceItem\.': 'SalesInvoiceItem.',
    r'models\.RawMaterial\.': 'RawMaterial.',
    r'models\.Meal\.': 'Meal.',
    r'models\.MealIngredient\.': 'MealIngredient.',
    r'models\.PurchaseInvoice\.': 'PurchaseInvoice.',
    r'models\.PurchaseInvoiceItem\.': 'PurchaseInvoiceItem.',
    r'models\.ExpenseInvoice\.': 'ExpenseInvoice.',
    r'models\.ExpenseInvoiceItem\.': 'ExpenseInvoiceItem.',
    r'models\.Product\.': 'Product.',
    r'models\.Invoice\.': 'Invoice.',
}

for pattern, replacement in replacements.items():
    content = re.sub(pattern, replacement, content)

# Write back to file
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Removed models. prefix from all model references in app.py")
