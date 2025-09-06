#!/usr/bin/env python3
"""
Test the simple app configuration
"""
import os

# Set environment
os.environ['USE_EVENTLET'] = '0'
os.environ['FLASK_ENV'] = 'production'

def test_simple_app():
    """Test the simple app"""
    print("🧪 Testing simple_app configuration...")
    
    try:
        from simple_app import app
        print("✅ App imported successfully")
        
        # Check configuration
        print(f"✅ Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        print(f"✅ Engine options: {app.config['SQLALCHEMY_ENGINE_OPTIONS']}")
        print(f"✅ Debug mode: {app.config['DEBUG']}")
        
        # Test routes
        with app.test_client() as client:
            response = client.get('/')
            print(f"✅ Root route: {response.status_code}")
            
            response = client.get('/login')
            print(f"✅ Login route: {response.status_code}")
            
            # Check if routes are registered
            routes = [rule.rule for rule in app.url_map.iter_rules()]
            print(f"✅ Total routes registered: {len(routes)}")
            
            # Check for key routes
            key_routes = ['/', '/login', '/dashboard']
            for route in key_routes:
                if route in routes:
                    print(f"✅ Route {route}: Found")
                else:
                    print(f"❌ Route {route}: Missing")
        
        print("🎉 All tests passed!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_simple_app()
