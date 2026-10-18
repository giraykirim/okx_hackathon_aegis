@echo off
title AEGIS LAYA ML Service (Port 8771)
set "TOOLS=C:\Users\hackathon\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\HackathonTools"
set "PATH=%TOOLS%\python\tools;%TOOLS%\bin;%TOOLS%\git\cmd;%PATH%"
cd /d "%~dp0backend"
echo =======================================================
echo [LAYA] Starting ModernBERT-Large ML Service on port 8771
echo =======================================================
.venv\Scripts\python.exe ..\ml\serve_v2_tuned.py --port 8771
pause
