import os
from app import app, socketio

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))  # 5000 افتراضيًا
    socketio.run(app, host="0.0.0.0", port=port, debug=True, use_reloader=True)
