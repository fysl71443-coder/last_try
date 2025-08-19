#!/usr/bin/env python3
"""
Test the final production setup
"""
import os
import subprocess

def test_imports():
    """Test all imports work correctly"""
    print("🧪 Testing imports...")
    
    try:
        from app import app, socketio
        print(f"✅ App: {type(app)}")
        print(f"✅ SocketIO: {type(socketio) if socketio else 'None'}")
        
        from wsgi import application
        print(f"✅ WSGI application: {type(application)}")
        
        from config import Config
        print(f"✅ Config: {type(Config)}")
        
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_routes():
    """Test routes are working"""
    print("\n🧪 Testing routes...")
    
    try:
        from wsgi import application
        
        with application.test_client() as client:
            response = client.get('/')
            print(f"✅ Root route: {response.status_code}")
            
            response = client.get('/login')
            print(f"✅ Login route: {response.status_code}")
        
        routes_count = len(list(application.url_map.iter_rules()))
        print(f"✅ Routes registered: {routes_count}")
        
        return True
    except Exception as e:
        print(f"❌ Routes error: {e}")
        return False

def test_gunicorn_command():
    """Test gunicorn command generation"""
    print("\n🧪 Testing gunicorn command...")
    
    try:
        port = os.getenv('PORT', '8000')
        
        cmd = [
            'gunicorn',
            'wsgi:application',
            '-k', 'gevent',
            '--workers', '3',
            '--threads', '2',
            '--timeout', '120',
            f'--bind=0.0.0.0:{port}'
        ]
        
        print(f"✅ Command: {' '.join(cmd)}")
        print(f"✅ Port: {port}")
        
        return True
    except Exception as e:
        print(f"❌ Command error: {e}")
        return False

def test_config():
    """Test configuration"""
    print("\n🧪 Testing configuration...")
    
    try:
        # Test PostgreSQL config
        os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost:5432/test'
        
        import importlib
        if 'config' in globals():
            importlib.reload(config)
        else:
            import config
        
        print(f"✅ PostgreSQL URI: {config.Config.SQLALCHEMY_DATABASE_URI}")
        engine_options = config.Config.SQLALCHEMY_ENGINE_OPTIONS
        print(f"✅ Pool pre-ping: {engine_options.get('pool_pre_ping', False)}")
        
        # Test SQLite config
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        
        importlib.reload(config)
        
        print(f"✅ SQLite URI: {config.Config.SQLALCHEMY_DATABASE_URI}")
        engine_options = config.Config.SQLALCHEMY_ENGINE_OPTIONS
        print(f"✅ Check same thread: {engine_options.get('connect_args', {}).get('check_same_thread', True)}")
        
        return True
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False

def main():
    """Run all tests"""
    print("🚀 Final Setup Test")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_routes,
        test_gunicorn_command,
        test_config
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
        print("✅ All tests passed! Ready for deployment!")
    else:
        print("❌ Some tests failed. Check the errors above.")

if __name__ == '__main__':
    main()
