#!/usr/bin/env python3
"""
Working Server - Independent Flask App
"""
from flask import Flask, jsonify

app = Flask(__name__)
app.config['SECRET_KEY'] = 'test-key'

@app.route('/')
def index():
    return '''
    <h1>🍽️ Restaurant Management System</h1>
    <p>✅ Server is running successfully on http://127.0.0.1:5000</p>
    <ul>
        <li><a href="/test">Test Route</a></li>
        <li><a href="/api/test">API Test</a></li>
        <li><a href="/status">System Status</a></li>
    </ul>
    <h3>📝 Next Steps:</h3>
    <ol>
        <li>Fix the duplicate route issue in app.py</li>
        <li>Initialize Git repository</li>
        <li>Test the main application</li>
        <li>Deploy the system</li>
    </ol>
    '''

@app.route('/test')
def test():
    return jsonify({'status': 'success', 'message': 'Test route working!'})

@app.route('/api/test')
def api_test():
    return jsonify({
        'status': 'success',
        'server': 'Flask Test Server',
        'port': 5000,
        'routes': ['/', '/test', '/api/test', '/status']
    })

@app.route('/status')
def status():
    return jsonify({
        'server_status': 'running',
        'flask_version': '2.x',
        'python_version': '3.x',
        'database': 'not connected (test mode)',
        'routes_count': len(app.url_map._rules)
    })

if __name__ == '__main__':
    print("🔧 Starting Working Server...")
    print("✅ Server will start on http://127.0.0.1:5000")
    print("⏹️  Press Ctrl+C to stop")
    print("-" * 50)
    
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,
        use_reloader=False
    )
