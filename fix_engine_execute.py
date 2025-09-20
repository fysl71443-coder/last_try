import os
import re
from sqlalchemy import text

def find_and_replace_engine_execute():
    """
    Find and replace all with engine.connect() as conn:
        conn.execute(text(...)) patterns with the new connection pattern:
    
    OLD: with engine.connect() as conn:
        conn.execute(text("SQL QUERY"))
    NEW: with engine.connect() as conn:
             conn.execute(text("SQL QUERY"))
    """
    
    # Get all Python files in the project
    python_files = []
    for root, dirs, files in os.walk('.'):
        # Skip certain directories
        if any(skip_dir in root for skip_dir in ['.git', '__pycache__', 'venv', 'env']):
            continue
            
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    print(f"Scanning {len(python_files)} Python files...")
    
    files_modified = 0
    total_replacements = 0
    
    for file_path in python_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Pattern to match engine.execute(...) calls
            pattern = r'(?:\w+\.)?engine\.execute\s*\(\s*([^)]+)\s*\)'

            matches = list(re.finditer(pattern, content, re.MULTILINE | re.DOTALL))
            
            if matches:
                print(f"\nFound {len(matches)} engine.execute patterns in {file_path}")
                
                # Process matches in reverse order to maintain string positions
                for match in reversed(matches):
                    full_match = match.group(0)
                    engine_prefix = match.group(1) or ''  # Could be 'db.' or similar
                    sql_content = match.group(2).strip()
                    
                    print(f"  - Found: {full_match}")
                    
                    # Check if the SQL content is already wrapped in text()
                    if not sql_content.startswith('text('):
                        # Wrap in text() if it's a string literal
                        if sql_content.startswith('"') or sql_content.startswith("'"):
                            sql_content = f"text({sql_content})"
                        else:
                            # If it's a variable, assume it needs text() wrapper
                            sql_content = f"text({sql_content})"
                    
                    # Create the replacement pattern
                    replacement = f"""with {engine_prefix}engine.connect() as conn:
        conn.execute({sql_content})"""
                    
                    # Replace in content
                    start, end = match.span()
                    content = content[:start] + replacement + content[end:]
                    
                    total_replacements += 1
                
                # Check if we need to add the text import
                if 'from sqlalchemy import' in content and 'text' not in content:
                    # Add text to existing sqlalchemy import
                    content = re.sub(
                        r'from sqlalchemy import ([^\n]+)',
                        r'from sqlalchemy import \1, text',
                        content
                    )
                elif 'from sqlalchemy import' not in content and total_replacements > 0:
                    # Add new import at the top
                    content = 'from sqlalchemy import text\n' + content
                
                # Write back the modified content
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                files_modified += 1
                print(f"  ✓ Updated {file_path}")
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    print(f"\n=== Summary ===")
    print(f"Files scanned: {len(python_files)}")
    print(f"Files modified: {files_modified}")
    print(f"Total replacements: {total_replacements}")
    
    if total_replacements == 0:
        print("\n✓ No engine.execute() patterns found in your codebase!")
        print("Your code is already using the correct connection pattern.")
    else:
        print(f"\n✓ Successfully replaced {total_replacements} engine.execute() patterns")
        print("All patterns have been updated to use the new connection pattern:")
        print("  with engine.connect() as conn:")
        print("      conn.execute(text('...'))")

def show_example():
    """Show examples of the old vs new patterns"""
    print("\n=== PATTERN EXAMPLES ===")
    print("\n❌ OLD PATTERN (deprecated):")
    print("# engine.execute('SELECT * FROM users')")
    print("# db.engine.execute('INSERT INTO users (name) VALUES (?)', ('John',))")

    print("\n✅ NEW PATTERN (recommended):")
    print("with engine.connect() as conn:")
    print("    conn.execute(text('SELECT * FROM users'))")
    print("")
    print("with engine.connect() as conn:")
    print("    conn.execute(text('INSERT INTO users (name) VALUES (:name)'), {'name': 'John'})")

if __name__ == '__main__':
    print("🔧 SQLAlchemy Engine.execute() Pattern Updater")
    print("=" * 50)
    
    show_example()
    
    response = input("\nDo you want to scan and update your codebase? (y/n): ").lower().strip()
    
    if response in ['y', 'yes']:
        find_and_replace_engine_execute()
    else:
        print("Scan cancelled.")
