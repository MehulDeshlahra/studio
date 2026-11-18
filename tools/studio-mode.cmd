@echo off
rem Studio laptop render mode. Double-click, press 1-4.
set F=C:\Users\mehul\studio-render\mode.txt
set /p CUR=<"%F%" 2>nul
if "%CUR%"=="" set CUR=auto
echo.
echo   Studio render mode now: %CUR%
echo.
echo   1  auto   full speed when you are away 3 min, gentle while you work (recommended)
echo   2  fast   full speed always
echo   3  quiet  gentle always (serious work)
echo   4  off    no rendering on this laptop
echo.
choice /c 1234 /n /m "  Choose 1-4: "
if errorlevel 4 (echo off>"%F%") else if errorlevel 3 (echo quiet>"%F%") else if errorlevel 2 (echo fast>"%F%") else (echo auto>"%F%")
set /p NEW=<"%F%"
echo.
echo   Set to: %NEW%
timeout /t 2 >nul
