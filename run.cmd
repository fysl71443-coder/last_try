@echo off
setlocal
REM Unified starter - calls python run.py
python -X utf8 run.py
endlocal
exit /b %ERRORLEVEL%

