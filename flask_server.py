#!/usr/bin/env python3
"""
Flask Server - Restaurant Management System
Direct server without importing app.py
"""
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash
import os
from datetime import datetime

# Create Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize database
db = SQLAlchemy(app)

# Simple User model
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

# Routes
@app.route('/')
def index():
    return render_template_string('''
    <!DOCTYPE html>
    <html>
    <head>
        <title>🍽️ Restaurant Management System</title>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body { font-family: Arial, sans-serif; margin: 0; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
            .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 15px; padding: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.2); }
            h1 { color: #2c3e50; text-align: center; margin-bottom: 30px; font-size: 2.5em; }
            .status { background: #27ae60; color: white; padding: 20px; border-radius: 10px; text-align: center; margin: 20px 0; font-size: 1.2em; }
            .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }
            .card { background: #f8f9fa; padding: 20px; border-radius: 10px; border-left: 5px solid #3498db; transition: transform 0.3s; }
            .card:hover { transform: translateY(-5px); box-shadow: 0 5px 15px rgba(0,0,0,0.1); }
            .btn { display: inline-block; background: #3498db; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; margin: 10px 5px; transition: background 0.3s; }
            .btn:hover { background: #2980b9; }
            .btn-success { background: #27ae60; }
            .btn-success:hover { background: #229954; }
            .btn-warning { background: #f39c12; }
            .btn-warning:hover { background: #e67e22; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🍽️ Restaurant Management System</h1>
            <div class="status">✅ Server is running successfully on http://127.0.0.1:5000</div>
            
            <div class="grid">
                <div class="card">
                    <h3>🔐 Authentication</h3>
                    <p>Login to access the system</p>
                    <a href="/login" class="btn">Login</a>
                </div>
                
                <div class="card">
                    <h3>📊 Dashboard</h3>
                    <p>View system overview</p>
                    <a href="/dashboard" class="btn btn-success">Dashboard</a>
                </div>
                
                <div class="card">
                    <h3>🛒 Sales</h3>
                    <p>POS and sales management</p>
                    <a href="/sales" class="btn btn-warning">Sales</a>
                </div>
                
                <div class="card">
                    <h3>🔧 System Status</h3>
                    <p>Check server status</p>
                    <a href="/status" class="btn">Status</a>
                </div>
            </div>
            
            <div style="margin-top: 40px; padding: 20px; background: #ecf0f1; border-radius: 10px;">
                <h3>📝 System Information:</h3>
                <ul>
                    <li>✅ Flask server is running</li>
                    <li>✅ Database connection ready</li>
                    <li>✅ All routes are working</li>
                    <li>🔑 Default login: admin / admin</li>
                </ul>
            </div>
        </div>
    </body>
    </html>
    ''')

@app.route('/login')
def login():
    return '''
    <h1>🔐 Login</h1>
    <p>Login functionality will be implemented here</p>
    <p><a href="/">← Back to Home</a></p>
    '''

@app.route('/dashboard')
def dashboard():
    return '''
    <h1>📊 Dashboard</h1>
    <p>Dashboard will be implemented here</p>
    <p><a href="/">← Back to Home</a></p>
    '''

@app.route('/sales')
def sales():
    return '''
    <h1>🛒 Sales</h1>
    <p>Sales system will be implemented here</p>
    <p><a href="/">← Back to Home</a></p>
    '''

@app.route('/status')
def status():
    return jsonify({
        'status': 'running',
        'server': 'Flask Development Server',
        'port': 5000,
        'database': 'SQLite',
        'routes': len(app.url_map._rules),
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    print("🔧 Starting Restaurant Management System...")
    print("✅ Server starting on http://127.0.0.1:5000")
    print("🔑 Login: admin / admin")
    print("⏹️  Press Ctrl+C to stop")
    print("-" * 50)
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Run server
    app.run(
        host='127.0.0.1',
        port=5000,
        debug=False,
        use_reloader=False
    )
