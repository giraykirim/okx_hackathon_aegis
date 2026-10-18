@echo off
title AEGIS Next.js Dashboard (Port 3000)
set "TOOLS=C:\Users\hackathon\AppData\Local\Packages\OpenAI.Codex_2p2nqsd0c76g0\LocalCache\Local\HackathonTools"
set "NODE=%TOOLS%\node\node-v24.22.0-win-x64"
set "PATH=%NODE%;%TOOLS%\bin;%PATH%"
cd /d "%~dp0frontend"
echo =======================================================
echo [FRONTEND] Starting Next.js Dashboard on port 3000
echo =======================================================
cmd.exe /c "npm run dev -- -p 3000"
pause
