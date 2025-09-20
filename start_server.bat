@echo off
echo 🍽️ Restaurant Management System
echo ================================
echo.

echo 📍 Current directory: %CD%
echo.

echo 🔍 Checking Python...
python --version
if %errorlevel% neq 0 (
    echo ❌ Python not found! Please install Python 3.x
    pause
    exit /b 1
)

echo.
echo 🔍 Checking Flask...
python -c "import flask; print('✅ Flask is available')"
if %errorlevel% neq 0 (
    echo ⚠️ Flask not found, installing...
    pip install flask
)

echo.
echo 🔍 Checking files...
if not exist "app.py" (
    echo ❌ app.py not found!
    echo 💡 Make sure you're in the correct directory
    pause
    exit /b 1
)
echo ✅ app.py found

if not exist "restaurant.db" (
    echo ⚠️ restaurant.db not found - will be created automatically
) else (
    echo ✅ restaurant.db found
)

echo.
echo 🚀 Starting server...
echo 🌐 Server will be available at: http://127.0.0.1:5000
echo 🔑 Login: admin / admin
echo ⏹️ Press Ctrl+C to stop the server
echo ================================
echo.

REM Try different server options
echo Trying main application...
python app.py
if %errorlevel% neq 0 (
    echo.
    echo ⚠️ Main app failed, trying minimal server...
    python minimal_server.py
    if %errorlevel% neq 0 (
        echo.
        echo ❌ All servers failed!
        echo 💡 Check the error messages above
        pause
        exit /b 1
    )
)

pause
