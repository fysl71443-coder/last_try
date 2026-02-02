"""Extract api_inventory_intelligence route."""
with open('app/routes.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

chunk = ''.join(lines[1050:1416])
chunk = chunk.replace('@main.route(', '@bp.route(')

with open('routes/inventory.py', 'a', encoding='utf-8') as out:
    out.write('\n\n')
    out.write(chunk)

del lines[1050:1416]

with open('app/routes.py', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print('Done')
