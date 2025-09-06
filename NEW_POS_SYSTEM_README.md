# New POS System - China Town & Palace India

## 🚀 Overview

The sales system has been completely upgraded with separate point-of-sale interfaces for each branch. This new system provides enhanced functionality, better user experience, and branch-specific customization.

## ✨ New Features

### 🏮 China Town POS
- **Dedicated Interface**: Separate POS system with Chinese-themed design
- **Menu Integration**: Categories and items loaded from Menu system
- **Customer Search**: Search customers by name or phone number
- **Auto-Discount**: Customer discount automatically applied
- **Table-Based Orders**: Track orders by table number (1-20)
- **Draft Invoice Printing**: Print invoices before payment with "UNPAID" notice
- **Secure Item Management**: Password-protected item voiding
- **Multiple Payment Methods**: Cash, Card, Bank Transfer, Other

### 🏛️ Palace India POS
- **Dedicated Interface**: Separate POS system with Indian-themed design
- **Menu Integration**: Categories and items loaded from Menu system
- **Customer Search**: Search customers by name or phone number
- **Auto-Discount**: Customer discount automatically applied
- **Table-Based Orders**: Track orders by table number (1-20)
- **Draft Invoice Printing**: Print invoices before payment with "UNPAID" notice
- **Secure Item Management**: Password-protected item voiding
- **Multiple Payment Methods**: Cash, Card, Bank Transfer, Other

### ⚙️ Branch-Specific Settings
- **Separate Passwords**: Each branch has its own void password (default: 1991)
- **Custom Tax Rates**: Branch-specific VAT rates
- **Custom Discounts**: Branch-specific default discount rates
- **Configurable Settings**: All settings can be changed from the admin panel

## 🔧 Technical Implementation

### New Database Fields
Added to `Settings` model:
- `china_town_void_password` (default: '1991')
- `china_town_vat_rate` (default: 15.00%)
- `china_town_discount_rate` (default: 0.00%)
- `place_india_void_password` (default: '1991')
- `place_india_vat_rate` (default: 15.00%)
- `place_india_discount_rate` (default: 0.00%)

### New Routes
- `/sales` - Branch selection page
- `/sales/china_town` - China Town POS interface
- `/sales/palace_india` - Palace India POS interface
- `/sales/legacy` - Legacy system redirect page

### New API Endpoints
- `GET /api/pos/<branch>/categories` - Get menu categories
- `GET /api/pos/<branch>/categories/<id>/items` - Get items in a category
- `GET /api/pos/<branch>/customers/search?q=<query>` - Search customers
- `POST /api/pos/<branch>/print_draft` - Print draft invoice
- `POST /api/pos/<branch>/process_payment` - Process payment and create invoice
- `POST /api/pos/<branch>/verify_void_password` - Verify void password

## 📋 Invoice Features

### Draft Invoice (Unpaid)
- Shows table number instead of customer name
- Displays customer phone number
- Shows customer-specific discount
- Includes "⚠️ UNPAID / غير مدفوعة" notice at bottom
- Can be printed multiple times without affecting system

### Final Invoice (Paid)
- Shows table number and invoice ID
- Displays customer phone number
- Shows customer-specific discount
- Shows payment method
- Includes "✅ PAID" confirmation
- Automatically saved to database

## 🔒 Security Features

### Item Voiding Protection
- Requires password to void/delete items from invoice
- Branch-specific passwords (configurable)
- Default password: 1991
- Can be changed from Settings → Branch Settings

### Access Control
- All POS functions require user login
- API endpoints are protected
- Settings changes require admin access

## 🎨 User Interface

### Modern Design
- Gradient backgrounds with branch-specific colors
- Responsive design for different screen sizes
- Touch-friendly buttons for POS terminals
- Clear visual feedback for all actions

### Branch Themes
- **China Town**: Pink/Orange gradient theme 🏮
- **Palace India**: Blue gradient theme 🏛️

## 📱 Usage Instructions

### For Staff
1. **Access POS**: Go to Sales → Choose your branch
2. **Select Table**: Choose table number from dropdown
3. **Search Customer**: Type name or phone to find existing customer (optional)
4. **Select Customer**: Click on customer from search results to auto-fill discount
5. **Add Items**: Click categories, then click items to add to invoice
6. **Print Draft**: Use "Print Invoice (Unpaid)" for kitchen/customer copy
7. **Process Payment**: Click "Payment & Print" → Choose method → Print final receipt

### For Managers
1. **Change Settings**: Go to Settings → Choose branch tab
2. **Update Passwords**: Change void passwords for each branch
3. **Adjust Tax Rates**: Set different VAT rates per branch
4. **Set Default Discounts**: Configure default discount rates

## 🧪 Testing

Run the test suite to verify all functionality:
```bash
python test_new_pos_system.py
```

The test covers:
- Database setup and new fields
- Route accessibility
- API endpoint functionality
- Invoice generation
- Template file existence

## 🔄 Migration from Old System

### Automatic Migration
- Database migration script automatically adds new fields
- Old sales data remains intact
- Settings are preserved with new defaults

### User Training
- Staff should be trained on new POS interface
- Managers should review new settings options
- Test all functionality before going live

## 📞 Support

If you encounter any issues:
1. Check that all database migrations have run
2. Verify all template files exist
3. Run the test suite to identify problems
4. Check browser console for JavaScript errors

## 🎯 Future Enhancements

Potential future improvements:
- Customer loyalty program integration
- Advanced reporting by branch
- Mobile app for order taking
- Kitchen display system integration
- Inventory integration with real-time updates

---

**System Status**: ✅ Ready for Production
**Last Updated**: 2025-01-06
**Version**: 2.0.0
