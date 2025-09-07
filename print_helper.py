"""
Print Helper Module
Provides unified printing functionality for all receipt templates
"""

from flask import render_template, current_app
from templates.print_config import (
    get_template_config, get_qr_config, get_print_buttons,
    select_template, format_qr_content, validate_template_data,
    DEFAULT_SETTINGS
)
import qrcode
import io
import base64
from PIL import Image

class PrintHelper:
    """Helper class for managing print templates and rendering"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize the print helper with Flask app"""
        app.config.setdefault('PRINT_QR_ENABLED', True)
        app.config.setdefault('PRINT_AUTO_CLOSE', True)
        app.config.setdefault('PRINT_DEFAULT_TEMPLATE', 'unified')
    
    def generate_qr_code(self, content, size=(100, 100)):
        """Generate QR code as base64 data URL"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
                box_size=10,
                border=4,
            )
            qr.add_data(content)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.resize(size, Image.Resampling.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            img_base64 = base64.b64encode(buffer.getvalue()).decode()
            return f"data:image/png;base64,{img_base64}"
        
        except Exception as e:
            current_app.logger.error(f"QR code generation failed: {e}")
            return None
    
    def prepare_template_data(self, invoice, items, settings=None, template_type='unified', **kwargs):
        """Prepare data for template rendering"""
        
        # Get template configuration
        template_config = get_template_config(template_type)
        qr_config = get_qr_config(template_type)
        
        # Prepare base data
        data = {
            'invoice': invoice,
            'items': items or [],
            'settings': settings or DEFAULT_SETTINGS,
            'template_type': template_type,
            'receipt_type': template_type,
            **kwargs
        }
        
        # Generate QR code if enabled
        if current_app.config.get('PRINT_QR_ENABLED', True):
            qr_content = format_qr_content(invoice, template_type)
            qr_size = (qr_config['width'], qr_config['height'])
            data['qr_data_url'] = self.generate_qr_code(qr_content, qr_size)
        
        # Add template-specific data
        if template_type == 'thermal':
            data.update({
                'company_name': settings.company_name if settings else DEFAULT_SETTINGS['company_name'],
                'logo_url': settings.logo_url if settings else DEFAULT_SETTINGS['logo_url'],
                'tax_number': settings.tax_number if settings else DEFAULT_SETTINGS['tax_number'],
                'phone': settings.phone if settings else DEFAULT_SETTINGS['phone']
            })
        
        # Add auto-print flag
        data['auto_print'] = kwargs.get('auto_print', current_app.config.get('PRINT_AUTO_CLOSE', False))
        
        return data
    
    def render_receipt(self, invoice, items, template_type=None, settings=None, **kwargs):
        """Render receipt template with provided data"""
        
        # Auto-select template if not specified
        if not template_type:
            context = kwargs.get('context', 'unified_print')
            template_type = select_template(context)
        
        # Get template configuration
        template_config = get_template_config(template_type)
        template_name = template_config['template']
        
        # Prepare template data
        data = self.prepare_template_data(
            invoice, items, settings, template_type, **kwargs
        )
        
        # Validate required data
        is_valid, missing_fields = validate_template_data(template_type, data)
        if not is_valid:
            current_app.logger.warning(f"Missing required fields for {template_type}: {missing_fields}")
        
        try:
            return render_template(template_name, **data)
        except Exception as e:
            current_app.logger.error(f"Template rendering failed for {template_name}: {e}")
            # Fallback to unified template
            if template_type != 'unified':
                return self.render_receipt(invoice, items, 'unified', settings, **kwargs)
            raise
    
    def render_thermal_receipt(self, invoice, items, settings=None, **kwargs):
        """Render thermal receipt specifically"""
        return self.render_receipt(invoice, items, 'thermal', settings, **kwargs)
    
    def render_sales_receipt(self, invoice, items, settings=None, **kwargs):
        """Render sales receipt specifically"""
        return self.render_receipt(invoice, items, 'sales_receipt', settings, **kwargs)
    
    def render_full_invoice(self, invoice, items, settings=None, **kwargs):
        """Render full invoice specifically"""
        return self.render_receipt(invoice, items, 'invoice_full', settings, **kwargs)
    
    def render_unified_receipt(self, invoice, items, settings=None, receipt_type='standard', **kwargs):
        """Render unified receipt with specified type"""
        kwargs['receipt_type'] = receipt_type
        return self.render_receipt(invoice, items, 'unified', settings, **kwargs)

# Global instance
print_helper = PrintHelper()

def init_print_helper(app):
    """Initialize print helper with Flask app"""
    print_helper.init_app(app)
    return print_helper

# Convenience functions for direct use
def render_receipt_template(invoice, items, template_type='unified', settings=None, **kwargs):
    """Direct function to render receipt template"""
    return print_helper.render_receipt(invoice, items, template_type, settings, **kwargs)

def generate_receipt_qr(invoice, template_type='unified'):
    """Generate QR code for receipt"""
    qr_content = format_qr_content(invoice, template_type)
    qr_config = get_qr_config(template_type)
    qr_size = (qr_config['width'], qr_config['height'])
    return print_helper.generate_qr_code(qr_content, qr_size)

# Template selection helpers
def get_best_template_for_context(context):
    """Get the best template for a given context"""
    return select_template(context)

def get_available_templates():
    """Get list of available templates"""
    from templates.print_config import PRINT_TEMPLATES
    return list(PRINT_TEMPLATES.keys())

def get_template_info(template_type):
    """Get information about a specific template"""
    return get_template_config(template_type)
