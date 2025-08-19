#!/usr/bin/env python3
"""
Test production configuration with pool_pre_ping and gevent
"""
import os

def test_production_config():
    """Test the production configuration"""
    print("🧪 Testing production configuration...")
    
    # Test PostgreSQL config
    print("\n1️⃣ Testing PostgreSQL configuration:")
    os.environ['DATABASE_URL'] = 'postgresql://user:pass@host:5432/db'
    
    # Reload config
    import importlib
    if 'config' in globals():
        importlib.reload(config)
    else:
        import config
    
    print(f"   Database URI: {config.Config.SQLALCHEMY_DATABASE_URI}")
    engine_options = config.Config.SQLALCHEMY_ENGINE_OPTIONS
    print(f"   Pool pre-ping: {engine_options.get('pool_pre_ping', False)}")
    print(f"   Pool size: {engine_options.get('pool_size', 'Not set')}")
    print(f"   Max overflow: {engine_options.get('max_overflow', 'Not set')}")
    print(f"   Pool timeout: {engine_options.get('pool_timeout', 'Not set')}")
    print(f"   Pool recycle: {engine_options.get('pool_recycle', 'Not set')}")
    
    # Test SQLite config
    print("\n2️⃣ Testing SQLite configuration:")
    if 'DATABASE_URL' in os.environ:
        del os.environ['DATABASE_URL']
    
    importlib.reload(config)
    
    print(f"   Database URI: {config.Config.SQLALCHEMY_DATABASE_URI}")
    engine_options = config.Config.SQLALCHEMY_ENGINE_OPTIONS
    print(f"   Connect args: {engine_options.get('connect_args', 'Not set')}")
    
    # Test app with new config
    print("\n3️⃣ Testing app with production config:")
    try:
        os.environ['DATABASE_URL'] = 'postgresql://test:test@localhost:5432/testdb'
        
        from simple_app import app
        print(f"   App created: {type(app)}")
        print(f"   Database URI: {app.config['SQLALCHEMY_DATABASE_URI']}")
        
        engine_options = app.config.get('SQLALCHEMY_ENGINE_OPTIONS', {})
        print(f"   Pool pre-ping: {engine_options.get('pool_pre_ping', False)}")
        print(f"   Pool size: {engine_options.get('pool_size', 'Default')}")
        
        # Test extensions
        from extensions import db
        print(f"   SQLAlchemy initialized: {type(db)}")

        print("✅ Production config test passed!")
        
    except Exception as e:
        print(f"❌ Production config test failed: {e}")
        import traceback
        traceback.print_exc()

def test_gevent_compatibility():
    """Test gevent compatibility"""
    print("\n🧪 Testing gevent compatibility...")
    
    try:
        import gevent
        print(f"✅ gevent version: {gevent.__version__}")
        
        # Test monkey patching
        from gevent import monkey
        print("✅ gevent monkey patching available")
        
        # Test with gunicorn worker
        try:
            from gunicorn.workers.ggevent import GeventWorker
            print("✅ gunicorn gevent worker available")
        except ImportError:
            print("⚠️ gunicorn gevent worker not available (install gunicorn[gevent])")
        
    except ImportError:
        print("❌ gevent not installed")

if __name__ == '__main__':
    test_production_config()
    test_gevent_compatibility()
