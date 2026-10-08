@echo off
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 goto use_python
py -3.11 "%~dp0sternberg.py" %*
goto finish
:use_python
python "%~dp0sternberg.py" %*
:finish
set "STERNBERG_EXIT=%errorlevel%"
if not "%STERNBERG_EXIT%"=="0" pause
exit /b %STERNBERG_EXIT%
