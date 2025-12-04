// Restaurant Management System - Main JavaScript

// Global variables
window.restaurantApp = {
    currentBranch: null,
    currentTable: null,
    cart: [],
    settings: {}
};

// Utility functions
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type} alert-dismissible slide-right`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container') || document.body;
    container.insertBefore(alertDiv, container.firstChild);
    requestAnimationFrame(()=>{ alertDiv.classList.add('show'); });
    try{ if(window.gsap){ gsap.from(alertDiv, { y:-20, opacity:0, duration:0.4, ease:'back.out(1.2)' }); } }catch(_e){}
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        if (alertDiv.parentNode) {
            alertDiv.remove();
        }
    }, 5000);
}

function showLoading(show = true) {
    let loader = document.getElementById('loading-spinner');
    if (show) {
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'loading-spinner';
            loader.className = 'spinner';
            document.body.appendChild(loader);
        }
        loader.style.display = 'block';
    } else {
        if (loader) {
            loader.style.display = 'none';
        }
    }
}

// Confirmation dialog - removed to avoid conflict with modal-system.js

// API helper functions
async function apiCall(url, options = {}) {
    try {
        showLoading(true);
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('API Error:', error);
        showAlert(`خطأ في الاتصال: ${error.message}`, 'danger');
        throw error;
    } finally {
        showLoading(false);
    }
}

// POS System functions
function addToCart(product) {
    const existingItem = window.restaurantApp.cart.find(item => item.id === product.id);
    
    if (existingItem) {
        existingItem.quantity += 1;
    } else {
        window.restaurantApp.cart.push({
            ...product,
            quantity: 1
        });
    }
    
    updateCartDisplay();
    showAlert(`تم إضافة ${product.name} إلى السلة`, 'success');
}

function removeFromCart(productId) {
    window.restaurantApp.cart = window.restaurantApp.cart.filter(item => item.id !== productId);
    updateCartDisplay();
    showAlert('تم حذف الصنف من السلة', 'info');
}

function updateCartDisplay() {
    const cartContainer = document.getElementById('cart-items');
    const totalContainer = document.getElementById('cart-total');
    
    if (!cartContainer) return;
    
    cartContainer.innerHTML = '';
    let total = 0;
    
    window.restaurantApp.cart.forEach(item => {
        const itemTotal = item.price * item.quantity;
        total += itemTotal;
        
        const itemDiv = document.createElement('div');
        itemDiv.className = 'invoice-item';
        itemDiv.innerHTML = `
            <div>
                <strong>${item.name}</strong><br>
                <small>${item.quantity} × ${item.price.toFixed(2)} ريال</small>
            </div>
            <div>
                <span class="me-2">${itemTotal.toFixed(2)} ريال</span>
                <button class="btn btn-sm btn-outline-danger" onclick="removeFromCart(${item.id})">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        cartContainer.appendChild(itemDiv);
    });
    
    if (totalContainer) {
        totalContainer.textContent = `${total.toFixed(2)} ريال`;
    }
}

// Table management functions
function selectTable(tableNumber, branchCode) {
    window.restaurantApp.currentTable = tableNumber;
    window.restaurantApp.currentBranch = branchCode;
    
    // Update UI to show selected table
    document.querySelectorAll('.table-card').forEach(card => {
        card.classList.remove('selected');
    });
    
    const selectedCard = document.querySelector(`[data-table="${tableNumber}"]`);
    if (selectedCard) {
        selectedCard.classList.add('selected');
    }
    
    showAlert(`تم اختيار الطاولة رقم ${tableNumber}`, 'success');
}

// Form validation
function validateForm(formOrId) {
    const form = (typeof formOrId === 'string') ? document.getElementById(formOrId) : formOrId;
    if (!form) return true; // لا تمنع الإرسال إذا لم نجد النموذج

    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;

    requiredFields.forEach(field => {
        if (!field.value || !field.value.toString().trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
        }
    });

    return isValid;
}

// Print functions
function printInvoice(invoiceId) {
    const printWindow = window.open(`/print/invoice/${invoiceId}`, '_blank');
    printWindow.onload = function() {
        printWindow.print();
    };
}

function printReport() {
    window.print();
}

function __initUI(){
    console.log('Restaurant Management System initialized');
    
    // Initialize tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined') {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function (tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }
    
    // Initialize any existing cart data
    updateCartDisplay();
    
    // Dashboard cards: rely on anchor default navigation (avoid programmatic redirects)
    document.querySelectorAll('.dashboard-card').forEach(card => {
        card.addEventListener('click', function(e) {
            const link = this.closest('a');
            if (link) {
                try { link.click(); } catch(_e) { window.location.assign(link.href); }
            }
        });
    });

    document.querySelectorAll('.dashboard-card, .sales-card, #tables-root a.btn, .product-card, .item-card, .invoice-container, .pos-container').forEach(el=>{
        el.classList.add('fade-in');
        requestAnimationFrame(()=>{ el.classList.add('show'); });
    });
    // Fallback: ensure any element with fade classes becomes visible even if not targeted above
    document.querySelectorAll('.fade-in, .fade-slide').forEach(el=>{
        if(!el.classList.contains('show')){ requestAnimationFrame(()=> el.classList.add('show')); }
    });

    document.querySelectorAll('.btn-primary, .btn-success, .btn-danger, .btn-outline-primary, .btn-outline-success, .btn-outline-danger').forEach(el=>{
        el.classList.add('scale-hover');
    });

    function animateOnLoad(selector, delay){
        const els = document.querySelectorAll(selector);
        els.forEach((el, i)=>{ setTimeout(()=>{ el.classList.add('show'); }, (delay||0) + i*100); });
    }
    window.animateOnLoad = animateOnLoad;
    animateOnLoad('.dashboard-card', 100);
    animateOnLoad('.item-card', 200);
    animateOnLoad('.invoice-container', 300);
    animateOnLoad('.alert', 400);
    // Fallback: force alerts visible
    document.querySelectorAll('.alert').forEach(el=>{ el.classList.add('show'); });

    document.querySelectorAll('.btn').forEach(btn=>{ btn.classList.add('ripple'); btn.classList.add('btn-glow'); });
    document.querySelectorAll('.ripple').forEach(button=>{
        button.addEventListener('click', function(e){
            const circle = document.createElement('span');
            circle.className = 'ripple-effect';
            this.appendChild(circle);
            const d = Math.max(this.clientWidth, this.clientHeight);
            circle.style.width = circle.style.height = d + 'px';
            const rect = this.getBoundingClientRect();
            const cx = (e.clientX - rect.left - d/2);
            const cy = (e.clientY - rect.top - d/2);
            circle.style.left = cx + 'px';
            circle.style.top = cy + 'px';
            setTimeout(()=>{ try{ circle.remove(); }catch(_){} }, 600);

            const ring = document.createElement('span');
            ring.className = 'click-ring';
            ring.style.width = ring.style.height = d + 'px';
            ring.style.left = cx + 'px';
            ring.style.top = cy + 'px';
            this.appendChild(ring);
            setTimeout(()=>{ try{ ring.remove(); }catch(_){} }, 520);

            const count = 10;
            for(let i=0;i<count;i++){
                const p = document.createElement('span');
                p.className = 'sparkle';
                p.style.left = (e.clientX - rect.left) + 'px';
                p.style.top = (e.clientY - rect.top) + 'px';
                this.appendChild(p);
                const ang = Math.random()*Math.PI*2;
                const rad = 30 + Math.random()*40;
                const dx = Math.cos(ang)*rad;
                const dy = Math.sin(ang)*rad;
                if(window.gsap){
                    try{ gsap.fromTo(p, { opacity:1, scale:0.9 }, { x:dx, y:dy, scale:0.1, opacity:0, duration:0.6, ease:'power2.out', onComplete: function(){ try{ p.remove(); }catch(_){} } }); }catch(_e){}
                } else {
                    p.style.setProperty('--dx', dx + 'px');
                    p.style.setProperty('--dy', dy + 'px');
                    p.classList.add('animate');
                    setTimeout(()=>{ try{ p.remove(); }catch(_){} }, 620);
                }
            }
        });
        button.addEventListener('mousedown', function(){ try{ this.classList.add('pulse'); setTimeout(()=>{ try{ this.classList.remove('pulse'); }catch(_){} }, 300); }catch(_e){} });
    });

    document.querySelectorAll('.dashboard-card, .product-card, .item-card, .btn').forEach(el=>{
        el.classList.add('hover-reflect');
        el.addEventListener('mousemove', function(e){
            const r = this.getBoundingClientRect();
            const x = ((e.clientX - r.left)/r.width)*100;
            const y = ((e.clientY - r.top)/r.height)*100;
            this.style.setProperty('--mx', x+'%');
            this.style.setProperty('--my', y+'%');
        });
    });

    try{
        if(window.gsap){
            const dc = document.querySelectorAll('.dashboard-card');
            if(dc.length){ gsap.from(dc, { opacity:0, y:20, duration:0.6, ease:'back.out(1.4)', stagger:0.08 }); }
            const ic = document.querySelectorAll('.item-card');
            if(ic.length){ gsap.from(ic, { opacity:0, y:24, duration:0.5, ease:'power3.out', stagger:0.05 }); }
            const inv = document.querySelectorAll('.invoice-container');
            if(inv.length){ gsap.from(inv, { opacity:0, y:-30, scale:0.98, duration:0.5, ease:'back.out(1.6)' }); }
            const btns = document.querySelectorAll('.btn');
            btns.forEach(b=>{
                b.addEventListener('mousedown', ()=>{ try{ gsap.to(b, { scale:0.97, rotate:0.5, duration:0.08, ease:'power1.out' }); }catch(_e){} });
                b.addEventListener('mouseup', ()=>{ try{ gsap.to(b, { scale:1, rotate:0, duration:0.12, ease:'power2.out' }); }catch(_e){} });
                b.addEventListener('mouseleave', ()=>{ try{ gsap.to(b, { scale:1, rotate:0, duration:0.12 }); }catch(_e){} });
            });
            const cards = document.querySelectorAll('.dashboard-card, .product-card');
            cards.forEach(c=>{
                c.addEventListener('mouseenter', ()=>{ try{ gsap.to(c, { scale:1.03, rotate:0.2, boxShadow:'0 8px 24px rgba(0,0,0,0.18)', duration:0.15 }); }catch(_e){} });
                c.addEventListener('mouseleave', ()=>{ try{ gsap.to(c, { scale:1, rotate:0, boxShadow:'', duration:0.2 }); }catch(_e){} });
            });
            window.animateListEnter = function(selector){ try{ const els=document.querySelectorAll(selector); if(els.length){ gsap.from(els, { opacity:0, y:24, duration:0.45, ease:'power2.out', stagger:0.04 }); } }catch(_e){} };
            const tr = document.querySelectorAll('table tbody tr');
            if(tr.length){ gsap.from(tr, { opacity:0, y:14, duration:0.4, ease:'power2.out', stagger:0.03 }); }
        }
    }catch(_e){}

    // Add form validation to all forms except login-form (server-side validates)
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', function(e) {
            // Skip client-side block for login form to ensure POST reaches server
            if (this && (this.id === 'login-form' || this.dataset.skipValidation === '1')) { return; }
            if (!validateForm(this)) {
                e.preventDefault();
                showAlert('يرجى ملء جميع الحقول المطلوبة', 'warning');
            }
        });
    });
}

if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', function(){ try{ __initUI(); }catch(_e){} });
} else {
    try{ __initUI(); }catch(_e){}
}

// Simple modal wrappers for unified API
window.openModal = function(modalSelector){
    try{
        const el = document.querySelector(modalSelector);
        if(!el) return;
        if(window.bootstrap && bootstrap.Modal){
            const inst = bootstrap.Modal.getOrCreateInstance(el);
            inst.show();
        } else {
            el.classList.add('show');
            el.style.display = 'block';
        }
    }catch(_e){}
};
window.closeModal = function(modalSelector){
    try{
        const el = document.querySelector(modalSelector);
        if(!el) return;
        if(window.bootstrap && bootstrap.Modal){
            const inst = bootstrap.Modal.getInstance(el) || bootstrap.Modal.getOrCreateInstance(el);
            inst.hide();
        } else {
            el.classList.remove('show');
            el.style.display = 'none';
        }
    }catch(_e){}
};

window.flyToTarget = function(srcEl, targetSelector){
    try{
        const target = document.querySelector(targetSelector);
        if(!srcEl || !target) return;
        const rect = srcEl.getBoundingClientRect();
        const trect = target.getBoundingClientRect();
        const clone = srcEl.cloneNode(true);
        clone.style.position = 'fixed';
        clone.style.left = rect.left + 'px';
        clone.style.top = rect.top + 'px';
        clone.style.width = rect.width + 'px';
        clone.style.zIndex = 9999;
        clone.style.pointerEvents = 'none';
        document.body.appendChild(clone);
        if(window.gsap && window.MotionPathPlugin){
            try{ gsap.registerPlugin(MotionPathPlugin); }catch(_e){}
            const p1x = rect.left, p1y = rect.top;
            const cx = p1x + (trect.left - p1x) * 0.5;
            const cy = rect.top - 80;
            const path = [{ x: p1x, y: p1y }, { x: cx, y: cy }, { x: trect.left, y: trect.top }];
            gsap.to(clone, { duration: 0.6, motionPath: { path: path, curviness: 1.25 }, scale: 0.6, opacity: 0.4, rotate: 2, ease: 'power3.inOut', onComplete: function(){ try{ clone.remove(); }catch(_){} if(target){ try{ gsap.fromTo(target, { scale:1.0 }, { scale:1.05, duration:0.16, yoyo:true, repeat:1, ease:'bounce.out' }); }catch(_e){} } try{ window.particleBurstAt(target); }catch(_e){} } });
        } else if(window.gsap){
            gsap.to(clone, { x: (trect.left - rect.left) + 6, y: (trect.top - rect.top) + 6, scale: 0.6, opacity: 0.4, rotate: 2, duration: 0.5, ease: 'power3.inOut', onComplete: function(){ try{ clone.remove(); }catch(_){} if(target){ try{ gsap.fromTo(target, { scale:1.0 }, { scale:1.02, duration:0.12, yoyo:true, repeat:1, ease:'power1.out' }); }catch(_e){} } try{ window.particleBurstAt(target); }catch(_e){} } });
        } else {
            clone.style.transition = 'all 0.5s ease';
            requestAnimationFrame(()=>{
                clone.style.transform = `translate(${(trect.left - rect.left) + 6}px, ${(trect.top - rect.top) + 6}px) scale(0.6)`;
                clone.style.opacity = '0.4';
            });
            setTimeout(()=>{ try{ clone.remove(); }catch(_){} try{ window.particleBurstAt(target); }catch(_e){} }, 520);
        }
    }catch(_){ }
};

document.addEventListener('shown.bs.modal', function(e){ try{ if(window.gsap){ gsap.from(e.target.querySelector('.modal-content')||e.target, { opacity:0, scale:0.95, duration:0.25, ease:'back.out(1.6)' }); } }catch(_e){} });

// Export functions for global use
window.apiCall = apiCall;
window.addToCart = addToCart;
window.removeFromCart = removeFromCart;
window.selectTable = selectTable;
window.printInvoice = printInvoice;
window.printReport = printReport;

window.triggerCelebration = function(elOrSel, intensity){
    try{
        const el = typeof elOrSel === 'string' ? document.querySelector(elOrSel) : elOrSel;
        if(!el) return;
        const r = el.getBoundingClientRect();
        const cx = r.left + r.width/2;
        const cy = r.top + r.height/2;
        const n = Math.max(12, intensity||20);
        for(let i=0;i<n;i++){
            const s = document.createElement('span');
            s.className = 'sparkle';
            s.style.position = 'fixed';
            s.style.left = cx + 'px';
            s.style.top = cy + 'px';
            const hue = Math.floor(Math.random()*360);
            s.style.background = `hsl(${hue} 90% 70%)`;
            s.style.boxShadow = `0 0 8px hsl(${hue} 90% 70%)`;
            document.body.appendChild(s);
            const ang = Math.random()*Math.PI*2;
            const rad = 50 + Math.random()*80;
            const dx = Math.cos(ang)*rad;
            const dy = Math.sin(ang)*rad;
            if(window.gsap){
                try{ gsap.fromTo(s, { opacity:1, scale:0.9 }, { x:dx, y:dy, scale:0.1, opacity:0, duration:0.7, ease:'power2.out', onComplete:function(){ try{ s.remove(); }catch(_){} } }); }catch(_e){}
            } else {
                s.style.setProperty('--dx', dx + 'px');
                s.style.setProperty('--dy', dy + 'px');
                s.classList.add('animate');
                setTimeout(()=>{ try{ s.remove(); }catch(_){} }, 740);
            }
        }
    }catch(_e){}
};

window.particleBurstAt = function(elOrSel){
    try{
        const el = typeof elOrSel === 'string' ? document.querySelector(elOrSel) : elOrSel;
        if(!el) return;
        const r = el.getBoundingClientRect();
        const cx = r.left + r.width/2;
        const cy = r.top + r.height/2;
        const n = 12;
        for(let i=0;i<n;i++){
            const s = document.createElement('span');
            s.className = 'sparkle';
            s.style.position = 'fixed';
            s.style.left = cx + 'px';
            s.style.top = cy + 'px';
            document.body.appendChild(s);
            const ang = Math.random()*Math.PI*2;
            const rad = 40 + Math.random()*60;
            const dx = Math.cos(ang)*rad;
            const dy = Math.sin(ang)*rad;
            if(window.gsap){
                try{ gsap.fromTo(s, { opacity:1, scale:0.9 }, { x:dx, y:dy, scale:0.1, opacity:0, duration:0.6, ease:'power2.out', onComplete:function(){ try{ s.remove(); }catch(_){} } }); }catch(_e){}
            } else {
                s.style.setProperty('--dx', dx + 'px');
                s.style.setProperty('--dy', dy + 'px');
                s.classList.add('animate');
                setTimeout(()=>{ try{ s.remove(); }catch(_){} }, 620);
            }
        }
    }catch(_e){}
};

window.animateNumber = function(el, to, duration){
    try{
        const start = parseFloat((el.textContent||'0').replace(/[^0-9\.\-]/g,''))||0;
        const diff = to - start;
        const d = Math.max(0.2, duration||0.6);
        const t0 = performance.now();
        function step(t){
            const p = Math.min(1, (t - t0)/(d*1000));
            const v = start + diff * p;
            el.textContent = v.toFixed(2);
            if(p<1) requestAnimationFrame(step);
        }
        requestAnimationFrame(step);
    }catch(_e){ el.textContent = (to||0).toFixed(2); }
};
