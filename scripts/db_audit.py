import os, sys
ROOT = os.path.abspath('.')
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from app import create_app
from extensions import db
from sqlalchemy import MetaData, inspect, text

app = create_app()

report = []
with app.app_context():
    engine = db.engine
    insp = inspect(engine)
    uri = app.config.get('SQLALCHEMY_DATABASE_URI')
    dialect = engine.dialect.name
    report.append(f"DB URI: {uri}")
    report.append(f"Dialect: {dialect}")
    tables = sorted(insp.get_table_names())
    report.append(f"Tables ({len(tables)}): {', '.join(tables)}")

    def table_count(name):
        try:
            res = db.session.execute(text(f"SELECT COUNT(*) FROM {name}"))
            return int(list(res)[0][0])
        except Exception:
            return None

    for t in tables:
        report.append("")
        report.append(f"Table: {t}")
        cols = insp.get_columns(t)
        for c in cols:
            col_line = f"  - {c['name']} {str(c.get('type'))}"
            if c.get('nullable') is False:
                col_line += " NOT NULL"
            report.append(col_line)
        pk = insp.get_pk_constraint(t)
        if pk and pk.get('constrained_columns'):
            report.append(f"  PK: {', '.join(pk['constrained_columns'])}")
        fks = insp.get_foreign_keys(t)
        for fk in fks:
            report.append(f"  FK: {', '.join(fk.get('constrained_columns', []))} -> {fk.get('referred_table')}({', '.join(fk.get('referred_columns', []))})")
        idx = insp.get_indexes(t)
        for i in idx:
            report.append(f"  IDX: {i.get('name')} on {', '.join(i.get('column_names') or [])} unique={i.get('unique')}")
        cnt = table_count(t)
        if cnt is not None:
            report.append(f"  Rows: {cnt}")

    expected_settings = [
        'company_name','tax_number','address','phone','email','vat_rate','currency',
        'place_india_label','china_town_label','default_theme','printer_type','currency_image','footer_message',
        'china_town_void_password','china_town_vat_rate','china_town_discount_rate',
        'place_india_void_password','place_india_vat_rate','place_india_discount_rate',
        'receipt_paper_width','receipt_font_size','receipt_show_logo','receipt_show_tax_number','receipt_footer_text',
        'receipt_logo_height','receipt_extra_bottom_mm','logo_url',
        'china_town_phone1','china_town_phone2','place_india_phone1','place_india_phone2'
    ]
    if 'settings' in tables:
        scols = {c['name'] for c in insp.get_columns('settings')}
        missing = [c for c in expected_settings if c not in scols]
        report.append("")
        report.append("Settings columns missing: " + (", ".join(missing) if missing else "None"))

    if 'sales_invoices' in tables:
        icols = {c['name'] for c in insp.get_columns('sales_invoices')}
        needed = ['branch','table_number','invoice_number','status','total_after_tax_discount']
        lacking = [c for c in needed if c not in icols]
        report.append("sales_invoices missing: " + (", ".join(lacking) if lacking else "None"))

print("\n".join(report))
