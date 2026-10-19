@echo off
rem Keeps Next Stop running: restarts 5 s after it stops. Exit code 3 = port already in use.
cd /d "%~dp0.."
:loop
python -u server.py --port 8080 >> server.log 2>&1
if %errorlevel%==3 exit /b 3
echo %date% %time% Next Stop stopped (code %errorlevel%), restarting in 5 s >> server.log
ping -n 6 127.0.0.1 >nul
goto loop
