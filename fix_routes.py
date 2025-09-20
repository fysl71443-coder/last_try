#!/usr/bin/env python3
"""
Fix duplicate routes in app.py
"""

def fix_duplicate_routes():
    """Find and fix duplicate routes"""
    with open('app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find all route definitions
    routes = {}
    functions = {}
    duplicates = []
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        # Look for @app.route lines
        if line.startswith('@app.route('):
            route_path = line
            
            # Look for function definition in next few lines
            for j in range(i+1, min(i+10, len(lines))):
                func_line = lines[j].strip()
                if func_line.startswith('def '):
                    func_name = func_line.split('(')[0].replace('def ', '')
                    
                    # Check for duplicates
                    if func_name in functions:
                        print(f"DUPLICATE FUNCTION: {func_name}")
                        print(f"  First: Line {functions[func_name]} - {routes[func_name]}")
                        print(f"  Second: Line {i+1} - {route_path}")
                        duplicates.append((i, j, func_name))
                    else:
                        routes[func_name] = route_path
                        functions[func_name] = i+1
                    break
        i += 1
    
    # Remove duplicates
    if duplicates:
        print(f"\nFound {len(duplicates)} duplicate routes. Fixing...")
        
        # Remove duplicate routes (keep the first one)
        lines_to_remove = set()
        for start_line, end_line, func_name in duplicates:
            # Mark lines for removal (from @app.route to end of function)
            for line_idx in range(start_line, min(end_line + 20, len(lines))):
                if lines[line_idx].strip().startswith('def ') and func_name in lines[line_idx]:
                    # Find end of function
                    indent_level = len(lines[line_idx]) - len(lines[line_idx].lstrip())
                    for end_idx in range(line_idx + 1, len(lines)):
                        if (lines[end_idx].strip() and 
                            len(lines[end_idx]) - len(lines[end_idx].lstrip()) <= indent_level and
                            not lines[end_idx].startswith(' ' * (indent_level + 1))):
                            break
                    
                    # Mark lines for removal
                    for remove_idx in range(start_line, end_idx):
                        lines_to_remove.add(remove_idx)
                    break
        
        # Create new file without duplicate lines
        new_lines = []
        for i, line in enumerate(lines):
            if i not in lines_to_remove:
                new_lines.append(line)
        
        # Write fixed file
        with open('app_fixed.py', 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
        
        print(f"✅ Fixed file saved as app_fixed.py")
        print(f"📝 Removed {len(lines_to_remove)} duplicate lines")
        
        # Backup original and replace
        import shutil
        shutil.copy('app.py', 'app_backup.py')
        shutil.copy('app_fixed.py', 'app.py')
        print("✅ Original backed up as app_backup.py")
        print("✅ Fixed version is now app.py")
        
    else:
        print("✅ No duplicate routes found")

if __name__ == '__main__':
    fix_duplicate_routes()
