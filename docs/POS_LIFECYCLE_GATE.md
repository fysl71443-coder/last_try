# POS Screen Lifecycle — Loading as Gate

## القاعدة (Rule)

- **لا تُخفِ شاشة التحميل** إلا بعد أن يصبح النظام **جاهزًا 100%**.
- Loading = **قفل تفاعلي (Gate)** وليس ديكورًا.

## Lifecycle Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  Page Load                                                       │
│  ─────────                                                       │
│  • isReady = false                                               │
│  • #pos-loading-overlay visible (z-index 9999)                   │
│  • #pos-screen has class .pos-gated → pointer-events: none       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  initPOS() [initSalesScreen] — single entry                      │
│  ─────────────────────────────────────────                      │
│  1. loadBranchSettings()     ← void password, etc.              │
│  2. loadDraftFromAPI()       ← draft items for table            │
│  3. preloadMenuItems()       ← all categories + items in memory  │
│     • /api/menu/all-items OR preloadMenuItemsFallback (parallel) │
│     • MENU_CACHE[categoryId] = [items] for every category        │
│  4. renderItems()            ← cart list                        │
│  5. setTotals()              ← subtotal, tax, grand              │
│  6. Bind events (category cards, buttons, customer, save)         │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  hideLoading() — ONLY HERE                                      │
│  ─────────────────────────                                      │
│  • setScreenReady(true)                                          │
│  • #pos-loading-overlay display = none                           │
│  • #pos-screen: remove .pos-gated, add .pos-ready                │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│  Ready — User can interact                                       │
│  ─────────────────────────                                      │
│  • Category click → openCategory(id, name)                       │
│    → data = MENU_CACHE[id] only (no API call)                    │
│  • Add item, change qty, pay, print — all from in-memory state    │
└─────────────────────────────────────────────────────────────────┘
```

## Single readiness flag

- **One flag only:** `SCREEN_READY` (or conceptually `isReady`).
- `setScreenReady(true)` is called **only at the end of initSalesScreen()**.
- On init error: `initSalesScreen().catch(… setScreenReady(true))` so the user is not stuck.

## No API on category click

- **Before:** `openCategory` could call `fetch(/api/menu/${catId}/items)` if `MENU_CACHE[catId]` was missing.
- **After:** `openCategory` uses only `MENU_CACHE[catId]`. If missing → show "No items". No network on click.

## Files touched

| File | Change |
|------|--------|
| `static/js/pos_table.js` | Lifecycle comment; `setScreenReady()` toggles `#pos-screen` .pos-gated / .pos-ready; `openCategory()` memory-only |
| `templates/sales_table_invoice.html` | Wrapper `#pos-screen.pos-gated`; CSS `.pos-gated { pointer-events: none }` |

## اختبار النجاح (Success test)

- لا تحتاج Refresh بعد فتح الصفحة.
- لا يوجد أي طلب API عند الضغط على قسم (أول نقرة تعمل فورًا).
- المسودة تظهر فورًا بعد التحميل.
- السلوك يشبه أجهزة الكاشير التجارية (تفاعل فوري بعد التحميل الأول).
