@echo off
cd /d "%~dp0"
title Bilibili AI Bot - Web UI
echo ======================================================
echo Starting Bilibili AI Bot Web Panel...
echo Please open browser at: http://127.0.0.1:5000
echo Default password:       admin()
echo ======================================================
python -u local-chat.py
pause
