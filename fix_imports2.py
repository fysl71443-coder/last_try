import re

# Read the app.py file
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix double models.models. references
content = content.replace('models.models.', 'models.')

# Write back to file
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed double models references in app.py")
