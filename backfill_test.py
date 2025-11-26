from app import create_app
from extensions import db
from models import JournalEntry, JournalLine
from datetime import date, datetime
import re

app = create_app()
c = app.test_client()

# 1️⃣ GET form للحصول على CSRF
resp = c.get('/financials/backfill_journals')
html = resp.get_data(as_text=True)
m = re.search(r'name="csrf_token" value="([^"]+)"', html)
csrf = m.group(1) if m else ''

print('GET /financials/backfill_journals status:', resp.status_code)
if not csrf:
    print('❌ CSRF token not found. Aborting.')
else:
    print('✅ CSRF token obtained.')

with app.app_context():
    start_date = '2025-10-01'
    end_date = date.today().strftime('%Y-%m-%d')

    # عدد القيود قبل العملية
    before = db.session.query(JournalEntry).count()

    # 2️⃣ POST لتوليد القيود
    resp2 = c.post(
        '/financials/backfill_journals',
        data={'start_date': start_date, 'end_date': end_date, 'csrf_token': csrf},
        follow_redirects=True
    )

    after = db.session.query(JournalEntry).count()
    delta = after - before

    print('POST status:', resp2.status_code)
    print('✅ Number of new JournalEntries created:', delta)
    print('Total JournalEntries after operation:', after)

    if delta == 0:
        print('⚠ No new entries were created. Check date range or existing data.')

    # 3️⃣ عرض ملخص آخر 10 قيود تم إنشاؤها
    new_entries = JournalEntry.query.order_by(JournalEntry.date.desc()).limit(10).all()
    print('\n📄 Last 10 Journal Entries:')
    for r in new_entries:
        entry_date = r.date.strftime('%Y-%m-%d') if isinstance(r.date, datetime) else r.date
        print(f'JE #{r.entry_number} | Date: {entry_date} | Debit: {float(r.total_debit or 0):.2f} | Credit: {float(r.total_credit or 0):.2f}')

    # 4️⃣ تحقق من التواريخ
    for r in new_entries:
        entry_date = r.date
        if entry_date < datetime.strptime(start_date, '%Y-%m-%d').date() or entry_date > datetime.today().date():
            print(f'⚠ JE #{r.entry_number} date {entry_date} out of range!')