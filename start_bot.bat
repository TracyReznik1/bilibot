@echo off
cd /d "%~dp0"
title Bilibili AI Bot - Daemon
echo ======================================================
echo Starting Bilibili AI Bot Main Daemon...
echo Listening for replies, nested comments, and @ mentions...
echo ======================================================
python -u ai.py
pause
