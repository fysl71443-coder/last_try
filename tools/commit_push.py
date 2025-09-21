import subprocess as s
import sys

cmds = [
    'git add app/routes.py',
    'git commit -m "fix(templates): pass required context to templates (sales, employees, VAT, financials)"',
    'git push origin main',
]
rc = 0
for c in cmds:
    print('> Running:', c)
    rc = s.call(c, shell=True)
    if rc != 0:
        print('Command failed with code', rc)
        break
sys.exit(rc)

