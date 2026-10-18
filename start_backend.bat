@echo off
title AEGIS FastAPI Backend (Port 8080)
set "TOOLS=C:\Users\hackathon\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\HackathonTools"
set "PATH=%TOOLS%\python\tools;%TOOLS%\bin;%TOOLS%\git\cmd;%PATH%"
cd /d "%~dp0backend"
echo =======================================================
echo [BACKEND] Starting AEGIS FastAPI on port 8080
echo =======================================================
.venv\Scripts\python.exe -m uvicorn aegis.app:create_app --factory --host 127.0.0.1 --port 8080
pause
