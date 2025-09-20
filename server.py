from app import app

if __name__ == '__main__':
    print("🚀 Starting Restaurant Management System")
    print("📍 URL: http://127.0.0.1:5000")
    print("🔑 Login: admin / admin")
    app.run(host='127.0.0.1', port=5000, debug=False)
