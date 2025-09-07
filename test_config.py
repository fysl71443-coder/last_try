#!/usr/bin/env python3
"""
Test the new simplified configuration
"""
import os

def test_config():
    """Test the configuration in different scenarios"""
    print("🧪 Testing simplified configuration...")
    
    # Test 1: Local development (no DATABASE_URL)
    print("\n1️⃣ Testing local development (SQLite):")
    if 'DATABASE_URL' in os.environ:
        del os.environ['DATABASE_URL']
    
    # Reload config
    import importlib
    if 'config' in globals():
        importlib.reload(config)
    else:
        import config
    
    print(f"   Database URI: {config.Config.SQLALCHEMY_DATABASE_URI}")
    print(f"   Engine options: {getattr(config.Config, 'SQLALCHEMY_ENGINE_OPTIONS', 'Not set')}")
    print(f"   Debug mode: {config.Config.DEBUG}")
    
    # Test 2: Production (with DATABASE_URL)
    print("\n2️⃣ Testing production (DATABASE_URL):")
    os.environ['DATABASE_URL'] = 'postgresql://user:pass@host:5432/db'
    os.environ['FLASK_ENV'] = 'production'
    
    importlib.reload(config)
    
    print(f"   Database URI: {config.Config.SQLALCHEMY_DATABASE_URI}")
    print(f"   Engine options: {getattr(config.Config, 'SQLALCHEMY_ENGINE_OPTIONS', 'Not set')}")
    print(f"   Debug mode: {config.Config.DEBUG}")
    
    # Test 3: App creation
    print("\n3️⃣ Testing app creation:")
    try:
        # Clean environment for app test
        if 'DATABASE_URL' in os.environ:
            del os.environ['DATABASE_URL']
        os.environ['FLASK_ENV'] = 'development'
        
        from simple_app import app
        print(f"   App created: {type(app)}")
        print(f"   Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"   Debug mode: {app.config['DEBUG']}")
        print(f"   Routes count: {len(list(app.url_map.iter_rules()))}")
        
        # Test basic routes
        with app.test_client() as client:
            response = client.get('/')
            print(f"   Root route: {response.status_code}")
            
            response = client.get('/login')
            print(f"   Login route: {response.status_code}")
        
        print("✅ All tests passed!")
        
    except Exception as e:
        print(f"❌ App test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_config()
