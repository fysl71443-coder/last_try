#!/usr/bin/env python3
"""
Script to replace all table_no references with table_number in Python files
"""
import os
import re

def fix_table_no_references():
    """Replace all table_no references with table_number"""
    
    # Files to process
    files_to_process = ['app.py']
    
    for file_path in files_to_process:
        if not os.path.exists(file_path):
            print(f"File {file_path} not found, skipping...")
            continue
            
        print(f"Processing {file_path}...")
        
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Replace patterns
        replacements = [
            # Variable assignments and references
            (r'\btable_no\b', 'table_number'),
            # But keep the old API parameter name for backward compatibility in some cases
            # We'll handle API compatibility separately if needed
        ]
        
        changes_made = 0
        for pattern, replacement in replacements:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                changes_count = len(re.findall(pattern, content))
                changes_made += changes_count
                content = new_content
                print(f"  - Replaced {changes_count} occurrences of '{pattern}' with '{replacement}'")
        
        if changes_made > 0:
            # Write back the modified content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"  ✓ Updated {file_path} with {changes_made} changes")
        else:
            print(f"  - No changes needed in {file_path}")
    
    print("\n=== Summary ===")
    print("Fixed table_no references to use table_number")
    print("Note: You may need to update templates and API calls accordingly")

if __name__ == '__main__':
    fix_table_no_references()
