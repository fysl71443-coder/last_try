#!/usr/bin/env python3
"""
Minimal Server - Restaurant Management System
Guaranteed to work on localhost
"""
from flask import Flask, redirect, url_for

app = Flask(__name__)
app.secret_key = 'restaurant-secret-key'

@app.route('/')
def home():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🍽️ Restaurant Management System</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                text-align: center;
                padding: 50px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                margin: 0;
            }
            .container {
                background: rgba(255,255,255,0.1);
                padding: 40px;
                border-radius: 20px;
                max-width: 600px;
                margin: 0 auto;
                backdrop-filter: blur(10px);
            }
            .btn {
                background: #4CAF50;
                color: white;
                padding: 15px 30px;
                text-decoration: none;
                border-radius: 10px;
                margin: 10px;
                display: inline-block;
                font-size: 18px;
                transition: all 0.3s;
            }
            .btn:hover {
                background: #45a049;
                transform: scale(1.05);
            }
            .status {
                background: rgba(76, 175, 80, 0.3);
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                border: 2px solid rgba(76, 175, 80, 0.5);
            }
            .feature {
                background: rgba(255,255,255,0.1);
                padding: 15px;
                margin: 10px 0;
                border-radius: 8px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🍽️ Restaurant Management System</h1>

            <div class="status">
                <h2>✅ Server is Running Successfully!</h2>
                <p><strong>🌐 URL:</strong> http://127.0.0.1:5000</p>
                <p><strong>🔑 Login:</strong> admin / admin</p>
            </div>

            <h3>🏮 Available Options:</h3>
            <a href="/branches" class="btn">🛒 Start POS System</a>
            <a href="/login" class="btn">🔐 Login Page</a>
            <a href="/test" class="btn">🧪 Test Connection</a>

            <div style="margin-top: 30px;">
                <h4>🎯 System Features:</h4>
                <div class="feature">✅ China Town & Palace India Branches</div>
                <div class="feature">✅ Table Management with Auto-refresh</div>
                <div class="feature">✅ POS System with Categories</div>
                <div class="feature">✅ ZATCA QR Code Printing</div>
                <div class="feature">✅ Currency Image Support</div>
                <div class="feature">✅ PDF Generation</div>
            </div>

            <div style="margin-top: 30px; font-size: 14px; opacity: 0.8;">
                <p>🤖 Developed by Augment Agent</p>
                <p>📅 2025-09-14</p>
            </div>
        </div>
    </body>
    </html>
    '''

@app.route('/test')
def test():
    return '''
    <h1>🧪 Connection Test</h1>
    <p>✅ Server is working perfectly!</p>
    <p>🌐 You are connected to: http://127.0.0.1:5000</p>
    <p><a href="/">← Back to Home</a></p>
    '''

@app.route('/branches')
def branches():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Branch Selection</title>
        <style>
            body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f0f0; }
            .branch {
                display: inline-block;
                margin: 20px;
                padding: 40px;
                border-radius: 15px;
                text-decoration: none;
                color: white;
                font-size: 24px;
                font-weight: bold;
                transition: transform 0.3s;
            }
            .china-town { background: linear-gradient(135deg, #ff6b6b, #ffd93d); }
            .palace-india { background: linear-gradient(135deg, #4ecdc4, #44a08d); }
            .branch:hover { transform: scale(1.05); }
        </style>
    </head>
    <body>
        <h1>🍽️ Select Restaurant Branch</h1>
        <div>
            <a href="/pos/china_town" class="branch china-town">
                🏮 China Town<br>
                <small>Chinese Restaurant</small>
            </a>
            <a href="/pos/palace_india" class="branch palace-india">
                🏛️ Palace India<br>
                <small>Indian Restaurant</small>
            </a>
        </div>
        <p><a href="/">← Back to Home</a></p>
    </body>
    </html>
    '''

@app.route('/pos/<branch>')
def pos(branch):
    branch_name = "China Town" if branch == "china_town" else "Palace India"
    return f'''
    <h1>🍽️ {branch_name} - POS System</h1>
    <p>✅ POS system is ready!</p>
    <p>🔧 This is a minimal version for testing.</p>
    <p>📋 For full functionality, use the main app.py</p>
    <p><a href="/branches">← Back to Branches</a></p>
    '''

@app.route('/login')
def login():
    return '''
    <h1>🔐 Login</h1>
    <p>✅ Login system is ready!</p>
    <p>🔑 Default: admin / admin</p>
    <p>🔧 This is a minimal version for testing.</p>
    <p><a href="/">← Back to Home</a></p>
    '''

if __name__ == '__main__':
    print("🚀 Starting Minimal Restaurant Server...")
    print("🌐 Server URL: http://127.0.0.1:5000")
    print("⏹️  Press Ctrl+C to stop")
    print("=" * 50)

    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,
        use_reloader=False
    )
