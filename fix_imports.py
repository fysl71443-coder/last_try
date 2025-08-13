import re

# Read the app.py file
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace all model references
replacements = {
    r'\bUser\.': 'models.User.',
    r'\bSalesInvoice\.': 'models.SalesInvoice.',
    r'\bSalesInvoiceItem\.': 'models.SalesInvoiceItem.',
    r'\bRawMaterial\.': 'models.RawMaterial.',
    r'\bMeal\.': 'models.Meal.',
    r'\bMealIngredient\.': 'models.MealIngredient.',
    r'\bPurchaseInvoice\.': 'models.PurchaseInvoice.',
    r'\bPurchaseInvoiceItem\.': 'models.PurchaseInvoiceItem.',
    r'\bExpenseInvoice\.': 'models.ExpenseInvoice.',
    r'\bExpenseInvoiceItem\.': 'models.ExpenseInvoiceItem.',
    r'\bProduct\.': 'models.Product.',
    r'\bInvoice\.': 'models.Invoice.',
}

for pattern, replacement in replacements.items():
    content = re.sub(pattern, replacement, content)

# Write back to file
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed all model imports in app.py")
