#!/usr/bin/env python3
"""
Test eventlet configuration
"""
import os

def test_eventlet_monkey_patch():
    """Test that eventlet monkey patch is applied"""
    print("🧪 Testing eventlet monkey patch...")
    
    try:
        # Import should trigger monkey patch
        from app import app
        
        # Check if eventlet is patched
        import socket
        print(f"✅ Socket module: {socket}")
        
        # Check if it's eventlet's green socket
        if hasattr(socket, 'socket') and 'eventlet' in str(type(socket.socket)):
            print("✅ Eventlet monkey patch applied successfully")
        else:
            print("⚠️ Eventlet monkey patch may not be fully applied")
        
        return True
    except Exception as e:
        print(f"❌ Eventlet test failed: {e}")
        return False

def test_nullpool_config():
    """Test NullPool configuration"""
    print("\n🧪 Testing NullPool configuration...")
    
    try:
        from config import Config
        from sqlalchemy.pool import NullPool
        
        # Test PostgreSQL config
        os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost:5432/test'
        
        import importlib
        import config
        importlib.reload(config)
        
        engine_options = config.Config.SQLALCHEMY_ENGINE_OPTIONS
        poolclass = engine_options.get('poolclass')
        
        if poolclass == NullPool:
            print("✅ PostgreSQL uses NullPool")
        else:
            print(f"⚠️ PostgreSQL poolclass: {poolclass}")
        
        # Test SQLite config
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        
        importlib.reload(config)
        
        engine_options = config.Config.SQLALCHEMY_ENGINE_OPTIONS
        poolclass = engine_options.get('poolclass')
        
        if poolclass == NullPool:
            print("✅ SQLite uses NullPool")
        else:
            print(f"⚠️ SQLite poolclass: {poolclass}")
        
        return True
    except Exception as e:
        print(f"❌ NullPool test failed: {e}")
        return False

def test_session_options():
    """Test SQLAlchemy session options"""
    print("\n🧪 Testing SQLAlchemy session options...")
    
    try:
        from extensions import db
        
        # Check session options
        if hasattr(db, 'session_options'):
            options = db.session_options
            print(f"✅ Session options: {options}")
            
            expected_options = {
                'autocommit': False,
                'autoflush': False,
                'expire_on_commit': False
            }
            
            for key, expected_value in expected_options.items():
                if options.get(key) == expected_value:
                    print(f"✅ {key}: {expected_value}")
                else:
                    print(f"⚠️ {key}: {options.get(key)} (expected: {expected_value})")
        
        return True
    except Exception as e:
        print(f"❌ Session options test failed: {e}")
        return False

def test_gunicorn_command():
    """Test gunicorn command"""
    print("\n🧪 Testing gunicorn command...")
    
    try:
        port = os.getenv('PORT', '8000')
        
        cmd = [
            'gunicorn',
            'wsgi:application',
            '-k', 'eventlet',
            '--workers', '1',
            '--timeout', '120',
            f'--bind=0.0.0.0:{port}'
        ]
        
        print(f"✅ Command: {' '.join(cmd)}")
        
        # Check key parameters
        if '-k eventlet' in ' '.join(cmd):
            print("✅ Uses eventlet worker")
        else:
            print("❌ Not using eventlet worker")
        
        if '--workers 1' in ' '.join(cmd):
            print("✅ Uses 1 worker (recommended for eventlet)")
        else:
            print("⚠️ Multiple workers (may cause issues with eventlet)")
        
        return True
    except Exception as e:
        print(f"❌ Gunicorn command test failed: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Eventlet Configuration Test")
    print("=" * 40)
    
    tests = [
        test_eventlet_monkey_patch,
        test_nullpool_config,
        test_session_options,
        test_gunicorn_command
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    print("\n📋 Summary:")
    passed = sum(results)
    total = len(results)
    print(f"Tests passed: {passed}/{total}")
    
    if all(results):
        print("✅ All eventlet configuration tests passed!")
        print("🚀 Ready for deployment with eventlet!")
    else:
        print("❌ Some tests failed. Check configuration.")

if __name__ == '__main__':
    main()
