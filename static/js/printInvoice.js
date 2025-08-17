(function(){
  // Provide a fallback payAndPrint if not defined by the page
  if (typeof window.payAndPrint === 'function') return;

  window.payAndPrint = async function(){
    try{
      const itemsSrc = Array.isArray(window.items) ? window.items : [];
      const items = itemsSrc.map(x => ({ meal_id: x.meal_id, qty: x.qty }));
      if(items.length === 0){
        alert('Add at least one item / أضف عنصراً واحداً على الأقل');
        return;
      }
      const payload = {
        branch_code: (window.BRANCH_CODE || document.body?.dataset?.branch || ''),
        table_no: Number(window.TABLE_NO || document.body?.dataset?.table || 0),
        items,
        customer_name: document.getElementById('custName')?.value || '',
        customer_phone: document.getElementById('custPhone')?.value || '',
        discount_pct: parseFloat(document.getElementById('discountPct')?.value || '0'),
        tax_pct: parseFloat(document.getElementById('taxPct')?.value || '0'),
        payment_method: document.getElementById('payMethod')?.value || 'CASH'
      };

      const headers = { 'Content-Type': 'application/json' };
      const token = document.querySelector('meta[name="csrf-token"]')?.content || document.getElementById('csrfTokenPage')?.value;
      if(token){ headers['X-CSRFToken'] = token; }

      const res = await fetch('/api/sales/checkout', {
        method: 'POST', headers, credentials: 'same-origin', body: JSON.stringify(payload)
      });
      if(!res.ok){
        const txt = await res.text();
        alert(txt || ('HTTP '+res.status));
        return;
      }
      const data = await res.json().catch(()=>null);
      if(!data || !data.ok){ alert((data && data.error) || 'Error'); return; }
      window.open(data.print_url, '_blank');
    }catch(e){
      console.error(e);
      alert('Error while paying/printing');
    }
  };
})();

