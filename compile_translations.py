#!/usr/bin/env python3
"""
Compile translation files for Flask-Babel
"""
import os
import sys
from babel.messages import frontend as babel

def compile_translations():
    """Compile .po files to .mo files"""
    
    languages = ['ar', 'en']
    
    for lang in languages:
        po_file = f'translations/{lang}/LC_MESSAGES/messages.po'
        mo_file = f'translations/{lang}/LC_MESSAGES/messages.mo'
        
        if os.path.exists(po_file):
            print(f"Compiling {lang} translations...")
            
            # Create a simple .mo file content
            try:
                # Use babel to compile
                from babel.messages.mofile import write_mo
                from babel.messages.pofile import read_po
                
                with open(po_file, 'rb') as f:
                    catalog = read_po(f)
                
                with open(mo_file, 'wb') as f:
                    write_mo(f, catalog)
                    
                print(f"OK Compiled {lang} -> {mo_file}")
                
            except ImportError:
                # Fallback: create empty .mo file
                with open(mo_file, 'wb') as f:
                    # Minimal .mo file header
                    f.write(b'\xde\x12\x04\x95\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
                print(f"WARN Created minimal {lang} -> {mo_file}")
                
        else:
            print(f"NOT FOUND {po_file}")

if __name__ == '__main__':
    compile_translations()
