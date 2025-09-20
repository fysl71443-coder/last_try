from flask import Flask, render_template, request, redirect, url_for, flash
from jinja2 import DictLoader
from datetime import datetime
from zoneinfo import ZoneInfo


app = Flask(__name__)
app.secret_key = "secret_key_for_sessions"

# ===== بيانات الفروع والطاولات =====
branches = [
    {"code": "CT", "name": "CHINA TOWN"},
    {"code": "PI", "name": "PALACE INDIA"},
]

# كل فرع وعدد طاولاته وحالة الانشغال
tables_data = {
    "CT": [{"number": i, "is_busy": False} for i in range(1, 10)],
    "PI": [{"number": i, "is_busy": False} for i in range(1, 7)],
}

# ===== بيانات العملاء (اسم/هاتف/نسبة خصم) =====
customers_data = [
    {"id": 1, "name": "Ahmed Ali", "phone": "+966500000001", "discount": 10},
    {"id": 2, "name": "Sara Mohammed", "phone": "+966500000002", "discount": 5},
    {"id": 3, "name": "Mohammed Saad", "phone": "+966500000003", "discount": 0},
]
# ===== إعدادات المطعم (قابلة للتعديل لاحقًا عبر Settings) =====
settings = {
    "restaurant_name": "PALACE INDIA",
    "vat_number": "300000000000003",
    "address": "Riyadh, KSA",
    "phone": "+966500000000",
    "logo_base64": "",  # ضع شعار المطعم Base64 هنا إن توفر
    "currency_code": "SAR",
    # شارة/رمز العملة كـ PNG مضمن (شفاف 1x1 مكان حامل)
    "currency_png_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMAAQAABQABDQottAAAAABJRU5ErkJggg==",
}


# ===== بيانات الأقسام والأصناف من شاشة المنيو =====
menu_data = {
    1: {"name": "Appetizers", "items": [{"name": "Spring Rolls", "price": 12.0}, {"name": "Garlic Bread", "price": 8.0}]},
    2: {"name": "Beef & Lamb", "items": [{"name": "Beef Steak", "price": 45.0}, {"name": "Lamb Chops", "price": 48.0}]},

    3: {"name": "Charcoal Grill / Kebabs", "items": [{"name": "Chicken Kebab", "price": 25.0}, {"name": "Seekh Kebab", "price": 27.0}]},
    4: {"name": "Chicken", "items": [{"name": "Butter Chicken", "price": 30.0}, {"name": "Grilled Chicken", "price": 28.0}]},
    5: {"name": "Chinese Sizzling", "items": [{"name": "Kung Pao Chicken", "price": 32.0}, {"name": "Szechuan Beef", "price": 35.0}]},
    6: {"name": "House Special", "items": [{"name": "Chef Special Noodles", "price": 22.0}]},
    7: {"name": "Indian Delicacy (Chicken)", "items": [{"name": "Tandoori Chicken", "price": 29.0}]},
    8: {"name": "Indian Delicacy (Fish)", "items": [{"name": "Fish Curry", "price": 33.0}]},
    9: {"name": "Indian Delicacy (Vegetables)", "items": [{"name": "Paneer Masala", "price": 24.0}]},
    10: {"name": "Juices", "items": [{"name": "Orange Juice", "price": 10.0}, {"name": "Apple Juice", "price": 10.0}]},
    11: {"name": "Noodles & Chopsuey", "items": [{"name": "Veg Noodles", "price": 18.0}, {"name": "Chicken Chopsuey", "price": 20.0}]},
    12: {"name": "Prawns", "items": [{"name": "Fried Prawns", "price": 38.0}]},
    13: {"name": "Rice & Biryani", "items": [{"name": "Chicken Biryani", "price": 26.0}, {"name": "Veg Biryani", "price": 22.0}]},
    14: {"name": "Salads", "items": [{"name": "Greek Salad", "price": 16.0}, {"name": "Caesar Salad", "price": 18.0}]},

    15: {"name": "Seafoods", "items": [{"name": "Grilled Salmon", "price": 42.0}]},
    16: {"name": "Shaw Faw", "items": [{"name": "Shawarma Wrap", "price": 15.0}]},
    17: {"name": "Soft Drink", "items": [{"name": "Coke", "price": 6.0}, {"name": "Pepsi", "price": 6.0}]},
    18: {"name": "Soups", "items": [{"name": "Tomato Soup", "price": 12.0}, {"name": "Chicken Soup", "price": 14.0}]},
}

# ===== تخزين الفواتير لكل طاولة بشكل منفصل =====
# المفتاح: (branch_code, table_number) -> قيمة: قائمة الأصناف
invoices = {}

# هيكل الفاتورة: { 'items': [..], 'customer': {id,name,phone,discount} | None }

def get_invoice_obj(branch_code, table_number):
    key = (branch_code, table_number)
    inv = invoices.get(key)
    if inv is None:

        inv = {'items': [], 'customer': None}
        invoices[key] = inv
    elif isinstance(inv, list):
        # ترقية البنية القديمة إلى الهيكل الجديد
        inv = {'items': inv, 'customer': None}
        invoices[key] = inv
    return inv

# ===== ترقيم الفواتير + توليد TLV للـ ZATCA =====
invoice_counters = {}  # {(branch_code, year): seq}

def next_invoice_no(branch_code: str) -> str:
    year = datetime.now(ZoneInfo("Asia/Riyadh")).year
    key = (branch_code, year)
    invoice_counters[key] = invoice_counters.get(key, 0) + 1
    return f"{branch_code}-{year}-{invoice_counters[key]:03d}"


def zatca_tlv_base64(seller_name: str, vat_number: str, timestamp_iso: str, total_with_vat: float, vat_amount: float) -> str:
    import base64
    def tlv(tag: int, value_bytes: bytes) -> bytes:
        length = len(value_bytes)
        return bytes([tag, length]) + value_bytes
    payload = b"".join([
        tlv(1, (seller_name or "").encode("utf-8")),
        tlv(2, (vat_number or "").encode("utf-8")),
        tlv(3, (timestamp_iso or "").encode("utf-8")),
        tlv(4, f"{total_with_vat:.2f}".encode("utf-8")),
        tlv(5, f"{vat_amount:.2f}".encode("utf-8")),
    ])
    return base64.b64encode(payload).decode("utf-8")

# ===== Templates (inline via DictLoader) =====
branches_html = """
<!DOCTYPE html>
<html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Branches</title></head>
<body>
<h2>Branches</h2>
<div style="margin:8px 0"><a href="{{ url_for('settings_currency') }}">Currency symbol settings</a></div>
{% for branch in branches %}
  <a href=\"{{ url_for('tables_view', branch_code=branch.code) }}\">{{ branch.name }}</a><br>
{% endfor %}
</body>
</html>
"""

tables_html = """
<!DOCTYPE html>
<html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Tables - {{ branch.name }}</title>
<style>
.tables-container { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; padding:20px; }
.table-card { padding:20px; border:1px solid #ccc; text-align:center; border-radius:8px; cursor:pointer; }
.table-card.busy { background:#ff6666; color:white; }
</style>
</head>
<body>
<h2>Branch: {{ branch.name }}</h2>
<div class=\"tables-container\">
{% for table in tables %}
  <div class=\"table-card {% if table.is_busy %}busy{% endif %}\" onclick=\"location.href='{{ url_for('new_invoice', branch_code=branch.code, table_number=table.number) }}'\">
    Table {{ table.number }}
  </div>
{% endfor %}
</div>
</body>
</html>
"""

new_invoice_html = """
<!DOCTYPE html>
<html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Table Invoice {{ table.number }}</title></head>
<body>

  <h2>Table Invoice {{ table.number }} - {{ branch.name }}</h2>





{% with messages = get_flashed_messages() %}
  {% if messages %}
    <ul>{% for msg in messages %}<li style=\"color:red;\">{{ msg }}</li>{% endfor %}</ul>
  {% endif %}
{% endwith %}
















<style>
.content{display:flex;gap:16px;flex-direction:row-reverse;align-items:flex-start}
.right{flex:1}
.left{flex:1}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:10px}
.btn-tile{padding:12px;border:1px solid #ddd;border-radius:10px;background:#f8f9fa;cursor:pointer;font-weight:600}
.btn-tile:hover{background:#e9ecef}
/* Differentiate categories vs items */
.btn-cat{background:#e7f1ff;border-color:#b6d4fe;color:#0b5ed7}
.btn-cat:hover{background:#dbe8ff}
.btn-item{background:#e8fff3;border-color:#b3e5c5;color:#0f5132}
.btn-item:hover{background:#dbffee}
.muted{color:#777}
  <div style=\"margin-top:12px;padding:10px;border:1px dashed #ccc;border-radius:8px\">
    <strong>Customer:</strong>
    <span id=\"cust-name\">—</span> • <span id=\"cust-phone\">—</span>
    <div style=\"margin-top:8px\">
      <input id=\"cust-query\" placeholder=\"Search by name or phone\" style=\"padding:6px\">
      <button type=\"button\" onclick=\"searchCustomer()\">Search</button>
      <span id=\"cust-feedback\" class=\"muted\"></span>
    </div>
    <div id=\"cust-results\" class=\"grid\" style=\"margin-top:8px\"></div>
  </div>

</style>
<div class=\"content\">
  <div class=\"right\">

    <h3>Categories</h3>
    <div id=\"categories-grid\" class=\"grid\"></div>
    <h3 style=\"margin-top:10px\">Items</h3>
    <div id=\"items-grid\" class=\"grid muted\">Select a category to view items</div>
    <form id=\"add-item-form\" method=\"POST\" style=\"display:none\">
      <input type=\"hidden\" name=\"category_id\" id=\"category_id\">
      <input type=\"hidden\" name=\"item_name\" id=\"item_name\">
      <input type="hidden" name="price" id="item_price">

      <input type=\"hidden\" name=\"add_item\" value=\"1\">
    </form>
    <!-- زر الرجوع أسفل الأقسام/الأصناف يمينًا -->
    <div style=\"margin-top:12px\">
      <a href=\"{{ url_for('tables_view', branch_code=branch.code) }}\">⬅️ Back to tables</a>
    </div>
    <!-- نموذج مخفي لحفظ العميل في الفاتورة -->
    <form id="customer-form" method="POST" action="{{ url_for('set_customer', branch_code=branch.code, table_number=table.number) }}" style="display:none">
      <input type="hidden" name="id" id="cust_id">




      <input type="hidden" name="name" id="cust_name">
      <input type="hidden" name="phone" id="cust_phone">
      <input type="hidden" name="discount" id="cust_discount_val">
    </form>




  </div>
  <div class=\"left\" style=\"padding:15px;border:1px solid #eee;border-radius:8px;background:#fafafa;width:100%\">

{% if selected_customer %}
<div style="margin-bottom:10px;padding:8px;border:1px dashed #bbb;border-radius:6px;background:#fff">
  <strong>Customer:</strong> {{ selected_customer.name }} • {{ selected_customer.phone }}
</div>
{% else %}
<div style="margin-bottom:10px;padding:8px;border:1px dashed #bbb;border-radius:6px;background:#fff">
  <strong>Customer:</strong> Cash Customer
</div>
{% endif %}

  <div class=\"muted\" style=\"margin-bottom:10px\">Branch: {{ branch.name }} • Table {{ table.number }} • {{ now_riyadh_str }}</div>


<h3>Items in invoice</h3>
<ul>
{% for it in current_items %}
<li>
  {{ it.name }} — {{ it.price }}
  <button type=\"button\" onclick=\"toggleDelete({{ loop.index0 }})\" style=\"margin-left:8px\">Delete</button>
  <form id=\"del-form-{{ loop.index0 }}\" method=\"POST\" action=\"{{ url_for('delete_item', branch_code=branch.code, table_number=table.number, item_index=loop.index0) }}\" style=\"display:none; margin-top:4px;\">
    <input type=\"password\" name=\"password\" placeholder=\"Password\" autocomplete=\"new-password\" style=\"padding:6px\">
    <button type=\"submit\">Confirm</button>
    <button type=\"button\" onclick=\"toggleDelete({{ loop.index0 }}, true)\">Cancel</button>
  </form>
</li>
{% endfor %}
</ul>

    <!-- لوحة العميل: بحث واختيار (داخل عمود الفاتورة الأيسر) -->
    <div style="margin:10px 0;padding:10px;border:1px dashed #ccc;border-radius:8px;background:#fff">
      <strong>Customer:</strong>
      <div style=\"margin-top:6px\">
        <span id=\"cust-name\">—</span> • <span id=\"cust-phone\">—</span>
      </div>
      <div style=\"margin-top:8px\">
        <input id=\"cust-query\" placeholder=\"Search by name or phone\" style=\"padding:6px\" onkeydown=\"if(event.key==='Enter'){event.preventDefault();searchCustomer();}\">
        <button type=\"button\" onclick=\"searchCustomer()\">Search</button>
        <span id=\"cust-feedback\" class=\"muted\"></span>
      </div>
      <!-- Special customer (KEETA/HUNGER) discount box -->
      <div id="special-cust-box" style="display:none;margin-top:8px;padding:8px;border:1px dashed #aaa;border-radius:6px;background:#f8f9fa">
        <div style="margin-bottom:6px;font-weight:600">Special discount for <span id="special-cust-name"></span></div>
        <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap">
          <label>Discount %:</label>
          <input id="special-discount-pct" type="number" min="0" max="100" step="0.01" value="0" style="width:120px;padding:6px">
          <button type="button" onclick="applySpecialCustomer()">Apply</button>
        </div>
      </div>

      <div id="cust-results" class="grid" style="margin-top:8px"></div>
    </div>

<div style=\"margin:10px 0;padding:8px;border:1px solid #ddd;border-radius:6px;background:#fff\">
  <div>Subtotal: {{ subtotal }}</div>
  <div>Discount ({{ discount_rate or 0 }}%): -{{ discount_amount }}</div>
  <div><strong>Total: {{ total }}</strong></div>
</div>

<h3>Payment options</h3>
<form id=\"payment-form\" method=\"POST\" action=\"{{ url_for('pay_invoice', branch_code=branch.code, table_number=table.number) }}\">
  <select name=\"payment_method\" style=\"margin-top:8px; padding:8px 10px; font-size:16px; height:42px; min-width:220px; border-radius:6px;\">
    <option value=\"CASH\">Cash</option>
    <option value=\"CARD\">Card</option>
    <option value=\"TRANSFER\">Transfer</option>

  </select>







<script>
// بناء شبكة الأقسام والأصناف على اليمين بدل القوائم المنسدلة
const MENU = {{ menu|tojson }}; const CUSTOMERS = {{ customers|tojson }};
function toggleDelete(idx, hide){
  const f = document.getElementById('del-form-'+idx);
  if(!f) return;
  if(hide){ f.style.display='none'; return; }
  f.style.display = (f.style.display==='none' || !f.style.display) ? 'block' : 'none';
  const inp = f.querySelector('input[name="password"]');
  if(inp) inp.focus();
}

let selectedCategory = null;

function buildCategories(){
  const grid = document.getElementById('categories-grid');
  grid.innerHTML = '';
  Object.entries(MENU).forEach(([catId, cat])=>{
    const btn = document.createElement('button');
    btn.className = 'btn-tile btn-cat';
    btn.textContent = cat.name;
    btn.onclick = ()=> selectCategory(catId);
    grid.appendChild(btn);
  });
}


// بيانات العملاء محليًا
let selectedCustomer = null;

function searchCustomer(){
  const inp = document.getElementById('cust-query');
  const q = (inp && inp.value ? inp.value : '').toLowerCase();
  const up = (inp && inp.value ? inp.value : '').trim().toUpperCase();
  const results = document.getElementById('cust-results');
  const fb = document.getElementById('cust-feedback');
  results.innerHTML = '';
  fb.textContent = '';
  // Always toggle special box based on current input
  toggleSpecialBox();
  if(!q){ fb.textContent = 'Enter a name or phone number'; return; }
  const matches = CUSTOMERS.filter(c=> (String(c.name).toLowerCase().includes(q) || String(c.phone).includes(q)) );
  // If special customer, don't block on "No results" — show the box and allow Apply
  if(matches.length===0){
    if(!(up==='KEETA' || up==='HUNGER')){ fb.textContent='No results'; }
    return;
  }
  matches.forEach(c=>{
    const btn = document.createElement('button');
    btn.className = 'btn-tile';
    btn.textContent = `${c.name} • ${c.phone}`;
    btn.onclick = ()=> selectCustomer(c);
    results.appendChild(btn);
  });
}

function selectCustomer(c){
  selectedCustomer = c;
  document.getElementById('cust-name').textContent = c.name || '-';
  document.getElementById('cust-phone').textContent = c.phone || '-';

  // حفظ العميل في الخادم لربط الخصم بالفاتورة
  const f = document.getElementById('customer-form');
  if(f){
    document.getElementById('cust_id').value = c.id || '';
    document.getElementById('cust_name').value = c.name || '';
    document.getElementById('cust_phone').value = c.phone || '';
    document.getElementById('cust_discount_val').value = c.discount || 0;
    f.submit();
  }
}



function selectCategory(catId){
  selectedCategory = catId;
  document.getElementById('category_id').value = catId;
  const itemsGrid = document.getElementById('items-grid');
  itemsGrid.classList.remove('muted');
  itemsGrid.innerHTML = '';
  const arr = (MENU[catId].items || []);
  arr.forEach(it=>{
    const name = (typeof it === 'string') ? it : (it.name || '');
    const price = (typeof it === 'string') ? 0 : (Number(it.price) || 0);
    const btn = document.createElement('button');
    btn.className = 'btn-tile btn-item';
    btn.textContent = price ? `${name} • ${price.toFixed(2)}` : name;
    btn.onclick = ()=> addItem(catId, name, price);
    itemsGrid.appendChild(btn);
  });
}

function addItem(catId, itemName, price){
  const f = document.getElementById('add-item-form');
  document.getElementById('category_id').value = catId;
  document.getElementById('item_name').value = itemName;
  const p = document.getElementById('item_price');
  if(p){ p.value = price || 0; }
  f.submit();
}

// عند التحميل: ابنِ شبكة الأقسام فقط

// Toggle special box visibility based on input
function toggleSpecialBox(){
  const inp = document.getElementById('cust-query');
  if(!inp) return;
  const up = (inp.value||'').trim().toUpperCase();
  const box = document.getElementById('special-cust-box');
  const lbl = document.getElementById('special-cust-name');
  if(box && lbl){
    if(up==='KEETA' || up==='HUNGER'){ box.style.display='block'; lbl.textContent = up; }
    else { box.style.display='none'; }
  }
}

// Apply special customer (KEETA/HUNGER) with entered discount
function applySpecialCustomer(){
  const inp = document.getElementById('cust-query');
  const up = (inp && inp.value ? inp.value : '').trim().toUpperCase();
  if(!(up==='KEETA' || up==='HUNGER')){ alert('Type KEETA or HUNGER in the search box first'); return; }
  const pctEl = document.getElementById('special-discount-pct');
  const pct = parseFloat(pctEl && pctEl.value ? pctEl.value : '0');
  if(isNaN(pct) || pct<0 || pct>100){ alert('Enter a valid discount 0-100'); return; }
  // Update visible labels
  const nameSpan = document.getElementById('cust-name');
  const phoneSpan = document.getElementById('cust-phone');
  if(nameSpan) nameSpan.textContent = up;
  if(phoneSpan) phoneSpan.textContent = '-';
  // Submit hidden form to link customer to invoice
  const f = document.getElementById('customer-form');
  if(f){
    document.getElementById('cust_id').value = '';
    document.getElementById('cust_name').value = up;
    document.getElementById('cust_phone').value = '';
    document.getElementById('cust_discount_val').value = pct.toString();
    f.submit();
  }
}

// Attach input listener for KEETA/HUNGER detection
(function(){
  const inp = document.getElementById('cust-query');
  if(inp){
    inp.addEventListener('input', toggleSpecialBox);
    // Initialize visibility
    toggleSpecialBox();
  }
})();

buildCategories();
</script>
</div> <!-- left -->
</div> <!-- content -->














</form>

<!-- أزرار أسفل الفاتورة: طباعة قبل الدفع، دفع وطباعة، إلغاء الفاتورة -->
<div class=\"invoice-footer\" style=\"margin-top:20px;padding:12px;border-top:1px solid #ddd;display:flex;gap:10px;flex-wrap:wrap;justify-content:flex-start\">
  <button type=\"button\" onclick=\"window.open('{{ url_for('preview_receipt', branch_code=branch.code, table_number=table.number) }}','_blank')\" style=\"padding:8px 12px;background:#007bff;color:#fff;border:none;border-radius:6px;cursor:pointer\">🖨️ Print before payment</button>
  <button type=\"submit\" form=\"payment-form\" style=\"padding:8px 12px;background:#28a745;color:#fff;border:none;border-radius:6px;cursor:pointer\">💳 Pay & Print</button>
  <button type=\"button\" onclick=\"document.getElementById('cancel-form').style.display='block'\" style=\"padding:8px 12px;background:#dc3545;color:#fff;border:none;border-radius:6px;cursor:pointer\">❌ Cancel invoice</button>
</div>

<!-- نموذج إلغاء الفاتورة (مخفي حتى الضغط) -->
<div id=\"cancel-form\" style=\"display:none;margin-top:10px;padding:10px;border:1px solid #dc3545;border-radius:6px;background:#f8d7da\">
  <form method=\"POST\" action=\"{{ url_for('cancel_invoice', branch_code=branch.code, table_number=table.number) }}\" style=\"display:flex;gap:8px;align-items:center;flex-wrap:wrap\">
    <label>Cancel password:</label>
    <input type=\"password\" name=\"password\" placeholder=\"Enter password\" autocomplete=\"new-password\" style=\"padding:6px\">
    <button type=\"submit\" style=\"padding:6px 10px;background:#dc3545;color:#fff;border:none;border-radius:4px\">Confirm cancel</button>
    <button type=\"button\" onclick=\"document.getElementById('cancel-form').style.display='none'\" style=\"padding:6px 10px;background:#6c757d;color:#fff;border:none;border-radius:4px\">Close</button>
  </form>
</div>























</body>
</html>
"""

receipt_html = """
<!DOCTYPE html>
<html lang=\"en\"><head>
  <meta charset=\"UTF-8\">
  <title>Receipt - {{ settings.restaurant_name }} - {{ location_name }} - Table {{ table.number }}</title>
  <style>
    /* تصميم للشاشة والطباعة الحرارية 80mm */
    body{
      font-family:Tahoma,Arial,sans-serif;
      direction:ltr;
      margin:0;
      padding:8px;
      width:80mm;
      max-width:80mm;
      font-size:12px;
      line-height:1.3;
    }
    .header,.footer{ text-align:center; margin-bottom:8px }
    .row{ display:flex; justify-content:space-between; align-items:flex-start; margin:4px 0 }
    .muted{ color:#666; font-size:10px }
    table{ width:100%; border-collapse:collapse; margin:6px 0; font-size:11px }
    th,td{ border:1px solid #ddd; padding:3px; text-align:right }
    th{ background:#f3f3f3; font-weight:bold }
    .totals{ margin:8px 0; padding:6px; border:1px solid #ddd; border-radius:4px; font-size:11px }
      .cur-img{ height:10px; vertical-align:text-bottom; margin-inline-start:3px }
      .cur-code{ color:#666; font-size:10px; margin-inline-start:3px }


    /* إعدادات الطباعة للطابعات الحرارية 80mm */
    @media print {
      body{
        width:80mm;
        max-width:80mm;
        margin:0;
        padding:4px;
        font-size:10px;
      }
      .no-print{ display:none }
      table{ font-size:9px }
      th,td{ padding:2px }
    }
  </style>
</head>
<body>
  <div class=\"header\">
    {% if settings.logo_base64 %}
      <img src=\"data:image/png;base64,{{ settings.logo_base64 }}\" alt=\"logo\" style=\"height:64px\"><br>
    {% endif %}
    <div style=\"font-weight:bold; font-size:18px\">{{ settings.restaurant_name }}</div>
    <div class=\"muted\">VAT: {{ settings.vat_number }} • {{ settings.address }} • {{ settings.phone }}</div>
    <div class=\"muted\">{{ now_riyadh_str }} (Asia/Riyadh)</div>
  </div>
  <hr>
  <div style=\"margin:8px 0; font-size:11px\">
    <div><strong>Location:</strong> {{ location_name }}</div>
    <div><strong>Invoice No:</strong> {{ invoice_no }}</div>
    <div><strong>Table:</strong> {{ table.number }}</div>
    <div><strong>Customer:</strong> {{ (customer.name if customer else 'Cash Customer') }}</div>
    {% if customer and customer.phone %}
    <div><strong>Customer phone:</strong> {{ customer.phone }}</div>
    {% endif %}
  </div>
  <h3 style=\"margin-top:10px\">Items</h3>
  <table>
    <thead>
      <tr>
        <th>Item</th>
        <th>Qty</th>
        <th>Unit price</th>
        <th>Line total</th>
      </tr>
    </thead>
    <tbody>
      {% for it in items %}
      <tr>
        <td>{{ it.name }}</td>
        <td style=\"text-align:center\">{{ it.qty }}</td>
        <td style=\"text-align:center\">{{ it.price }} {% if currency_png_base64 %}<img class=\"cur-img\" src=\"data:image/png;base64,{{ currency_png_base64 }}\" alt=\"cur\">{% elif currency_code %}<span class=\"cur-code\">{{ currency_code }}</span>{% endif %}</td>
        <td style=\"text-align:center\">{{ it.line_total }} {% if currency_png_base64 %}<img class=\"cur-img\" src=\"data:image/png;base64,{{ currency_png_base64 }}\" alt=\"cur\">{% elif currency_code %}<span class=\"cur-code\">{{ currency_code }}</span>{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  <div class=\"totals\">
    <div>Subtotal: {{ subtotal }} {% if currency_png_base64 %}<img class="cur-img" src="data:image/png;base64,{{ currency_png_base64 }}" alt="cur">{% elif currency_code %}<span class="cur-code">{{ currency_code }}</span>{% endif %}</div>
    {% if discount_amount > 0 %}
    <div>Discount ({{ discount_rate or 0 }}%): -{{ discount_amount }} {% if currency_png_base64 %}<img class="cur-img" src="data:image/png;base64,{{ currency_png_base64 }}" alt="cur">{% elif currency_code %}<span class="cur-code">{{ currency_code }}</span>{% endif %}</div>
    {% endif %}
    <div>Total before VAT: {{ total }} {% if currency_png_base64 %}<img class="cur-img" src="data:image/png;base64,{{ currency_png_base64 }}" alt="cur">{% elif currency_code %}<span class="cur-code">{{ currency_code }}</span>{% endif %}</div>
    <div>VAT ({{ vat_rate }}%): {{ vat_amount }} {% if currency_png_base64 %}<img class="cur-img" src="data:image/png;base64,{{ currency_png_base64 }}" alt="cur">{% elif currency_code %}<span class="cur-code">{{ currency_code }}</span>{% endif %}</div>
    <div style=\"font-weight:bold; border-top:1px solid #ccc; padding-top:4px; margin-top:4px\">
      Grand total: {{ grand_total }} {% if currency_png_base64 %}<img class=\"cur-img\" src=\"data:image/png;base64,{{ currency_png_base64 }}\" alt=\"cur\">{% elif currency_code %}<span class=\"cur-code\">{{ currency_code }}</span>{% endif %}
    </div>
  </div>

  <!-- QR Code متوافق مع ZATCA -->
  <div class=\"footer\" style=\"margin:12px 0\">
    <img src=\"https://api.qrserver.com/v1/create-qr-code/?size=120x120&data={{ zatca_qr_b64 }}\" alt=\"ZATCA QR\" style=\"max-width:120px\"><br>
    <div class=\"muted\">ZATCA-compliant QR</div>
  </div>

  <!-- رسالة الشكر -->
  <div class=\"footer\" style=\"margin:8px 0; border-top:1px dashed #ccc; padding-top:8px\">
    <div style=\"font-size:11px\">Thank you for your visit</div>

  </div>

  <!-- أزرار التحكم (مخفية عند الطباعة) -->
  <div class=\"no-print\" style=\"margin-top:12px; text-align:center; border-top:1px solid #ddd; padding-top:8px\">
    <button onclick=\"window.print()\" type=\"button\" style=\"padding:8px 12px; background:#007bff; color:#fff; border:none; border-radius:4px; margin:4px\">🖨️ Print</button>
    <form method=\"POST\" action=\"{{ url_for('confirm_payment', branch_code=branch.code, table_number=table.number) }}\" style=\"display:inline\">
      <input type=\"hidden\" name=\"payment_method\" value=\"{{ payment_method }}\">
      <button type=\"submit\" style=\"padding:8px 12px; background:#28a745; color:#fff; border:none; border-radius:4px; margin:4px\">✔️ Confirm payment & finish</button>
    </form>
    <br>
    <a href=\"{{ url_for('new_invoice', branch_code=branch.code, table_number=table.number) }}\" style=\"color:#6c757d; text-decoration:none; font-size:11px\">← Back to invoice</a>
  </div>
</body></html>
"""

# Settings page to upload/paste currency symbol
settings_currency_html = """
<!DOCTYPE html>
<html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Currency Symbol</title></head>
<body>
<h2>Currency Symbol</h2>
<p>Current preview:</p>
{% if settings.currency_png_base64 %}
  <img src=\"data:image/png;base64,{{ settings.currency_png_base64 }}\" style=\"height:24px\" alt=\"currency\">
{% else %}
  <span>No symbol set</span>
{% endif %}
<form method=\"POST\" enctype=\"multipart/form-data\" style=\"margin-top:10px\">
  <div><label>Upload PNG:</label> <input type=\"file\" name=\"file\" accept=\"image/png\"></div>
  <div style=\"margin-top:6px\"><label>Or paste Base64:</label><br>
    <textarea name=\"base64\" rows=\"4\" cols=\"60\" placeholder=\"iVBOR...\"></textarea>
  </div>
  <button type=\"submit\" style=\"margin-top:8px\">Save</button>
</form>
<div style=\"margin-top:12px\"><a href=\"{{ url_for('branches_view') }}\">\u2190 Back</a></div>
</body>
</html>
"""


app.jinja_loader = DictLoader({
    "branches.html": branches_html,
    "tables.html": tables_html,
    "new_invoice.html": new_invoice_html,
    "receipt.html": receipt_html,
    "settings_currency.html": settings_currency_html,
})

# ===== Routes =====
# مسار افتراضي للصفحة الرئيسية → تحويل للفروع
@app.route("/")
def index():
    return redirect(url_for("branches_view"))

# مسار ملائم: /sales → تحويل للفروع أيضًا
@app.route("/sales")
def sales_root():
    return redirect(url_for("branches_view"))


# شاشة الفروع
@app.route("/branches")
def branches_view():
    return render_template("branches.html", branches=branches)


# Settings: upload/paste currency symbol (PNG base64)
@app.route("/settings/currency", methods=["GET","POST"])
def settings_currency():
    if request.method == "POST":
        b64 = (request.form.get("base64") or "").strip()
        file = request.files.get("file")
        import base64
        updated = False
        if file and getattr(file, 'filename', ''):
            data = file.read()
            try:
                settings["currency_png_base64"] = base64.b64encode(data).decode("utf-8")
                flash("Currency symbol updated from file")
                updated = True
            except Exception:
                flash("Failed to read file")
        elif b64:
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            b64 = b64.replace("\n","").replace("\r","")
            try:
                base64.b64decode(b64, validate=True)
                settings["currency_png_base64"] = b64
                flash("Currency symbol updated from base64")
                updated = True
            except Exception:
                flash("Invalid base64 string")
        else:
            flash("No file or base64 provided")
        return redirect(url_for("settings_currency"))
    return render_template("settings_currency.html", settings=settings)

# شاشة الطاولات
@app.route("/sales/<branch_code>/tables")
def tables_view(branch_code):
    branch = next((b for b in branches if b["code"] == branch_code), None)
    tables = tables_data.get(branch_code, [])
    return render_template("tables.html", branch=branch, tables=tables)

# إنشاء الفاتورة أو عرضها
@app.route("/sales/<branch_code>/table/<int:table_number>/new_invoice", methods=["GET", "POST"])
def new_invoice(branch_code, table_number):
    branch = next((b for b in branches if b["code"] == branch_code), None)
    table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)

    # إضافة صنف
    if request.method == "POST" and "add_item" in request.form:
        item_name = request.form.get("item_name")
        price = float(request.form.get("price") or 0)
        inv = get_invoice_obj(branch_code, table_number)
        inv['items'].append({"name": item_name, "price": price, "qty": 1})
        table["is_busy"] = True  # الطاولة تصبح مشغولة
        return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))

    inv = get_invoice_obj(branch_code, table_number)
    # تطبيع العناصر إلى {name, price, qty, line_total}
    normalized = []
    for it in inv['items']:
        if isinstance(it, dict):
            name = it.get('name')
            price = float(it.get('price') or 0)
            qty = int(it.get('qty') or 1)
        else:
            name = str(it)
            price = 0.0
            qty = 1
        normalized.append({'name': name, 'price': price, 'qty': qty, 'line_total': round(price*qty, 2)})
    subtotal = round(sum(i['line_total'] for i in normalized), 2)
    cust = inv.get('customer') or {}
    discount_rate = float((cust.get('discount') if isinstance(cust, dict) else 0) or 0)
    discount_amount = round(subtotal * (discount_rate/100.0), 2)
    total = round(subtotal - discount_amount, 2)
    vat_rate = 15.0
    vat_amount = round(total * (vat_rate/100.0), 2)
    grand_total = round(total + vat_amount, 2)
    now_riyadh_str = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d %H:%M")
    return render_template(
        "new_invoice.html",
        branch=branch,
        table=table,
        menu=menu_data,
        customers=customers_data,
        current_items=normalized,
        selected_customer=inv.get('customer'),
        subtotal=subtotal,
        discount_rate=discount_rate,
        discount_amount=discount_amount,
        total=total,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        grand_total=grand_total,
        now_riyadh_str=now_riyadh_str,
        settings=settings
    )

# معاينة الإيصال قبل الدفع (80mm) دون إظهار طريقة الدفع
@app.route("/sales/<branch_code>/table/<int:table_number>/preview", methods=["GET"])
def preview_receipt(branch_code, table_number):
    branch = next((b for b in branches if b["code"] == branch_code), None)
    table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
    inv = get_invoice_obj(branch_code, table_number)

    # تطبيع العناصر وحساب الإجماليات
    normalized = []
    for it in inv['items']:
        if isinstance(it, dict):
            name = it.get('name')
            price = float(it.get('price') or 0)
            qty = int(it.get('qty') or 1)
        else:
            name = str(it)
            price = 0.0
            qty = 1
        normalized.append({'name': name, 'price': price, 'qty': qty, 'line_total': round(price*qty, 2)})

    subtotal = round(sum(i['line_total'] for i in normalized), 2)
    cust = inv.get('customer') or {}
    discount_rate = float((cust.get('discount') if isinstance(cust, dict) else 0) or 0)
    discount_amount = round(subtotal * (discount_rate/100.0), 2)
    total = round(subtotal - discount_amount, 2)
    vat_rate = 15.0
    vat_amount = round(total * (vat_rate/100.0), 2)
    grand_total = round(total + vat_amount, 2)

    # تأكيد رقم الفاتورة للعرض فقط (قبل التأكيد)
    if not inv.get('invoice_no'):
        inv['invoice_no'] = next_invoice_no(branch_code)
    invoice_no = inv['invoice_no']

    timestamp_iso = datetime.now(ZoneInfo("Asia/Riyadh")).isoformat()
    zatca_qr_b64 = zatca_tlv_base64(settings.get('restaurant_name'), settings.get('vat_number'), timestamp_iso, grand_total, vat_amount)

    return render_template(
        "receipt.html",
        branch=branch,
        table=table,
        items=normalized,
        customer=inv.get('customer'),
        payment_method="",  # لا نعرض طريقة الدفع في المعاينة
        subtotal=subtotal,
        discount_rate=discount_rate,
        discount_amount=discount_amount,
        total=total,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        grand_total=grand_total,
        now_riyadh_str=datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d %H:%M"),
        settings=settings,
        invoice_no=invoice_no,
        location_name=branch.get('name'),
        currency_code=settings.get('currency_code'),
        currency_png_base64=settings.get('currency_png_base64'),
        zatca_qr_b64=zatca_qr_b64
    )

# حذف صنف مع كلمة سر
@app.route("/sales/<branch_code>/table/<int:table_number>/delete_item/<int:item_index>", methods=["POST"])
def delete_item(branch_code, table_number, item_index):
    password = request.form.get("password")
    if password != "1991":
        flash("Wrong password!")
        return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))
    inv = get_invoice_obj(branch_code, table_number)
    if 0 <= item_index < len(inv['items']):
        inv['items'].pop(item_index)
    # إذا أصبحت الفاتورة فارغة، نجعل الطاولة فارغة
    if not inv['items']:
        table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
        table["is_busy"] = False
    return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))

# إلغاء الفاتورة مع كلمة سر
@app.route("/sales/<branch_code>/table/<int:table_number>/cancel_invoice", methods=["POST"])
def cancel_invoice(branch_code, table_number):
    password = request.form.get("password")
    if password != "1991":
        flash("Wrong password!")
        return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))
    invoices.pop((branch_code, table_number), None)
    table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
    table["is_busy"] = False
    return redirect(url_for("tables_view", branch_code=branch_code))

# الدفع وطباعة الفاتورة مباشرة
@app.route("/sales/<branch_code>/table/<int:table_number>/pay", methods=["POST"])
def pay_invoice(branch_code, table_number):
    payment_method = request.form.get("payment_method")
    branch = next((b for b in branches if b["code"] == branch_code), None)
    table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
    inv = get_invoice_obj(branch_code, table_number)
    # تطبيع العناصر وحساب الإجماليات
    normalized = []
    for it in inv['items']:
        if isinstance(it, dict):
            name = it.get('name')
            price = float(it.get('price') or 0)
            qty = int(it.get('qty') or 1)
        else:
            name = str(it)
            price = 0.0
            qty = 1
        normalized.append({'name': name, 'price': price, 'qty': qty, 'line_total': round(price*qty, 2)})
    subtotal = round(sum(i['line_total'] for i in normalized), 2)
    cust = inv.get('customer') or {}
    discount_rate = float((cust.get('discount') if isinstance(cust, dict) else 0) or 0)
    discount_amount = round(subtotal * (discount_rate/100.0), 2)
    total = round(subtotal - discount_amount, 2)
    vat_rate = 15.0
    vat_amount = round(total * (vat_rate/100.0), 2)
    grand_total = round(total + vat_amount, 2)
    now_riyadh_str = datetime.now(ZoneInfo("Asia/Riyadh")).strftime("%Y-%m-%d %H:%M")
    if not inv.get('invoice_no'):
        inv['invoice_no'] = next_invoice_no(branch_code)
    invoice_no = inv['invoice_no']
    timestamp_iso = datetime.now(ZoneInfo("Asia/Riyadh")).isoformat()
    zatca_qr_b64 = zatca_tlv_base64(settings.get('restaurant_name'), settings.get('vat_number'), timestamp_iso, grand_total, vat_amount)

    # لا نقوم بالإفراغ الآن؛ نعرض صفحة الدفع/الطباعة أولاً
    return render_template(
        "receipt.html",
        branch=branch,
        table=table,
        items=normalized,
        customer=inv.get('customer'),
        payment_method=payment_method,
        subtotal=subtotal,
        discount_rate=discount_rate,
        discount_amount=discount_amount,
        total=total,
        vat_rate=vat_rate,
        vat_amount=vat_amount,
        grand_total=grand_total,
        now_riyadh_str=now_riyadh_str,
        settings=settings,
        invoice_no=invoice_no,
        location_name=branch.get('name'),
        currency_code=settings.get('currency_code'),
        currency_png_base64=settings.get('currency_png_base64'),
        zatca_qr_b64=zatca_qr_b64
    )

@app.route("/sales/<branch_code>/table/<int:table_number>/pay/confirm", methods=["POST"])
def confirm_payment(branch_code, table_number):
    payment_method = request.form.get("payment_method")
    # إنهاء العملية: تفريغ الفاتورة وتفريغ الطاولة
    invoices.pop((branch_code, table_number), None)
    table = next((t for t in tables_data[branch_code] if t["number"] == table_number), None)
    table["is_busy"] = False
    flash(f"Payment successful via {payment_method}. Invoice posted.")
    return redirect(url_for("tables_view", branch_code=branch_code))

@app.route("/sales/<branch_code>/table/<int:table_number>/set_customer", methods=["POST"])
def set_customer(branch_code, table_number):
    inv = get_invoice_obj(branch_code, table_number)
    inv['customer'] = {
        'id': request.form.get('id'),
        'name': request.form.get('name'),
        'phone': request.form.get('phone'),
        'discount': float(request.form.get('discount') or 0)
    }
    flash("Customer linked to invoice")
    return redirect(url_for("new_invoice", branch_code=branch_code, table_number=table_number))

if __name__ == "__main__":
    # Run on all interfaces so you can open from this PC or others; use stable single-process server
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)

