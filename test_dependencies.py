#!/usr/bin/env python3
"""
Test script to check if all required dependencies are installed
This helps debug deployment issues on Render
"""

import sys
import os

def test_dependency(name, import_statement=None):
    """Test if a dependency can be imported"""
    try:
        if import_statement:
            exec(import_statement)
        else:
            __import__(name)
        print(f"✅ {name}: OK")
        return True
    except ImportError as e:
        print(f"❌ {name}: MISSING - {e}")
        return False
    except Exception as e:
        print(f"⚠️ {name}: ERROR - {e}")
        return False

def main():
    """Test all critical dependencies"""
    print("🧪 Testing Dependencies on Render")
    print("=" * 50)
    
    dependencies = [
        ("Flask", "import flask"),
        ("pandas", "import pandas as pd; print(f'pandas version: {pd.__version__}')"),
        ("openpyxl", "import openpyxl; print(f'openpyxl version: {openpyxl.__version__}')"),
        ("Flask-Babel", "from flask_babel import gettext"),
        ("reportlab", "import reportlab"),
        ("psycopg2", "import psycopg2"),
        ("SQLAlchemy", "import sqlalchemy"),
    ]
    
    results = []
    for name, import_stmt in dependencies:
        results.append(test_dependency(name, import_stmt))
    
    print("\n📋 Summary:")
    print("=" * 50)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All dependencies are available!")
    else:
        print("❌ Some dependencies are missing!")
        print("\n🔧 Troubleshooting:")
        print("1. Check requirements.txt")
        print("2. Trigger a new deployment")
        print("3. Check Render build logs")
    
    # Test pandas specifically for Excel functionality
    print("\n🔍 Testing pandas Excel functionality:")
    try:
        import pandas as pd
        import io
        
        # Test CSV
        csv_data = "Name,Value\nTest,123"
        df_csv = pd.read_csv(io.StringIO(csv_data))
        print("✅ pandas CSV reading: OK")
        
        # Test Excel (this will fail if openpyxl is missing)
        try:
            # Create a simple Excel file in memory
            excel_buffer = io.BytesIO()
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df_csv.to_excel(writer, index=False)
            excel_buffer.seek(0)
            
            # Try to read it back
            df_excel = pd.read_excel(excel_buffer, engine='openpyxl')
            print("✅ pandas Excel reading: OK")
        except Exception as e:
            print(f"❌ pandas Excel reading: FAILED - {e}")
            
    except Exception as e:
        print(f"❌ pandas functionality test: FAILED - {e}")
    
    print(f"\n🐍 Python version: {sys.version}")
    print(f"📁 Current directory: {os.getcwd()}")
    
    return passed == total

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
