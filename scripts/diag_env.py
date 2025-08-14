import os, sys
print('CWD=', os.getcwd())
print('PYTHON=', sys.executable)
print('PYTHONPATH=', os.environ.get('PYTHONPATH'))
print('SYS_PATH0=', sys.path[0] if sys.path else None)

# Ensure project root on sys.path
root = os.path.abspath(os.path.dirname(__file__) + os.sep + '..')
if root not in sys.path:
    sys.path.insert(0, root)
print('ADDED_ROOT_TO_SYSPATH=', root)

try:
    import app
    print('APP_FILE=', getattr(app, '__file__', None))
    print('APP_DIR=', os.path.dirname(getattr(app, '__file__', '')))
    print('Has /sales route:', any('/sales' in str(k) for k in app.app.url_map.iter_rules()))
except Exception as e:
    print('IMPORT_APP_ERROR=', repr(e))

