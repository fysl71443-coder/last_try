#!/usr/bin/env python3
"""
Simple Flask Server Runner
"""
import os
import sys

def main():
    try:
        print("Starting Restaurant Management System...")
        
        # Honor environment variables
        # FLASK_ENV can be provided by the caller; don't override if set
        os.environ.setdefault('FLASK_ENV', os.getenv('FLASK_ENV', 'development'))
        debug_env = os.getenv('FLASK_DEBUG', os.getenv('DEBUG', '0')).strip().lower()
        debug_enabled = debug_env in ('1', 'true', 'yes', 'on')
        use_reloader = debug_enabled if os.getenv('USE_RELOADER') is None else os.getenv('USE_RELOADER').strip().lower() in ('1','true','yes','on')
        # Force local SQLite DB for development to avoid hitting remote DATABASE_URL
        try:
            base = os.path.dirname(os.path.abspath(__file__))
            inst = os.path.abspath(os.path.join(base, '..', 'instance'))
            os.makedirs(inst, exist_ok=True)
            db_file = os.path.join(inst, 'accounting_app.db')
            os.environ['DATABASE_URL'] = 'sqlite:///' + db_file.replace('\\','/')
        except Exception:
            pass
        
        # Import app
        from app import create_app
        app = create_app()
        
        print("App imported successfully")
        print("Server starting on http://127.0.0.1:5000")
        print("Login: admin / admin123")
        print(f"Debug: {'ON' if debug_enabled else 'OFF'} | Reloader: {'ON' if use_reloader else 'OFF'}")
        print("Press Ctrl+C to stop")
        print("-" * 50)
        
        # Run server
        app.run(
            host='127.0.0.1',
            port=5000,
            debug=debug_enabled,
            use_reloader=use_reloader
        )
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    main()
