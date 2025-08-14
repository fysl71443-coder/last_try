import os
os.environ.setdefault('USE_EVENTLET','0')
os.environ.setdefault('PYTHONPATH','.')

from app import app

with app.test_client() as c:
    r = c.get('/sales', follow_redirects=True)
    data = r.data.decode('utf-8','ignore')
    print('STATUS=', r.status_code)
    print('HAS_PLACE_INDIA=', ('Place India' in data))
    print('HAS_CHINA_TOWN=', ('China Town' in data))
    # Print a small snippet for visual confirmation
    print('SNIPPET=', data[:300].replace('\n',' ') )

