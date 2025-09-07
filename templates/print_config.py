# Print Template Configuration
# This file contains configuration for different print templates

PRINT_TEMPLATES = {
    'thermal': {
        'template': 'print/receipt.html',
        'width': '320px',
        'font_size': '12px',
        'description': 'Thermal printer receipt (58mm/80mm)',
        'features': ['compact', 'qr_code', 'auto_print']
    },
    
    'sales_receipt': {
        'template': 'sales_receipt.html', 
        'width': '148px',
        'font_size': '10px',
        'description': 'Sales receipt with adaptive layout',
        'features': ['adaptive_layout', 'qr_code', 'auto_print', 'settings_based']
    },
    
    'invoice_full': {
        'template': 'invoice_print.html',
        'width': '800px', 
        'font_size': '14px',
        'description': 'Full invoice with professional design',
        'features': ['professional_design', 'detailed_info', 'qr_code']
    },
    
    'unified': {
        'template': 'unified_receipt.html',
        'width': 'variable',
        'font_size': 'variable',
        'description': 'Unified template with customizable layout',
        'features': ['customizable', 'multilingual', 'responsive', 'qr_code']
    },
    
    'payment_page': {
        'template': 'payment.html',
        'width': '100%',
        'font_size': '14px', 
        'description': 'Payment page with print functionality',
        'features': ['payment_integration', 'print_footer']
    }
}

# Template selection based on context
TEMPLATE_SELECTION = {
    'pos_payment': 'sales_receipt',
    'invoice_preview': 'invoice_full', 
    'thermal_print': 'thermal',
    'unified_print': 'unified',
    'payment_print': 'payment_page'
}

# Default settings for templates
DEFAULT_SETTINGS = {
    'company_name': 'Restaurant System',
    'logo_url': '/static/logo.svg',
    'tax_number': '',
    'phone': '',
    'address': '',
    'currency': 'ر.س',
    'show_qr_code': True,
    'auto_print': False,
    'receipt_width': 320,
    'receipt_font_size': 12
}

# QR Code configuration
QR_CONFIG = {
    'size': {
        'thermal': {'width': 80, 'height': 80},
        'sales_receipt': {'width': 96, 'height': 96}, 
        'invoice_full': {'width': 100, 'height': 100},
        'unified': {'width': 100, 'height': 100}
    },
    'content_template': 'Invoice: {invoice_number}\nTotal: {total} ر.س\nDate: {date}\nBranch: {branch}',
    'error_correction': 'M'  # L, M, Q, H
}

# Print button configurations
PRINT_BUTTONS = {
    'thermal': {
        'print_text': 'Print Receipt',
        'print_text_ar': 'طباعة الإيصال',
        'close_text': 'Close',
        'close_text_ar': 'إغلاق'
    },
    'sales_receipt': {
        'print_text': 'Print',
        'print_text_ar': 'طباعة', 
        'auto_close': True
    },
    'invoice_full': {
        'print_text': 'Print Invoice',
        'print_text_ar': 'طباعة الفاتورة',
        'close_text': 'Close',
        'close_text_ar': 'إغلاق'
    }
}

# Footer messages configuration
FOOTER_MESSAGES = {
    'thank_you': {
        'en': 'THANK YOU FOR VISIT',
        'ar': 'شكراً لزيارتكم'
    },
    'visit_again': {
        'en': 'Visit us again!',
        'ar': 'زورونا مرة أخرى!'
    },
    'great_day': {
        'en': 'Have a great day!',
        'ar': 'نتمنى لكم يوماً سعيداً!'
    },
    'thank_you_visiting': {
        'en': 'Thank you for visiting us!',
        'ar': 'شكراً لزيارتكم لنا!'
    },
    'hope_see_again': {
        'en': 'We hope to see you again soon',
        'ar': 'نأمل أن نراكم مرة أخرى قريباً'
    }
}

def get_template_config(template_type):
    """Get configuration for a specific template type"""
    return PRINT_TEMPLATES.get(template_type, PRINT_TEMPLATES['unified'])

def get_qr_config(template_type):
    """Get QR code configuration for a template type"""
    return QR_CONFIG['size'].get(template_type, QR_CONFIG['size']['unified'])

def get_print_buttons(template_type):
    """Get print button configuration for a template type"""
    return PRINT_BUTTONS.get(template_type, PRINT_BUTTONS['invoice_full'])

def select_template(context):
    """Select appropriate template based on context"""
    return TEMPLATE_SELECTION.get(context, 'unified')

def format_qr_content(invoice, template_type='unified'):
    """Format QR code content based on invoice data"""
    try:
        content = f"Invoice: {invoice.invoice_number or invoice.id}\nTotal: {invoice.total_after_tax_discount:.2f} ر.س\nDate: {invoice.date.strftime('%Y-%m-%d') if invoice.date else ''}\nBranch: {invoice.branch or invoice.branch_code or 'Main'}"
        return content
    except Exception as e:
        # Fallback to simple content
        return f"Invoice: {invoice.invoice_number or invoice.id}"

# Template validation
def validate_template_data(template_type, data):
    """Validate that required data is present for template"""
    required_fields = {
        'thermal': ['invoice', 'items'],
        'sales_receipt': ['invoice', 'items', 'settings'],
        'invoice_full': ['invoice', 'items'],
        'unified': ['invoice', 'items'],
        'payment_page': ['invoice']
    }
    
    template_required = required_fields.get(template_type, ['invoice'])
    missing_fields = []
    
    for field in template_required:
        if field not in data or data[field] is None:
            missing_fields.append(field)
    
    return len(missing_fields) == 0, missing_fields
