@echo off
title AEGIS Launch All Services
echo =========================================================================
echo  Starting AEGIS: LAYA (:8771), Backend (:8080), Frontend (:3000)
echo =========================================================================
echo.
echo 1/3 Starting LAYA ML service on port 8771...
start "AEGIS LAYA (:8771)" "%~dp0start_laya.bat"
timeout /t 3 /nobreak >nul

echo 2/3 Starting AEGIS FastAPI backend on port 8080...
start "AEGIS Backend (:8080)" "%~dp0start_backend.bat"
timeout /t 3 /nobreak >nul

echo 3/3 Starting Next.js frontend on port 3000...
start "AEGIS Frontend (:3000)" "%~dp0start_frontend.bat"
timeout /t 2 /nobreak >nul

echo.
echo =========================================================================
echo  All 3 AEGIS services have been launched in separate windows!
echo  - Frontend: http://localhost:3000
echo  - Backend:  http://127.0.0.1:8080/api/snapshot
echo  - LAYA ML:  http://127.0.0.1:8771/health
echo =========================================================================
pause
