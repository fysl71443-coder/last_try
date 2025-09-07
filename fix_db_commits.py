#!/usr/bin/env python3
"""
Fix all db.session.commit() calls to use safe_db_commit()
"""
import re

def fix_db_commits():
    """Replace all db.session.commit() with safe_db_commit()"""
    
    # Read the file
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Count original commits
    original_commits = len(re.findall(r'db\.session\.commit\(\)', content))
    print(f"Found {original_commits} db.session.commit() calls")
    
    # Replace db.session.commit() with safe_db_commit()
    # But keep the one inside safe_db_commit function itself
    lines = content.split('\n')
    new_lines = []
    in_safe_db_commit = False
    
    for i, line in enumerate(lines):
        # Check if we're inside safe_db_commit function
        if 'def safe_db_commit(' in line:
            in_safe_db_commit = True
        elif line.strip().startswith('def ') and in_safe_db_commit:
            in_safe_db_commit = False
        
        # Replace db.session.commit() if not inside safe_db_commit
        if 'db.session.commit()' in line and not in_safe_db_commit:
            # Get indentation
            indent = len(line) - len(line.lstrip())
            spaces = ' ' * indent
            
            # Replace with safe_db_commit
            new_line = line.replace('db.session.commit()', 'safe_db_commit()')
            new_lines.append(new_line)
            print(f"Line {i+1}: {line.strip()} -> {new_line.strip()}")
        else:
            new_lines.append(line)
    
    # Join lines back
    new_content = '\n'.join(new_lines)
    
    # Count new commits
    new_commits = len(re.findall(r'safe_db_commit\(\)', new_content))
    remaining_commits = len(re.findall(r'db\.session\.commit\(\)', new_content))
    
    print(f"\nReplaced {original_commits - remaining_commits} commits")
    print(f"New safe_db_commit() calls: {new_commits}")
    print(f"Remaining db.session.commit(): {remaining_commits} (should be 1 - inside safe_db_commit)")
    
    # Write back to file
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✅ File updated successfully!")

if __name__ == '__main__':
    fix_db_commits()
